"""Lightning stop-work rule (T046) and resettable 30-minute all-clear (T047).

From the challenge brief (not a prototype setting):

- A qualifying strike within 10 miles of a site creates a stop-work alert.
- The all-clear time is the latest qualifying strike's time plus 30 minutes. Every new
  qualifying strike resets it.
- The alert clears only when that window passes with no new qualifying strike.

Details:

- Distance is the strike Observation's `value` (miles to the site, computed by the
  lightning feed). Exactly 10.0 miles qualifies.
- Every lightning reading counts, including GOES GLM in-cloud flashes, which can't be told
  apart from cloud-to-ground strikes. This is the cautious choice.
- Timing uses each strike's `observed_at`, never the fetch time, so GLM delivery delay
  can't shorten the window.
- The alert is `simulated` only if every strike behind it was simulated (replay).
- A stale or unavailable lightning feed never clears an alert. Past its all-clear time,
  the alert is held active until a healthy reading confirms no new strike.

`evaluate_lightning` is pure: it takes the site's current lightning alert and the latest
lightning Observations and returns the next alert state. Persistence and audit logging
belong to the caller (T048).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

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

STOP_WORK_MILES = 10.0
ALL_CLEAR = timedelta(minutes=30)


class Transition(StrEnum):
    NONE = "none"  # no alert before or after
    TRIGGERED = "triggered"  # new stop-work alert
    RESET = "reset"  # a newer qualifying strike moved the all-clear time
    CLEARED = "cleared"  # 30 strike-free minutes passed with a healthy feed
    HELD = "held"  # all-clear time passed, but the feed can't confirm no new strike
    UNCHANGED = "unchanged"  # active alert, still inside its window


@dataclass(frozen=True)
class LightningResult:
    alert: Alert | None
    transition: Transition


def qualifying_strikes(site_id: str, observations: list[Observation]) -> list[Observation]:
    """Strikes for this site within 10 miles, oldest first. "None" readings have no value."""
    strikes = [
        o
        for o in observations
        if o.hazard_type == HazardType.LIGHTNING_STRIKE
        and o.site_id in (None, site_id)
        and isinstance(o.value, int | float)
        and o.value <= STOP_WORK_MILES
        and o.data_state is not DataState.UNAVAILABLE
    ]
    return sorted(strikes, key=lambda o: o.observed_at)


def feed_is_healthy(observations: list[Observation]) -> bool:
    """False when the lightning feed fell back to stale data or reported unavailable."""
    readings = [o for o in observations if o.hazard_type == HazardType.LIGHTNING_STRIKE]
    if not readings:
        return False
    return all(o.data_state not in (DataState.STALE, DataState.UNAVAILABLE) for o in readings)


def evaluate_lightning(
    site_id: str,
    observations: list[Observation],
    current: Alert | None,
    now: datetime,
) -> LightningResult:
    """Next lightning stop-work state for one site.

    `current` is the site's latest lightning alert, active or cleared, or None.
    """
    active = current if current and current.state is AlertState.ACTIVE else None
    # Strikes at or before the last alert's latest event were already counted.
    counted_until = current.latest_event_at if current else None
    new = [
        s
        for s in qualifying_strikes(site_id, observations)
        if s.observed_at <= now and (counted_until is None or s.observed_at > counted_until)
    ]

    if active is None:
        if not new or new[-1].observed_at + ALL_CLEAR <= now:
            return LightningResult(None, Transition.NONE)
        return LightningResult(_new_alert(site_id, _current_run(new)), Transition.TRIGGERED)

    if new:
        return LightningResult(_extend(active, new), Transition.RESET)
    if active.clear_after and now >= active.clear_after:
        if feed_is_healthy(observations):
            return LightningResult(
                active.model_copy(update={"state": AlertState.CLEARED}), Transition.CLEARED
            )
        return LightningResult(active, Transition.HELD)
    return LightningResult(active, Transition.UNCHANGED)


def _current_run(strikes: list[Observation]) -> list[Observation]:
    """Strikes since the last 30-minute gap. An earlier run would already have cleared."""
    start = 0
    for i in range(1, len(strikes)):
        if strikes[i].observed_at - strikes[i - 1].observed_at >= ALL_CLEAR:
            start = i
    return strikes[start:]


def _new_alert(site_id: str, strikes: list[Observation]) -> Alert:
    first, latest = strikes[0], strikes[-1]
    return Alert(
        id=f"ltg-alert:{site_id}:{first.observed_at.isoformat()}",
        site_id=site_id,
        rule=AlertRule.LIGHTNING_STOP_WORK,
        state=AlertState.ACTIVE,
        triggered_at=first.observed_at,
        latest_event_at=latest.observed_at,
        clear_after=latest.observed_at + ALL_CLEAR,
        distance_miles=float(latest.value),
        trigger_observation_ids=[_ref(s) for s in strikes],
        evidence=[_evidence(s) for s in strikes],
        simulated=all(s.simulated for s in strikes),
        is_prototype_rule=False,
    )


def _extend(alert: Alert, strikes: list[Observation]) -> Alert:
    latest = strikes[-1]
    return alert.model_copy(
        update={
            "latest_event_at": latest.observed_at,
            "clear_after": latest.observed_at + ALL_CLEAR,
            "distance_miles": float(latest.value),
            "trigger_observation_ids": alert.trigger_observation_ids + [_ref(s) for s in strikes],
            "evidence": alert.evidence + [_evidence(s) for s in strikes],
            "simulated": alert.simulated and all(s.simulated for s in strikes),
        }
    )


def _ref(strike: Observation) -> str:
    return strike.id or strike.source_ref or f"ltg:{strike.observed_at.isoformat()}"


def _evidence(strike: Observation) -> Evidence:
    return Evidence(
        id=_ref(strike),
        kind=EvidenceKind.OBSERVATION,
        label=strike.label or f"Strike {strike.value} mi",
        observed_at=strike.observed_at,
    )
