from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from app.schemas.common import Evidence, GeneratedBy, Schema


class NoticeSource(StrEnum):
    FEED = "feed"
    CREW_REPORT = "crew_report"


class RadiusSource(StrEnum):
    GEMINI = "gemini"
    DEFAULT = "default"


class NoticeStatus(StrEnum):
    POTENTIAL = "potential"
    CONFIRMED = "confirmed"


class HazardNotice(Schema):
    """A "potential {hazard_label}" notice sent to teams and supervisors inside the radius.

    The potential notice carries no instruction. `instruction` is set only after a notified
    supervisor confirms the hazard and sends accepted or edited text.
    """

    id: str
    hazard_label: str
    source: NoticeSource
    source_ref: str = Field(description="Observation id or crew report id that raised the notice.")
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius_miles: float = Field(gt=0, le=50)
    radius_source: RadiusSource
    status: NoticeStatus
    created_at: datetime
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    suggested_instruction: str | None = None
    instruction: str | None = None
    instruction_sent_at: datetime | None = None
    evidence: list[Evidence] = []

    @model_validator(mode="after")
    def _potential_has_no_instruction(self) -> "HazardNotice":
        if self.status is NoticeStatus.POTENTIAL and (
            self.instruction is not None or self.suggested_instruction is not None
        ):
            raise ValueError("a potential notice must not carry an instruction")
        return self


class HazardConfirmResponse(Schema):
    """Response of `POST /api/hazards/{id}/confirm`. The request takes no body."""

    notice: HazardNotice
    suggested_instruction: str | None = Field(
        description="Gemini draft for the supervisor to edit. Null when Gemini fails; supervisor writes it."
    )
    generated_by: GeneratedBy | None = None


class InstructionSend(Schema):
    """Body for `POST /api/hazards/{id}/instruction`: the supervisor's final text."""

    instruction: str = Field(min_length=1, max_length=500)
