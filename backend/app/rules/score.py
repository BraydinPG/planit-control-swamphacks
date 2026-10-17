"""T051A deterministic Site Hazard Index; prototype, never work authorization.

Index = round(clamp(sum(qualified factor contributions), 0, 10), 1).
Default points: active lightning alert 3; heat 0 or 0.5--2 (103--125 F);
strongest flood watch/warning 1/2; hurricane 2; earthquake 1.5; confirmed-present
reports low/moderate/high 0.5/1/1.5, capped at 3 per reviewed category. Bands:
<3 low, <6 moderate, <8 high, otherwise critical. No ML/Gemini term.

Qualification uses trusted normalized site-linked feeds, as-of availability, latest
fetch per feed, existing cache ages, valid windows, sources and units. Heat pairs
must share station/grid, issue time, valid time and location. Regional thresholds
remain T049A's 50 mi hurricane and M4+/25 mi earthquake prototypes. Repeated
observations cannot add extra factors. Reports deduplicate IDs and shared notice
IDs; distinct reports remain visible even when capped. Confirmed hazards do not
expire automatically: no qualified resolution field exists in the report contract.

Stale positive factors remain labeled stale; unavailable readings add no measured
points and remain explicitly unknown. Replay can demonstrate arithmetic but never
establish live coverage. Completeness/confidence is current live heat/flood/lightning
coverage / 3, not statistical confidence or coverage of all worker hazards. Optional
regional feeds remain outside that denominator and expose their own unknown state.
An active lightning alert is authoritative even during outage; this module never
evaluates or clears it, nor treats it as proof of current feed health.

CONTRACT LIMIT: HazardScore requires a number and one of four numeric bands. A zero
with missing evidence is an incomplete index, NOT verified low risk. Consumers must
read completeness and factor states. docs/SITE_RISK_SCORING.md proposes a separate
evidence-status field for Rudra; no schema/persistence/UI change is made here.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from math import isfinite

from app.ingestion import nws_alerts, nws_weather
from app.ingestion.base import SiteLike
from app.ingestion.settings import get_ingestion_settings
from app.rules.factors import flood_factor, heat_factor
from app.rules.regional import earthquake_factor, hurricane_factor
from app.rules.settings import RuleSettings, get_rule_settings
from app.schemas import (
    Alert,
    AlertRule,
    AlertState,
    CrewReport,
    DataState,
    FactorContribution,
    HazardScore,
    HazardType,
    Observation,
    ReviewStatus,
    RiskLevel,
    Severity,
)

MODEL_VERSION = "rules-0.2"
MAX_SCORE = 10.0
LIGHTNING = "lightning"
CREW_REPORT = "crew_report"
CURRENT_STATES = frozenset({DataState.OBSERVED, DataState.FORECAST})
SOURCES = {
    HazardType.WEATHER: {"NWS"},
    HazardType.FORECAST: {"NWS"},
    HazardType.FLOOD_ALERT: {"NWS"},
    HazardType.HURRICANE: {"NWS", "NHC"},
    HazardType.EARTHQUAKE: {"USGS"},
    HazardType.LIGHTNING_STRIKE: {"GOES GLM", "lightning-replay"},
}


def risk_level(score: float) -> RiskLevel:
    """Numeric band only; even LOW never means that work is authorized."""
    if score < 3:
        return RiskLevel.LOW
    if score < 6:
        return RiskLevel.MODERATE
    if score < 8:
        return RiskLevel.HIGH
    return RiskLevel.CRITICAL


def compute_score(
    site_id: str,
    observations: list[Observation],
    alerts: list[Alert],
    reports: list[CrewReport],
    now: datetime,
    previous: HazardScore | None = None,
    settings: RuleSettings | None = None,
    site: SiteLike | None = None,
) -> HazardScore:
    """Pure aggregation; callers retain authorization, persistence and alert policy."""
    if not _aware(now):
        raise ValueError("now must include a timezone")
    if not site_id or not site_id.strip():
        raise ValueError("site_id must be nonempty")
    if site is not None and (
        site.id != site_id
        or not _finite(site.lat)
        or not _finite(site.lon)
        or not -90 <= site.lat <= 90
        or not -180 <= site.lon <= 180
    ):
        raise ValueError("site must match site_id and have valid coordinates")
    settings = settings or get_rule_settings()
    readings = _qualified(site_id, observations, now, settings)
    site_alerts = [
        a
        for a in alerts
        if a.site_id == site_id
        and _aware(a.triggered_at)
        and _aware(a.latest_event_at)
        and a.triggered_at <= a.latest_event_at <= now
    ]
    heat = _heat(readings, now, settings)
    flood = _explain_unknown(flood_factor(readings, settings), readings, {HazardType.FLOOD_ALERT})
    lightning = lightning_factor(readings, site_alerts, settings)
    factors = [lightning, heat, flood, *report_factors(reports, settings, site_id, now)]
    factors += [
        _explain_unknown(f, readings, {kind})
        for kind, f in (
            (HazardType.HURRICANE, hurricane_factor(site, readings, settings)),
            (HazardType.EARTHQUAKE, earthquake_factor(site, readings, settings)),
        )
        if f is not None
    ]
    # Alert authority and feed coverage differ: an active/held alert supplies points,
    # but cannot make an unavailable or replay-only lightning feed current.
    lightning_current = any(
        o.hazard_type == HazardType.LIGHTNING_STRIKE and o.data_state in CURRENT_STATES
        for o in readings
    )
    completeness = (
        sum(f.data_state in CURRENT_STATES for f in (heat, flood)) + lightning_current
    ) / 3
    total = round(max(0.0, min(MAX_SCORE, sum(f.contribution for f in factors))), 1)
    return HazardScore(
        site_id=site_id,
        risk_score=total,
        risk_level=risk_level(total),
        factor_contributions=factors,
        model_version=MODEL_VERSION,
        model_is_fallback=False,  # No model called; not an ML fallback indicator.
        confidence=round(completeness, 2),
        data_completeness=round(completeness, 2),
        previous_score=previous.risk_score if previous and previous.site_id == site_id else None,
        created_at=now,
    )


def _aware(at: datetime) -> bool:
    return at.tzinfo is not None and at.utcoffset() is not None


def _finite(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and isfinite(value)


def _key(o: Observation) -> str:
    """Total ordering makes ties independent of input/DB row order."""
    return o.model_dump_json()


def _qualified(
    site_id: str, observations: list[Observation], now: datetime, settings: RuleSettings
) -> list[Observation]:
    cache = get_ingestion_settings()

    # Same snapshot rule as services.scoring.current_readings, also for direct callers.
    def feed(o: Observation) -> tuple:
        # Replay is a fallback for the same lightning feed, not extra live coverage.
        return (
            (o.hazard_type,)
            if o.hazard_type == HazardType.LIGHTNING_STRIKE
            else (o.hazard_type, o.source)
        )

    latest: dict[tuple, datetime] = {}
    relevant = [
        o for o in observations if o.site_id in (None, site_id) and o.hazard_type in SOURCES
    ]
    for o in relevant:
        if o.fetched_at and _aware(o.fetched_at) and o.fetched_at <= now:
            key = feed(o)
            latest[key] = max(latest.get(key, o.fetched_at), o.fetched_at)
    result = []
    for o in sorted(relevant, key=_key):
        if (
            o.fetched_at
            and _aware(o.fetched_at)
            and o.fetched_at < latest.get(feed(o), o.fetched_at)
        ):
            continue
        reason = _invalid_reason(o, now, settings)
        if reason:
            result.append(
                o.model_copy(
                    update={
                        "data_state": DataState.UNAVAILABLE,
                        "value": None,
                        "label": f"Unknown: excluded evidence ({reason})",
                    }
                )
            )
            continue
        if o.data_state is DataState.UNAVAILABLE:
            result.append(o)
            continue
        if o.simulated or o.data_state is DataState.SIMULATED or o.source == "lightning-replay":
            # Retain origin when age changes the single state enum to STALE.
            o = o.model_copy(update={"simulated": True})
        # Warning issue and quake occurrence times differ from query refresh time.
        age = now - (o.fetched_at or o.observed_at)
        if o.hazard_type == HazardType.WEATHER:
            age = max(age, now - o.observed_at)
        if age > cache.unavailable_after:
            o = o.model_copy(
                update={
                    "data_state": DataState.UNAVAILABLE,
                    "value": None,
                    "label": "Unknown: last usable evidence exceeds cache availability age",
                }
            )
        elif age > cache.stale_after:
            o = o.model_copy(update={"data_state": DataState.STALE})
        elif o.simulated or o.source == "lightning-replay":
            if o.data_state is not DataState.STALE:
                o = o.model_copy(update={"data_state": DataState.SIMULATED})
        result.append(o)
    return result


def _invalid_reason(o: Observation, now: datetime, settings: RuleSettings) -> str | None:
    times = [
        o.observed_at,
        *([o.fetched_at] if o.fetched_at else []),
        *([o.valid_at] if o.valid_at else []),
    ]
    if any(not _aware(at) for at in times):
        return "timezone missing"
    if o.observed_at > now or (o.fetched_at and o.fetched_at > now):
        return "not available as of scoring time"
    if o.fetched_at and o.observed_at > o.fetched_at:
        return "observation/issue time follows fetch time"
    if o.source not in SOURCES[o.hazard_type]:
        return "source not qualified for this factor"
    if o.data_state is DataState.CREW_REPORTED:
        return "observation is not a confirmed report"
    if o.hazard_type == HazardType.WEATHER and o.data_state is DataState.FORECAST:
        return "forecast must use the forecast observation type"
    if o.site_id is None and not (
        o.hazard_type == HazardType.EARTHQUAKE
        or (o.hazard_type == HazardType.HURRICANE and o.source == "NHC")
    ):
        return "missing site association"
    if o.hazard_type == HazardType.FORECAST:
        if not o.valid_at or not now <= o.valid_at <= now + timedelta(
            hours=settings.heat_window_hours
        ):
            return "forecast outside eligible horizon"
        if o.valid_at < o.observed_at:
            return "forecast valid time precedes issue time"
    elif o.hazard_type == HazardType.WEATHER and o.valid_at and o.valid_at > now:
        return "observed weather has a future valid time"
    elif o.hazard_type == HazardType.FLOOD_ALERT or (
        o.hazard_type == HazardType.HURRICANE and o.source == "NWS"
    ):
        if o.valid_at and o.valid_at <= now:
            return "official notice has expired"
    if isinstance(o.value, float) and not isfinite(o.value):
        return "nonfinite measurement"
    if o.hazard_type in {HazardType.WEATHER, HazardType.FORECAST}:
        if o.label in {nws_weather.HEAT_INDEX, nws_weather.TEMPERATURE}:
            if not _finite(o.value) or o.unit not in {"°F", "F"}:
                return "temperature/heat index requires finite Fahrenheit value"
        elif o.label == nws_weather.RELATIVE_HUMIDITY:
            if not _finite(o.value) or o.unit != "%" or not 0 <= o.value <= 100:
                return "relative humidity requires percent in [0,100]"
    if o.hazard_type == HazardType.FLOOD_ALERT and o.value is None:
        if o.data_state is not DataState.UNAVAILABLE and o.label != nws_alerts.NO_ACTIVE_ALERTS:
            return "missing explicit successful no-alert result"
    if o.hazard_type == HazardType.FLOOD_ALERT and o.value is not None:
        if o.value not in nws_alerts.FLOOD_EVENTS:
            return "unrecognized official flood event"
    if o.hazard_type in {HazardType.EARTHQUAKE, HazardType.HURRICANE}:
        if o.source in {"USGS", "NHC"} and o.source_ref and not _finite(o.value):
            return "regional event measurement missing"
    if o.hazard_type == HazardType.HURRICANE and o.source == "NHC" and o.value is not None:
        if not _finite(o.value) or o.value < 0 or o.unit != "kt":
            return "NHC storm intensity requires nonnegative knots"
    return None


def _heat(readings: list[Observation], now: datetime, settings: RuleSettings) -> FactorContribution:
    groups = defaultdict(list)
    for o in readings:
        if o.hazard_type in {HazardType.WEATHER, HazardType.FORECAST}:
            groups[
                (
                    o.hazard_type,
                    o.source,
                    o.source_ref,
                    o.lat,
                    o.lon,
                    o.observed_at,
                    o.valid_at,
                    o.simulated,
                )
            ].append(o)
    candidates = []
    for group in groups.values():
        usable = [o for o in group if o.data_state is not DataState.UNAVAILABLE]
        if usable and not usable[0].source_ref:
            # A direct published heat-index metric is usable; deriving one requires
            # a station/grid identity in addition to matching time and coordinates.
            usable = [o for o in usable if o.label == nws_weather.HEAT_INDEX]
        if not usable:
            continue
        state = (
            DataState.STALE
            if any(o.data_state is DataState.STALE for o in usable)
            else DataState.SIMULATED
            if any(o.data_state is DataState.SIMULATED for o in usable)
            else DataState.FORECAST
            if usable[0].hazard_type == HazardType.FORECAST
            else DataState.OBSERVED
        )
        candidate = heat_factor(
            [o.model_copy(update={"data_state": state}) for o in usable], now, settings
        )
        if candidate.data_state is not DataState.UNAVAILABLE and _finite(candidate.value):
            if candidate.data_state is DataState.STALE and any(o.simulated for o in usable):
                candidate = candidate.model_copy(
                    update={
                        "label": candidate.label + " (simulated replay inputs)",
                    }
                )
            if not any(o.label == nws_weather.HEAT_INDEX for o in usable):
                humidity = next(o for o in usable if o.label == nws_weather.RELATIVE_HUMIDITY)
                candidate = candidate.model_copy(
                    update={
                        "label": candidate.label
                        + "; derived from co-timed temperature and humidity"
                        f" (humidity evidence {humidity.id or humidity.source_ref};"
                        f" issue/observation {humidity.observed_at.isoformat()})",
                    }
                )
            candidates.append(candidate)
    if candidates:
        return _label_state(max(candidates, key=lambda f: (f.value, f.evidence_id or "", f.source)))
    unknown = heat_factor([], now, settings).model_copy(
        update={
            "label": (
                "Heat index unknown (no qualified direct metric or co-timed "
                "station/grid temperature-humidity pair)"
            ),
        }
    )
    return _explain_unknown(unknown, readings, {HazardType.WEATHER, HazardType.FORECAST})


def _label_state(factor: FactorContribution) -> FactorContribution:
    if factor.data_state in {DataState.STALE, DataState.SIMULATED}:
        return factor.model_copy(
            update={"label": f"{factor.label} [{factor.data_state.value}; not live coverage]"}
        )
    return factor


def _explain_unknown(
    factor: FactorContribution, readings: list[Observation], kinds: set[HazardType]
) -> FactorContribution:
    if (
        factor.data_state is DataState.STALE
        and factor.evidence_id
        and any(o.id == factor.evidence_id and o.simulated for o in readings)
    ):
        factor = factor.model_copy(update={"label": factor.label + " (simulated replay inputs)"})
    if factor.data_state is DataState.UNAVAILABLE:
        rejected = [
            o for o in readings if o.hazard_type in kinds and o.data_state is DataState.UNAVAILABLE
        ]
        if rejected:
            o = rejected[-1]
            factor = factor.model_copy(
                update={
                    "label": f"{factor.label}; {o.label or 'source unavailable'}",
                    "source": o.source,
                    "evidence_id": o.id,
                }
            )
    return _label_state(factor)


def lightning_factor(
    observations: list[Observation], alerts: list[Alert], settings: RuleSettings
) -> FactorContribution:
    active = [
        a
        for a in alerts
        if a.rule is AlertRule.LIGHTNING_STOP_WORK and a.state is AlertState.ACTIVE
    ]
    readings = [o for o in observations if o.hazard_type == HazardType.LIGHTNING_STRIKE]
    healthy = any(o.data_state in CURRENT_STATES for o in readings)
    if active:
        alert = max(active, key=lambda a: (a.latest_event_at, a.id))
        distance = (
            f", latest qualifying strike {alert.distance_miles:g} mi"
            if alert.distance_miles is not None
            else ""
        )
        return _label_state(
            FactorContribution(
                factor=LIGHTNING,
                label="Lightning stop-work active"
                + distance
                + ("; feed coverage unknown" if not healthy else ""),
                contribution=settings.lightning_stop_work_points,
                value=alert.distance_miles,
                unit="mi" if alert.distance_miles is not None else None,
                source="lightning-replay" if alert.simulated else "deterministic lightning alert",
                observed_at=alert.latest_event_at,
                data_state=DataState.SIMULATED if alert.simulated else DataState.OBSERVED,
                is_prototype=True,
                evidence_id=alert.id,
            )
        )
    usable = [o for o in readings if o.data_state is not DataState.UNAVAILABLE]
    latest = max(usable, key=lambda o: (o.observed_at, _key(o))) if usable else None
    state = latest.data_state if latest else DataState.UNAVAILABLE
    return _explain_unknown(
        FactorContribution(
            factor=LIGHTNING,
            label="No active lightning stop-work alert (not clearance)"
            if state in CURRENT_STATES | {DataState.SIMULATED}
            else "Lightning status unknown (feed stale or unavailable)",
            contribution=0.0,
            source=latest.source if latest else "lightning",
            observed_at=latest.observed_at if latest else None,
            data_state=state,
            is_prototype=True,
            evidence_id=latest.id if latest else None,
        ),
        readings,
        {HazardType.LIGHTNING_STRIKE},
    )


def report_factors(
    reports: list[CrewReport], settings: RuleSettings, site_id: str, now: datetime
) -> list[FactorContribution]:
    """Trusted confirmation only; bounded points, all independent IDs visible.

    Latest version per ID wins; equal timestamps prefer exclusion over confirmation.
    Shared notice IDs identify one hazard, unlike nearby/same-category reports.
    Highest reviewed severity gets credit first, then ID. No automatic expiry.
    """
    points = {
        Severity.LOW: settings.report_low_points,
        Severity.MODERATE: settings.report_moderate_points,
        Severity.HIGH: settings.report_high_points,
    }
    versions = {}
    for r in reports:
        if r.site_id != site_id or not _aware(r.created_at) or r.created_at > now:
            continue
        at = r.reviewed_at or r.created_at
        if not _aware(at) or at > now or at < r.created_at:
            continue
        key = (
            at,
            not (r.review_status is ReviewStatus.CONFIRMED and r.hazard_present),
            r.model_dump_json(),
        )
        if r.id not in versions or key > versions[r.id][0]:
            versions[r.id] = (key, r)
    eligible = [
        r
        for _, r in versions.values()
        if r.review_status is ReviewStatus.CONFIRMED and r.hazard_present
    ]
    eligible.sort(key=lambda r: (-points[r.confirmed_severity or Severity.MODERATE], r.id))
    used = defaultdict(float)
    notices = set()
    factors = []
    for r in eligible:
        severity = r.confirmed_severity or Severity.MODERATE
        category = r.confirmed_category or r.category
        credit = min(points[severity], max(0, settings.report_category_max_points - used[category]))
        duplicate = r.notice_id is not None and r.notice_id in notices
        if duplicate:
            credit = 0.0
        elif r.notice_id:
            notices.add(r.notice_id)
        used[category] += credit
        label = f"Confirmed crew report: {category.replace('_', ' ')}"
        if duplicate:
            label += " (shared notice already counted; evidence retained)"
        elif credit < points[severity]:
            label += (
                f" (prototype category cap {settings.report_category_max_points:g};"
                " evidence retained)"
            )
        if r.confirmed_severity is None:
            label += " (reviewed severity missing; legacy moderate weight)"
        factors.append(
            FactorContribution(
                factor=CREW_REPORT,
                label=label,
                contribution=credit,
                value=severity.value,
                source="crew report",
                observed_at=r.reviewed_at or r.created_at,
                data_state=DataState.CREW_REPORTED,
                is_prototype=True,
                evidence_id=r.id,
            )
        )
    return factors
