from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import FactorContribution, RiskLevel, Schema


class ModelDataQuality(Schema):
    """Conditional-event compatibility metadata; never an approved score term."""

    completeness: float | None = Field(default=None, ge=0, le=1)
    missing_features: list[str] = []
    is_fallback: bool = Field(
        default=False, description="True when the model artifact or required features were missing."
    )
    notes: list[str] = []
    status: Literal["not_approved_for_score"] = "not_approved_for_score"
    prediction_scope: Literal["conditional_on_confirmed_active_event"] = (
        "conditional_on_confirmed_active_event"
    )
    event_type: str | None = None
    event_status: str | None = None
    as_of_utc: datetime | None = None
    include_model_component_in_site_score: Literal[False] = False
    confidence_status: Literal["not_calibrated"] = "not_calibrated"
    outlook_status: Literal["ok", "unavailable", "not_applicable_no_confirmed_event"] = (
        "unavailable"
    )
    evidence_quality: str | None = None


class ModelOutput(Schema):
    """Cache's compatibility shape. Conditional persistence is excluded from scores."""

    hazard_probabilities: dict[str, float] = Field(
        description="Explicit active_event_persists_* probabilities; never event onset."
    )
    model_component_0_10: float = Field(ge=0, le=10)
    factor_contributions: dict[str, float] | list[FactorContribution] = Field(
        description="No approved ML score factors; compatibility returns an empty list."
    )
    confidence: float | None = Field(
        ge=0, le=1, description="Null when individual prediction confidence is not calibrated."
    )
    model_version: str
    data_quality: ModelDataQuality


class HazardScore(Schema):
    """Final deterministic/confirmed-report score; unapproved ML terms are excluded."""

    site_id: str
    risk_score: float = Field(ge=0, le=10)
    risk_level: RiskLevel
    factor_contributions: list[FactorContribution]
    model_version: str
    model_is_fallback: bool
    confidence: float = Field(ge=0, le=1)
    data_completeness: float = Field(ge=0, le=1)
    previous_score: float | None = Field(default=None, ge=0, le=10)
    created_at: datetime
