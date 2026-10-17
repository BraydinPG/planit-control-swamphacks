from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from app.schemas.common import Schema

ADVISORY_NOTICE = "Advisory only. Does not change the score, clear alerts, or authorize work."


class EventOutlook(Schema):
    """Compact view of Cache's `predict_active_event()` for a confirmed active event (T050).

    A separate advisory field on `SiteDetail`. It is never a score factor and never changes
    alerts or the lightning timer. `ongoing_probability` is the chance the recorded event
    is still ongoing at each horizon. It is not a return-to-work countdown.
    """

    status: Literal["ok", "unavailable", "not_applicable_no_confirmed_event"]
    event_id: str | None = None
    event_type: str | None = None
    as_of_utc: datetime | None = None
    generated_at_utc: datetime
    ongoing_probability: dict[str, float] = Field(
        default_factory=dict, description='Horizon ("6h", "12h", "24h") -> probability (0–1).'
    )
    remaining_hours_p10: float | None = None
    remaining_hours_median: float | None = None
    remaining_hours_p90: float | None = None
    trend: str = "unknown"
    model_version: str
    is_simulated: bool
    production_eligible: Literal[False] = False
    limitations: list[str] = []
    advisory_notice: Literal[
        "Advisory only. Does not change the score, clear alerts, or authorize work."
    ] = ADVISORY_NOTICE


# ---- T050A: one card per confirmed event (canonical mirror of ml-event-outlooks-1.0.0) ----
#
# `SiteDetail.event_outlooks` carries one card per qualifying event at the site, keyed by
# `event_id`. Cards are advisory: they never change the score, alerts, the lightning timer,
# or work authorization. `forecast.kind` selects the card type; "unavailable" is a visible
# reason, never a zero probability.


class OutlookConfirmation(Schema):
    status: Literal["confirmed_active", "historical_replay", "unconfirmed", "resolved"]
    basis: Literal[
        "independent_observation",
        "confirmed_worksite_report",
        "historical_record",
        "hypothetical_activation",
        "official_event_record",
        "warning_only",
        "none",
    ]
    source_id: str | None = None
    confirmed_at_utc: datetime | None = None
    available_at_utc: datetime | None = None


class OutlookAssociation(Schema):
    site_id: str
    method: Literal["site_verified", "regional_context", "reference_replay", "unknown"]
    source_id: str | None = None
    description: str


class OutlookEvidenceRef(Schema):
    id: str
    source_id: str
    valid_time_utc: datetime
    available_at_utc: datetime


class DurationPersistence(Schema):
    horizon_hours: int
    recorded_event_ongoing_probability: float = Field(ge=0, le=1)


class RemainingDurationHours(Schema):
    p10: float | None = None
    median: float | None = None
    p90: float | None = None


class DurationForecast(Schema):
    """Historical duration research for a recorded NOAA event interval, not clearance."""

    kind: Literal["historical_duration_research"] = "historical_duration_research"
    target_definition: str
    model_version: str
    estimator: str
    persistence: list[DurationPersistence]
    remaining_duration_hours: RemainingDurationHours
    model_card: str
    training_support_at_event_age: int | None = None
    trend: Literal["unknown"] = "unknown"


class OfficialSource(Schema):
    id: str
    provider: Literal["NHC", "USGS"]
    url: str
    sha256: str
    issued_at_utc: datetime
    retrieved_at_utc: datetime
    available_at_utc: datetime | None = None
    vintage: Literal["archive_capture", "contemporaneous_capture"]


class StormPoint(Schema):
    lat: float
    lon: float
    valid_at_utc: datetime
    max_sustained_wind_kt: float
    gust_kt: float | None = None
    phase: str | None = None


class OfficialEventForecast(Schema):
    """An issued NHC advisory track. Cyclone-scale; no site wind or event end."""

    kind: Literal["official_event_forecast"] = "official_event_forecast"
    cyclone_id: str
    storm_name: str
    provider_version: str
    source: OfficialSource
    next_advisory_at_utc: datetime
    initial_position: StormPoint
    forecast_points: list[StormPoint]
    site_wind_forecast: None = None


class Mainshock(Schema):
    lat: float
    lon: float
    event_id: str
    time_utc: datetime
    magnitude: float


class AftershockBin(Schema):
    magnitude_at_least: float
    probability_at_least_one: float = Field(ge=0, le=1)
    count_p95_minimum: int | None = None
    count_p95_maximum: int | None = None


class AftershockWindow(Schema):
    label: str
    start_utc: datetime
    end_utc: datetime
    bins: list[AftershockBin]


class AftershockRegion(Schema):
    lat: float
    lon: float
    radius_km: float
    interpretation: Literal["provider_sequence_region_not_site_probability"] = (
        "provider_sequence_region_not_site_probability"
    )


class OfficialAftershockForecast(Schema):
    """A published USGS aftershock forecast for the whole sequence region."""

    kind: Literal["official_aftershock_forecast"] = "official_aftershock_forecast"
    mainshock: Mainshock
    provider_version: str
    source: OfficialSource
    mainshock_source: OfficialSource
    expires_at_utc: datetime
    region: AftershockRegion
    windows: list[AftershockWindow]
    earthquake_remaining_duration: None = None


class UnavailableForecast(Schema):
    kind: Literal["unavailable"] = "unavailable"
    reason_code: str
    reason: str
    required_inputs: list[str] = []


OutlookForecast = Annotated[
    DurationForecast | OfficialEventForecast | OfficialAftershockForecast | UnavailableForecast,
    Field(discriminator="kind"),
]

OutlookPresentation = Literal["current", "replay", "historical_example"]


class EventOutlookCard(Schema):
    """One event's advisory outlook. Separate per event; never combined into a site risk."""

    event_id: str
    site_id: str
    notice_id: str | None = None
    event_name: str
    event_type: str
    presentation: OutlookPresentation = Field(
        description='"historical_example" = archived product shown as an example, not a '
        'current prediction; "replay" = simulated/replayed activation; "current" otherwise.'
    )
    confirmation: OutlookConfirmation
    association: OutlookAssociation
    as_of_utc: datetime
    event_start_utc: datetime | None = None
    last_observation_at_utc: datetime | None = None
    last_forecast_issued_at_utc: datetime | None = None
    evidence_status: Literal[
        "rejected_for_forecast", "accepted_for_research", "issued_provider_product"
    ]
    status: Literal["available", "unavailable", "not_applicable"]
    forecast: OutlookForecast
    evidence: list[OutlookEvidenceRef] = []
    limitations: list[str] = []
    is_simulated: bool
    research_only: bool
    production_eligibility: Literal[False] = False
    site_hazard_probability: None = None
    advisory_notice: Literal[
        "Advisory only. Does not change the score, clear alerts, or authorize work."
    ] = ADVISORY_NOTICE
