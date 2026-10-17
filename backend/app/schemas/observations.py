from datetime import datetime
from enum import StrEnum

from pydantic import Field

from app.schemas.common import DataState, Schema


class HazardType(StrEnum):
    """Observation types produced by the ingestion adapters in backend/app/ingestion/."""

    WEATHER = "weather"
    FORECAST = "forecast"
    FLOOD_ALERT = "flood_alert"
    FLOOD_GAUGE = "flood_gauge"
    LIGHTNING_STRIKE = "lightning_strike"
    HURRICANE = "hurricane"
    EARTHQUAKE = "earthquake"


class Observation(Schema):
    """A normalized reading from a live feed or the lightning replay fixture.

    The first nine fields are the ingestion interface in AGENTS.md. `id` and `site_id`
    are assigned when the observation is stored.
    """

    source: str = Field(description='Feed name, e.g. "NWS", "USGS", "NHC", "lightning-replay".')
    hazard_type: HazardType
    value: float | str | None = None
    unit: str | None = None
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    observed_at: datetime
    valid_at: datetime | None = None
    data_state: DataState

    id: str | None = None
    site_id: str | None = None
    simulated: bool = False
    label: str | None = Field(default=None, description='Human label, e.g. "Flood Warning".')
    source_ref: str | None = Field(default=None, description="Upstream event or alert id.")
    fetched_at: datetime | None = Field(
        default=None, description="Last successful fetch; drives the stale state."
    )
