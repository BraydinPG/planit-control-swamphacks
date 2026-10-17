from datetime import datetime

from pydantic import Field

from app.schemas.common import Evidence, GeneratedBy, RiskLevel, Schema


class BriefingHazard(Schema):
    hazard: str
    risk_level: RiskLevel
    evidence_ids: list[str] = Field(min_length=1)


class RecommendedAction(Schema):
    action: str
    evidence_ids: list[str] = Field(min_length=1)


class Briefing(Schema):
    """Next-day briefing, generated at 6 PM site-local time and stored (spec.md section 6).

    `risk_level` is the site's computed score level at generation time, never Gemini's.
    """

    id: str
    site_id: str | None = None
    organization_id: str | None = None
    forecast_window_start: datetime
    forecast_window_end: datetime
    summary: str
    risk_level: RiskLevel
    hazards: list[BriefingHazard]
    recommended_actions: list[RecommendedAction]
    evidence: list[Evidence]
    unknowns: list[str]
    generated_by: GeneratedBy
    created_at: datetime
