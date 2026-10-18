"""Conservative geographic batching, cache invalidation and serial persistence."""

import time
from copy import deepcopy
from datetime import timedelta
from threading import Event, Lock, get_ident

import httpx
import pytest
from sqlalchemy import select

from app.db import models as db
from app.ingestion import runtime
from app.ingestion.alert_matching import matches
from app.ingestion.base import FeedError
from app.ingestion.flood_gauges import FloodGaugeFeed
from app.ingestion.http import HttpPolicy, RequestFailure
from app.ingestion.json_client import JsonClient
from app.ingestion.nws import NwsClient
from app.schemas import DataState, HazardType
from app.services import refresh
from tests.feed_fakes import WATER_URL, cache, gauge_series, water
from tests.nws_fakes import BASE, NOW, Site, alerts, point
from tests.test_refresh import count, none_feed, reading, strike_feed
from tests.test_refresh import session as session


def client(handler, **kwargs):
    return NwsClient(
        "offline tests",
        transport=httpx.MockTransport(handler),
        policy=HttpPolicy(min_interval_seconds=0, backoff_seconds=0, retries=0),
        **kwargs,
    )


def test_point_cache_coordinate_identity_expiry_and_simultaneous_lookup():
    calls = []

    def handler(request):
        calls.append(request)
        time.sleep(0.005)
        return httpx.Response(200, json=point())

    with client(handler, point_cache_seconds=0.02) as nws:
        sites = [Site(str(i)) for i in range(8)]
        list(runtime.ordered_map(nws.point, sites, 6))
        assert len(calls) == 1  # same coordinates, different site IDs
        nws.point(sites[0])
        assert len(calls) == 1
        nws.point(Site(sites[0].id, sites[0].lat + 0.2, sites[0].lon))
        assert len(calls) == 2
        time.sleep(0.025)
        nws.point(sites[0])
        assert len(calls) == 3


@pytest.mark.parametrize(
    "status,confirmed", [(404, False), (404, True), (429, False), (500, False)]
)
def test_only_explicit_coverage_problem_gets_negative_ttl(status, confirmed):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status,
            json={
                "type": "https://api.weather.gov/problems/InvalidPoint",
                "detail": "Point not covered by this provider" if confirmed else "Provider error",
            },
            headers={"Retry-After": "0"},
        )

    with client(handler, not_covered_cache_seconds=0.02) as nws:
        for _ in range(2):
            with pytest.raises(RequestFailure) as caught:
                nws.point(Site())
            assert caught.value.not_covered is confirmed
        assert len(calls) == (1 if confirmed else 2)
        if confirmed:
            time.sleep(0.025)
            with pytest.raises(RequestFailure):
                nws.point(Site())
            assert len(calls) == 2


def test_invalid_coordinates_and_untrusted_metadata_never_make_http_request():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={})

    with client(handler) as nws:
        for site in (Site(lat=91), Site(lon=float("nan")), Site(lat=True)):
            with pytest.raises(FeedError):
                nws.point(site)
        for url in ("https://untrusted.test/data", "http://api.weather.gov/data"):
            with pytest.raises(FeedError):
                nws.get_json(url)
    assert calls == []


def test_coverage_reason_is_unavailable_and_logged_with_region_endpoint_and_status(caplog):
    def handler(request):
        return httpx.Response(
            404,
            json={
                "type": BASE + "/problems/InvalidPoint",
                "detail": "Outside provider coverage",
            },
        )

    with client(handler) as nws:
        rows = cache("NWS", HazardType.WEATHER).refresh(
            Site("eia860m-MA-123"), NOW, lambda site, at: [nws.point(site)]
        )
    assert len(rows) == 1 and rows[0].data_state == DataState.UNAVAILABLE
    assert rows[0].value is None and "Not covered by this provider" in rows[0].label
    assert '"final_state": "not_covered"' in caplog.text
    assert '"region": "MA"' in caplog.text and '"http_status": 404' in caplog.text
    assert "/points/25.7600%2C-80.4900" in caplog.text or "/points/25.7600,-80.4900" in caplog.text


def test_mismatched_cached_site_evidence_does_not_corrupt_other_site():
    feed_cache = cache("NWS", HazardType.WEATHER)
    first, second = Site("a"), Site("b")
    feed_cache.refresh(first, NOW, lambda s, at: [reading(s, HazardType.WEATHER, at, 4)])
    bad = feed_cache.refresh(
        second, NOW, lambda s, at: [reading(first, HazardType.WEATHER, at, 99)]
    )
    assert bad[0].site_id == "b" and bad[0].value is None
    assert feed_cache.snapshot(first, NOW)[0].value == 4


def polygon(west=-81, south=25, east=-80, north=26):
    return [[west, south], [east, south], [east, north], [west, north], [west, south]]


def test_zone_queries_shared_but_polygon_holes_disjoint_and_expiration_are_respected():
    collection = alerts("Flood Warning", "Hurricane Warning", "Flood Watch", "Flood Warning")
    collection["features"][0]["geometry"] = {
        "type": "Polygon",
        "coordinates": [polygon(), polygon(-80.6, 25.5, -80.4, 25.8)],
    }
    collection["features"][1]["properties"]["affectedZones"] = [BASE + "/zones/forecast/FLZ001"]
    collection["features"][2]["properties"]["ends"] = (NOW - timedelta(seconds=1)).isoformat()
    collection["features"][3]["geometry"] = {
        "type": "Polygon",
        "coordinates": [polygon(-85, 20, -84, 21)],
    }
    calls = []

    def handler(request):
        calls.append(request)
        payload = deepcopy(point())
        payload["properties"]["forecastZone"] = BASE + "/zones/forecast/FLZ001"
        return httpx.Response(200, json=payload if "/points/" in request.url.path else collection)

    with client(handler) as nws, runtime.round_scope():
        in_hole = nws.active_alerts(Site("hole"), NOW)
        inside = nws.active_alerts(Site("inside", 25.3, -80.8), NOW)
        outside = nws.active_alerts(Site("outside", 28, -82), NOW)
        # Reused by the second adapter too, not one alert request per hazard.
        nws.active_alerts(Site("inside", 25.3, -80.8), NOW)
    assert [r["properties"]["event"] for r in in_hole["features"]] == ["Hurricane Warning"]
    assert len(inside["features"]) == 2
    assert len(outside["features"]) == 1  # zone notice, never the disjoint polygon
    assert len([r for r in calls if r.url.path == "/alerts/active"]) == 1


def test_uncertain_zone_geometry_falls_back_to_point_query():
    feature = alerts("Flood Warning")["features"][0]
    feature["geometry"] = {"type": "Polygon", "coordinates": [polygon(), polygon(-90, 20, -89, 21)]}
    assert matches(feature, Site(), set()) is None  # hole outside shell is invalid
    calls = []

    def handler(request):
        calls.append(request)
        payload = point()
        payload["properties"]["forecastZone"] = BASE + "/zones/forecast/FLZ001"
        if "/points/" not in request.url.path:
            payload = {"features": [feature]} if "zone" in request.url.params else alerts()
        return httpx.Response(200, json=payload)

    with client(handler) as nws:
        assert nws.active_alerts(Site(), NOW) == {"features": []}
    assert "point" in calls[-1].url.params


def test_alert_pagination_complete_and_test_cancel_messages_excluded():
    calls = []
    collection = alerts("Flood Warning", "Flood Warning", "Flood Warning")
    collection["features"][1]["properties"]["status"] = "Test"
    collection["features"][2]["properties"]["messageType"] = "Cancel"

    def handler(request):
        calls.append(request)
        if "/points/" in request.url.path:
            return httpx.Response(200, json=point())
        if "cursor" not in request.url.params:
            return httpx.Response(
                200,
                json={
                    "features": [],
                    "pagination": {"next": BASE + "/alerts/active?cursor=next"},
                },
            )
        return httpx.Response(200, json=collection)

    with client(handler) as nws:
        assert len(nws.active_alerts(Site(), NOW)["features"]) == 1
    assert len(calls) == 3


def test_gauge_batching_keeps_site_identity_gauge_location_and_source_time():
    calls = []
    gauge = gauge_series("123", 2)

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=water(gauge))

    with JsonClient(transport=httpx.MockTransport(handler)) as http:
        feed = FloodGaugeFeed(http, cache("USGS", HazardType.FLOOD_GAUGE), WATER_URL)
        sites = [Site("a"), Site("b", 25.761, -80.491), Site("far", 40, -100)]
        rows = feed.fetch(sites, NOW)
    assert len(calls) == 2
    assert [r.site_id for r in rows] == [s.id for s in sites]
    assert rows[0].source_ref == rows[1].source_ref == "USGS-123"
    assert rows[0].id != rows[1].id
    location = gauge["sourceInfo"]["geoLocation"]["geogLocation"]
    assert rows[0].lat == rows[1].lat == location["latitude"]
    assert rows[0].observed_at == rows[1].observed_at == NOW - timedelta(minutes=15)
    assert rows[-1].value is None and "unknown" in rows[-1].label
    for req in calls:
        west, south, east, north = map(float, req.url.params["bBox"].split(","))
        assert (east - west) * (north - south) <= 25


@pytest.mark.parametrize("value", ["nan", "inf", "-999999"])
def test_gauge_nonfinite_and_string_nodata_never_become_zero(value):
    gauge = gauge_series("123", 1, value=value)
    gauge["variable"]["noDataValue"] = "-999999"
    with JsonClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=water(gauge)))
    ) as http:
        feed = FloodGaugeFeed(http, cache("USGS", HazardType.FLOOD_GAUGE), WATER_URL)
        rows = feed.fetch([Site()], NOW)
    assert len(rows) == 1 and rows[0].value is None


def test_one_failed_gauge_batch_only_stales_its_sites_and_never_renews_timestamps():
    failed = False

    def handler(request):
        if failed and float(request.url.params["bBox"].split(",")[0]) < -90:
            return httpx.Response(503)
        return httpx.Response(200, json=water())

    with JsonClient(
        transport=httpx.MockTransport(handler), policy=HttpPolicy(min_interval_seconds=0, retries=0)
    ) as http:
        feed = FloodGaugeFeed(http, cache("USGS", HazardType.FLOOD_GAUGE), WATER_URL)
        sites = [Site("good"), Site("fails", 40, -100)]
        initial = feed.fetch(sites, NOW)
        failed = True
        rows = feed.fetch(sites, NOW + timedelta(minutes=5))
    assert rows[0].data_state == DataState.OBSERVED
    assert rows[1].data_state == DataState.STALE
    assert rows[1].fetched_at == initial[1].fetched_at == NOW
    assert rows[1].observed_at == NOW and rows[1].value is None


def test_feed_workers_bounded_ordered_and_never_given_orm_objects():
    lock = Lock()
    active = peak = 0
    sites = [runtime.SiteSnapshot(str(i), 25, -80) for i in range(12)]

    def fetch(site, now):
        nonlocal active, peak
        assert isinstance(site, runtime.SiteSnapshot)
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.005)
        with lock:
            active -= 1
        return [reading(site, HazardType.WEATHER, now, 3)]

    rows = cache("TEST", HazardType.WEATHER).refresh_many(sites, NOW, fetch, workers=3)
    assert [r.site_id for r in rows] == [s.id for s in sites]
    assert 1 < peak <= 3


def test_database_writes_serial_missing_subfeeds_explicit_and_demo_excluded(session, monkeypatch):
    thread = get_ident()
    original = refresh.store_observations
    session.add(
        db.Site(id="demo", name="demo", lat=25, lon=-80, source="demo", location_type="demo_site")
    )
    session.commit()

    def store(db_session, rows):
        assert get_ident() == thread and db_session is session
        original(db_session, rows)

    def fetch(sites, now):
        assert all(isinstance(s, runtime.SiteSnapshot) and s.id != "demo" for s in sites)
        return [reading(s, HazardType.WEATHER, now, 90, source="NWS") for s in sites]

    monkeypatch.setattr(refresh, "store_observations", store)
    feed = refresh.Feed(
        "NWS",
        HazardType.WEATHER,
        fetch,
        (("NWS", HazardType.WEATHER), ("NWS", HazardType.FORECAST)),
    )
    result = refresh.refresh_all(session, NOW, [feed])
    assert result.metrics["complete_feed_sites"] == 0
    assert result.metrics["partial_feed_sites"] == 2
    assert result.metrics["coverage"]["NWS/forecast"] == {"unavailable": 2}
    assert result.metrics["coverage"]["NWS/weather"] == {"current": 2}
    assert count(session, db.Observation, db.Observation.site_id == "demo") == 0
    assert all(
        r.value is None
        for r in session.scalars(
            select(db.Observation).where(db.Observation.hazard_type == "forecast")
        )
    )


def test_failed_association_never_persists_foreign_site_and_outage_never_clears_lightning(session):
    refresh.refresh_all(session, NOW, [strike_feed(5, NOW)])

    def forged(sites, now):
        return [reading(Site("foreign"), HazardType.WEATHER, now, 4)]

    result = refresh.refresh_all(
        session,
        NOW + timedelta(hours=1),
        [
            refresh.Feed("NWS", HazardType.WEATHER, forged),
            none_feed(HazardType.EARTHQUAKE),
        ],
    )
    assert result.failed_feeds == ["NWS weather"]
    assert count(session, db.Observation, db.Observation.site_id == "foreign") == 0
    assert set(result.lightning.values()) == {"held"}
    assert count(session, db.Observation, db.Observation.hazard_type == "earthquake") == 2


def test_cancelled_round_does_not_persist_or_score(session):
    stop = Event()
    stop.set()
    result = refresh.refresh_all(session, NOW, [none_feed(HazardType.WEATHER)], cancel=stop)
    assert result.metrics["cancelled"] is True
    assert count(session, db.Observation) == 0
    assert count(session, db.HazardScore) == 0
