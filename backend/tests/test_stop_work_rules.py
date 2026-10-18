"""T049C: prototype tiered stop-work rules (`app.rules.stop_work`)."""

from datetime import timedelta

import pytest

from app.rules.settings import RuleSettings
from app.rules.stop_work import (
    EVENT_RULES,
    WARNING_RULES,
    StopWorkSettings,
    Transition,
    evaluate_stop_work,
)
from app.schemas import (
    ADVISORY_TIER,
    DANGER_TIERS,
    Alert,
    AlertRule,
    AlertState,
    DataState,
    HazardType,
    Observation,
)
from tests.nws_fakes import NOW, Site

SITE = Site()  # 25.76, -80.49
RULES = RuleSettings.model_construct()
WINDOWS = StopWorkSettings(warning_all_clear_minutes=30, earthquake_all_clear_minutes=60)
WARNING_WINDOW = timedelta(minutes=30)
QUAKE_WINDOW = timedelta(minutes=60)

# Rule -> (hazard type, NWS event value) for every NWS warning rule.
WARNINGS = {
    AlertRule.TORNADO: (HazardType.SEVERE_STORM, "Tornado Warning"),
    AlertRule.HURRICANE: (HazardType.HURRICANE, "Hurricane Warning"),
    AlertRule.FLASH_FLOOD: (HazardType.FLOOD_ALERT, "Flash Flood Warning"),
    AlertRule.SEVERE_THUNDERSTORM: (HazardType.SEVERE_STORM, "Severe Thunderstorm Warning"),
    AlertRule.TROPICAL_STORM: (HazardType.HURRICANE, "Tropical Storm Warning"),
    AlertRule.FLOOD: (HazardType.FLOOD_ALERT, "Flood Warning"),
}


def reading(hazard_type, value, minutes_ago=0.0, **extra) -> Observation:
    fields = dict(
        id=f"{hazard_type}:{value}:{minutes_ago}",
        site_id=SITE.id,
        source="NWS",
        hazard_type=hazard_type,
        value=value,
        label=str(value) if value is not None else "No active alerts",
        source_ref=f"urn:{value}",
        lat=SITE.lat,
        lon=SITE.lon,
        observed_at=NOW - timedelta(minutes=minutes_ago),
        data_state=DataState.OBSERVED,
    )
    return Observation(**(fields | extra))


def quake(magnitude, miles_north, minutes_ago, **extra) -> Observation:
    # About 69 miles per degree of latitude.
    fields = dict(
        id=f"usgs:{magnitude}:{minutes_ago}",
        source="USGS",
        unit="mw",
        lat=SITE.lat + miles_north / 69.0,
    )
    return reading(HazardType.EARTHQUAKE, magnitude, minutes_ago, **(fields | extra))


def run(rule, observations, current=None, at=NOW):
    return evaluate_stop_work(rule, SITE, observations, current, at, RULES, WINDOWS)


def test_tier_map_covers_every_rule() -> None:
    assert set(DANGER_TIERS) == set(AlertRule)
    assert set(WARNING_RULES) | set(EVENT_RULES) | {
        AlertRule.LIGHTNING_STOP_WORK,
        AlertRule.HEAT,
    } == set(AlertRule)
    assert DANGER_TIERS[AlertRule.HEAT] == ADVISORY_TIER
    assert DANGER_TIERS[AlertRule.TORNADO] == 1
    assert DANGER_TIERS[AlertRule.LIGHTNING_STOP_WORK] == 2
    assert DANGER_TIERS[AlertRule.FLOOD] == 3


# ---- warning rules: trigger, hold, window, reset, clear ----


@pytest.mark.parametrize("rule", list(WARNINGS))
def test_listed_warning_triggers_with_no_all_clear_time(rule) -> None:
    hazard_type, event = WARNINGS[rule]
    result = run(rule, [reading(hazard_type, event, 20)])
    assert result.transition is Transition.TRIGGERED
    alert = result.alert
    assert alert.rule is rule and alert.state is AlertState.ACTIVE
    assert alert.clear_after is None
    assert alert.is_prototype_rule is True
    assert alert.danger_tier == DANGER_TIERS[rule]
    assert alert.evidence[0].label == event


@pytest.mark.parametrize("rule", list(WARNINGS))
def test_watches_and_other_events_never_trigger(rule) -> None:
    hazard_type, event = WARNINGS[rule]
    watch = event.replace("Warning", "Watch")
    observations = [reading(hazard_type, watch), reading(hazard_type, None)]
    assert run(rule, observations).transition is Transition.NONE


def test_unavailable_reading_never_triggers() -> None:
    obs = reading(HazardType.SEVERE_STORM, "Tornado Warning", data_state=DataState.UNAVAILABLE)
    assert run(AlertRule.TORNADO, [obs]).transition is Transition.NONE


def active_warning(rule=AlertRule.TORNADO) -> Alert:
    hazard_type, event = WARNINGS[rule]
    return run(rule, [reading(hazard_type, event, 20)], at=NOW - timedelta(minutes=10)).alert


def test_still_listed_warning_is_unchanged() -> None:
    alert = active_warning()
    result = run(
        AlertRule.TORNADO, [reading(HazardType.SEVERE_STORM, "Tornado Warning", 20)], alert
    )
    assert result.transition is Transition.UNCHANGED
    assert result.alert.clear_after is None


def test_healthy_feed_without_the_warning_starts_the_window() -> None:
    alert = active_warning()
    result = run(AlertRule.TORNADO, [reading(HazardType.SEVERE_STORM, None)], alert)
    assert result.transition is Transition.RESET
    assert result.alert.clear_after == NOW + WARNING_WINDOW
    assert result.alert.state is AlertState.ACTIVE


@pytest.mark.parametrize("state", [DataState.STALE, DataState.UNAVAILABLE])
def test_unhealthy_feed_holds_and_never_starts_the_window(state) -> None:
    alert = active_warning()
    held = run(AlertRule.TORNADO, [reading(HazardType.SEVERE_STORM, None, data_state=state)], alert)
    assert held.transition is Transition.HELD
    assert held.alert.clear_after is None
    # No reading at all is not a healthy "no warning" either.
    assert run(AlertRule.TORNADO, [], alert).transition is Transition.HELD


def test_stale_reading_that_still_lists_the_warning_keeps_it_active() -> None:
    alert = active_warning()
    stale = reading(HazardType.SEVERE_STORM, "Tornado Warning", 20, data_state=DataState.STALE)
    result = run(AlertRule.TORNADO, [stale], alert)
    assert result.transition is Transition.UNCHANGED
    assert result.alert.state is AlertState.ACTIVE


def test_warning_reappearing_in_the_window_resets_it() -> None:
    alert = active_warning().model_copy(update={"clear_after": NOW + timedelta(minutes=10)})
    again = reading(HazardType.SEVERE_STORM, "Tornado Warning", 1, id="tor-2")
    result = run(AlertRule.TORNADO, [again], alert)
    assert result.transition is Transition.RESET
    assert result.alert.clear_after is None
    assert result.alert.id == alert.id
    assert "tor-2" in result.alert.trigger_observation_ids


def test_window_elapsed_with_a_healthy_feed_clears() -> None:
    alert = active_warning().model_copy(update={"clear_after": NOW - timedelta(seconds=1)})
    result = run(AlertRule.TORNADO, [reading(HazardType.SEVERE_STORM, None)], alert)
    assert result.transition is Transition.CLEARED
    assert result.alert.state is AlertState.CLEARED


def test_window_elapsed_with_an_unavailable_feed_holds() -> None:
    alert = active_warning().model_copy(update={"clear_after": NOW - timedelta(minutes=5)})
    down = reading(HazardType.SEVERE_STORM, None, data_state=DataState.UNAVAILABLE)
    assert run(AlertRule.TORNADO, [down], alert).transition is Transition.HELD


def test_window_still_running_is_unchanged() -> None:
    alert = active_warning().model_copy(update={"clear_after": NOW + timedelta(minutes=5)})
    result = run(AlertRule.TORNADO, [reading(HazardType.SEVERE_STORM, None)], alert)
    assert result.transition is Transition.UNCHANGED


def test_nhc_storm_center_inside_the_distance_triggers_the_hurricane_rule() -> None:
    def storm(miles):
        return reading(
            HazardType.HURRICANE,
            85.0,
            30,
            id=f"nhc:{miles}",
            source="NHC",
            unit="kt",
            label="Hurricane Test, 85 kt",
            lat=SITE.lat + miles / 69.0,
        )

    inside = run(AlertRule.HURRICANE, [storm(40)])
    assert inside.transition is Transition.TRIGGERED
    assert inside.alert.distance_miles == pytest.approx(40, abs=0.5)
    assert inside.alert.event_label.startswith("Hurricane center 40 mi")
    assert run(AlertRule.HURRICANE, [storm(80)]).transition is Transition.NONE


def test_tropical_storm_warning_does_not_trigger_the_hurricane_rule() -> None:
    obs = reading(HazardType.HURRICANE, "Tropical Storm Warning")
    assert run(AlertRule.HURRICANE, [obs]).transition is Transition.NONE
    assert run(AlertRule.TROPICAL_STORM, [obs]).transition is Transition.TRIGGERED


# ---- earthquake: event rule like lightning ----


def test_qualifying_quake_triggers_with_a_60_minute_window() -> None:
    result = run(AlertRule.EARTHQUAKE, [quake(4.6, 12, 5)])
    assert result.transition is Transition.TRIGGERED
    alert = result.alert
    assert alert.clear_after == alert.latest_event_at + QUAKE_WINDOW
    assert alert.event_label == "M4.6 earthquake 12 mi from site"
    assert alert.danger_tier == 2


@pytest.mark.parametrize(
    ("magnitude", "miles", "minutes_ago"),
    [(3.9, 5, 5), (4.6, 40, 5), (4.6, 5, 61)],
    ids=["too-small", "too-far", "window-already-over"],
)
def test_non_qualifying_quakes_do_not_trigger(magnitude, miles, minutes_ago) -> None:
    result = run(AlertRule.EARTHQUAKE, [quake(magnitude, miles, minutes_ago)])
    assert result.transition is Transition.NONE


def test_aftershock_resets_the_window() -> None:
    first = run(AlertRule.EARTHQUAKE, [quake(4.6, 12, 30)]).alert
    result = run(AlertRule.EARTHQUAKE, [quake(4.6, 12, 30), quake(4.1, 8, 2)], first)
    assert result.transition is Transition.RESET
    assert result.alert.clear_after == NOW - timedelta(minutes=2) + QUAKE_WINDOW
    assert result.alert.id == first.id


def test_quake_window_clears_only_with_a_healthy_feed() -> None:
    first = run(AlertRule.EARTHQUAKE, [quake(4.6, 12, 30)], at=NOW - timedelta(minutes=29)).alert
    later = NOW + timedelta(minutes=31)
    healthy = [quake(None, 0, 0, id="usgs:none", label="No earthquakes")]
    down = [quake(None, 0, 0, id="usgs:down", data_state=DataState.UNAVAILABLE)]
    assert run(AlertRule.EARTHQUAKE, down, first, later).transition is Transition.HELD
    assert run(AlertRule.EARTHQUAKE, healthy, first, later).transition is Transition.CLEARED


def test_lightning_has_no_prototype_rule_here() -> None:
    with pytest.raises(ValueError):
        run(AlertRule.LIGHTNING_STOP_WORK, [])
