"""Shared building blocks for the PlanIT Control API contract."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Schema(BaseModel):
    """Base for every contract model. Unknown fields are rejected so name drift fails loudly."""

    model_config = ConfigDict(extra="forbid")


class DataState(StrEnum):
    OBSERVED = "observed"
    FORECAST = "forecast"
    CREW_REPORTED = "crew_reported"
    SIMULATED = "simulated"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class RiskLevel(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class EvidenceKind(StrEnum):
    OBSERVATION = "observation"
    ALERT = "alert"
    REPORT = "report"
    SCORE_FACTOR = "score_factor"
    MODEL_OUTPUT = "model_output"
    NOTICE = "notice"


class GeneratedBy(StrEnum):
    """Who produced a piece of text. `fallback` is the deterministic template used when Gemini fails."""

    GEMINI = "gemini"
    FALLBACK = "fallback"


class Evidence(Schema):
    """A supplied input that generated text or an alert can cite by `id`."""

    id: str
    kind: EvidenceKind
    label: str
    observed_at: datetime | None = None


class FactorContribution(Schema):
    """One term of the final 0–10 score, with its source and freshness."""

    factor: str
    label: str
    contribution: float = Field(description="Points added to the 0–10 score.")
    value: float | str | None = None
    unit: str | None = None
    source: str
    observed_at: datetime | None = None
    data_state: DataState
    is_prototype: bool = Field(
        default=False, description="True when the threshold is a configurable prototype, not policy."
    )
    evidence_id: str | None = None
