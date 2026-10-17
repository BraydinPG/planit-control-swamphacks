from datetime import datetime

from pydantic import Field

from app.schemas.common import Evidence, GeneratedBy, RiskLevel, Schema


class BriefingHazard(Schema):
    hazard: str
    points: float | None = Field(
        description="Points this hazard adds to the site's 0–10 index, from the deterministic "
        "score. Null when none of its evidence is a score factor, e.g. a forecast. Never "
        "Gemini's."
    )
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
    risk_score: float | None = Field(
        default=None,
        ge=0,
        le=10,
        description="The site's 0–10 hazard index when the briefing was generated. Null for "
        "briefings stored before it was recorded.",
    )
    data_completeness: float | None = Field(default=None, ge=0, le=1)
    hazards: list[BriefingHazard]
    recommended_actions: list[RecommendedAction]
    evidence: list[Evidence]
    unknowns: list[str]
    generated_by: GeneratedBy
    created_at: datetime
