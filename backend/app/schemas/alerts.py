from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from app.schemas.common import Evidence, Schema


class AlertRule(StrEnum):
    LIGHTNING_STOP_WORK = "lightning_stop_work"
    TORNADO = "tornado"
    HURRICANE = "hurricane"
    FLASH_FLOOD = "flash_flood"
    EARTHQUAKE = "earthquake"
    SEVERE_THUNDERSTORM = "severe_thunderstorm"
    TROPICAL_STORM = "tropical_storm"
    FLOOD = "flood"
    HEAT = "heat"


class AlertState(StrEnum):
    ACTIVE = "active"
    CLEARED = "cleared"


# Danger tiers (prototype ranking chosen by the team, not official policy). Lower is more
# dangerous. Tiers 1-3 are stop-work alerts; ADVISORY_TIER is below every stop-work tier.
# The interface shows only the most dangerous tier that has an active alert and merges
# the alerts in that tier. The server still returns every alert; nothing is suppressed.
ADVISORY_TIER = 4
DANGER_TIERS: dict[AlertRule, int] = {
    AlertRule.TORNADO: 1,
    AlertRule.HURRICANE: 1,
    AlertRule.FLASH_FLOOD: 1,
    AlertRule.EARTHQUAKE: 2,
    AlertRule.LIGHTNING_STOP_WORK: 2,
    AlertRule.SEVERE_THUNDERSTORM: 2,
    AlertRule.TROPICAL_STORM: 3,
    AlertRule.FLOOD: 3,
    AlertRule.HEAT: ADVISORY_TIER,
}
EVENT_NAMES: dict[AlertRule, str] = {
    AlertRule.TORNADO: "Tornado Warning",
    AlertRule.HURRICANE: "Hurricane Warning",
    AlertRule.FLASH_FLOOD: "Flash Flood Warning",
    AlertRule.EARTHQUAKE: "Earthquake",
    AlertRule.LIGHTNING_STOP_WORK: "Lightning",
    AlertRule.SEVERE_THUNDERSTORM: "Severe Thunderstorm Warning",
    AlertRule.TROPICAL_STORM: "Tropical Storm Warning",
    AlertRule.FLOOD: "Flood Warning",
    AlertRule.HEAT: "Heat",
}


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
        default=None,
        description=(
            "All-clear time. Lightning: latest strike + 30 minutes. Warnings: null while the "
            "warning is listed, then 30 minutes after a healthy feed stops listing it. "
            "Resets on each new qualifying event."
        ),
    )
    distance_miles: float | None = Field(default=None, ge=0)
    trigger_observation_ids: list[str] = []
    evidence: list[Evidence] = []
    simulated: bool = False
    is_prototype_rule: bool = Field(
        default=False, description="False only for the required lightning rule."
    )
    acknowledgements: list[Acknowledgement] = []
    danger_tier: int = Field(
        default=ADVISORY_TIER,
        ge=1,
        le=ADVISORY_TIER,
        description="Set from the rule by the server. 1 is most dangerous; 4 is an advisory.",
    )
    event_label: str = Field(
        default="", description="Plain event name, e.g. 'Flash Flood Warning'. Set by the server."
    )

    @model_validator(mode="after")
    def _describe(self) -> "Alert":
        # Derived from stored fields, so no database column holds them.
        self.danger_tier = DANGER_TIERS[self.rule]
        if not self.event_label:
            self.event_label = event_label(self)
        return self


def event_label(alert: "Alert") -> str:
    name = EVENT_NAMES[alert.rule]
    miles = alert.distance_miles
    if alert.rule is AlertRule.LIGHTNING_STOP_WORK:
        return f"Lightning {miles:.1f} mi from site" if miles is not None else name
    if alert.rule is AlertRule.EARTHQUAKE:
        latest = alert.evidence[-1].label if alert.evidence else None
        return latest or (f"Earthquake {miles:.0f} mi from site" if miles else name)
    if alert.rule is AlertRule.HURRICANE and miles:
        return f"Hurricane center {miles:.0f} mi from site"
    return name
