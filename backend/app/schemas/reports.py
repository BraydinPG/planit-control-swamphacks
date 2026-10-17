from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from app.schemas.common import GeneratedBy, Schema


class ReportCategory(StrEnum):
    """Crew-reported hazards. Broken poles and on-site fires have no feed; reports are the only source."""

    BROKEN_POLE_DOWNED_LINE = "broken_pole_downed_line"
    ON_SITE_FIRE = "on_site_fire"
    WILDLIFE = "wildlife"
    FLOODING = "flooding"
    OTHER = "other"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class Severity(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class ReportEnrichment(Schema):
    """Gemini's suggestion for a report. Always pending human review; never affects the score."""

    suggested_category: ReportCategory
    description: str
    severity_suggestion: Severity
    confidence: float = Field(ge=0, le=1)
    visible_evidence: list[str] = []
    needs_review: Literal[True] = True
    generated_by: GeneratedBy


class CrewReport(Schema):
    id: str
    organization_id: str
    team_id: str
    site_id: str
    reporter_id: str
    category: ReportCategory
    hazard_present: bool
    note: str | None = None
    photo_url: str | None = None
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    review_status: ReviewStatus
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    confirmed_category: ReportCategory | None = None
    confirmed_severity: Severity | None = None
    enrichment: ReportEnrichment | None = None
    notice_id: str | None = Field(
        default=None, description="Potential-hazard notice created when hazard_present is true."
    )
    created_at: datetime


class ReportCreate(Schema):
    """Form fields for `POST /api/reports` (multipart). The photo is sent as the `photo` file part."""

    site_id: str
    category: ReportCategory
    hazard_present: bool
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    note: str | None = Field(default=None, max_length=1000)


class ReportReview(Schema):
    """Body for `POST /api/reports/{id}/review`."""

    decision: Literal["confirmed", "rejected"]
    category: ReportCategory | None = None
    severity: Severity | None = None
    note: str | None = Field(default=None, max_length=1000)
