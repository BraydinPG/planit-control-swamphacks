"""ML-owned types; backend authorization and route schemas remain Rudra's."""

from typing import Literal, NotRequired, TypedDict


class EventLocation(TypedDict, total=False):
    lat: float
    lon: float
    region: str
    spatial_match_quality: Literal["site_verified", "point_nearby", "region_only", "unknown"]


class EvidenceReference(TypedDict):
    id: str
    source: str
    available_at_utc: str
    valid_time_utc: NotRequired[str]


class Observation(TypedDict):
    valid_time_utc: str
    acquired_at_utc: NotRequired[str]
    type: NotRequired[str]
    value: NotRequired[float | None]
    unit: NotRequired[str]
    source: NotRequired[str]
    freshness: NotRequired[str]


class EventContext(TypedDict):
    event_id: str
    event_type: str
    event_status: Literal["confirmed_active", "historical_replay"]
    as_of_utc: str
    event_start_utc: str
    site_id: NotRequired[str | None]
    location: NotRequired[EventLocation]
    recent_observations: NotRequired[list[Observation]]
    evidence: NotRequired[list[EvidenceReference]]
    is_simulated: NotRequired[bool]
    event_definition: NotRequired[str]
    station_id: NotRequired[str]


class DurationOutlook(TypedDict):
    p10: float | None
    median: float | None
    p90: float | None
    tail_horizon_hours: int
    max_remaining_hours: float
    tail_beyond_24h: bool | None


class EventOutcomes(TypedDict):
    recorded_event_ongoing_probability: dict[str, float]
    recorded_event_ended_probability: dict[str, float]
    remaining_duration_hours: DurationOutlook
    baseline_recorded_event_ongoing_probability: dict[str, float | None]
    trend: Literal["unknown"]
    trend_basis: str


class EventPrediction(TypedDict):
    status: Literal["ok", "unavailable", "not_applicable_no_confirmed_event"]
    scope: str
    site_id: str | None
    event_id: str | None
    event_type: str | None
    as_of_utc: str | None
    generated_at_utc: str
    outcomes: EventOutcomes | dict
    evidence_quality: dict
    worker_context: dict
    model_version: str
    is_simulated: bool
    production_eligibility: bool
    contract_version: NotRequired[str]
    event_category: NotRequired[str]
    applicable_location: NotRequired[EventLocation | None]
    data_version: NotRequired[str | None]
    research_only: NotRequired[bool]
    operational_evaluation_eligible: NotRequired[bool]
