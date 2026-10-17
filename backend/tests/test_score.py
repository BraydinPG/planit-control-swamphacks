"""T051: final 0–10 score from deterministic factors and confirmed reports."""

from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db, get_now
from app.db import models as db
from app.ingestion.nws_alerts import NO_ACTIVE_ALERTS
from app.ingestion.nws_weather import HEAT_INDEX
from app.main import app
from app.rules.score import MODEL_VERSION, compute_score, risk_level
from app.rules.settings import RuleSettings
from app.schemas import (
    Alert,
    CrewReport,
    DataState,
    HazardType,
    Observation,
    RiskLevel,
)
from app.services.scoring import score_site
from tests import auth_fakes
from tests.nws_fakes import NOW

SETTINGS = RuleSettings(_env_file=None)
SITE = "site-demo"


def obs(hazard_type, label, value, state=DataState.OBSERVED, **extra) -> Observation:
    return Observation(
        id=f"{hazard_type}:{label}:{value}",
        site_id=SITE,
        source=extra.pop("source", "NWS"),
        hazard_type=hazard_type,
        value=value,
        label=label,
        lat=25.76,
        lon=-80.49,
        observed_at=NOW - timedelta(minutes=10),
        data_state=state,
        **extra,
    )


def heat(value=110.0, state=DataState.OBSERVED):
    return obs(HazardType.WEATHER, HEAT_INDEX, value, state, unit="°F")


def flood(value=None, state=DataState.OBSERVED):
    return obs(HazardType.FLOOD_ALERT, value or NO_ACTIVE_ALERTS, value, state)


def no_lightning(state=DataState.SIMULATED):
    return obs(
        HazardType.LIGHTNING_STRIKE,
        "No strikes",
        None,
        state,
        source="lightning-replay" if state == DataState.SIMULATED else "GOES GLM",
        simulated=state == DataState.SIMULATED,
    )


def lightning_alert(state="active") -> Alert:
    return Alert(
        id="ltg-alert:1",
        site_id=SITE,
        rule="lightning_stop_work",
        state=state,
        triggered_at=NOW - timedelta(minutes=12),
        latest_event_at=NOW - timedelta(minutes=3),
        clear_after=NOW + timedelta(minutes=27),
        distance_miles=4.2,
        simulated=True,
    )


def report(status="confirmed", present=True, severity="high") -> CrewReport:
    return CrewReport(
        id=f"report-{status}-{present}-{severity}",
        organization_id="org-1",
        team_id="team-a",
        site_id=SITE,
        reporter_id="crew-1",
        category="broken_pole_downed_line",
        hazard_present=present,
        lat=25.76,
        lon=-80.49,
        review_status=status,
        confirmed_severity=severity if status == "confirmed" else None,
        created_at=NOW - timedelta(minutes=30),
    )


def score(observations=(), alerts=(), reports=()):
    return compute_score(SITE, list(observations), list(alerts), list(reports), NOW, None, SETTINGS)


def points(result, factor: str) -> list[float]:
    return [f.contribution for f in result.factor_contributions if f.factor == factor]


# ---- pure score ----


@pytest.mark.parametrize(
    ("value", "level"),
    [(0, "low"), (2.9, "low"), (3, "moderate"), (5.9, "moderate"), (6, "high"), (8, "critical")],
)
def test_risk_level_bands(value, level) -> None:
    assert risk_level(value) is RiskLevel(level)


def test_score_sums_factors_with_contributions() -> None:
    result = score([heat(110.0), flood("Flood Watch"), no_lightning()], [lightning_alert()])
    # lightning 3.0 + heat 110 °F (0.5 + 1.5 * 7/22 ≈ 0.98) + flood watch 1.0
    assert result.risk_score == 5.0
    assert result.risk_level is RiskLevel.MODERATE
    assert {f.factor for f in result.factor_contributions} == {"lightning", "heat_index", "flood"}
    assert all(f.is_prototype for f in result.factor_contributions)
    assert result.model_version == MODEL_VERSION


def test_score_is_capped_at_10() -> None:
    reports = [report(severity="high").model_copy(update={"id": f"report-{i}"}) for i in range(10)]
    result = score(
        [heat(125.0), flood("Flood Warning"), no_lightning()], [lightning_alert()], reports
    )
    assert result.risk_score == 10.0
    assert result.risk_level is RiskLevel.CRITICAL


def test_only_confirmed_present_reports_count() -> None:
    reports = [
        report("confirmed", True, "high"),
        report("confirmed", False, "high"),
        report("pending", True),
        report("rejected", True),
    ]
    result = score([heat(90.0), flood(), no_lightning()], [], reports)
    assert points(result, "crew_report") == [1.5]
    assert result.risk_score == 1.5


def test_cleared_lightning_alert_adds_nothing() -> None:
    result = score([heat(90.0), flood(), no_lightning()], [lightning_alert("cleared")])
    assert points(result, "lightning") == [0.0]


def test_all_inputs_current_gives_full_completeness() -> None:
    result = score([heat(90.0), flood(), no_lightning(DataState.OBSERVED)])
    assert result.data_completeness == 1.0
    assert result.confidence == 1.0
    assert result.risk_score == 0.0


def test_missing_inputs_lower_completeness_and_stay_visible() -> None:
    result = score([heat(90.0)])
    assert result.data_completeness == pytest.approx(0.33)
    states = {f.factor: f.data_state for f in result.factor_contributions}
    assert states["flood"] is DataState.UNAVAILABLE
    assert states["lightning"] is DataState.UNAVAILABLE
    assert result.risk_score == 0.0  # unknown, not safe: completeness shows the gap


def test_stale_inputs_count_but_lower_completeness() -> None:
    result = score(
        [
            heat(110.0, DataState.STALE),
            flood("Flood Warning", DataState.STALE),
            no_lightning(DataState.STALE),
        ]
    )
    assert result.data_completeness == 0.0
    assert result.risk_score > 0


def test_model_component_is_excluded() -> None:
    result = score([heat(90.0), flood(), no_lightning()])
    assert "model" not in {f.factor for f in result.factor_contributions}
    assert result.model_is_fallback is False


def test_score_is_deterministic() -> None:
    inputs = ([heat(110.0), flood("Flood Watch"), no_lightning()], [lightning_alert()])
    assert score(*inputs) == score(*inputs)


# ---- stored score appears in GET /api/sites ----


@pytest.fixture
def session_factory() -> Iterator[sessionmaker]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    db.Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


def seed(session: Session) -> None:
    session.add(
        db.Site(
            id=SITE,
            name="Demo Plant",
            lat=25.76,
            lon=-80.49,
            location_type="power_plant",
            source="EIA-860M August 2026 (representative power plant location)",
        )
    )
    common = dict(site_id=SITE, lat=25.76, lon=-80.49, fetched_at=NOW - timedelta(minutes=5))
    session.add_all(
        [
            db.Observation(
                id="hi",
                source="NWS",
                hazard_type="weather",
                value="110.0",
                unit="°F",
                label=HEAT_INDEX,
                observed_at=NOW - timedelta(minutes=20),
                data_state="observed",
                **common,
            ),
            db.Observation(
                id="fw",
                source="NWS",
                hazard_type="flood_alert",
                value="Flood Watch",
                label="Flood Watch",
                observed_at=NOW - timedelta(minutes=90),
                data_state="observed",
                **common,
            ),
            db.Observation(
                id="ltg",
                source="lightning-replay",
                hazard_type="lightning_strike",
                value=None,
                label="No replayed strikes",
                simulated=True,
                observed_at=NOW - timedelta(minutes=1),
                data_state="simulated",
                **common,
            ),
            db.Alert(
                id="ltg-alert:1",
                site_id=SITE,
                rule="lightning_stop_work",
                state="active",
                triggered_at=NOW - timedelta(minutes=12),
                latest_event_at=NOW - timedelta(minutes=3),
                clear_after=NOW + timedelta(minutes=27),
                distance_miles=4.2,
                simulated=True,
            ),
        ]
    )
    session.commit()


def test_stored_score_is_returned_by_sites_api(session_factory) -> None:
    with session_factory() as session:
        seed(session)
        first = score_site(session, SITE, NOW - timedelta(minutes=30), SETTINGS)
        second = score_site(session, SITE, NOW, SETTINGS)
    assert second.previous_score == first.risk_score

    def override() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override
    app.dependency_overrides[get_now] = lambda: NOW
    auth_fakes.install(app)
    try:
        client = TestClient(app, headers=auth_fakes.supervisor())
        [summary] = client.get("/api/sites").json()
        detail = client.get(f"/api/sites/{SITE}").json()
    finally:
        app.dependency_overrides.clear()

    assert summary["risk_score"] == second.risk_score == 5.0
    assert summary["risk_level"] == "moderate"
    assert summary["model_version"] == MODEL_VERSION
    assert summary["data_completeness"] == 0.67  # replay is not live coverage
    assert [f["factor"] for f in summary["top_factors"]] == ["lightning", "flood", "heat_index"]
    contributions = detail["score"]["factor_contributions"]
    assert {f["factor"] for f in contributions} == {"lightning", "heat_index", "flood"}
    assert all(f["source"] and f["is_prototype"] for f in contributions)
    assert detail["score"]["previous_score"] == first.risk_score
