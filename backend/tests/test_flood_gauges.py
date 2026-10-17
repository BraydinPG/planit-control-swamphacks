"""T045D: USGS flood gauges, with NWS flood alerts as the fallback."""

from datetime import timedelta

from app.ingestion.flood_gauges import GAGE_HEIGHT, SOURCE, STREAMFLOW, FloodGaugeFeed
from app.ingestion.nws_alerts import NwsFloodAlertFeed
from app.schemas import DataState, HazardType
from tests.feed_fakes import WATER_URL, FakeFeeds, cache, gauge_series, water
from tests.nws_fakes import NOW, FakeNws, Site
from tests.nws_fakes import cache as nws_cache


def feed(fake: FakeFeeds, max_gauges: int = 3) -> FloodGaugeFeed:
    return FloodGaugeFeed(
        fake.client(), cache(SOURCE, HazardType.FLOOD_GAUGE), WATER_URL, 10, max_gauges
    )


def test_fixture_gauge_reading_produces_an_observation() -> None:
    fake = FakeFeeds(
        {
            WATER_URL: water(
                gauge_series("02290000", 3.2, "00065", "6.42"),
                gauge_series("02290000", 3.2, "00060", "351"),
            )
        }
    )
    observations = feed(fake).fetch([Site()], NOW)

    height = next(o for o in observations if o.label.startswith(GAGE_HEIGHT))
    flow = next(o for o in observations if o.label.startswith(STREAMFLOW))
    assert height.hazard_type == HazardType.FLOOD_GAUGE
    assert (height.value, height.unit) == (6.42, "ft")
    assert (flow.value, flow.unit) == (351.0, "ft3/s")
    assert height.label == "Gage height, EXAMPLE CANAL 02290000 (3.2 mi E)"
    assert height.source_ref == "USGS-02290000"
    assert height.observed_at == NOW - timedelta(minutes=15)
    assert height.data_state is DataState.OBSERVED

    params = fake.requests[0].url.params
    assert params["parameterCd"] == "00065,00060"
    assert len(params["bBox"].split(",")) == 4


def test_no_data_far_gauges_and_extra_gauges_are_skipped() -> None:
    fake = FakeFeeds(
        {
            WATER_URL: water(
                gauge_series("A", 1.0),
                gauge_series("B", 2.0, value="-999999"),
                gauge_series("C", 3.0),
                gauge_series("D", 12.0),
            )
        }
    )
    observations = feed(fake, max_gauges=1).fetch([Site()], NOW)
    assert [o.source_ref for o in observations] == ["USGS-A"]


def test_old_reading_is_stale() -> None:
    fake = FakeFeeds({WATER_URL: water(gauge_series("A", 1.0, at=NOW - timedelta(hours=3)))})
    [obs] = feed(fake).fetch([Site()], NOW)
    assert obs.data_state is DataState.STALE


def test_no_nearby_gauge_points_to_nws_flood_alerts() -> None:
    [obs] = feed(FakeFeeds({WATER_URL: water()})).fetch([Site()], NOW)
    assert obs.value is None
    assert "NWS flood alerts" in obs.label
    assert obs.data_state is DataState.OBSERVED


def test_failed_gauge_fetch_leaves_nws_flood_alerts_as_the_fallback() -> None:
    gauges = FakeFeeds({WATER_URL: water(gauge_series("A", 1.0))})
    gauges.fail = True
    floods = NwsFloodAlertFeed(FakeNws().client(), nws_cache(HazardType.FLOOD_ALERT))

    [gauge] = feed(gauges).fetch([Site()], NOW)
    [alert] = floods.fetch([Site()], NOW)
    assert gauge.data_state is DataState.UNAVAILABLE
    assert alert.data_state is DataState.OBSERVED
    assert alert.value == "Flood Watch"
