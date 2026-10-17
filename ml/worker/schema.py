"""Versioned, ML-owned advisory contract. No backend route/schema replacement."""

from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ml.schemas import parse_utc

CONTRACT_VERSION = "2.0.0"
HazardKind = Literal[
    "wind",
    "heat",
    "rain",
    "flood_context",
    "coastal_water",
    "waves",
    "wildfire",
    "air_quality",
    "earthquake",
    "winter",
    "visibility",
    "space_weather",
    "landslide",
    "tsunami",
    "volcanic",
    "infrastructure",
]
Method = Literal["observed", "issued_forecast", "official_warning", "retrospective"]
Probability = Annotated[float, Field(ge=0, le=1, strict=True)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True)


class Point(Contract):
    lat: float = Field(ge=-90, le=90, strict=True)
    lon: float = Field(ge=-180, le=180, strict=True)


class Footprint(Contract):
    kind: Literal["point", "polygon", "regional", "global", "unknown"]
    point: Point | None = None
    # GeoJSON polygon rings, [longitude, latitude]; holes supported.
    rings: list[list[list[float]]] = Field(default_factory=list)
    precision: str
    site_id: str | None = None
    relation: Literal["unspecified", "verified_gauge_basin"] = "unspecified"
    relation_evidence_id: str | None = None

    @model_validator(mode="after")
    def geometry(self):
        if self.kind == "point" and self.point is None:
            raise ValueError("point geometry requires coordinates")
        if self.kind == "polygon":
            if not self.rings:
                raise ValueError("polygon requires rings")
            for ring in self.rings:
                if len(ring) < 4 or ring[0] != ring[-1]:
                    raise ValueError("polygon rings must be closed")
                for pair in ring:
                    if len(pair) != 2:
                        raise ValueError("polygon coordinates require lon/lat pairs")
                    Point(lon=pair[0], lat=pair[1])
                if max(p[0] for p in ring) - min(p[0] for p in ring) > 180:
                    raise ValueError("antimeridian polygon requires an explicit split geometry")
        return self


class SiteContext(Point):
    id: str = Field(min_length=1)
    name: str
    site_type: Literal["representative_monitored_site", "fixture_site"]
    source: str
    source_version: str
    is_fixture: bool = True


class Confirmation(Contract):
    source: str = Field(min_length=1)
    record_id: str = Field(min_length=1)
    confirmed_at: str
    available_at: str
    is_fixture: bool = True

    @field_validator("confirmed_at", "available_at")
    @classmethod
    def timestamps(cls, value):
        return parse_utc(value, "confirmation time").isoformat().replace("+00:00", "Z")


class Evidence(Contract):
    evidence_id: str = Field(min_length=1, max_length=200)
    publisher: str = Field(min_length=1)
    origin_url: str
    source_record_id: str = Field(min_length=1)
    original_type: str
    hazard: HazardKind
    method: Method
    variable: str
    value: float | str | None = None
    unit: str
    observed_at: str | None = None
    issued_at: str | None = None
    available_at: str | None = None
    valid_from: str
    valid_to: str
    ingested_at: str
    source_version: str | None = None
    availability_basis: Literal["retrieved_by_pipeline", "issued_archive", "fixture", "unknown"]
    footprint: Footprint
    data_state: Literal["current", "stale", "missing", "retrospective"] = "current"
    quality_flags: list[str] = Field(default_factory=list)
    is_fixture: bool = False
    datum: str | None = None
    human_review_status: Literal["not_applicable", "confirmed", "pending", "rejected"] = (
        "not_applicable"
    )
    value_basis: Literal["source_value", "derived"] = "source_value"
    derived_from_evidence_ids: list[str] = Field(default_factory=list)
    computation_version: str | None = None

    @field_validator("value", mode="before")
    @classmethod
    def finite_value_type(cls, value):
        if isinstance(value, bool):
            raise ValueError("boolean is not a measurement")
        return value

    @field_validator("origin_url")
    @classmethod
    def public_origin(cls, value):
        parsed = urlparse(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
        ):
            raise ValueError("origin must be a public HTTPS URL without credentials/query secrets")
        return value

    @field_validator(
        "observed_at", "issued_at", "available_at", "valid_from", "valid_to", "ingested_at"
    )
    @classmethod
    def timestamps(cls, value):
        return (
            parse_utc(value, "evidence time").isoformat().replace("+00:00", "Z")
            if value is not None
            else None
        )

    @model_validator(mode="after")
    def chronology(self):
        if parse_utc(self.valid_to, "valid_to") < parse_utc(self.valid_from, "valid_from"):
            raise ValueError("evidence validity is reversed")
        if self.method == "observed" and self.observed_at is None:
            raise ValueError("observation time required")
        if self.method in ("issued_forecast", "official_warning") and self.issued_at is None:
            raise ValueError("issued product requires issue time")
        if self.available_at and parse_utc(self.available_at, "available_at") > parse_utc(
            self.ingested_at, "ingested_at"
        ):
            raise ValueError("evidence cannot be available after ingestion")
        if (
            self.availability_basis == "retrieved_by_pipeline"
            and self.available_at != self.ingested_at
        ):
            raise ValueError("retrieval availability cannot be backdated")
        if self.availability_basis == "fixture" and not self.is_fixture:
            raise ValueError("fixture availability must be labeled simulated")
        return self


class SpatialMatch(Contract):
    kind: Literal[
        "station_at_location",
        "nearby_station",
        "verified_gauge_basin",
        "polygon_intersects",
        "county_only_context",
        "track_center_distance",
        "epicenter_distance",
        "global_context",
        "uncertain",
        "no_supported_association",
    ]
    distance_km: float | None = Field(default=None, ge=0)
    distance_miles: float | None = Field(default=None, ge=0)
    limitation: str


class EvidenceAssessment(Contract):
    evidence: Evidence
    accepted: bool
    spatial_match: SpatialMatch
    reasons: list[str]
    freshness: Literal["current", "issued_valid", "stale", "future", "retrospective", "unknown"]


class ConfirmedEventInput(Contract):
    event_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    event_status: Literal["confirmed_active", "historical_replay"]
    event_start_utc: str
    as_of_utc: str
    confirmation: Confirmation
    site_id: str | None = None
    location: dict = Field(
        default_factory=dict
    )  # Legacy location is validated by validate_event_context.
    event_definition: str | None = None
    station_id: str | None = None
    is_simulated: bool = False
    recent_observations: list[dict] = Field(default_factory=list)
    evidence: list[dict] = Field(default_factory=list)

    @model_validator(mode="after")
    def legacy_event_contract(self):
        from ml.schemas import validate_event_context

        validate_event_context(self.model_dump())
        return self


class WorkerOutlookRequest(Contract):
    event_context: ConfirmedEventInput
    site_context: SiteContext
    evidence: list[Evidence] = Field(max_length=200)


class Condition(Contract):
    evidence_id: str
    method: Method
    variable: str
    value: float | str
    unit: str
    valid_from: str
    valid_to: str
    spatial_match: SpatialMatch
    datum: str | None = None
    value_basis: Literal["source_value", "derived"] = "source_value"
    derived_from_evidence_ids: list[str] = Field(default_factory=list)
    computation_version: str | None = None


class SiteHazard(Contract):
    kind: HazardKind
    status: Literal["observed", "issued_forecast", "official_warning", "partial", "unavailable"]
    conditions: list[Condition]
    probability: Literal[None] = None  # No empirically validated local probability target yet.
    confidence: Literal[None] = None
    evidence_ids: list[str]
    unknowns: list[str]
    planning_context: str
    warning_evidence_ids: list[str] = Field(default_factory=list)


class EventOutlook(Contract):
    status: Literal["supported_research", "unavailable"]
    target: str | None
    model_version: str
    data_version: str | None
    estimator: str | None = None
    ongoing_probability: dict[str, Probability] = Field(default_factory=dict)
    remaining_duration_hours: dict[str, float | bool | None] = Field(default_factory=dict)
    trend: Literal["unknown"] = "unknown"
    fit_cutoff_utc: str | None = None
    historical_feature_availability_verified: Literal[False] = False
    limitations: list[str]

    @model_validator(mode="after")
    def supported_outcomes(self):
        if self.status == "unavailable" and (
            self.ongoing_probability or self.remaining_duration_hours
        ):
            raise ValueError("unavailable event cannot contain estimates")
        if self.status == "supported_research" and (
            not self.data_version
            or not self.target
            or not self.ongoing_probability
            or self.model_version == "unavailable"
        ):
            raise ValueError(
                "research estimates require model/data identity and supported outcomes"
            )
        import re

        if any(not re.fullmatch(r"[1-9]\d*h", key) for key in self.ongoing_probability):
            raise ValueError("event horizons must be explicit positive hours")
        ordered = [
            p
            for _, p in sorted(self.ongoing_probability.items(), key=lambda item: int(item[0][:-1]))
        ]
        if any(left < right for left, right in zip(ordered, ordered[1:])):
            raise ValueError("event persistence must not increase with horizon")
        allowed = {
            "p10",
            "median",
            "p90",
            "tail_horizon_hours",
            "max_remaining_hours",
            "tail_beyond_24h",
        }
        if set(self.remaining_duration_hours) - allowed:
            raise ValueError("unsupported duration field or quantile")
        for key in ("p10", "median", "p90"):
            value = self.remaining_duration_hours.get(key)
            if value is not None and (isinstance(value, bool) or value < 0):
                raise ValueError("invalid remaining duration")
        quantiles = [
            self.remaining_duration_hours[k]
            for k in ("p10", "median", "p90")
            if self.remaining_duration_hours.get(k) is not None
        ]
        if quantiles != sorted(quantiles):
            raise ValueError("duration quantiles must be ordered")
        maximum = self.remaining_duration_hours.get("max_remaining_hours")
        if maximum is not None and any(value > maximum for value in quantiles):
            raise ValueError("duration quantile exceeds supported remaining horizon")
        return self


class WorkerOutlook(Contract):
    contract_version: Literal["2.0.0"] = CONTRACT_VERSION
    site: SiteContext
    event_id: str | None
    event_type: str | None
    confirmation: Confirmation | None
    as_of_utc: str
    generated_at_utc: str
    status: Literal["supported_research", "partial", "unavailable"]
    research_only: Literal[True] = True
    operational_evaluation_eligible: Literal[False] = False
    production_eligibility: Literal[False] = False
    is_demo_or_simulated: bool
    event_outlook: EventOutlook
    site_hazards: list[SiteHazard]
    evidence: list[EvidenceAssessment]
    unknowns: list[str]
    limitations: list[str]
    not_work_clearance: Literal[True] = True
    safety_statement: Literal[
        "Advisory context only. No permission to access, work, or resume work; official warnings and deterministic controls remain authoritative."
    ] = "Advisory context only. No permission to access, work, or resume work; official warnings and deterministic controls remain authoritative."

    @field_validator("as_of_utc", "generated_at_utc")
    @classmethod
    def timestamps(cls, value):
        return parse_utc(value, "outlook time").isoformat().replace("+00:00", "Z")
