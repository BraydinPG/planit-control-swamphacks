"""T054A: obtain an unsent draft and deliver only the confirming supervisor's final text.

Each organization confirms and instructs separately (`NoticeAssessment`): a supervisor's
instruction reaches only their own organization's teams inside the stored radius.
"""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from app import gemini
from app.db import models as db
from app.gemini.outlooks import notice_outlook
from app.outlook import EventOutlookService
from app.schemas import GeneratedBy
from app.security import CurrentUser
from app.services.alerts import audit
from app.services.hazards import assessing_organization
from app.services.notice_views import adopt_legacy
from app.services.reports import notice_team_organizations


def draft_instruction(
    session: Session,
    notice: db.HazardNotice,
    assessment: db.NoticeAssessment,
    client: gemini.GeminiClient,
    now: datetime,
    outlooks: EventOutlookService | None = None,
) -> GeneratedBy | None:
    """Called only after confirmation has committed; failure never undoes confirmation.

    With `outlooks`, a confirmed event's expected duration is offered to the draft (T058B).
    """
    outlook = notice_outlook(session, notice, now, outlooks) if outlooks else None
    result = gemini.suggest_confirmed_instruction(
        hazard_label=notice.hazard_label,
        radius_miles=notice.radius_miles,
        source=notice.source,
        evidence=notice.evidence or [],
        client=client,
        outlook=outlook,
    )
    if not result.ok:
        return None
    changed = session.execute(
        update(db.NoticeAssessment)
        .where(
            db.NoticeAssessment.notice_id == assessment.notice_id,
            db.NoticeAssessment.organization_id == assessment.organization_id,
            db.NoticeAssessment.confirmed_by == assessment.confirmed_by,
            db.NoticeAssessment.instruction_sent_at.is_(None),
        )
        .values(suggested_instruction=result.value.suggested_instruction)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        session.rollback()
        session.refresh(assessment)
        return None
    audit(
        session,
        "gemini:instructions",
        "notice.instruction.suggest",
        f"{notice.id}@{assessment.organization_id}",
        now,
    )
    session.commit()
    session.refresh(assessment)
    return GeneratedBy.GEMINI


def send_instruction(
    session: Session, notice_id: str, instruction: str, user: CurrentUser, now: datetime
) -> tuple[db.HazardNotice, db.NoticeAssessment]:
    notice = session.get(db.HazardNotice, notice_id)
    if notice is None:
        raise HTTPException(404, "Hazard notice not found")
    organization_id = assessing_organization(session, user)
    adopt_legacy(session, notice_id)
    assessment = session.get(db.NoticeAssessment, (notice_id, organization_id))
    if assessment is None:
        raise HTTPException(409, "Confirm the hazard before sending an instruction")
    if assessment.confirmed_by != user.sub:
        raise HTTPException(403, "Only the confirming supervisor may send the instruction")
    text = instruction.strip()
    if not text or len(text) > 500:
        raise HTTPException(422, "Instruction must contain 1 to 500 non-blank characters")
    changed = session.execute(
        update(db.NoticeAssessment)
        .where(
            db.NoticeAssessment.notice_id == notice_id,
            db.NoticeAssessment.organization_id == organization_id,
            db.NoticeAssessment.confirmed_by == user.sub,
            db.NoticeAssessment.instruction_sent_at.is_(None),
        )
        .values(instruction=text, instruction_sent_at=now)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        session.rollback()
        raise HTTPException(409, "Your organization has already sent an instruction")
    # Reuse the stored geometry/radius; Gemini is not called again to select recipients.
    own_teams = sorted(
        team_id
        for team_id, team_org in notice_team_organizations(session, notice)
        if team_org == organization_id
    )
    audit(session, user.sub, "notice.instruction.send", notice.id, now)
    for team_id in own_teams:
        audit(session, user.sub, "notice.instruction.deliver", f"{notice.id}->{team_id}", now)
    session.commit()
    session.refresh(notice)
    session.refresh(assessment)
    return notice, assessment
