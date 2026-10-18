"""T049: prototype heat and flood factors."""

from datetime import timedelta

import pytest

from app.ingestion.nws_alerts import NO_ACTIVE_ALERTS
from app.ingestion.nws_weather import HEAT_INDEX, RELATIVE_HUMIDITY, TEMPERATURE
from app.rules.factors import flood_factor, heat_factor, heat_index_f
from app.rules.settings import RuleSettings
from app.schemas import DataState, HazardType, Observation
from tests.nws_fakes import NOW

SETTINGS = RuleSettings(_env_file=None)


def obs(hazard_type, label, value, minutes=0, valid_in=None, state=None, **extra) -> Observation:
    forecast = hazard_type == HazardType.FORECAST
    return Observation(
        id=f"{hazard_type}:{label}:{minutes}:{valid_in}",
        site_id="site-demo",
        source="NWS",
        hazard_type=hazard_type,
        value=value,
        label=label,
        lat=25.76,
        lon=-80.49,
        observed_at=NOW - timedelta(minutes=minutes),
        valid_at=NOW + timedelta(hours=valid_in) if valid_in is not None else None,
        data_state=state or (DataState.FORECAST if forecast else DataState.OBSERVED),
        **extra,
    )


def forecast_pair(temp: float, rh: float, hours: float) -> list[Observation]:
    return [
        obs(HazardType.FORECAST, TEMPERATURE, temp, valid_in=hours),
        obs(HazardType.FORECAST, RELATIVE_HUMIDITY, rh, valid_in=hours),
    ]


# ---- heat index formula: values from the NWS heat index chart ----


@pytest.mark.parametrize(
    ("temp", "rh", "expected"),
    [(90, 70, 106), (96, 50, 108), (100, 40, 109), (86, 90, 105), (80, 40, 80), (70, 50, 69)],
)
def test_heat_index_matches_nws_chart(temp, rh, expected) -> None:
    assert heat_index_f(temp, rh) == pytest.approx(expected, abs=1.5)


# ---- heat factor ----


def test_below_threshold_adds_nothing_but_is_shown() -> None:
    factor = heat_factor([obs(HazardType.WEATHER, HEAT_INDEX, 95.0)], NOW, SETTINGS)
    assert factor.contribution == 0
    assert factor.value == 95.0
    assert "below prototype threshold 103" in factor.label
    assert factor.is_prototype


@pytest.mark.parametrize(("hi", "points"), [(103.0, 2.5), (114.0, 3.0), (125.0, 3.5), (140, 3.5)])
def test_points_scale_from_threshold_to_extreme(hi, points) -> None:
    factor = heat_factor([obs(HazardType.WEATHER, HEAT_INDEX, hi)], NOW, SETTINGS)
    assert factor.contribution == points


def test_forecast_heat_index_is_computed_from_temperature_and_humidity() -> None:
    factor = heat_factor(forecast_pair(96, 50, hours=3), NOW, SETTINGS)
    assert factor.value == pytest.approx(108, abs=1.5)
    assert factor.contribution > 0
    assert factor.data_state is DataState.FORECAST
    assert "(forecast)" in factor.label
    assert factor.observed_at == NOW + timedelta(hours=3)


def test_uses_highest_heat_index_in_window() -> None:
    observations = [
        obs(HazardType.WEATHER, HEAT_INDEX, 98.0),
        *forecast_pair(96, 50, hours=2),
        *forecast_pair(100, 60, hours=20),  # outside the 12 h window
    ]
    factor = heat_factor(observations, NOW, SETTINGS)
    assert factor.value == pytest.approx(108, abs=1.5)


def test_factor_carries_source_time_and_evidence() -> None:
    reading = obs(HazardType.WEATHER, HEAT_INDEX, 110.0, minutes=20)
    factor = heat_factor([reading], NOW, SETTINGS)
    assert factor.source == "NWS"
    assert factor.observed_at == reading.observed_at
    assert factor.evidence_id == reading.id


def test_stale_reading_still_counts_and_stays_stale() -> None:
    factor = heat_factor(
        [obs(HazardType.WEATHER, HEAT_INDEX, 110.0, state=DataState.STALE)], NOW, SETTINGS
    )
    assert factor.contribution > 0
    assert factor.data_state is DataState.STALE


def test_no_usable_reading_is_unknown_not_dropped() -> None:
    unavailable = obs(HazardType.WEATHER, None, None, state=DataState.UNAVAILABLE)
    for observations in ([], [unavailable]):
        factor = heat_factor(observations, NOW, SETTINGS)
        assert factor.data_state is DataState.UNAVAILABLE
        assert factor.contribution == 0
        assert "unknown" in factor.label


def test_threshold_is_configurable() -> None:
    lower = RuleSettings(heat_index_threshold_f=90, _env_file=None)
    assert heat_factor([obs(HazardType.WEATHER, HEAT_INDEX, 95.0)], NOW, lower).contribution > 0


# ---- flood factor ----


def flood(value, label=None, state=None, minutes=0) -> Observation:
    return obs(
        HazardType.FLOOD_ALERT, label or value or NO_ACTIVE_ALERTS, value, minutes, state=state
    )


@pytest.mark.parametrize(
    ("event", "points"),
    [("Flood Warning", 2.0), ("Flash Flood Warning", 2.0), ("Flood Watch", 1.0)],
)
def test_each_flood_alert_type(event, points) -> None:
    factor = flood_factor([flood(event)], SETTINGS)
    assert factor.contribution == points
    assert factor.value == event
    assert factor.is_prototype and factor.source == "NWS"


def test_strongest_alert_counts_once() -> None:
    factor = flood_factor([flood("Flood Watch"), flood("Flood Warning", minutes=5)], SETTINGS)
    assert factor.contribution == 2.0


def test_no_active_alerts_adds_zero_and_is_observed() -> None:
    factor = flood_factor([flood(None)], SETTINGS)
    assert factor.contribution == 0
    assert factor.data_state is DataState.OBSERVED
    assert factor.label == NO_ACTIVE_ALERTS


def test_unavailable_flood_feed_is_unknown_not_no_flood() -> None:
    factor = flood_factor(
        [flood(None, label="NWS flood_alert unavailable", state=DataState.UNAVAILABLE)], SETTINGS
    )
    assert factor.data_state is DataState.UNAVAILABLE
    assert "unknown" in factor.label
    assert factor.label != NO_ACTIVE_ALERTS


def test_stale_cached_warning_still_counts() -> None:
    factor = flood_factor([flood("Flood Warning", state=DataState.STALE)], SETTINGS)
    assert factor.contribution == 2.0
    assert factor.data_state is DataState.STALE
