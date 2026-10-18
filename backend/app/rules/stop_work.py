"""Prototype stop-work rules for warnings and earthquakes (T049C).

Lightning keeps its own brief-required rule in `app.rules.lightning`. These rules give
the other dangerous events the same lifecycle: a deterministic trigger, a resettable
all-clear window, held while the feed can't confirm, acknowledgeable and audited (the
caller, `app.services.alerts`, persists and audits).

Warning rules (tornado, hurricane, flash flood, severe thunderstorm, tropical storm,
flood) are conditions, not instants:

- An active NWS warning of that event for the site point triggers the alert. For the
  hurricane rule, an NHC storm center within `hurricane_storm_distance_miles` also does
  (`app.rules.regional.hurricane_detections`).
- While the warning is listed, the alert has no all-clear time (`clear_after=None`).
- When a healthy feed stops listing it, the all-clear time is set to now plus
  `warning_all_clear_minutes` (30). If the warning reappears first, the window resets.
  Starting the window is recorded as a reset (the all-clear time moved).
- A stale or unavailable feed never starts the window and never clears the alert. A stale
  reading that still lists the warning keeps the alert active.

Earthquake is an event, like a strike: a qualifying USGS event (`earthquake_detections`,
M4.0+ within 25 mi by default) triggers, the all-clear time is the latest qualifying
origin time plus `earthquake_all_clear_minutes` (60), and each new qualifying event
(an aftershock) resets it.

Watches never trigger. Distances and magnitudes reuse the hurricane and earthquake
settings in `RuleSettings`; the all-clear windows are in `StopWorkSettings`. All are
prototype values, not official policy. `evaluate_stop_work` is pure.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.ingestion.base import SiteLike
from app.rules.lightning import LightningResult as StopWorkResult
from app.rules.lightning import Transition
from app.rules.regional import NHC, NWS, earthquake_detections, hurricane_detections
from app.rules.settings import RuleSettings
from app.schemas import (
    Alert,
    AlertRule,
    AlertState,
    DataState,
    Evidence,
    EvidenceKind,
    HazardType,
    Observation,
)

__all__ = [
    "EVENT_RULES",
    "WARNING_RULES",
    "Qualifying",
    "StopWorkResult",
    "StopWorkSettings",
    "Transition",
    "evaluate_stop_work",
    "get_stop_work_settings",
    "qualifying",
]


class StopWorkSettings(BaseSettings):
    """Prototype all-clear windows, read from the environment or backend/.env.

    Lightning's 30-minute window is fixed by the brief and lives in `app.rules.lightning`.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    warning_all_clear_minutes: int = Field(default=30, ge=1, le=24 * 60)
    earthquake_all_clear_minutes: int = Field(default=60, ge=1, le=24 * 60)


@lru_cache
def get_stop_work_settings() -> StopWorkSettings:
    return StopWorkSettings()


@dataclass(frozen=True)
class Qualifying:
    """One reading that qualifies for a stop-work rule."""

    observation: Observation
    distance_miles: float | None
    label: str  # evidence label


def _nws_warning(event: str, hazard_type: HazardType):
    def find(site: SiteLike, observations: list[Observation], _: RuleSettings):
        return [
            Qualifying(o, None, o.label or event)
            for o in _readings(site.id, observations, hazard_type)
            if o.source == NWS and o.value == event and o.data_state is not DataState.UNAVAILABLE
        ]

    return find


def _hurricanes(site: SiteLike, observations: list[Observation], settings: RuleSettings):
    found = []
    for d in hurricane_detections(site, observations, settings):
        o = d.observation
        if o.source == NWS and o.value == "Hurricane Warning":
            found.append(Qualifying(o, None, o.label or "Hurricane Warning"))
        elif o.source == NHC:
            label = f"{o.label or 'NHC storm'} (center {d.distance_miles:.0f} mi from site)"
            found.append(Qualifying(o, d.distance_miles, label))
    return found


def _earthquakes(site: SiteLike, observations: list[Observation], settings: RuleSettings):
    return [
        Qualifying(
            d.observation,
            d.distance_miles,
            f"M{float(d.observation.value):.1f} earthquake {d.distance_miles:.0f} mi from site",
        )
        for d in earthquake_detections(site, observations, settings)
    ]


Finder = Callable[[SiteLike, list[Observation], RuleSettings], list[Qualifying]]

# Rule -> (qualifying readings, hazard type whose feed health gates clearing).
WARNING_RULES: dict[AlertRule, tuple[Finder, HazardType]] = {
    AlertRule.TORNADO: (
        _nws_warning("Tornado Warning", HazardType.SEVERE_STORM),
        HazardType.SEVERE_STORM,
    ),
    AlertRule.HURRICANE: (_hurricanes, HazardType.HURRICANE),
    AlertRule.FLASH_FLOOD: (
        _nws_warning("Flash Flood Warning", HazardType.FLOOD_ALERT),
        HazardType.FLOOD_ALERT,
    ),
    AlertRule.SEVERE_THUNDERSTORM: (
        _nws_warning("Severe Thunderstorm Warning", HazardType.SEVERE_STORM),
        HazardType.SEVERE_STORM,
    ),
    AlertRule.TROPICAL_STORM: (
        _nws_warning("Tropical Storm Warning", HazardType.HURRICANE),
        HazardType.HURRICANE,
    ),
    AlertRule.FLOOD: (
        _nws_warning("Flood Warning", HazardType.FLOOD_ALERT),
        HazardType.FLOOD_ALERT,
    ),
}
EVENT_RULES: dict[AlertRule, tuple[Finder, HazardType]] = {
    AlertRule.EARTHQUAKE: (_earthquakes, HazardType.EARTHQUAKE),
}
PREFIX = {
    AlertRule.TORNADO: "tornado",
    AlertRule.HURRICANE: "hurricane",
    AlertRule.FLASH_FLOOD: "flash-flood",
    AlertRule.SEVERE_THUNDERSTORM: "svr-tstorm",
    AlertRule.TROPICAL_STORM: "tropical-storm",
    AlertRule.FLOOD: "flood",
    AlertRule.EARTHQUAKE: "eq",
}


def qualifying(
    rule: AlertRule, site: SiteLike, observations: list[Observation], settings: RuleSettings
) -> list[Qualifying]:
    finder, _ = WARNING_RULES.get(rule) or EVENT_RULES[rule]
    return finder(site, observations, settings)


def feed_is_healthy(hazard_type: HazardType, site_id: str, observations: list[Observation]):
    """False when the feed reported nothing, fell back to stale, or is unavailable."""
    readings = _readings(site_id, observations, hazard_type)
    return bool(readings) and all(
        o.data_state not in (DataState.STALE, DataState.UNAVAILABLE) for o in readings
    )


def evaluate_stop_work(
    rule: AlertRule,
    site: SiteLike,
    observations: list[Observation],
    current: Alert | None,
    now: datetime,
    settings: RuleSettings,
    windows: StopWorkSettings | None = None,
) -> StopWorkResult:
    """Next state of one prototype stop-work rule for one site.

    `current` is the site's latest alert for this rule, active or cleared, or None.
    """
    windows = windows or get_stop_work_settings()
    if rule in WARNING_RULES:
        window = timedelta(minutes=windows.warning_all_clear_minutes)
        return _evaluate_warning(rule, site, observations, current, now, settings, window)
    if rule in EVENT_RULES:
        window = timedelta(minutes=windows.earthquake_all_clear_minutes)
        return _evaluate_event(rule, site, observations, current, now, settings, window)
    raise ValueError(f"{rule} has no prototype stop-work rule")


def _evaluate_warning(rule, site, observations, current, now, settings, window):
    finder, hazard_type = WARNING_RULES[rule]
    found = [q for q in finder(site, observations, settings) if q.observation.observed_at <= now]
    active = current if current and current.state is AlertState.ACTIVE else None

    if active is None:
        if not found:
            return StopWorkResult(None, Transition.NONE)
        return StopWorkResult(_new_alert(rule, site.id, found, now, None), Transition.TRIGGERED)
    if found:
        if active.clear_after is None:
            return StopWorkResult(active, Transition.UNCHANGED)
        # The warning reappeared during the all-clear window: back to no all-clear time.
        return StopWorkResult(_extend(active, found, now, None), Transition.RESET)
    if not feed_is_healthy(hazard_type, site.id, observations):
        return StopWorkResult(active, Transition.HELD)
    if active.clear_after is None:
        # A healthy feed no longer lists the warning: the all-clear window starts now.
        started = active.model_copy(update={"clear_after": now + window})
        return StopWorkResult(started, Transition.RESET)
    if now >= active.clear_after:
        return StopWorkResult(
            active.model_copy(update={"state": AlertState.CLEARED}), Transition.CLEARED
        )
    return StopWorkResult(active, Transition.UNCHANGED)


def _evaluate_event(rule, site, observations, current, now, settings, window):
    finder, hazard_type = EVENT_RULES[rule]
    active = current if current and current.state is AlertState.ACTIVE else None
    counted_until = current.latest_event_at if current else None
    new = sorted(
        (
            q
            for q in finder(site, observations, settings)
            if q.observation.observed_at <= now
            and (counted_until is None or q.observation.observed_at > counted_until)
        ),
        key=lambda q: q.observation.observed_at,
    )

    if active is None:
        if not new or new[-1].observation.observed_at + window <= now:
            return StopWorkResult(None, Transition.NONE)
        latest = new[-1].observation.observed_at
        alert = _new_alert(rule, site.id, new, new[0].observation.observed_at, latest + window)
        return StopWorkResult(alert, Transition.TRIGGERED)
    if new:
        latest = new[-1].observation.observed_at
        return StopWorkResult(_extend(active, new, latest, latest + window), Transition.RESET)
    if active.clear_after and now >= active.clear_after:
        if feed_is_healthy(hazard_type, site.id, observations):
            return StopWorkResult(
                active.model_copy(update={"state": AlertState.CLEARED}), Transition.CLEARED
            )
        return StopWorkResult(active, Transition.HELD)
    return StopWorkResult(active, Transition.UNCHANGED)


def _new_alert(
    rule: AlertRule,
    site_id: str,
    found: list[Qualifying],
    triggered_at: datetime,
    clear_after: datetime | None,
) -> Alert:
    latest = max(found, key=lambda q: q.observation.observed_at)
    return Alert(
        id=f"{PREFIX[rule]}-alert:{site_id}:{triggered_at.isoformat()}",
        site_id=site_id,
        rule=rule,
        state=AlertState.ACTIVE,
        triggered_at=triggered_at,
        latest_event_at=max(triggered_at, latest.observation.observed_at),
        clear_after=clear_after,
        distance_miles=_nearest(found),
        trigger_observation_ids=[_ref(q.observation) for q in found],
        evidence=[_evidence(q) for q in found],
        simulated=all(q.observation.simulated for q in found),
        is_prototype_rule=True,
    )


def _extend(alert: Alert, found: list[Qualifying], latest_event_at: datetime, clear_after) -> Alert:
    return alert.model_copy(
        update={
            "latest_event_at": max(alert.latest_event_at, latest_event_at),
            "clear_after": clear_after,
            "distance_miles": _nearest(found),
            "trigger_observation_ids": alert.trigger_observation_ids
            + [_ref(q.observation) for q in found],
            "evidence": alert.evidence + [_evidence(q) for q in found],
            "simulated": alert.simulated and all(q.observation.simulated for q in found),
        }
    )


def _nearest(found: list[Qualifying]) -> float | None:
    miles = [q.distance_miles for q in found if q.distance_miles is not None]
    return min(miles) if miles else None


def _readings(site_id: str, observations: list[Observation], hazard_type: HazardType):
    return [
        o for o in observations if o.hazard_type == hazard_type and o.site_id in (None, site_id)
    ]


def _ref(o: Observation) -> str:
    return o.id or o.source_ref or f"{o.hazard_type}:{o.observed_at.isoformat()}"


def _evidence(q: Qualifying) -> Evidence:
    o = q.observation
    return Evidence(
        id=_ref(o), kind=EvidenceKind.OBSERVATION, label=q.label, observed_at=o.observed_at
    )
