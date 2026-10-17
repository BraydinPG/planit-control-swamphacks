from datetime import datetime
from typing import Literal

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
