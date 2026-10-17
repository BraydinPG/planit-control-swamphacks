"""The Site Hazard Index reaches the API, ranking, and briefings unchanged.

Controlled checks on in-memory SQLite with fake JWTs: no Tiger Data, Auth0, or provider
request. They cover what the frontend reads, not live persistence.
"""

from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_now
from app.api.sites import _sort_key
from app.db import models as db
from app.demo import DEMO_SITE_ID
from app.gemini import briefings
from app.main import app
from app.outlook import get_event_outlook_service
from app.rules.score import MODEL_VERSION
from app.schemas import (
    DataState,
    FactorContribution,
    GeneratedBy,
    HazardScore,
    RiskLevel,
    SiteSummary,
    TeamRef,
)
from tests import auth_fakes
from tests.auth_fakes import crew, supervisor
from tests.test_briefings import EVENING_EAST, NO_GEMINI, generate
from tests.test_briefings import factory as briefing_factory  # noqa: F401
from tests.test_demo_seed import CREW, NOW, OUTLOOKS, SUPERVISOR, factory, seeded  # noqa: F401


@pytest.fixture
def api(seeded) -> Iterator[TestClient]:  # noqa: F811
    def override_db() -> Iterator[Session]:
        with seeded() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_now] = lambda: NOW + timedelta(minutes=1)
    app.dependency_overrides[get_event_outlook_service] = lambda: OUTLOOKS
    auth_fakes.install(app)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# ---- ranking: an unknown zero is not safer than an observed zero ----


def summary(name: str, score: float | None, completeness: float, team: bool = False):
    return SiteSummary(
        id=name, name=name, lat=27.0, lon=-82.0,
        assigned_team=TeamRef(id="t", name="Team", organization_id="o") if team else None,
        risk_score=score, risk_level=None if score is None else RiskLevel.LOW,
        updated_at=None, active_alerts=0, top_factors=[],
        data_completeness=completeness, model_version=MODEL_VERSION,
    )  # fmt: skip


def test_equal_scores_rank_less_evidence_first() -> None:
    sites = [
        summary("a-observed-zero", 0.0, 1.0),
        summary("b-unknown-zero", 0.0, 0.0),
        summary("c-partial-zero", 0.0, 0.67),
        summary("d-unscored", None, 0.0),
        summary("e-higher", 2.0, 1.0),
        summary("z-assigned", 0.0, 1.0, team=True),
    ]
    order = [s.id for s in sorted(sites, key=_sort_key)]
    assert order == [
        "z-assigned",
        "e-higher",
        "b-unknown-zero",
        "c-partial-zero",
        "a-observed-zero",
        "d-unscored",
    ]


# ---- T069: one stored score everywhere the frontend reads it ----


@pytest.mark.parametrize("headers", [crew(CREW), supervisor(SUPERVISOR)], ids=["crew", "sup"])
def test_demo_score_matches_across_list_detail_db_and_briefing(api, seeded, headers) -> None:  # noqa: F811
    [listed] = [s for s in api.get("/api/sites", headers=headers).json() if s["id"] == DEMO_SITE_ID]
    detail = api.get(f"/api/sites/{DEMO_SITE_ID}", headers=headers).json()
    briefing = api.get(f"/api/sites/{DEMO_SITE_ID}/briefing", headers=headers).json()
    with seeded() as session:
        latest = session.scalars(
            select(db.HazardScore)
            .where(db.HazardScore.site_id == DEMO_SITE_ID)
            .order_by(db.HazardScore.created_at.desc())
        ).first()

    stored = detail["score"]
    assert stored["model_version"] == MODEL_VERSION == "rules-0.2"
    for view in (listed, detail):
        assert view["risk_score"] == stored["risk_score"] == latest.risk_score
        assert view["risk_level"] == stored["risk_level"] == latest.risk_level
        assert view["data_completeness"] == stored["data_completeness"]
        assert view["model_version"] == MODEL_VERSION
    assert stored["factor_contributions"] == latest.factor_contributions
    top = listed["top_factors"]
    assert 0 < len(top) <= 3 and all(f in stored["factor_contributions"] for f in top)

    # The briefing snapshot is the stored index; its hazards' points add up to it.
    assert briefing["risk_score"] == latest.risk_score
    assert briefing["risk_level"] == latest.risk_level
    assert briefing["data_completeness"] == latest.data_completeness
    points = sum(h["points"] or 0 for h in briefing["hazards"])
    raw = sum(f["contribution"] for f in stored["factor_contributions"])
    assert points == pytest.approx(raw, abs=0.15)
    assert briefing["risk_score"] == round(min(raw, 10), 1)


def test_demo_replay_is_positive_evidence_with_no_live_coverage(api) -> None:
    detail = api.get(f"/api/sites/{DEMO_SITE_ID}", headers=supervisor(SUPERVISOR)).json()
    assert detail["risk_score"] > 0 and detail["data_completeness"] == 0
    states = {f["data_state"] for f in detail["score"]["factor_contributions"]}
    assert DataState.SIMULATED in states and DataState.OBSERVED not in states
    briefing = api.get(f"/api/sites/{DEMO_SITE_ID}/briefing", headers=supervisor(SUPERVISOR))
    assert any("not evidence of low risk" in u for u in briefing.json()["unknowns"])


# ---- briefings label incomplete evidence and keep stale points ----


def score_with(factors: list[FactorContribution], completeness: float) -> HazardScore:
    raw = sum(f.contribution for f in factors)
    return HazardScore(
        site_id="site-ny", risk_score=round(min(raw, 10), 1),
        risk_level=RiskLevel.LOW if raw < 3 else RiskLevel.MODERATE,
        factor_contributions=factors, model_version=MODEL_VERSION, model_is_fallback=False,
        confidence=completeness, data_completeness=completeness, created_at=EVENING_EAST,
    )  # fmt: skip


def stale_heat() -> FactorContribution:
    return FactorContribution(
        factor="heat_index", label="Heat index 112 °F [stale; not live coverage]",
        contribution=1.11, source="NWS", observed_at=EVENING_EAST - timedelta(hours=2),
        data_state=DataState.STALE, is_prototype=True, evidence_id="obs-heat",
    )  # fmt: skip


def test_stale_points_stay_in_briefing_hazards_and_are_listed_unknown(
    briefing_factory,  # noqa: F811
    monkeypatch,
) -> None:
    score = score_with([stale_heat()], 0.33)
    monkeypatch.setattr(briefings, "score_site", lambda *a, **k: score)
    briefing = generate(briefing_factory, NO_GEMINI)
    assert briefing.generated_by == GeneratedBy.FALLBACK
    assert briefing.risk_score == 1.1
    assert sum(h.points or 0 for h in briefing.hazards) == pytest.approx(1.1, abs=0.05)
    assert any("stale" in u for u in briefing.unknowns)
    assert any("33%" in u and "understate" in u for u in briefing.unknowns)


def test_zero_with_no_evidence_is_labelled_not_low(briefing_factory, monkeypatch) -> None:  # noqa: F811
    unavailable = FactorContribution(
        factor="heat_index", label="Heat index unavailable", contribution=0, source="NWS",
        data_state=DataState.UNAVAILABLE,
    )  # fmt: skip
    score = score_with([unavailable], 0.0)
    monkeypatch.setattr(briefings, "score_site", lambda *a, **k: score)
    briefing = generate(briefing_factory, NO_GEMINI)
    assert (briefing.risk_score, briefing.data_completeness) == (0.0, 0.0)
    assert any("not evidence of low risk" in u for u in briefing.unknowns)
