"""Supervisor confirmation (T054) and explicit instruction approval/send (T054A)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_now
from app.api.sites import DbSession
from app.gemini import GeminiClient, get_gemini_client
from app.schemas import HazardConfirmResponse, HazardNotice, InstructionSend
from app.security import CurrentUser, require_permission, require_role, roles
from app.services.hazards import confirm_hazard
from app.services.instructions import draft_instruction, send_instruction

router = APIRouter(prefix="/api/hazards", tags=["hazards"])
Confirmer = Annotated[CurrentUser, Depends(require_permission(roles.CONFIRM_HAZARDS))]
Now = Annotated[datetime, Depends(get_now)]
Gemini = Annotated[GeminiClient, Depends(get_gemini_client)]
Sender = Annotated[CurrentUser, Depends(require_permission(roles.SEND_INSTRUCTIONS))]


@router.post(
    "/{notice_id}/confirm",
    response_model=HazardConfirmResponse,
    dependencies=[Depends(require_role("supervisor"))],
)
def confirm_notice(notice_id: str, user: Confirmer, session: DbSession, now: Now, client: Gemini):
    notice = confirm_hazard(session, notice_id, user, now)
    generated_by = draft_instruction(session, notice, client, now)
    return HazardConfirmResponse(
        notice=HazardNotice.model_validate(notice, from_attributes=True),
        suggested_instruction=notice.suggested_instruction,
        generated_by=generated_by,
    )


@router.post(
    "/{notice_id}/instruction",
    response_model=HazardNotice,
    dependencies=[Depends(require_role("supervisor"))],
)
def instruct(
    notice_id: str, body: InstructionSend, user: Sender, session: DbSession, now: Now
) -> HazardNotice:
    notice = send_instruction(session, notice_id, body.instruction, user, now)
    return HazardNotice.model_validate(notice, from_attributes=True)
