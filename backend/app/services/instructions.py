"""T054A: obtain an unsent draft and deliver only the confirming supervisor's final text."""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from app import gemini
from app.db import models as db
from app.schemas import GeneratedBy, NoticeStatus
from app.security import CurrentUser
from app.services.alerts import audit
from app.services.reports import notice_recipients


def draft_instruction(
    session: Session, notice: db.HazardNotice, client: gemini.GeminiClient, now: datetime
) -> GeneratedBy | None:
    """Called only after confirmation has committed; failure never undoes confirmation."""
    if notice.status != NoticeStatus.CONFIRMED or not notice.confirmed_by:
        return None
    result = gemini.suggest_confirmed_instruction(
        hazard_label=notice.hazard_label,
        radius_miles=notice.radius_miles,
        source=notice.source,
        evidence=notice.evidence or [],
        client=client,
    )
    if not result.ok:
        return None
    changed = session.execute(
        update(db.HazardNotice)
        .where(
            db.HazardNotice.id == notice.id,
            db.HazardNotice.status == NoticeStatus.CONFIRMED,
            db.HazardNotice.confirmed_by == notice.confirmed_by,
            db.HazardNotice.instruction_sent_at.is_(None),
        )
        .values(suggested_instruction=result.value.suggested_instruction)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        session.rollback()
        session.refresh(notice)
        return None
    audit(session, "gemini:instructions", "notice.instruction.suggest", notice.id, now)
    session.commit()
    session.refresh(notice)
    return GeneratedBy.GEMINI


def send_instruction(
    session: Session, notice_id: str, instruction: str, user: CurrentUser, now: datetime
) -> db.HazardNotice:
    notice = session.get(db.HazardNotice, notice_id)
    if notice is None:
        raise HTTPException(404, "Hazard notice not found")
    if notice.status != NoticeStatus.CONFIRMED:
        raise HTTPException(409, "Confirm the hazard before sending an instruction")
    if notice.confirmed_by != user.sub:
        raise HTTPException(403, "Only the confirming supervisor may send the instruction")
    text = instruction.strip()
    if not text or len(text) > 500:
        raise HTTPException(422, "Instruction must contain 1 to 500 non-blank characters")
    changed = session.execute(
        update(db.HazardNotice)
        .where(
            db.HazardNotice.id == notice_id,
            db.HazardNotice.status == NoticeStatus.CONFIRMED,
            db.HazardNotice.confirmed_by == user.sub,
            db.HazardNotice.instruction_sent_at.is_(None),
        )
        .values(instruction=text, instruction_sent_at=now)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        session.rollback()
        raise HTTPException(409, "An instruction has already been sent for this hazard")
    # Reuse the stored geometry/radius; Gemini is not called again to select recipients.
    recipients = notice_recipients(session, notice)
    audit(session, user.sub, "notice.instruction.send", notice.id, now)
    for team_id in recipients.team_ids:
        audit(session, user.sub, "notice.instruction.deliver", f"{notice.id}->{team_id}", now)
    session.commit()
    session.refresh(notice)
    return notice
