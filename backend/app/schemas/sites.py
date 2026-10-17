from datetime import datetime

from pydantic import Field

from app.schemas.alerts import Alert
from app.schemas.common import FactorContribution, RiskLevel, Schema
from app.schemas.hazards import HazardNotice
from app.schemas.observations import Observation
from app.schemas.orgs import TeamRef
from app.schemas.outlook import EventOutlook, EventOutlookCard
from app.schemas.reports import CrewReport
from app.schemas.scores import HazardScore


class SiteSummary(Schema):
    """Item of `GET /api/sites`. Field names are frozen by the AGENTS.md shared contract.

    The list is ordered with assigned sites first, then by risk_score descending.
    `risk_score`, `risk_level`, and `updated_at` are null until the site has a computed
    score. Null means "not scored yet", never "low risk".
    """

    id: str
    name: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    assigned_team: TeamRef | None
    risk_score: float | None = Field(ge=0, le=10)
    risk_level: RiskLevel | None
    updated_at: datetime | None
    active_alerts: int = Field(ge=0)
    top_factors: list[FactorContribution]
    data_completeness: float = Field(ge=0, le=1)
    model_version: str


class SiteDetail(SiteSummary):
    """Response of `GET /api/sites/{id}`."""

    location_type: str = Field(description='e.g. "power_plant".')
    source: str = Field(description='e.g. "EIA-860M (representative power plant location)".')
    region: str | None = None
    observations: list[Observation]
    score: HazardScore | None
    alerts: list[Alert]
    reports: list[CrewReport]
    notices: list[HazardNotice] = []
    event_outlook: EventOutlook | None = Field(
        default=None,
        description="Advisory outlook for a supervisor-confirmed active event. Null when none.",
    )
    event_outlooks: list[EventOutlookCard] = Field(
        default=[],
        description="T050A: one advisory card per confirmed event at the site, keyed by "
        "event_id. Never changes the score, alerts, the lightning timer, or work authorization.",
    )
