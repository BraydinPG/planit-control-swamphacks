"""T046 10-mile stop-work trigger and T047 resettable 30-minute all-clear."""

from datetime import timedelta

import pytest

from app.ingestion import lightning
from app.ingestion.lightning import LightningFeed, StrikeStore
from app.rules.lightning import (
    ALL_CLEAR,
    STOP_WORK_MILES,
    Transition,
    evaluate_lightning,
)
from app.schemas import AlertRule, AlertState, DataState, HazardType, Observation
from tests.feed_fakes import cache
from tests.nws_fakes import NOW, Site

SITE = "site-demo"


def strike(miles: float | None, minutes_ago: float, **overrides) -> Observation:
    fields = dict(
        id=f"ltg:{minutes_ago}:{miles}",
        site_id=SITE,
        source="lightning-replay",
        hazard_type=HazardType.LIGHTNING_STRIKE,
        value=miles,
        unit="mi",
        lat=25.8,
        lon=-80.5,
        observed_at=NOW - timedelta(minutes=minutes_ago),
        data_state=DataState.SIMULATED,
        simulated=True,
        label=f"Strike {miles} mi (replay)",
    )
    return Observation(**(fields | overrides))


def none_reading(**overrides) -> Observation:
    return strike(None, 0, id="ltg:none", label="No lightning", **overrides)


def triggered(*strikes: Observation):
    return evaluate_lightning(SITE, list(strikes), None, NOW).alert


# ---- T046: 10-mile trigger ----


def test_strike_inside_10_miles_creates_stop_work_alert() -> None:
    result = evaluate_lightning(SITE, [strike(4.2, 1)], None, NOW)
    assert result.transition is Transition.TRIGGERED
    alert = result.alert
    assert alert.rule is AlertRule.LIGHTNING_STOP_WORK
    assert alert.state is AlertState.ACTIVE
    assert alert.distance_miles == 4.2
    assert alert.is_prototype_rule is False


def test_strike_outside_10_miles_does_not_trigger() -> None:
    result = evaluate_lightning(SITE, [strike(14.5, 1)], None, NOW)
    assert result.transition is Transition.NONE
    assert result.alert is None


@pytest.mark.parametrize(("miles", "qualifies"), [(10.0, True), (10.1, False), (9.9, True)])
def test_boundary_distance(miles: float, qualifies: bool) -> None:
    assert STOP_WORK_MILES == 10.0
    assert (triggered(strike(miles, 1)) is not None) is qualifies


def test_none_reading_never_triggers() -> None:
    assert triggered(none_reading()) is None


def test_other_sites_and_unavailable_readings_are_ignored() -> None:
    assert triggered(strike(3.0, 1, site_id="other-site")) is None
    assert triggered(strike(3.0, 1, data_state=DataState.UNAVAILABLE)) is None


def test_alert_records_rule_inputs_and_evidence() -> None:
    alert = triggered(strike(6.8, 10), strike(14.5, 5), strike(4.2, 2))
    assert alert.trigger_observation_ids == ["ltg:10:6.8", "ltg:2:4.2"]
    assert [e.id for e in alert.evidence] == alert.trigger_observation_ids
    assert alert.triggered_at == NOW - timedelta(minutes=10)
    assert alert.latest_event_at == NOW - timedelta(minutes=2)


def test_simulated_only_when_every_strike_is_simulated() -> None:
    live = dict(source="GOES GLM", simulated=False, data_state=DataState.OBSERVED)
    assert triggered(strike(5, 3)).simulated is True
    assert triggered(strike(5, 3, **live)).simulated is False
    assert triggered(strike(5, 3), strike(6, 2, id="live", **live)).simulated is False


def test_old_strike_whose_window_already_passed_does_not_trigger() -> None:
    assert triggered(strike(4.0, 31)) is None


def test_new_alert_starts_after_last_30_minute_gap() -> None:
    alert = triggered(strike(5, 55), strike(5, 10))
    assert alert.triggered_at == NOW - timedelta(minutes=10)
    assert alert.trigger_observation_ids == ["ltg:10:5"]


# ---- T047: resettable 30-minute all-clear ----


def test_clear_after_is_latest_strike_plus_30_minutes() -> None:
    alert = triggered(strike(6.8, 10))
    assert alert.clear_after == NOW - timedelta(minutes=10) + ALL_CLEAR


def test_second_strike_resets_the_timer() -> None:
    first = evaluate_lightning(SITE, [strike(6.8, 20)], None, NOW - timedelta(minutes=19)).alert
    later = NOW
    result = evaluate_lightning(SITE, [strike(6.8, 20), strike(4.2, 1)], first, later)
    assert result.transition is Transition.RESET
    assert result.alert.id == first.id
    assert result.alert.triggered_at == first.triggered_at
    assert result.alert.latest_event_at == NOW - timedelta(minutes=1)
    assert result.alert.clear_after == NOW - timedelta(minutes=1) + ALL_CLEAR
    assert result.alert.clear_after > first.clear_after
    assert result.alert.trigger_observation_ids == ["ltg:20:6.8", "ltg:1:4.2"]


def test_strike_outside_10_miles_does_not_reset() -> None:
    first = triggered(strike(6.8, 5))
    result = evaluate_lightning(SITE, [strike(6.8, 5), strike(14.5, 1)], first, NOW)
    assert result.transition is Transition.UNCHANGED
    assert result.alert.clear_after == first.clear_after


def test_already_counted_strike_does_not_reset() -> None:
    first = triggered(strike(6.8, 5))
    result = evaluate_lightning(SITE, [strike(6.8, 5)], first, NOW + timedelta(minutes=10))
    assert result.transition is Transition.UNCHANGED


def test_30_strike_free_minutes_clear_the_alert() -> None:
    alert = triggered(strike(6.8, 0))
    just_before = evaluate_lightning(
        SITE, [none_reading()], alert, NOW + ALL_CLEAR - timedelta(seconds=1)
    )
    assert just_before.transition is Transition.UNCHANGED
    assert just_before.alert.state is AlertState.ACTIVE
    cleared = evaluate_lightning(SITE, [none_reading()], alert, NOW + ALL_CLEAR)
    assert cleared.transition is Transition.CLEARED
    assert cleared.alert.state is AlertState.CLEARED
    assert cleared.alert.clear_after == alert.clear_after


def test_reset_then_clear_uses_the_latest_strike() -> None:
    alert = triggered(strike(6.8, 20))
    alert = evaluate_lightning(SITE, [strike(4.2, 5)], alert, NOW).alert
    at_old_deadline = NOW + timedelta(minutes=10)  # first strike + 30 min
    assert evaluate_lightning(SITE, [none_reading()], alert, at_old_deadline).alert.state is (
        AlertState.ACTIVE
    )
    at_new_deadline = NOW + timedelta(minutes=25)  # second strike + 30 min
    result = evaluate_lightning(SITE, [none_reading()], alert, at_new_deadline)
    assert result.transition is Transition.CLEARED


@pytest.mark.parametrize("state", [DataState.STALE, DataState.UNAVAILABLE])
def test_feed_outage_never_clears_the_alert(state: DataState) -> None:
    alert = triggered(strike(6.8, 0))
    later = NOW + ALL_CLEAR + timedelta(minutes=5)
    result = evaluate_lightning(SITE, [none_reading(data_state=state)], alert, later)
    assert result.transition is Transition.HELD
    assert result.alert.state is AlertState.ACTIVE


def test_no_readings_at_all_never_clears_the_alert() -> None:
    alert = triggered(strike(6.8, 0))
    result = evaluate_lightning(SITE, [], alert, NOW + timedelta(hours=2))
    assert result.transition is Transition.HELD


def test_strike_after_clear_starts_a_new_alert() -> None:
    first = evaluate_lightning(SITE, [strike(6.8, 40)], None, NOW - timedelta(minutes=40)).alert
    first = evaluate_lightning(SITE, [none_reading()], first, NOW - timedelta(minutes=5)).alert
    assert first.state is AlertState.CLEARED
    result = evaluate_lightning(SITE, [strike(6.8, 40), strike(5.0, 1)], first, NOW)
    assert result.transition is Transition.TRIGGERED
    assert result.alert.id != first.id
    assert result.alert.trigger_observation_ids == ["ltg:1:5.0"]


def test_future_dated_strike_is_ignored() -> None:
    assert triggered(strike(4.0, -5)) is None


# ---- end to end with Braydin's replay fixture ----


def test_replay_fixture_triggers_resets_and_clears() -> None:
    store = StrikeStore()
    feed = LightningFeed(
        store,
        cache(lightning.REPLAY_SOURCE, HazardType.LIGHTNING_STRIKE),
        search_radius_miles=30,
        lookback=timedelta(minutes=60),
    )
    site = Site()
    steps = lightning.replay_steps()

    def submit(step: int, at):
        item = steps[step]
        lat, lon = lightning.destination(
            site.lat, site.lon, item["bearing_deg"], item["distance_mi"]
        )
        store.submit(lat, lon, at, simulated=True)

    t0 = NOW
    submit(0, t0)  # 6.8 mi: triggers
    first = evaluate_lightning(site.id, feed.fetch([site], t0), None, t0)
    assert first.transition is Transition.TRIGGERED and first.alert.simulated

    t1 = t0 + timedelta(minutes=12)
    submit(1, t1)  # 4.2 mi: resets
    reset = evaluate_lightning(site.id, feed.fetch([site], t1), first.alert, t1)
    assert reset.transition is Transition.RESET
    assert reset.alert.clear_after == t1 + ALL_CLEAR

    t2 = t1 + timedelta(minutes=5)
    submit(2, t2)  # 14.5 mi: reported, but does not reset
    outside = evaluate_lightning(site.id, feed.fetch([site], t2), reset.alert, t2)
    assert outside.transition is Transition.UNCHANGED

    t3 = t1 + ALL_CLEAR
    cleared = evaluate_lightning(site.id, feed.fetch([site], t3), outside.alert, t3)
    assert cleared.transition is Transition.CLEARED
