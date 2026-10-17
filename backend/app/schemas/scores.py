from datetime import datetime

from pydantic import Field

from app.schemas.common import FactorContribution, RiskLevel, Schema


class ModelDataQuality(Schema):
    completeness: float = Field(ge=0, le=1)
    missing_features: list[str] = []
    is_fallback: bool = Field(
        default=False, description="True when the model artifact or required features were missing."
    )
    notes: list[str] = []


class ModelOutput(Schema):
    """Return shape of Cache's `predict_site(features)` in ml/."""

    hazard_probabilities: dict[str, float] = Field(description="Hazard name -> probability (0–1).")
    model_component_0_10: float = Field(ge=0, le=10)
    factor_contributions: dict[str, float] = Field(description="Feature name -> contribution.")
    confidence: float = Field(ge=0, le=1)
    model_version: str
    data_quality: ModelDataQuality


class HazardScore(Schema):
    """Final displayed score: model output plus deterministic factors plus confirmed reports."""

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
