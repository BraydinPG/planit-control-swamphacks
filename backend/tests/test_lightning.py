"""T045 lightning input and replay fixture. Live GOES GLM (T045A) is in test_glm.py."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.ingestion import lightning
from app.ingestion.geo import distance_miles
from app.ingestion.lightning import LightningFeed, StrikeStore
from app.schemas import DataState, HazardType
from tests.feed_fakes import cache, near
from tests.nws_fakes import NOW, Site


def feed(store: StrikeStore) -> LightningFeed:
    return LightningFeed(
        store,
        cache(lightning.REPLAY_SOURCE, HazardType.LIGHTNING_STRIKE),
        search_radius_miles=30,
        lookback=timedelta(minutes=60),
    )


@pytest.fixture(autouse=True)
def replay_only_module_feed(monkeypatch):
    """Module-level fetch without the live GLM poller, so tests never touch the network."""
    monkeypatch.setattr(lightning, "_default_feed", feed(lightning._store))
    lightning.clear_strikes()
    yield
    lightning.clear_strikes()


def test_tests_can_submit_a_strike_without_a_live_feed() -> None:
    eastern = timezone(timedelta(hours=-4))
    strike = lightning.submit_strike(
        25.712345678, -80.512345678, datetime(2026, 10, 17, 13, 55, tzinfo=eastern), True
    )

    assert strike.hazard_type == HazardType.LIGHTNING_STRIKE
    assert (strike.lat, strike.lon) == (25.7123, -80.5123)
    assert strike.observed_at == datetime(2026, 10, 17, 17, 55, tzinfo=UTC)
    assert strike.observed_at.tzinfo == UTC
    assert strike.simulated is True
    assert strike.data_state is DataState.SIMULATED
    assert strike.source == "lightning-replay"
    assert "replay" in strike.label

    [reading] = lightning.fetch([Site()], NOW)
    assert reading.source_ref == strike.id
    assert reading.site_id == "site-demo"
    assert reading.unit == "mi"
    assert reading.value == pytest.approx(
        distance_miles(Site().lat, Site().lon, strike.lat, strike.lon), abs=0.05
    )


@pytest.mark.parametrize(
    ("lat", "lon", "time"),
    [
        (91, -80.0, NOW),
        (25.0, -181, NOW),
        (25.0, -80.0, datetime(2026, 10, 17, 12, 0)),
    ],
)
def test_invalid_strikes_are_rejected(lat, lon, time) -> None:
    with pytest.raises(ValueError):
        StrikeStore().submit(lat, lon, time, simulated=True)


def test_site_receives_nearby_recent_strikes_only() -> None:
    store = StrikeStore()
    inside = store.submit(*near(315, 6.8), NOW - timedelta(minutes=5), simulated=True)
    store.submit(*near(0, 45), NOW - timedelta(minutes=5), simulated=True)  # beyond radius
    store.submit(*near(90, 3), NOW - timedelta(minutes=90), simulated=True)  # too old
    store.submit(*near(90, 3), NOW + timedelta(minutes=1), simulated=True)  # not yet

    [reading] = feed(store).fetch([Site()], NOW)
    assert reading.source_ref == inside.id
    assert reading.value == 6.8
    assert reading.label == "Strike 6.8 mi NW (replay)"
    assert reading.data_state is DataState.SIMULATED
    assert reading.fetched_at == NOW


def test_replay_fixture_reproduces_the_demo_sequence() -> None:
    site = Site()
    first = lightning.replay_strike(site, 0, NOW - timedelta(minutes=10))
    second = lightning.replay_strike(site, 1, NOW - timedelta(minutes=2))
    outside = lightning.replay_strike(site, 2, NOW - timedelta(minutes=1))
    assert all(
        s.simulated and s.data_state is DataState.SIMULATED for s in (first, second, outside)
    )

    readings = {r.source_ref: r for r in lightning.fetch([site], NOW)}
    assert readings[first.id].label == "Strike 6.8 mi NW (replay)"
    assert readings[second.id].label == "Strike 4.2 mi W (replay)"
    assert readings[outside.id].value == 14.5
    assert len(lightning.replay_steps()) == 3


def test_no_strikes_is_explicit_and_labeled_simulated() -> None:
    [reading] = feed(StrikeStore()).fetch([Site()], NOW)
    assert reading.value is None
    assert reading.simulated is True
    assert reading.data_state is DataState.SIMULATED
    assert reading.label.startswith("No replayed strikes within 30 mi")


def test_no_strikes_without_live_feed_says_live_is_not_enabled() -> None:
    [reading] = feed(StrikeStore()).fetch([Site()], NOW)
    assert reading.label.endswith("(live lightning not enabled)")
    assert reading.source == "lightning-replay"


def test_a_live_strike_would_be_observed_not_simulated() -> None:
    store = StrikeStore()
    store.submit(*near(180, 2), NOW - timedelta(minutes=1), simulated=False)
    [reading] = feed(store).fetch([Site()], NOW)
    assert reading.simulated is False
    assert reading.data_state is DataState.OBSERVED
    assert reading.source == "GOES GLM"
    assert reading.label == "Strike 2.0 mi S (GOES GLM)"
