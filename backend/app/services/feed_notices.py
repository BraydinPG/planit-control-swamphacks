"""Potential-hazard notices from source detections (T049A).

A qualifying hurricane or earthquake reading (`app.rules.regional`) sends one
"potential {hazard}" notice with no instruction, like a crew report marked present
(T053). Instructions come only after a notified supervisor confirms (T054/T054A).

- Radius: Braydin's Gemini radius function when it answers with a positive radius up to
  50 miles, otherwise the spec.md section 5 default (hurricane 50 mi, earthquake 25 mi),
  stored with `radius_source="default"`. These are prototype distances.
- Center: the storm center or epicenter for NHC and USGS readings, the site for an NWS
  warning issued for the site point.
- One notice per event: a hurricane per storm or warning and site, an earthquake per
  USGS event. A later refresh of the same event sends nothing new.
- Only fresh readings send notices. Stale and unavailable readings never do.

Recipients and delivery auditing reuse `app.services.reports`.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as db
from app.ingestion.base import SiteLike
from app.rules.regional import (
    EARTHQUAKE,
    HURRICANE,
    Detection,
    earthquake_detections,
    hurricane_detections,
)
from app.rules.settings import RuleSettings, get_rule_settings
from app.schemas import (
    DataState,
    Evidence,
    EvidenceKind,
    NoticeSource,
    NoticeStatus,
    Observation,
    RadiusSource,
)
from app.services.alerts import audit
from app.services.reports import MAX_RADIUS_MILES, Recipients, notice_recipients

RULE_ACTOR = "system:rules"

# spec.md section 5 defaults (prototype distances, not official policy).
DEFAULT_RADIUS_MILES = {HURRICANE: 50.0, EARTHQUAKE: 25.0}
FRESH_STATES = frozenset({DataState.OBSERVED, DataState.FORECAST, DataState.SIMULATED})


def send_feed_notices(
    session: Session,
    site: SiteLike,
    observations: list[Observation],
    now: datetime,
    settings: RuleSettings | None = None,
) -> list[tuple[db.HazardNotice, Recipients]]:
    """Create notices for new qualifying readings at one site. Returns what was sent."""
    settings = settings or get_rule_settings()
    detections = hurricane_detections(site, observations, settings) + earthquake_detections(
        site, observations, settings
    )
    sent: list[tuple[db.HazardNotice, Recipients]] = []
    for detection in detections:
        if detection.observation.data_state not in FRESH_STATES:
            continue
        if _already_sent(session, detection.key):
            continue
        notice = _notice(detection, now)
        session.add(notice)
        session.flush()
        recipients = notice_recipients(session, notice)
        audit(session, RULE_ACTOR, "notice.create", notice.id, now)
        for team_id in recipients.team_ids:
            audit(session, RULE_ACTOR, "notice.deliver", f"{notice.id}->{team_id}", now)
        for supervisor_id in recipients.supervisor_ids:
            # T054 checks receipt-time authority, not today's team assignments.
            audit(
                session,
                "system:notices",
                "notice.supervisor.deliver",
                f"{notice.id}->{supervisor_id}",
                now,
            )
        sent.append((notice, recipients))
    session.commit()
    return sent


def notice_radius(detection: Detection) -> tuple[float, RadiusSource]:
    """Gemini's radius when available and valid, else the hazard's labeled default."""
    suggested = _gemini_radius(detection)
    if suggested is not None and 0 < suggested <= MAX_RADIUS_MILES:
        return float(suggested), RadiusSource.GEMINI
    return DEFAULT_RADIUS_MILES[detection.hazard], RadiusSource.DEFAULT


def _notice(detection: Detection, now: datetime) -> db.HazardNotice:
    o = detection.observation
    radius, source = notice_radius(detection)
    return db.HazardNotice(
        id=f"notice:{uuid4().hex}",
        hazard_label=detection.hazard_label,
        source=NoticeSource.FEED,
        source_ref=detection.key,
        lat=detection.lat,
        lon=detection.lon,
        radius_miles=radius,
        radius_source=source,
        status=NoticeStatus.POTENTIAL,
        created_at=now,
        evidence=[
            Evidence(
                id=o.id or detection.key,
                kind=EvidenceKind.OBSERVATION,
                label=f"{o.source}: {o.label or o.value}",
                observed_at=o.observed_at,
            ).model_dump(mode="json")
        ],
    )


def _already_sent(session: Session, key: str) -> bool:
    return (
        session.scalars(
            select(db.HazardNotice.id).where(
                db.HazardNotice.source == NoticeSource.FEED, db.HazardNotice.source_ref == key
            )
        ).first()
        is not None
    )


def _gemini_radius(detection: Detection) -> float | None:
    """Braydin's `suggest_notice_radius`, same contract as `app.services.reports`."""
    try:
        from app import gemini

        suggest = getattr(gemini, "suggest_notice_radius", None)
        if suggest is None:
            return None
        o = detection.observation
        value = suggest(detection.hazard_label, detection.lat, detection.lon, o.source, [o.id])
        return float(value) if isinstance(value, int | float) else None
    except Exception:
        return None
