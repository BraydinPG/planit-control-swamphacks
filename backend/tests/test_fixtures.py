"""Frontend fixtures must validate against the schemas and stay in sync with the generator."""

import json

import pytest
from pydantic import TypeAdapter

from app.schemas import (
    Alert,
    Briefing,
    CrewReport,
    DataState,
    HazardNotice,
    SiteDetail,
    SiteSummary,
)
from scripts.generate_fixtures import FIXTURES, OUT_DIR, dump

MODELS: dict[str, type] = {
    "sites.json": list[SiteSummary],
    "site-detail.json": SiteDetail,
    "alerts.json": list[Alert],
    "reports.json": list[CrewReport],
    "hazard-notices.json": list[HazardNotice],
    "briefings.json": list[Briefing],
}


def load(name: str) -> object:
    return json.loads((OUT_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(MODELS))
def test_fixture_validates(name: str) -> None:
    TypeAdapter(MODELS[name]).validate_python(load(name))


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_fixture_file_is_up_to_date(name: str) -> None:
    assert load(name) == dump(FIXTURES[name]), (
        f"{name} is out of date; run `python -m scripts.generate_fixtures` from backend/"
    )


def test_sites_ordered_assigned_first_then_risk() -> None:
    sites = TypeAdapter(list[SiteSummary]).validate_python(load("sites.json"))
    keys = [(s.assigned_team is None, -s.risk_score) for s in sites]
    assert keys == sorted(keys)


def test_fixtures_cover_every_data_state() -> None:
    detail = SiteDetail.model_validate(load("site-detail.json"))
    sites = TypeAdapter(list[SiteSummary]).validate_python(load("sites.json"))
    states = {o.data_state for o in detail.observations}
    states |= {f.data_state for s in sites for f in s.top_factors}
    states |= {f.data_state for f in detail.score.factor_contributions}
    assert states == set(DataState)


def test_briefing_claims_cite_supplied_evidence() -> None:
    for briefing in TypeAdapter(list[Briefing]).validate_python(load("briefings.json")):
        supplied = {e.id for e in briefing.evidence}
        for item in [*briefing.hazards, *briefing.recommended_actions]:
            assert set(item.evidence_ids) <= supplied, briefing.id


def test_fallback_and_gemini_variants_present() -> None:
    assert {item["generated_by"] for item in load("briefings.json")} == {"gemini", "fallback"}


def test_lightning_alert_shows_reset_state() -> None:
    alert = next(
        a
        for a in TypeAdapter(list[Alert]).validate_python(load("alerts.json"))
        if a.rule == "lightning_stop_work" and a.state == "active"
    )
    assert alert.latest_event_at > alert.triggered_at
    assert (alert.clear_after - alert.latest_event_at).total_seconds() == 30 * 60
