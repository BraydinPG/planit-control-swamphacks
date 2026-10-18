"""How one organization sees a hazard notice (each organization assesses for itself)."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as db
from app.schemas import HazardNotice, NoticeStatus


def assessment_for(
    session: Session, notice_id: str, organization_id: str | None
) -> db.NoticeAssessment | None:
    """The organization's assessment, or, for a notice confirmed before per-organization
    assessments existed (no assessment rows at all), its original confirmation for
    everyone. The legacy stand-in is never added to the session.
    """
    if organization_id is not None:
        found = session.get(db.NoticeAssessment, (notice_id, organization_id))
        if found is not None:
            return found
    return legacy_assessment(session, notice_id)


def legacy_assessment(session: Session, notice_id: str) -> db.NoticeAssessment | None:
    notice = session.get(db.HazardNotice, notice_id)
    if notice is None or notice.status != NoticeStatus.CONFIRMED or not notice.confirmed_by:
        return None
    has_rows = session.scalar(
        select(db.NoticeAssessment.notice_id).where(db.NoticeAssessment.notice_id == notice_id)
    )
    if has_rows is not None:
        return None
    return db.NoticeAssessment(
        notice_id=notice.id,
        organization_id="",
        confirmed_by=notice.confirmed_by,
        confirmed_at=notice.confirmed_at or notice.created_at,
        suggested_instruction=notice.suggested_instruction,
        instruction=notice.instruction,
        instruction_sent_at=notice.instruction_sent_at,
    )


def notice_view(
    notice: db.HazardNotice, assessment: db.NoticeAssessment | None, viewer_sub: str | None
) -> HazardNotice:
    """The notice as one organization sees it: potential until that organization confirms.

    Another organization's confirmation or instruction never shows here. The unsent draft
    is visible only to the supervisor who confirmed it.
    """
    confirmed = assessment is not None
    return HazardNotice(
        id=notice.id,
        hazard_label=notice.hazard_label,
        source=notice.source,
        source_ref=notice.source_ref,
        lat=notice.lat,
        lon=notice.lon,
        radius_miles=notice.radius_miles,
        radius_source=notice.radius_source,
        status=NoticeStatus.CONFIRMED if confirmed else NoticeStatus.POTENTIAL,
        created_at=_aware(notice.created_at),
        confirmed_by=assessment.confirmed_by if confirmed else None,
        confirmed_at=_aware(assessment.confirmed_at) if confirmed else None,
        suggested_instruction=(
            assessment.suggested_instruction
            if confirmed and viewer_sub == assessment.confirmed_by
            else None
        ),
        instruction=assessment.instruction if confirmed else None,
        instruction_sent_at=(
            _aware(assessment.instruction_sent_at)
            if confirmed and assessment.instruction_sent_at
            else None
        ),
        evidence=notice.evidence or [],
    )


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def adopt_legacy(session: Session, notice_id: str) -> None:
    """Before the first per-organization write, store an older notice's confirmation as its
    confirmer's organization's assessment, so a second organization can't erase it."""
    legacy = legacy_assessment(session, notice_id)
    if legacy is None:
        return
    organization_id = session.scalar(
        select(db.Membership.organization_id).where(db.Membership.user_id == legacy.confirmed_by)
    )
    if organization_id is None:
        return
    legacy.organization_id = organization_id
    session.add(legacy)
    session.flush()
