"""T073: alert timing and feed failures through the refresh loop.

Every feed (weather, forecast, flood, lightning, hurricane, earthquake) runs through a
real `FeedCache`, so outages fall back to stale and then unavailable exactly as the
adapters do. Fake fetches only; no network.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import models as db
from app.ingestion import FeedCache, FeedError
from app.ingestion.lightning import REPLAY_SOURCE, LightningFeed, StrikeStore
from app.ingestion.nws_alerts import NO_ACTIVE_ALERTS
from app.ingestion.nws_weather import HEAT_INDEX, RELATIVE_HUMIDITY, TEMPERATURE
from app.schemas import DataState, HazardType, Observation
from app.services.refresh import Feed, refresh_all

NOW = datetime(2026, 10, 17, 18, 0, tzinfo=UTC)
STALE_AFTER = timedelta(minutes=60)
UNAVAILABLE_AFTER = timedelta(minutes=360)
SITE_ID, SITE_LAT, SITE_LON = "site-a", 25.76, -80.49


class Site:
    id, lat, lon = SITE_ID, SITE_LAT, SITE_LON


SITE = Site()

# Feed name -> score factor that reports its state.
FACTOR = {
    "flood": "flood",
    "lightning": "lightning",
    "hurricane": "hurricane",
    "earthquake": "earthquake",
}


class FakeFeed:
    """One feed behind a real FeedCache. Set `down` to make every fetch fail."""

    def __init__(self, name: str, source: str, hazard_type: HazardType, make) -> None:
        self.name = name
        self.hazard_type = hazard_type
        self.make = make
        self.down = False
        self.cache = FeedCache(source, hazard_type, STALE_AFTER, UNAVAILABLE_AFTER)
        self.last: list[Observation] = []

    def fetch(self, sites, now: datetime) -> list[Observation]:
        self.last = [o for s in sites for o in self.cache.refresh(s, now, self._fetch_site)]
        return self.last

    def _fetch_site(self, site, now: datetime) -> list[Observation]:
        if self.down:
            raise FeedError(f"{self.name} down")
        return self.make(site, now)

    def feed(self) -> Feed:
        return Feed(self.name, self.hazard_type, self.fetch)


def obs(site, hazard_type, source, now, key, value=None, **extra) -> Observation:
    return Observation(
        id=f"{source}:{hazard_type}:{site.id}:{key}",
        site_id=site.id,
        source=source,
        hazard_type=hazard_type,
        value=value,
        lat=extra.pop("lat", site.lat),
        lon=extra.pop("lon", site.lon),
        observed_at=extra.pop("observed_at", now),
        data_state=extra.pop("data_state", DataState.OBSERVED),
        **extra,
    )


class Lightning:
    """Strikes as (miles, time). Readings within the last hour, or a "none" reading."""

    def __init__(self) -> None:
        self.strikes: list[tuple[float, datetime]] = []

    def __call__(self, site, now):
        recent = [(m, at) for m, at in self.strikes if now - timedelta(hours=1) < at <= now]
        if not recent:
            return [
                obs(
                    site,
                    HazardType.LIGHTNING_STRIKE,
                    REPLAY_SOURCE,
                    now,
                    f"none:{now}",
                    label="No replayed strikes",
                    data_state=DataState.SIMULATED,
                    simulated=True,
                )
            ]
        return [
            obs(
                site,
                HazardType.LIGHTNING_STRIKE,
                REPLAY_SOURCE,
                now,
                f"strike:{at}",
                value=miles,
                unit="mi",
                observed_at=at,
                label=f"Strike {miles} mi",
                data_state=DataState.SIMULATED,
                simulated=True,
            )
            for miles, at in recent
        ]


def build_feeds(lightning: Lightning, hurricane_event: str | None = None) -> dict[str, FakeFeed]:
    def weather(site, now):
        return [
            obs(site, HazardType.WEATHER, "NWS", now, f"{label}:{now}", value, label=label)
            for label, value in ((TEMPERATURE, 85.0), (RELATIVE_HUMIDITY, 60.0), (HEAT_INDEX, 92.0))
        ]

    def forecast(site, now):
        at = now + timedelta(hours=2)
        return [
            obs(
                site,
                HazardType.FORECAST,
                "NWS",
                now,
                f"{label}:{at}",
                value,
                label=label,
                valid_at=at,
                data_state=DataState.FORECAST,
            )
            for label, value in ((TEMPERATURE, 88.0), (RELATIVE_HUMIDITY, 55.0))
        ]

    def flood(site, now):
        return [
            obs(site, HazardType.FLOOD_ALERT, "NWS", now, f"none:{now}", label=NO_ACTIVE_ALERTS)
        ]

    def hurricane(site, now):
        if hurricane_event:
            return [
                obs(
                    site,
                    HazardType.HURRICANE,
                    "NWS",
                    now,
                    "warning",
                    hurricane_event,
                    label=hurricane_event,
                    source_ref="urn:warning",
                    observed_at=NOW,
                )
            ]
        return [obs(site, HazardType.HURRICANE, "NHC", now, f"none:{now}", label="No storms")]

    def earthquake(site, now):
        return [obs(site, HazardType.EARTHQUAKE, "USGS", now, f"none:{now}", label="No quakes")]

    return {
        "weather": FakeFeed("weather", "NWS", HazardType.WEATHER, weather),
        "forecast": FakeFeed("forecast", "NWS", HazardType.FORECAST, forecast),
        "flood": FakeFeed("flood", "NWS", HazardType.FLOOD_ALERT, flood),
        "lightning": FakeFeed("lightning", REPLAY_SOURCE, HazardType.LIGHTNING_STRIKE, lightning),
        "hurricane": FakeFeed("hurricane", "NWS", HazardType.HURRICANE, hurricane),
        "earthquake": FakeFeed("earthquake", "USGS", HazardType.EARTHQUAKE, earthquake),
    }


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    db.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as s:
        s.add(db.Organization(id="org-1", name="Sunbelt"))
        s.add(
            db.Site(
                id=SITE_ID,
                name=SITE_ID,
                lat=SITE_LAT,
                lon=SITE_LON,
                location_type="power_plant",
                source="EIA-860M (representative)",
            )
        )
        s.flush()
        s.add(db.Team(id="team-a", organization_id="org-1", name="Crew A", site_id=SITE_ID))
        s.commit()
        yield s
    engine.dispose()


def run(session, feeds: dict[str, FakeFeed], now: datetime):
    return refresh_all(session, now, [f.feed() for f in feeds.values()])


def factors(session, now: datetime) -> dict[str, dict]:
    score = session.scalars(select(db.HazardScore).where(db.HazardScore.created_at == now)).one()
    return {f["factor"]: f for f in score.factor_contributions}


def lightning_alert(session) -> db.Alert | None:
    return session.scalars(select(db.Alert).where(db.Alert.site_id == SITE_ID)).first()


# 1. Every feed's outage reads stale, then unavailable, never "none".

ALL_FEEDS = ["weather", "forecast", "flood", "lightning", "hurricane", "earthquake"]


@pytest.mark.parametrize("name", ALL_FEEDS)
@pytest.mark.parametrize(
    ("after", "expected"),
    [(timedelta(minutes=10), DataState.STALE), (timedelta(hours=7), DataState.UNAVAILABLE)],
)
def test_feed_outage_is_stale_then_unavailable(session, name, after, expected) -> None:
    feeds = build_feeds(Lightning())
    run(session, feeds, NOW)
    feeds[name].down = True
    later = NOW + after
    result = run(session, feeds, later)
    assert result.failed_sites == []

    assert {o.data_state for o in feeds[name].last} == {expected}
    stored = session.scalars(
        select(db.Observation.data_state).where(
            db.Observation.hazard_type == feeds[name].hazard_type,
            db.Observation.id.in_([o.id for o in feeds[name].last if o.id])
            | db.Observation.id.like("unavailable:%"),
        )
    ).all()
    assert expected.value in stored

    got = factors(session, later)
    if name in FACTOR:
        factor = got[FACTOR[name]]
        assert factor["data_state"] == expected.value
        assert factor["contribution"] == 0.0
    # The other feeds stay current.
    for other, factor_name in FACTOR.items():
        if other != name:
            assert got[factor_name]["data_state"] not in ("stale", "unavailable"), other


def test_weather_and_forecast_outage_makes_heat_unknown(session) -> None:
    feeds = build_feeds(Lightning())
    feeds["weather"].down = feeds["forecast"].down = True
    run(session, feeds, NOW)
    heat = factors(session, NOW)["heat_index"]
    assert heat["data_state"] == "unavailable" and heat["contribution"] == 0.0
    assert "unknown" in heat["label"]


def test_feed_that_never_answered_is_stored_unavailable(session) -> None:
    feeds = build_feeds(Lightning())
    for f in feeds.values():
        f.down = True
    run(session, feeds, NOW)
    states = set(session.scalars(select(db.Observation.data_state)))
    assert states == {"unavailable"}


# 2. A feed outage never clears an alert.


def trigger(session) -> tuple[dict[str, FakeFeed], Lightning]:
    lightning = Lightning()
    lightning.strikes.append((5.0, NOW - timedelta(minutes=1)))
    feeds = build_feeds(lightning)
    result = run(session, feeds, NOW)
    assert result.lightning[SITE_ID] == "triggered"
    return feeds, lightning


@pytest.mark.parametrize("after", [timedelta(minutes=45), timedelta(hours=7)])
def test_lightning_outage_holds_alert_past_all_clear(session, after) -> None:
    feeds, _ = trigger(session)
    feeds["lightning"].down = True
    later = NOW + after
    result = run(session, feeds, later)
    assert result.lightning[SITE_ID] == "held"
    assert lightning_alert(session).state == "active"
    assert factors(session, later)["lightning"]["contribution"] == 3.0


@pytest.mark.parametrize("name", ["weather", "forecast", "flood", "hurricane", "earthquake"])
def test_other_feed_outage_never_clears_early(session, name) -> None:
    feeds, _ = trigger(session)
    feeds[name].down = True
    result = run(session, feeds, NOW + timedelta(minutes=10))  # inside the 30-minute window
    assert result.lightning[SITE_ID] == "unchanged"
    assert lightning_alert(session).state == "active"


@pytest.mark.parametrize("name", ["weather", "forecast", "flood", "hurricane", "earthquake"])
def test_other_feed_outage_does_not_block_a_healthy_clear(session, name) -> None:
    feeds, _ = trigger(session)
    feeds[name].down = True
    result = run(session, feeds, NOW + timedelta(minutes=45))
    assert result.lightning[SITE_ID] == "cleared"


def test_stale_hurricane_reading_sends_no_new_notice_and_keeps_the_old_one(session) -> None:
    feeds = build_feeds(Lightning(), hurricane_event="Hurricane Warning")
    assert run(session, feeds, NOW).notices == 1
    feeds["hurricane"].down = True
    assert run(session, feeds, NOW + timedelta(minutes=10)).notices == 0
    notice = session.scalars(select(db.HazardNotice)).one()
    assert notice.status == "potential" and notice.instruction is None
    hurricane = factors(session, NOW + timedelta(minutes=10))["hurricane"]
    assert hurricane["data_state"] == "stale" and hurricane["contribution"] == 2.0


# 3. The real lightning adapter reports unavailable, not "no strikes", when it fails.


def test_lightning_adapter_failure_is_unavailable_then_stale() -> None:
    cache = FeedCache(REPLAY_SOURCE, HazardType.LIGHTNING_STRIKE, STALE_AFTER, UNAVAILABLE_AFTER)
    feed = LightningFeed(StrikeStore(), cache, live=None)

    def boom(site, now):
        raise FeedError("store unreachable")

    healthy = feed.fetch_site
    feed.fetch_site = boom
    [first] = feed.fetch([SITE], NOW)
    assert first.data_state is DataState.UNAVAILABLE and first.value is None

    feed.fetch_site = healthy
    feed.fetch([SITE], NOW)
    feed.fetch_site = boom
    later = feed.fetch([SITE], NOW + timedelta(minutes=10))
    assert {o.data_state for o in later} == {DataState.STALE}


# 4. Timing edges through the refresh loop.


@pytest.mark.parametrize(("miles", "transition"), [(10.0, "triggered"), (10.1, "none")])
def test_ten_mile_boundary(session, miles, transition) -> None:
    lightning = Lightning()
    lightning.strikes.append((miles, NOW - timedelta(minutes=1)))
    result = run(session, build_feeds(lightning), NOW)
    assert result.lightning[SITE_ID] == transition


def test_second_strike_resets_and_clears_exactly_30_minutes_later(session) -> None:
    feeds, lightning = trigger(session)  # strike at NOW - 1 min
    second = NOW + timedelta(minutes=20)
    lightning.strikes.append((8.0, second))
    assert run(session, feeds, second).lightning[SITE_ID] == "reset"
    assert lightning_alert(session).clear_after.replace(tzinfo=UTC) == second + timedelta(
        minutes=30
    )

    just_before = second + timedelta(minutes=30) - timedelta(seconds=1)
    assert run(session, feeds, just_before).lightning[SITE_ID] == "unchanged"
    at_clear = second + timedelta(minutes=30)
    assert run(session, feeds, at_clear).lightning[SITE_ID] == "cleared"
    assert lightning_alert(session).state == "cleared"


def test_every_refresh_writes_one_score(session) -> None:
    feeds = build_feeds(Lightning())
    for minutes in (0, 5, 10):
        run(session, feeds, NOW + timedelta(minutes=minutes))
    total = session.scalar(select(func.count()).select_from(db.HazardScore))
    assert total == 3
