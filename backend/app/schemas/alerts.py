from datetime import datetime
from enum import StrEnum

from pydantic import Field

from app.schemas.common import Evidence, Schema


class AlertRule(StrEnum):
    LIGHTNING_STOP_WORK = "lightning_stop_work"
    FLOOD = "flood"
    HEAT = "heat"
    HURRICANE = "hurricane"
    EARTHQUAKE = "earthquake"


class AlertState(StrEnum):
    ACTIVE = "active"
    CLEARED = "cleared"


class Acknowledgement(Schema):
    id: str
    alert_id: str
    user_id: str
    acknowledged_at: datetime


class Alert(Schema):
    """A deterministic rule result. Gemini and the model never create or clear alerts.

    `POST /api/alerts/{id}/acknowledge` takes no body; the user and time come from the token
    and the server clock.
    """

    id: str
    site_id: str
    rule: AlertRule
    state: AlertState
    triggered_at: datetime
    latest_event_at: datetime = Field(
        description="Latest qualifying event, e.g. the newest strike."
    )
    clear_after: datetime | None = Field(
        default=None, description="Lightning: latest_event_at + 30 minutes. Resets on each strike."
    )
    distance_miles: float | None = Field(default=None, ge=0)
    trigger_observation_ids: list[str] = []
    evidence: list[Evidence] = []
    simulated: bool = False
    is_prototype_rule: bool = Field(
        default=False, description="False only for the required lightning rule."
    )
    acknowledgements: list[Acknowledgement] = []
