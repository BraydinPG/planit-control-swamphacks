"""Tiger Data tables for the published API schemas.

Importing this module does not open a connection. T012 creates the tables and hypertables.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class Organization(Base):
    """One supervisor controls one organization. Many organizations share the deployment."""

    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)

    teams: Mapped[list["Team"]] = relationship(back_populates="organization")
    members: Mapped[list["Membership"]] = relationship(back_populates="organization")


class Site(Base):
    """A monitored location. At most one team is assigned to it."""

    __tablename__ = "sites"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    location_type: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    # IANA time zone, e.g. America/New_York. Filled from the NWS point lookup; drives the
    # 6 PM site-local briefing schedule.
    timezone: Mapped[str | None] = mapped_column(String, nullable=True)

    assigned_team: Mapped["Team | None"] = relationship(back_populates="site", uselist=False)


class Team(Base):
    """A team belongs to one organization and is assigned to one location."""

    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    site_id: Mapped[str | None] = mapped_column(ForeignKey("sites.id"), unique=True, nullable=True)

    organization: Mapped[Organization] = relationship(back_populates="teams")
    site: Mapped[Site | None] = relationship(back_populates="assigned_team")
    members: Mapped[list["Membership"]] = relationship(back_populates="team")


class Membership(Base):
    """A person belongs to one organization. A crew member also belongs to one team."""

    __tablename__ = "memberships"
    __table_args__ = (
        CheckConstraint(
            "(role = 'supervisor' AND team_id IS NULL) OR (role = 'crew' AND team_id IS NOT NULL)",
            name="membership_role_matches_team",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    role: Mapped[str] = mapped_column(String, nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="members")
    team: Mapped[Team | None] = relationship(back_populates="members")


class Observation(Base):
    """Time-ordered feed reading. T012 converts this table to a hypertable."""

    __tablename__ = "observations"
    __table_args__ = (PrimaryKeyConstraint("id", "observed_at"),)

    id: Mapped[str] = mapped_column(String)
    site_id: Mapped[str | None] = mapped_column(ForeignKey("sites.id"), nullable=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    hazard_type: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str | None] = mapped_column(String, nullable=True)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    valid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_state: Mapped[str] = mapped_column(String, nullable=False)
    simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class HazardPrediction(Base):
    """Stored compatibility model output. It is not an approved site-score term."""

    __tablename__ = "hazard_predictions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), nullable=False)
    hazard_probabilities: Mapped[dict] = mapped_column(JSON, nullable=False)
    model_component_0_10: Mapped[float] = mapped_column(Float, nullable=False)
    factor_contributions: Mapped[list] = mapped_column(JSON, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    data_quality: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class HazardScore(Base):
    __tablename__ = "hazard_scores"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String, nullable=False)
    factor_contributions: Mapped[list] = mapped_column(JSON, nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    model_is_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    data_completeness: Mapped[float] = mapped_column(Float, nullable=False)
    previous_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Alert(Base):
    """Deterministic alert. T012 converts this table to a hypertable."""

    __tablename__ = "alerts"
    __table_args__ = (PrimaryKeyConstraint("id", "triggered_at"),)

    id: Mapped[str] = mapped_column(String)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), nullable=False)
    rule: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    latest_event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    clear_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    distance_miles: Mapped[float | None] = mapped_column(Float, nullable=True)
    trigger_observation_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_prototype_rule: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Acknowledgement(Base):
    """Records who acknowledged an alert. alert_id is indexed, not a foreign key.

    Timescale requires the alert time column in every unique key, so a foreign key
    cannot point at alerts.id alone.
    """

    __tablename__ = "acknowledgements"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    alert_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CrewReport(Base):
    __tablename__ = "crew_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), nullable=False)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), nullable=False)
    reporter_id: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    hazard_present: Mapped[bool] = mapped_column(Boolean, nullable=False)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    review_status: Mapped[str] = mapped_column(String, nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_category: Mapped[str | None] = mapped_column(String, nullable=True)
    confirmed_severity: Mapped[str | None] = mapped_column(String, nullable=True)
    location_source: Mapped[str | None] = mapped_column(String, nullable=True)
    location_accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    site_distance_miles: Mapped[float | None] = mapped_column(Float, nullable=True)
    enrichment: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notice_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class HazardNotice(Base):
    """Potential notice. The instruction stays empty until a supervisor sends it."""

    __tablename__ = "hazard_notices"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    hazard_label: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    source_ref: Mapped[str] = mapped_column(String, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    radius_miles: Mapped[float] = mapped_column(Float, nullable=False)
    radius_source: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_by: Mapped[str | None] = mapped_column(String, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suggested_instruction: Mapped[str | None] = mapped_column(String, nullable=True)
    instruction: Mapped[str | None] = mapped_column(String, nullable=True)
    instruction_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class Briefing(Base):
    __tablename__ = "briefings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    site_id: Mapped[str | None] = mapped_column(ForeignKey("sites.id"), nullable=True)
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    forecast_window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    forecast_window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    summary: Mapped[str] = mapped_column(String, nullable=False)
    risk_level: Mapped[str] = mapped_column(String, nullable=False)
    hazards: Mapped[list] = mapped_column(JSON, nullable=False)
    recommended_actions: Mapped[list] = mapped_column(JSON, nullable=False)
    evidence: Mapped[list] = mapped_column(JSON, nullable=False)
    unknowns: Mapped[list] = mapped_column(JSON, nullable=False)
    generated_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuditEvent(Base):
    """Time-ordered audit row. T012 converts this table to a hypertable."""

    __tablename__ = "audit_events"
    __table_args__ = (
        PrimaryKeyConstraint("id", "created_at"),
        UniqueConstraint("actor", "action", "entity", "created_at"),
    )

    id: Mapped[str] = mapped_column(String)
    actor: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    entity: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
