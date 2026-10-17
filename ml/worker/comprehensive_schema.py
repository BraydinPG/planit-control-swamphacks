"""Opt-in 2.1 advisory. The strict 2.0 callable/schema remain unchanged."""

from typing import Literal
from pydantic import Field, field_validator, model_validator

from ml.schemas import parse_utc
from ml.worker.schema import Contract, Footprint, Point, WorkerOutlook, WorkerOutlookRequest

Identifier = str


class OfficialAlert(Contract):
    id: str = Field(min_length=1, max_length=240)
    publisher: Literal["NOAA NWS"] = "NOAA NWS"
    event: str = Field(min_length=1, max_length=160)
    status: str = Field(max_length=40)
    message_type: str = Field(max_length=40)
    sent: str
    updated: str
    effective: str
    onset: str | None = None
    expires: str
    ends: str | None = None
    available_at: str
    ingested_at: str
    source_version: str = Field(min_length=1, max_length=100)
    origin_url: Literal["https://api.weather.gov/alerts"] = "https://api.weather.gov/alerts"
    polygons: list[Footprint] = Field(default_factory=list, max_length=30)
    zone_ids: list[str] = Field(default_factory=list, max_length=1000)
    query_site_id: str | None = None
    query_point: Point | None = None
    query_url: str | None = None
    references: list[str] = Field(default_factory=list, max_length=100)
    severity: str = Field(default="Unknown", max_length=40)
    certainty: str = Field(default="Unknown", max_length=40)
    urgency: str = Field(default="Unknown", max_length=40)
    is_fixture: bool = False

    @field_validator(
        "sent", "updated", "effective", "onset", "expires", "ends", "available_at", "ingested_at"
    )
    @classmethod
    def timestamps(cls, value):
        return (
            parse_utc(value, "CAP timestamp").isoformat().replace("+00:00", "Z") if value else None
        )

    @model_validator(mode="after")
    def coherent(self):
        if self.available_at != self.ingested_at:
            raise ValueError("Capture availability cannot be backdated")
        if parse_utc(self.expires, "expires") <= parse_utc(self.sent, "sent"):
            raise ValueError("Alert expires before issue")
        if parse_utc(self.updated, "updated") < parse_utc(self.sent, "sent"):
            raise ValueError("Update precedes issue")
        from ml.worker.geometry import checked_polygon

        for polygon in self.polygons:
            if polygon.kind != "polygon":
                raise ValueError("Alert coverage must contain polygon geometry")
            checked_polygon(polygon.rings)
        if any(v is not None for v in (self.query_site_id, self.query_point, self.query_url)):
            if any(v is None for v in (self.query_site_id, self.query_point, self.query_url)):
                raise ValueError("Incomplete provider point-query provenance")
            from ml.sources.bounded import validate_url
            from urllib.parse import parse_qs, urlparse

            parsed = urlparse(validate_url(self.query_url))
            if parsed.hostname != "api.weather.gov" or parsed.path != "/alerts/active":
                raise ValueError("Point proof requires the NWS active-alert endpoint")
            lat, lon = map(float, parse_qs(parsed.query).get("point", [""])[0].split(","))
            if abs(lat - self.query_point.lat) > 1e-8 or abs(lon - self.query_point.lon) > 1e-8:
                raise ValueError("Provider query coordinates disagree with recorded point")
        return self


class AlertAssessment(Contract):
    alert: OfficialAlert
    accepted: bool
    status: Literal["issued_notice", "unmatched", "not_current", "rejected"]
    reasons: list[str]
    site_spatial_match: str


class ReviewedReport(Contract):
    id: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9_.:-]+$")
    site_id: str = Field(min_length=1, max_length=160)
    hazard_id: str = Field(min_length=1, max_length=100)
    issuer: str = Field(min_length=1, max_length=100)
    kind: Literal["crew_report", "asset_telemetry", "official_local_notice"]
    state: Literal["present", "absent", "unknown"]
    review_status: Literal["pending", "confirmed", "rejected", "ai_suggested"]
    reviewer_role: Literal["crew", "supervisor", "asset_operator", "none"]
    reviewed_at: str | None = None
    observed_at: str
    available_at: str
    valid_to: str
    lat: float = Field(ge=-90, le=90, strict=True)
    lon: float = Field(ge=-180, le=180, strict=True)
    source_version: str = Field(min_length=1, max_length=100)
    is_fixture: bool = True

    @field_validator("reviewed_at", "observed_at", "available_at", "valid_to")
    @classmethod
    def timestamps(cls, value):
        return (
            parse_utc(value, "report timestamp").isoformat().replace("+00:00", "Z")
            if value
            else None
        )


class TrustPolicy(Contract):
    """Server-owned policy, never a field in a client request or proof of authentication."""

    allowed_report_issuers: frozenset[str] = frozenset()
    allow_fixture_reports: bool = False
    maximum_report_age_hours: float = Field(default=2, gt=0, le=24)


class ReportAssessment(Contract):
    report: ReviewedReport
    accepted: bool
    reasons: list[str]


class ContextSignal(Contract):
    id: str = Field(min_length=1, max_length=160)
    hazard_id: Literal["shaking", "geomagnetic_storm", "drought", "floodplain", "wildfire"]
    method: Literal[
        "issued_model_estimate", "official_message", "background_context", "mapped_observation"
    ]
    source: str
    origin_url: str
    source_version: str
    issued_at: str
    observed_at: str | None = None
    available_at: str
    valid_to: str | None = None
    footprint: Footprint
    value: float | None = None
    unit: Literal["MMI", "context"]
    description: str = Field(max_length=600)
    source_metadata: dict[str, str | float] = Field(default_factory=dict)
    is_fixture: bool = False

    @field_validator("issued_at", "observed_at", "available_at", "valid_to")
    @classmethod
    def timestamps(cls, value):
        return (
            parse_utc(value, "context timestamp").isoformat().replace("+00:00", "Z")
            if value
            else None
        )

    @model_validator(mode="after")
    def bounded_estimate(self):
        if self.value is not None and not (
            self.hazard_id == "shaking" and self.unit == "MMI" and 1 <= self.value <= 12
        ):
            raise ValueError("Only source-derived bounded MMI estimates supported")
        if self.method == "mapped_observation" and self.observed_at is None:
            raise ValueError("Mapped observation requires acquisition time")
        if self.footprint.kind == "polygon":
            from ml.worker.geometry import checked_polygon

            checked_polygon(self.footprint.rings)
        return self

    @field_validator("origin_url")
    @classmethod
    def source_origin(cls, value):
        from ml.sources.bounded import validate_url

        return validate_url(value)


class ContextAssessment(Contract):
    signal: ContextSignal
    accepted: bool
    reasons: list[str]
    site_spatial_match: str


class WorksiteHazard(Contract):
    hazard_id: str
    status: Literal[
        "evidence_available", "reported_present", "reported_absent", "partial", "unknown"
    ]
    evidence_status: Literal["accepted", "mixed", "rejected", "not_supplied"]
    source_ids: list[str]
    observed_or_valid_windows: list[dict[str, str]]
    site_spatial_match: list[str]
    methods: list[
        Literal[
            "observed",
            "issued_forecast",
            "official_warning",
            "reported",
            "issued_model_estimate",
            "context",
            "unknown",
        ]
    ]
    description: str
    unknowns: list[str]
    needs_field_verification: Literal[True] = True
    production_eligibility: Literal[False] = False
    probability: Literal[None] = None
    severity: Literal[None] = None
    # A source MMI value may be included here; never a damage or clearance estimate.
    numerical_evidence: list[dict] = Field(default_factory=list)


class LightningRecord(Contract):
    id: str = Field(min_length=1, max_length=160)
    observed_at: str
    available_at: str
    lat: float = Field(ge=-90, le=90, strict=True)
    lon: float = Field(ge=-180, le=180, strict=True)
    source_version: str = Field(min_length=1)
    is_replay: Literal[True] = True

    @field_validator("observed_at", "available_at")
    @classmethod
    def timestamps(cls, value):
        return parse_utc(value, "lightning replay time").isoformat().replace("+00:00", "Z")


class LightningContext(Contract):
    record: LightningRecord
    accepted: bool
    distance_miles: float = Field(ge=0)
    reasons: list[str]
    rule_authority: Literal[
        "Rudra deterministic service; no ML trigger, timer, reset or clearance"
    ] = "Rudra deterministic service; no ML trigger, timer, reset or clearance"


class SourceAvailability(Contract):
    provider: str = Field(min_length=1, max_length=100)
    state: Literal["current", "stale", "unavailable", "fixture_only"]
    attempted: bool
    last_success_at: str | None = None
    reason: str = Field(max_length=300)

    @field_validator("last_success_at")
    @classmethod
    def timestamp(cls, value):
        return (
            parse_utc(value, "source success time").isoformat().replace("+00:00", "Z")
            if value
            else None
        )

    @model_validator(mode="after")
    def current_needs_receipt(self):
        if self.state == "current" and self.last_success_at is None:
            raise ValueError("Current source requires a successful capture time")
        return self


class ComprehensiveRequest(WorkerOutlookRequest):
    alerts: list[OfficialAlert] = Field(default_factory=list, max_length=600)
    reports: list[ReviewedReport] = Field(default_factory=list, max_length=100)
    context_signals: list[ContextSignal] = Field(default_factory=list, max_length=100)
    lightning_replay: list[LightningRecord] = Field(default_factory=list, max_length=100)
    source_states: list[SourceAvailability] = Field(default_factory=list, max_length=30)


class ComprehensiveOutlook(WorkerOutlook):
    contract_version: Literal["2.1.0"] = "2.1.0"
    registry_version: Literal["1.0.0"] = "1.0.0"
    worksite_hazards: list[WorksiteHazard]
    official_notices: list[AlertAssessment]
    reviewed_reports: list[ReportAssessment]
    context_evidence: list[ContextAssessment]
    lightning_replay_context: list[LightningContext]
    source_availability: list[SourceAvailability]
    trust_boundary: Literal[
        "Upstream authentication and verification required; schema validity is not source authenticity."
    ] = "Upstream authentication and verification required; schema validity is not source authenticity."


def to_legacy(outlook: ComprehensiveOutlook | dict) -> dict:
    validated = ComprehensiveOutlook.model_validate(outlook)
    old = validated.model_dump(include=set(WorkerOutlook.model_fields), mode="json")
    old["contract_version"] = "2.0.0"
    return WorkerOutlook.model_validate(old).model_dump(mode="json")
