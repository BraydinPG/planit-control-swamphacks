"""ML-owned 1.0.0 contract, deliberately separate from canonical SiteDetail."""

from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import AfterValidator, Field, model_validator

from ml.schemas import parse_utc
from ml.worker.schema import Contract, Point


def utc(value: str) -> str:
    return parse_utc(value, "timestamp").isoformat().replace("+00:00", "Z")


def identifier(value: str) -> str:
    if ".." in value:
        raise ValueError("Parent path syntax is not an identifier")
    return value


Utc = Annotated[str, AfterValidator(utc)]
Id = Annotated[
    str,
    Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9:_.-]{0,159}$"),
    AfterValidator(identifier),
]
Probability = Annotated[float, Field(ge=0, le=1, strict=True)]
Hours = Annotated[float, Field(ge=0, strict=True)]


class ReferenceSite(Point):
    id: Id
    name: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=300)
    # The current reference inventory is not proof of a historical work order.
    inventory_vintage: str = Field(min_length=1, max_length=100)


class Confirmation(Contract):
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
    source_id: Id | None = None
    confirmed_at_utc: Utc | None = None
    available_at_utc: Utc | None = None


class Association(Contract):
    site_id: Id
    method: Literal["site_verified", "regional_context", "reference_replay", "unknown"]
    source_id: Id | None = None
    description: str = Field(min_length=1, max_length=600)


class ObservationRef(Contract):
    id: Id
    source_id: Id
    valid_time_utc: Utc
    available_at_utc: Utc


class EventInput(Contract):
    event_id: Id
    notice_id: Id | None = None
    event_name: str = Field(min_length=1, max_length=200)
    event_type: str = Field(min_length=1, max_length=100)
    confirmation: Confirmation
    association: Association
    event_start_utc: Utc | None = None
    event_definition: str | None = Field(default=None, max_length=200)
    observations: list[ObservationRef] = Field(default_factory=list, max_length=100)
    station_id: Id | None = None
    official_product_id: Id | None = None


class OutlookRequest(Contract):
    contract_version: Literal["ml-event-outlooks-1.0.0"] = "ml-event-outlooks-1.0.0"
    site: ReferenceSite
    as_of_utc: Utc
    events: list[EventInput] = Field(max_length=32)

    @model_validator(mode="after")
    def unique_events(self):
        if len({e.event_id for e in self.events}) != len(self.events):
            raise ValueError("Duplicate event IDs must be reconciled upstream")
        return self


class SourceRecord(Contract):
    id: Id
    provider: Literal["NHC", "USGS"]
    url: str = Field(max_length=700)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    issued_at_utc: Utc
    retrieved_at_utc: Utc
    available_at_utc: Utc | None = None
    vintage: Literal["archive_capture", "contemporaneous_capture"]

    @model_validator(mode="after")
    def provenance(self):
        url = urlparse(self.url)
        hosts = {
            "NHC": {"www.nhc.noaa.gov", "ftp.nhc.noaa.gov"},
            "USGS": {"earthquake.usgs.gov"},
        }
        if (
            url.scheme != "https"
            or url.hostname not in hosts[self.provider]
            or url.username
            or url.password
            or url.port not in (None, 443)
            or url.query
            or url.fragment
        ):
            raise ValueError("Unapproved official source URL")
        if self.available_at_utc and not parse_utc(
            self.issued_at_utc, "issue"
        ) <= parse_utc(self.available_at_utc, "available") <= parse_utc(
            self.retrieved_at_utc, "retrieved"
        ):
            raise ValueError(
                "Official availability must follow issuance and precede capture"
            )
        if parse_utc(self.retrieved_at_utc, "retrieved") < parse_utc(
            self.issued_at_utc, "issued"
        ):
            raise ValueError("Capture cannot predate the issued product")
        return self


class RemainingDuration(Contract):
    p10: Hours | None
    median: Hours | None
    p90: Hours | None

    @model_validator(mode="after")
    def ordered(self):
        known = [v for v in (self.p10, self.median, self.p90) if v is not None]
        if known != sorted(known):
            raise ValueError("Duration quantiles must be ordered")
        return self


class Persistence(Contract):
    horizon_hours: int = Field(ge=1, le=168, strict=True)
    recorded_event_ongoing_probability: Probability


class DurationForecast(Contract):
    kind: Literal["historical_duration_research"] = "historical_duration_research"
    target_definition: str
    model_version: str
    estimator: str
    persistence: list[Persistence] = Field(min_length=1)
    remaining_duration_hours: RemainingDuration
    model_card: str
    training_support_at_event_age: int | None = None
    trend: Literal["unknown"] = "unknown"


class StormPoint(Point):
    valid_at_utc: Utc
    max_sustained_wind_kt: float = Field(ge=0, le=250, strict=True)
    gust_kt: float | None = Field(default=None, ge=0, le=300, strict=True)
    phase: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def wind(self):
        if self.gust_kt is not None and self.gust_kt < self.max_sustained_wind_kt:
            raise ValueError("Gust cannot be below maximum sustained wind")
        return self


class OfficialEventForecast(Contract):
    kind: Literal["official_event_forecast"] = "official_event_forecast"
    cyclone_id: Id
    storm_name: str
    provider_version: str
    source: SourceRecord
    next_advisory_at_utc: Utc
    initial_position: StormPoint
    forecast_points: list[StormPoint] = Field(min_length=1, max_length=30)
    site_wind_forecast: None = None

    @model_validator(mode="after")
    def validity(self):
        issued = parse_utc(self.source.issued_at_utc, "issued")
        times = [
            parse_utc(p.valid_at_utc, "forecast valid") for p in self.forecast_points
        ]
        if (
            self.source.provider != "NHC"
            or times != sorted(set(times))
            or any(t <= issued for t in times)
            or parse_utc(self.initial_position.valid_at_utc, "initial") != issued
            or parse_utc(self.next_advisory_at_utc, "next") <= issued
        ):
            raise ValueError("Invalid NHC product times / provider")
        return self


class Mainshock(Point):
    event_id: Id
    time_utc: Utc
    magnitude: float = Field(ge=-2, le=10, strict=True)


class AftershockBin(Contract):
    magnitude_at_least: float = Field(ge=0, le=10, strict=True)
    probability_at_least_one: Probability
    count_p95_minimum: int | None = Field(default=None, ge=0, strict=True)
    count_p95_maximum: int | None = Field(default=None, ge=0, strict=True)


class AftershockWindow(Contract):
    label: str
    start_utc: Utc
    end_utc: Utc
    bins: list[AftershockBin] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def ordered(self):
        if parse_utc(self.end_utc, "end") <= parse_utc(self.start_utc, "start"):
            raise ValueError("Aftershock window must have positive duration")
        mags = [b.magnitude_at_least for b in self.bins]
        if mags != sorted(set(mags)):
            raise ValueError("Magnitude thresholds must be distinct and increasing")
        return self


class AftershockRegion(Point):
    radius_km: float = Field(gt=0, le=2000, strict=True)
    interpretation: Literal["provider_sequence_region_not_site_probability"] = (
        "provider_sequence_region_not_site_probability"
    )


class OfficialAftershockForecast(Contract):
    kind: Literal["official_aftershock_forecast"] = "official_aftershock_forecast"
    mainshock: Mainshock
    provider_version: str
    source: SourceRecord
    mainshock_source: SourceRecord
    expires_at_utc: Utc
    region: AftershockRegion
    windows: list[AftershockWindow] = Field(min_length=1, max_length=10)
    earthquake_remaining_duration: None = None

    @model_validator(mode="after")
    def validity(self):
        if self.source.provider != "USGS" or self.mainshock_source.provider != "USGS":
            raise ValueError("USGS provenance required")
        issued, expires = (
            parse_utc(self.source.issued_at_utc, "issued"),
            parse_utc(self.expires_at_utc, "expires"),
        )
        if not parse_utc(self.mainshock.time_utc, "mainshock") <= issued < expires:
            raise ValueError("Invalid aftershock product chronology")
        if any(parse_utc(w.end_utc, "end") > expires for w in self.windows):
            raise ValueError("Aftershock window exceeds expiration")
        return self


class UnavailableForecast(Contract):
    kind: Literal["unavailable"] = "unavailable"
    reason_code: str
    reason: str
    required_inputs: list[str] = Field(default_factory=list)


Forecast = Annotated[
    DurationForecast
    | OfficialEventForecast
    | OfficialAftershockForecast
    | UnavailableForecast,
    Field(discriminator="kind"),
]


class EventOutlook(Contract):
    event_id: Id
    notice_id: Id | None
    event_name: str
    event_type: str
    confirmation: Confirmation
    association: Association
    as_of_utc: Utc
    event_start_utc: Utc | None
    last_observation_at_utc: Utc | None
    last_forecast_issued_at_utc: Utc | None
    evidence_status: Literal[
        "rejected_for_forecast", "accepted_for_research", "issued_provider_product"
    ]
    status: Literal["available", "unavailable", "not_applicable"]
    forecast: Forecast
    evidence: list[ObservationRef]
    limitations: list[str]
    is_simulated: bool
    research_only: bool
    production_eligibility: Literal[False] = False
    site_hazard_probability: None = None

    @model_validator(mode="after")
    def consistent(self):
        if (self.status == "available") == isinstance(
            self.forecast, UnavailableForecast
        ):
            raise ValueError("Status and forecast kind disagree")
        if self.last_forecast_issued_at_utc and parse_utc(
            self.last_forecast_issued_at_utc, "issued"
        ) > parse_utc(self.as_of_utc, "asof"):
            raise ValueError("Future-issued forecast")
        return self


class OutlookBatch(Contract):
    contract_version: Literal["ml-event-outlooks-1.0.0"] = "ml-event-outlooks-1.0.0"
    site: ReferenceSite
    as_of_utc: Utc
    status: Literal["available", "partial", "unavailable", "not_applicable"]
    event_outlooks: list[EventOutlook]
    work_authorization: Literal["outside_advisory_authority"] = (
        "outside_advisory_authority"
    )
    affects_site_score: Literal[False] = False
    affects_alerts_or_lightning_timer: Literal[False] = False
    unverified_worksite_hazards: list[str] = Field(
        default_factory=lambda: [
            "Electrical / energized water: unknown; qualified field verification required",
            "Structural / access: unknown; field verification required",
            "Chemical / biological / wildlife: unknown; confirmed reports required",
        ]
    )
