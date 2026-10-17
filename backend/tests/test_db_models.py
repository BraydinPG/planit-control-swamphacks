from sqlalchemy import CheckConstraint

from app.db.models import (
    Acknowledgement,
    Alert,
    AuditEvent,
    Briefing,
    CrewReport,
    HazardNotice,
    HazardPrediction,
    HazardScore,
    Membership,
    Observation,
    Organization,
    Site,
    Team,
)


def test_models_import() -> None:
    tables = {
        Organization.__tablename__,
        Team.__tablename__,
        Site.__tablename__,
        Observation.__tablename__,
        Alert.__tablename__,
        HazardPrediction.__tablename__,
        HazardScore.__tablename__,
        CrewReport.__tablename__,
        HazardNotice.__tablename__,
        Acknowledgement.__tablename__,
        Briefing.__tablename__,
        AuditEvent.__tablename__,
        Membership.__tablename__,
    }
    assert tables <= set(Organization.metadata.tables)


def test_hypertable_keys_include_time() -> None:
    assert [column.name for column in Observation.__table__.primary_key] == ["id", "observed_at"]
    assert [column.name for column in Alert.__table__.primary_key] == ["id", "triggered_at"]
    assert [column.name for column in AuditEvent.__table__.primary_key] == ["id", "created_at"]
    assert not Acknowledgement.__table__.foreign_keys


def test_membership_rules() -> None:
    assert Team.site_id.unique
    assert Membership.user_id.unique
    checks = [
        constraint.sqltext.text
        for constraint in Membership.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    ]
    assert any("supervisor" in text and "crew" in text for text in checks)
