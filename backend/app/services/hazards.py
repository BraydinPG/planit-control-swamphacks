"""T054 human review and T055 atomic score refresh for confirmed present reports.

Each organization inside a notice's radius assesses it for itself (`NoticeAssessment`).
"""

import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import models as db
from app.schemas import NoticeSource, NoticeStatus, ReportReview, ReviewStatus
from app.security import CurrentUser, membership_for
from app.services.alerts import audit
from app.services.notice_views import adopt_legacy
from app.services.scoring import score_site


def assessing_organization(session: Session, user: CurrentUser) -> str:
    """The organization a supervisor assesses hazards for."""
    membership = membership_for(session, user)
    if membership is None or membership.role != "supervisor":
        raise HTTPException(403, "Your account is not linked to an organization")
    return membership.organization_id


def confirm_hazard(
    session: Session, notice_id: str, user: CurrentUser, now: datetime
) -> tuple[db.HazardNotice, db.NoticeAssessment]:
    """Confirm a received notice for the caller's own organization.

    Each organization inside the radius confirms separately. Only the reporting
    organization's confirmation also confirms the crew report and rescores its site.
    """
    notice = session.get(db.HazardNotice, notice_id)
    if notice is None:
        raise HTTPException(404, "Hazard notice not found")
    receipt = session.scalar(
        select(db.AuditEvent.id).where(
            db.AuditEvent.actor == "system:notices",
            db.AuditEvent.action == "notice.supervisor.deliver",
            db.AuditEvent.entity == f"{notice.id}->{user.sub}",
        )
    )
    if receipt is None:
        raise HTTPException(403, "You did not receive this hazard notice")
    organization_id = assessing_organization(session, user)
    adopt_legacy(session, notice_id)

    # The (notice, organization) key lets exactly one supervisor per organization confirm,
    # even across concurrent transactions.
    assessment = db.NoticeAssessment(
        notice_id=notice_id,
        organization_id=organization_id,
        confirmed_by=user.sub,
        confirmed_at=now,
    )
    session.add(assessment)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "Your organization has already confirmed this hazard") from None
    # The notice records the first confirmation anywhere; a later one leaves it unchanged.
    session.execute(
        update(db.HazardNotice)
        .where(db.HazardNotice.id == notice_id, db.HazardNotice.confirmed_by.is_(None))
        .values(status=NoticeStatus.CONFIRMED, confirmed_by=user.sub, confirmed_at=now)
        .execution_options(synchronize_session=False)
    )

    if notice.source == NoticeSource.CREW_REPORT:
        report = session.get(db.CrewReport, notice.source_ref)
        if report is None or not report.hazard_present or report.notice_id != notice_id:
            session.rollback()
            raise HTTPException(409, "The notice has no matching present report")
        if report.organization_id == organization_id:
            reviewed = session.execute(
                update(db.CrewReport)
                .where(
                    db.CrewReport.id == report.id,
                    db.CrewReport.review_status == ReviewStatus.PENDING,
                )
                .values(
                    review_status=ReviewStatus.CONFIRMED,
                    reviewed_by=user.sub,
                    reviewed_at=now,
                    confirmed_category=report.category,
                )
                .execution_options(synchronize_session=False)
            )
            if reviewed.rowcount != 1:
                session.rollback()
                raise HTTPException(409, "The linked report has already been reviewed")
            # Bulk updates bypass the identity map; refresh before the scoring query reads it.
            session.expire(report)
            score_site(session, report.site_id, now, commit=False)
            audit(session, user.sub, "score.refresh.confirmed_report", report.id, now)
            audit(session, user.sub, "report.confirm", report.id, now)
    audit(session, user.sub, "notice.confirm", notice_id, now)
    session.commit()
    session.refresh(notice)
    session.refresh(assessment)
    return notice, assessment


def review_absent_report(
    session: Session, report_id: str, review: ReportReview, user: CurrentUser, now: datetime
) -> db.CrewReport:
    report = session.get(db.CrewReport, report_id)
    if report is None:
        raise HTTPException(404, "Report not found")
    membership = membership_for(session, user)
    if membership is None or membership.organization_id != report.organization_id:
        raise HTTPException(
            403, "Only the reporting organization's supervisor may review this report"
        )
    if report.hazard_present:
        raise HTTPException(409, "Confirm present hazards through their notice")
    accepted = review.decision == ReviewStatus.CONFIRMED
    changed = session.execute(
        update(db.CrewReport)
        .where(db.CrewReport.id == report_id, db.CrewReport.review_status == ReviewStatus.PENDING)
        .values(
            review_status=review.decision,
            reviewed_by=user.sub,
            reviewed_at=now,
            confirmed_category=(review.category or report.category) if accepted else None,
            confirmed_severity=review.severity if accepted else None,
        )
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        session.rollback()
        raise HTTPException(409, "This report has already been reviewed")
    audit(session, user.sub, f"report.review.{review.decision}", report_id, now)
    if review.note:
        audit(
            session,
            user.sub,
            "report.review.note",
            json.dumps({"report_id": report_id, "note": review.note}),
            now,
        )
    session.commit()
    session.refresh(report)
    return report
