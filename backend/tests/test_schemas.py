from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas import (
    DataState,
    HazardNotice,
    HazardType,
    Observation,
    SiteDetail,
    SiteSummary,
)

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)

# Field lists copied from the AGENTS.md shared contract and ingestion interface.
SITE_SUMMARY_CONTRACT = {
    "id",
    "name",
    "lat",
    "lon",
    "risk_score",
    "risk_level",
    "updated_at",
    "assigned_team",
    "active_alerts",
    "top_factors",
    "data_completeness",
    "model_version",
}
INGESTION_INTERFACE = {
    "source",
    "hazard_type",
    "value",
    "unit",
    "lat",
    "lon",
    "observed_at",
    "valid_at",
    "data_state",
}


def site_summary(**overrides: object) -> dict:
    return {
        "id": "site-1",
        "name": "Example Site",
        "lat": 27.0,
        "lon": -82.0,
        "assigned_team": None,
        "risk_score": 4.2,
        "risk_level": "moderate",
        "updated_at": NOW,
        "active_alerts": 0,
        "top_factors": [],
        "data_completeness": 0.8,
        "model_version": "baseline-0.1",
        **overrides,
    }


def potential_notice(**overrides: object) -> dict:
    return {
        "id": "notice-1",
        "hazard_label": "broken electrical pole",
        "source": "crew_report",
        "source_ref": "report-1",
        "lat": 27.0,
        "lon": -82.0,
        "radius_miles": 1,
        "radius_source": "default",
        "status": "potential",
        "created_at": NOW,
        **overrides,
    }


def test_site_summary_fields_match_contract() -> None:
    assert set(SiteSummary.model_fields) == SITE_SUMMARY_CONTRACT


def test_site_detail_extends_summary() -> None:
    assert SITE_SUMMARY_CONTRACT <= set(SiteDetail.model_fields)


def test_observation_includes_ingestion_interface() -> None:
    assert INGESTION_INTERFACE <= set(Observation.model_fields)
    required = {name for name, field in Observation.model_fields.items() if field.is_required()}
    assert required <= INGESTION_INTERFACE


def test_hazard_types_match_ingestion_interface() -> None:
    assert {t.value for t in HazardType} == {
        "weather",
        "forecast",
        "flood_alert",
        "flood_gauge",
        "lightning_strike",
        "hurricane",
        "earthquake",
    }


def test_data_states_match_spec() -> None:
    assert {s.value for s in DataState} == {
        "observed",
        "forecast",
        "crew_reported",
        "simulated",
        "stale",
        "unavailable",
    }


def test_valid_site_summary() -> None:
    assert SiteSummary.model_validate(site_summary()).risk_score == 4.2


@pytest.mark.parametrize(
    "overrides",
    [
        {"risk_score": 11},
        {"risk_score": -1},
        {"data_completeness": 1.5},
        {"lat": 91},
        {"risk_level": "unknown"},
        {"unexpected_field": 1},
    ],
)
def test_site_summary_rejects_invalid(overrides: dict) -> None:
    with pytest.raises(ValidationError):
        SiteSummary.model_validate(site_summary(**overrides))


def test_potential_notice_cannot_carry_instruction() -> None:
    HazardNotice.model_validate(potential_notice())
    with pytest.raises(ValidationError):
        HazardNotice.model_validate(potential_notice(instruction="Evacuate"))


def test_notice_radius_capped_at_50_miles() -> None:
    with pytest.raises(ValidationError):
        HazardNotice.model_validate(potential_notice(radius_miles=51))
    with pytest.raises(ValidationError):
        HazardNotice.model_validate(potential_notice(radius_miles=0))
