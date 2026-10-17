"""Final 0–10 site hazard score (T051).

Score = the sum of these factor contributions, capped at 10:

| Factor | Points (prototype weights in `RuleSettings`) |
|---|---|
| Lightning stop-work alert active | `lightning_stop_work_points` (3.0) |
| Heat index (T049) | 0, or 0.5–2.0 at or above the 103 °F prototype threshold |
| Flood alert (T049) | Warning 2.0, Watch 1.0, none 0 |
| Confirmed crew report, hazard present (each) | low 0.5, moderate 1.0, high 1.5 |
| Hurricane (T049A, P1) | `hurricane_points` (2.0) for a warning or a storm within 50 mi |
| Earthquake (T049A, P1) | `earthquake_points` (1.5) for M4.0+ within 25 mi |

Risk level bands: below 3 low, below 6 moderate, below 8 high, 8 or more critical.

Excluded:
- Cache's model component. The contract keeps the conditional active-event outlook out of
  the score until its meaning is approved.
- Pending, rejected, and "hazard absent" reports. Potential notices also don't count.

Missing data:
- Unknown inputs never count as zero risk silently. Each one appears as a factor with
  `data_state` stale or unavailable, and lowers `data_completeness`.
- `data_completeness` is the share of expected inputs (heat, flood, lightning) with a
  current reading. Stale and unavailable readings don't count as current.
- Hurricane and earthquake factors appear only when those P1 feeds have reported, and
  don't count toward `data_completeness`. NHC storm distance needs `site`; see
  `app.rules.regional`.
- `confidence` equals `data_completeness`. The rules have no calibrated confidence.
"""

from datetime import datetime

from app.ingestion.base import SiteLike
from app.rules.factors import flood_factor, heat_factor
from app.rules.lightning import feed_is_healthy
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

MODEL_VERSION = "rules-0.1"
MAX_SCORE = 10.0
LIGHTNING = "lightning"
CREW_REPORT = "crew_report"
CURRENT_STATES = frozenset({DataState.OBSERVED, DataState.FORECAST, DataState.SIMULATED})


def risk_level(score: float) -> RiskLevel:
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
    settings = settings or get_rule_settings()
    heat = heat_factor(observations, now, settings)
    flood = flood_factor(observations, settings)
    lightning = lightning_factor(observations, alerts, settings)
    factors = [lightning, heat, flood, *report_factors(reports, settings)]
    factors += [
        f
        for f in (
            hurricane_factor(site, observations, settings),
            earthquake_factor(site, observations, settings),
        )
        if f
    ]

    expected = (heat, flood, lightning)
    completeness = sum(f.data_state in CURRENT_STATES for f in expected) / len(expected)
    total = round(min(MAX_SCORE, sum(f.contribution for f in factors)), 1)
    return HazardScore(
        site_id=site_id,
        risk_score=total,
        risk_level=risk_level(total),
        factor_contributions=factors,
        model_version=MODEL_VERSION,
        model_is_fallback=False,
        confidence=round(completeness, 2),
        data_completeness=round(completeness, 2),
        previous_score=previous.risk_score if previous else None,
        created_at=now,
    )


def lightning_factor(
    observations: list[Observation], alerts: list[Alert], settings: RuleSettings
) -> FactorContribution:
    active = [
        a
        for a in alerts
        if a.rule is AlertRule.LIGHTNING_STOP_WORK and a.state is AlertState.ACTIVE
    ]
    if active:
        alert = max(active, key=lambda a: a.latest_event_at)
        return FactorContribution(
            factor=LIGHTNING,
            label=(
                f"Lightning stop-work active, nearest strike {alert.distance_miles:g} mi"
                + (" (simulated replay)" if alert.simulated else "")
            ),
            contribution=settings.lightning_stop_work_points,
            value=alert.distance_miles,
            unit="mi",
            source="lightning-replay" if alert.simulated else "GOES GLM",
            observed_at=alert.latest_event_at,
            data_state=DataState.SIMULATED if alert.simulated else DataState.OBSERVED,
            is_prototype=True,
            evidence_id=alert.id,
        )
    readings = [o for o in observations if o.hazard_type == HazardType.LIGHTNING_STRIKE]
    if not readings or not feed_is_healthy(observations):
        return FactorContribution(
            factor=LIGHTNING,
            label="Lightning status unknown (feed stale or unavailable)",
            contribution=0.0,
            source="lightning",
            data_state=(
                DataState.STALE
                if any(o.data_state is not DataState.UNAVAILABLE for o in readings)
                else DataState.UNAVAILABLE
            ),
            is_prototype=True,
        )
    latest = max(readings, key=lambda o: o.observed_at)
    return FactorContribution(
        factor=LIGHTNING,
        label="No lightning stop-work alert",
        contribution=0.0,
        source=latest.source,
        observed_at=latest.observed_at,
        data_state=latest.data_state,
        is_prototype=True,
        evidence_id=latest.id,
    )


def report_factors(reports: list[CrewReport], settings: RuleSettings) -> list[FactorContribution]:
    """Only confirmed reports that say the hazard is present add points."""
    points = {
        Severity.LOW: settings.report_low_points,
        Severity.MODERATE: settings.report_moderate_points,
        Severity.HIGH: settings.report_high_points,
    }
    return [
        FactorContribution(
            factor=CREW_REPORT,
            label=f"Confirmed crew report: {_category(r)}",
            contribution=points[r.confirmed_severity or Severity.MODERATE],
            value=(r.confirmed_severity or Severity.MODERATE).value,
            source="crew report",
            observed_at=r.reviewed_at or r.created_at,
            data_state=DataState.CREW_REPORTED,
            is_prototype=True,
            evidence_id=r.id,
        )
        for r in reports
        if r.review_status is ReviewStatus.CONFIRMED and r.hazard_present
    ]


def _category(report: CrewReport) -> str:
    return (report.confirmed_category or report.category).replace("_", " ")
