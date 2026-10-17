"""Prototype heat and flood score factors (T049).

Both factors read Observations from the NWS feeds (`app.ingestion.nws_weather`,
`app.ingestion.nws_alerts`) and return one `FactorContribution` each, always labeled
`is_prototype=True`. Thresholds and points are in `RuleSettings`. They are prototype
settings, not official policy, and they set no work/rest schedule.

Heat:
- Uses the highest heat index among the current station reading and the hourly forecast
  for the next `heat_window_hours`.
- NWS forecasts have no heat-index field, so it is computed from forecast temperature
  and relative humidity with the NWS Rothfusz regression (`heat_index_f`).
- Below `heat_index_threshold_f`, heat adds 0. From the threshold to
  `heat_index_extreme_f`, points scale linearly from `heat_min_points` to
  `heat_max_points`.

Flood:
- Flood Warning or Flash Flood Warning adds `flood_warning_points`, and Flood Watch adds
  `flood_watch_points`. The strongest active alert counts once.
- USGS gauge readings are not flood stages, so they don't add points. NWS alerts stay the
  flood signal.

Missing data: when no usable reading exists (feed unavailable or never fetched), the
factor still appears with `contribution=0`, `data_state="unavailable"`, and a label that
says the value is unknown. It is never silently dropped, so the score can lower its data
completeness. Stale readings still count, so old bad news is not ignored, and they keep
`data_state="stale"`.
"""

from datetime import datetime, timedelta
from math import sqrt

from app.ingestion import nws_alerts, nws_weather
from app.rules.settings import RuleSettings
from app.schemas import DataState, FactorContribution, HazardType, Observation

HEAT = "heat_index"
FLOOD = "flood"
FLOOD_WARNINGS = frozenset({"Flood Warning", "Flash Flood Warning"})
FLOOD_WATCHES = frozenset({"Flood Watch"})


def heat_index_f(temperature_f: float, humidity: float) -> float:
    """NWS heat index (°F) from air temperature (°F) and relative humidity (%).

    Steadman's simple formula below 80 °F, otherwise the Rothfusz regression with the
    NWS low- and high-humidity adjustments.
    """
    t, rh = temperature_f, humidity
    simple = 0.5 * (t + 61.0 + (t - 68.0) * 1.2 + rh * 0.094)
    if (simple + t) / 2 < 80:
        return simple
    hi = (
        -42.379
        + 2.04901523 * t
        + 10.14333127 * rh
        - 0.22475541 * t * rh
        - 0.00683783 * t * t
        - 0.05481717 * rh * rh
        + 0.00122874 * t * t * rh
        + 0.00085282 * t * rh * rh
        - 0.00000199 * t * t * rh * rh
    )
    if rh < 13 and 80 <= t <= 112:
        hi -= ((13 - rh) / 4) * sqrt((17 - abs(t - 95)) / 17)
    elif rh > 85 and 80 <= t <= 87:
        hi += ((rh - 85) / 10) * ((87 - t) / 5)
    return hi


def heat_factor(
    observations: list[Observation], now: datetime, settings: RuleSettings
) -> FactorContribution:
    candidates = _heat_candidates(observations, now, settings.heat_window_hours)
    if not candidates:
        return _unknown(HEAT, "Heat index unknown (no usable NWS reading)", "NWS")
    value, source_obs = max(candidates, key=lambda c: c[0])
    value = round(value, 1)
    points = _heat_points(value, settings)
    when = "forecast" if source_obs.hazard_type == HazardType.FORECAST else "observed"
    status = "above" if points else "below"
    return FactorContribution(
        factor=HEAT,
        label=(
            f"Heat index {value:g} °F ({when}), {status} prototype threshold "
            f"{settings.heat_index_threshold_f:g} °F"
        ),
        contribution=points,
        value=value,
        unit="°F",
        source=source_obs.source,
        observed_at=source_obs.valid_at or source_obs.observed_at,
        data_state=source_obs.data_state,
        is_prototype=True,
        evidence_id=source_obs.id,
    )


def flood_factor(observations: list[Observation], settings: RuleSettings) -> FactorContribution:
    readings = [
        o
        for o in observations
        if o.hazard_type == HazardType.FLOOD_ALERT and o.data_state is not DataState.UNAVAILABLE
    ]
    if not readings:
        return _unknown(FLOOD, "Flood alerts unknown (NWS feed unavailable)", "NWS")
    alerts = [o for o in readings if o.value in FLOOD_WARNINGS | FLOOD_WATCHES]
    if not alerts:
        latest = max(readings, key=lambda o: o.observed_at)
        return FactorContribution(
            factor=FLOOD,
            label=latest.label or nws_alerts.NO_ACTIVE_ALERTS,
            contribution=0.0,
            source=latest.source,
            observed_at=latest.observed_at,
            data_state=latest.data_state,
            is_prototype=True,
            evidence_id=latest.id,
        )
    strongest = max(alerts, key=lambda o: (o.value in FLOOD_WARNINGS, o.observed_at))
    points = (
        settings.flood_warning_points
        if strongest.value in FLOOD_WARNINGS
        else settings.flood_watch_points
    )
    return FactorContribution(
        factor=FLOOD,
        label=f"{strongest.value} in effect (prototype weight)",
        contribution=points,
        value=strongest.value,
        source=strongest.source,
        observed_at=strongest.observed_at,
        data_state=strongest.data_state,
        is_prototype=True,
        evidence_id=strongest.id,
    )


def _heat_candidates(
    observations: list[Observation], now: datetime, window_hours: int
) -> list[tuple[float, Observation]]:
    """(heat index °F, source observation) pairs from usable readings."""
    usable = [o for o in observations if o.data_state is not DataState.UNAVAILABLE]
    candidates: list[tuple[float, Observation]] = []

    observed = [o for o in usable if o.hazard_type == HazardType.WEATHER]
    reported = [o for o in observed if o.label == nws_weather.HEAT_INDEX and _number(o.value)]
    if reported:
        latest = max(reported, key=lambda o: o.observed_at)
        candidates.append((float(latest.value), latest))
    else:
        candidates += _computed(observed, key=lambda o: o.observed_at)

    horizon = now + timedelta(hours=window_hours)
    forecast = [
        o
        for o in usable
        if o.hazard_type == HazardType.FORECAST and o.valid_at and now <= o.valid_at <= horizon
    ]
    candidates += _computed(forecast, key=lambda o: o.valid_at)
    return candidates


def _computed(observations: list[Observation], key) -> list[tuple[float, Observation]]:
    """Heat index from temperature and humidity readings that share a timestamp."""
    temps: dict[datetime, Observation] = {}
    humidity: dict[datetime, float] = {}
    for o in observations:
        if not _number(o.value):
            continue
        if o.label == nws_weather.TEMPERATURE:
            temps[key(o)] = o
        elif o.label == nws_weather.RELATIVE_HUMIDITY:
            humidity[key(o)] = float(o.value)
    return [
        (heat_index_f(float(temp.value), humidity[at]), temp)
        for at, temp in temps.items()
        if at in humidity
    ]


def _heat_points(value: float, settings: RuleSettings) -> float:
    low, high = settings.heat_index_threshold_f, settings.heat_index_extreme_f
    if value < low:
        return 0.0
    share = 1.0 if high <= low else min(1.0, (value - low) / (high - low))
    points = settings.heat_min_points + share * (
        settings.heat_max_points - settings.heat_min_points
    )
    return round(points, 2)


def _unknown(factor: str, label: str, source: str) -> FactorContribution:
    return FactorContribution(
        factor=factor,
        label=label,
        contribution=0.0,
        source=source,
        data_state=DataState.UNAVAILABLE,
        is_prototype=True,
    )


def _number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)
