"""Frontend fixtures must validate against the schemas and stay in sync with the generator."""

import json

import pytest
from pydantic import TypeAdapter

from app.rules.score import compute_score
from app.schemas import (
    Alert,
    Briefing,
    CrewReport,
    DataState,
    HazardNotice,
    SiteDetail,
    SiteSummary,
)
from scripts.generate_fixtures import (
    ALERTS,
    FIXTURE_RULES,
    FIXTURES,
    NOW,
    OUT_DIR,
    REPORTS,
    SCORES,
    SITE_OBSERVATIONS,
    dump,
)

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


def test_fixture_scores_come_from_rules_without_model_terms() -> None:
    detail = SiteDetail.model_validate(load("site-detail.json"))
    for site in TypeAdapter(list[SiteSummary]).validate_python(load("sites.json")):
        computed = compute_score(
            site.id, SITE_OBSERVATIONS[site.id], ALERTS, REPORTS, NOW, settings=FIXTURE_RULES
        )
        assert computed == SCORES[site.id]
        assert site.model_version == "rules-0.2"
        assert site.risk_score == computed.risk_score
        assert site.risk_level == computed.risk_level
        assert site.updated_at == computed.created_at
        assert site.data_completeness == computed.data_completeness == 0
        assert all(f.factor != "model" for f in computed.factor_contributions)
        assert site.risk_score == round(
            sum(f.contribution for f in computed.factor_contributions), 1
        )
        if site.id == detail.id:
            assert detail.score == computed
            assert detail.top_factors == site.top_factors
    assert all(o.simulated for o in detail.observations)
    assert detail.risk_score == 6.1  # 3 lightning + 1.11 heat + 1 watch + 1 confirmed wildlife


def test_both_briefings_cite_the_same_computed_score() -> None:
    detail = SiteDetail.model_validate(load("site-detail.json"))
    points = {
        f.evidence_id: f.contribution for f in detail.score.factor_contributions if f.contribution
    }
    for briefing in TypeAdapter(list[Briefing]).validate_python(load("briefings.json")):
        assert briefing.risk_score == detail.risk_score
        assert briefing.risk_level == detail.risk_level
        assert briefing.data_completeness == detail.data_completeness == 0
        assert round(sum(h.points or 0 for h in briefing.hazards), 1) == detail.risk_score
        for hazard in briefing.hazards:
            if hazard.points is not None:
                assert hazard.points == sum(points.get(id, 0) for id in hazard.evidence_ids)
        assert any("no current live feed coverage" in u for u in briefing.unknowns)
