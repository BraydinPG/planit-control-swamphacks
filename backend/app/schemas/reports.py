from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from app.schemas.common import Evidence, GeneratedBy, Schema


class ReportCategory(StrEnum):
    """Crew-reported hazards.

    Broken poles and on-site fires have no feed; crew reports are the only source.
    """

    BROKEN_POLE_DOWNED_LINE = "broken_pole_downed_line"
    ON_SITE_FIRE = "on_site_fire"
    ACCESS_MAT_DETERIORATION = "access_mat_deterioration"
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


class LocationSource(StrEnum):
    """Where a report's coordinates came from (T053A)."""

    DEVICE = "device"  # browser geolocation, only with the crew member's permission
    SITE = "site"  # the site's own coordinates: approximate
    PIN = "pin"  # a point the crew member placed on the map


class MatCondition(StrEnum):
    """The crew's A-D grade for an access mat report (T034B). D means unusable.

    No approved grading rubric exists, so the letters carry no thresholds. Grade A is
    recorded as no hazard present; B, C and D as hazard present.
    """

    A = "A"
    B = "B"
    C = "C"
    D = "D"


class AnalysisVerdict(StrEnum):
    """Whether the supplied data backs up the crew member's report."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    INCONCLUSIVE = "inconclusive"


class AnalysisPoint(Schema):
    """One reason for the verdict, citing the ids of the evidence it rests on."""

    statement: str
    evidence_ids: list[str] = Field(
        description='The "id" values of the supplied evidence, e.g. "photo" or "crew:note".'
    )


class ReportEnrichment(Schema):
    """Gemini's side-panel analysis of a crew report (T060; spec.md section 6).

    Gemini reads the photo, the crew member's category, present-or-absent answer, and
    note, and the site's current data, then says whether that data supports or
    contradicts the report, and why. It is a labeled suggestion for the supervisor: it
    never changes the report, its review state, or the score. `evidence` lists what
    Gemini was given, so each cited id can be shown with its label. `status="unavailable"`
    means the analysis failed and the report stands without it.
    """

    status: Literal["complete", "unavailable"]
    verdict: AnalysisVerdict | None = None
    summary: str | None = None
    supporting: list[AnalysisPoint] = []
    contradicting: list[AnalysisPoint] = []
    also_visible: list[str] = Field(
        default=[], description="Hazards in the photo that the crew member did not report."
    )
    suggested_category: ReportCategory | None = None
    severity_suggestion: Severity | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    unknowns: list[str] = []
    evidence: list[Evidence] = []
    unavailable_reason: str | None = None
    needs_review: Literal[True] = True
    generated_by: GeneratedBy
    analyzed_at: datetime


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
    location_source: LocationSource | None = Field(
        default=None, description="Null for reports filed before T053A."
    )
    location_accuracy_m: float | None = None
    mat_condition: MatCondition | None = Field(
        default=None, description="The crew's A-D grade; access mat reports only."
    )
    site_distance_miles: float | None = Field(
        default=None, description="Backend-computed distance from the report to its site."
    )
    enrichment: ReportEnrichment | None = Field(
        default=None,
        description="Null while the analysis runs (it starts after the report "
        "is saved) and for reports filed before T060.",
    )
    notice_id: str | None = Field(
        default=None, description="Potential-hazard notice created when hazard_present is true."
    )
    created_at: datetime


class ReportCreate(Schema):
    """Form fields for `POST /api/reports` (multipart).

    The photo is sent as the `photo` file part.
    """

    site_id: str
    category: ReportCategory
    hazard_present: bool
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    note: str | None = Field(default=None, max_length=1000)
    location_source: LocationSource = LocationSource.SITE
    location_accuracy_m: float | None = Field(
        default=None, ge=0, description="Device accuracy radius. Only with location_source=device."
    )
    mat_condition: MatCondition | None = Field(
        default=None,
        description="Required for access_mat_deterioration and only accepted there. "
        "A means hazard_present is false; B, C and D mean it is true.",
    )

    @model_validator(mode="after")
    def accuracy_only_from_the_device(self) -> "ReportCreate":
        if self.location_accuracy_m is not None and self.location_source != LocationSource.DEVICE:
            raise ValueError("location_accuracy_m is only accepted with location_source=device")
        return self

    @model_validator(mode="after")
    def mat_condition_matches_category(self) -> "ReportCreate":
        is_mat = self.category == ReportCategory.ACCESS_MAT_DETERIORATION
        if is_mat and self.mat_condition is None:
            raise ValueError("mat_condition (A-D) is required for access mat reports")
        if not is_mat and self.mat_condition is not None:
            raise ValueError("mat_condition is only accepted for access mat reports")
        if is_mat and self.hazard_present != (self.mat_condition != MatCondition.A):
            raise ValueError("Grade A is hazard absent; grades B, C and D are hazard present")
        return self


class ReportReview(Schema):
    """Body for `POST /api/reports/{id}/review`."""

    decision: Literal["confirmed", "rejected"]
    category: ReportCategory | None = None
    severity: Severity | None = None
    note: str | None = Field(default=None, max_length=1000)
