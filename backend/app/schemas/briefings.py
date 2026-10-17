from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import Evidence, FactorContribution, GeneratedBy, RiskLevel, Schema


class BriefingHazard(Schema):
    hazard: str
    risk_level: RiskLevel
    evidence_ids: list[str] = Field(min_length=1)


class RecommendedAction(Schema):
    action: str
    evidence_ids: list[str] = Field(min_length=1)


class BriefingRequest(Schema):
    """Body for `POST /api/sites/{id}/briefings`. `organization` is supervisor-only."""

    scope: Literal["site", "organization"] = "site"


class Briefing(Schema):
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


class Explanation(Schema):
    """Explains an already-computed score. Never changes the score or alert state.

    On fallback, `explanation` is null and the UI shows `top_factors` without prose.
    """

    site_id: str
    score_created_at: datetime
    explanation: str | None
    top_factors: list[FactorContribution]
    change_since_previous: str | None = None
    evidence: list[Evidence]
    unknowns: list[str]
    generated_by: GeneratedBy
    created_at: datetime
