"""T041 `GET /api/sites` and T042 `GET /api/sites/{id}` against an in-memory database."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db, get_now
from app.db import models as db
from app.main import app
from app.schemas import SiteDetail, SiteSummary

NOW = datetime(2026, 10, 17, 18, 0, tzinfo=UTC)
SOURCE = "EIA-860M August 2026 (representative power plant location)"


def ago(**kwargs: float) -> datetime:
    return NOW - timedelta(**kwargs)


def factor(name: str, contribution: float) -> dict:
    return {
        "factor": name,
        "label": name,
        "contribution": contribution,
        "source": "NWS",
        "data_state": "observed",
    }


def site(site_id: str, name: str, lat: float = 25.76, lon: float = -80.49) -> db.Site:
    return db.Site(
        id=site_id, name=name, lat=lat, lon=lon, location_type="power_plant", source=SOURCE
    )


def score(site_id: str, risk: float, created_at: datetime, factors: list[dict]) -> db.HazardScore:
    return db.HazardScore(
        id=f"score-{site_id}-{created_at.isoformat()}",
        site_id=site_id,
        risk_score=risk,
        risk_level="high" if risk >= 6 else "low",
        factor_contributions=factors,
        model_version="rules-0.1",
        model_is_fallback=False,
        confidence=0.7,
        data_completeness=0.8,
        created_at=created_at,
    )


def seed(session: Session) -> None:
    session.add(db.Organization(id="org-1", name="Sunbelt Utility"))
    session.add_all(
        [
            site("site-a", "Alpha Plant"),
            site("site-b", "Bravo Plant", 26.1, -81.2),
            site("site-c", "Charlie Plant", 27.9, -82.4),
            site("site-d", "Delta Plant", 28.5, -81.3),
        ]
    )
    session.flush()
    session.add_all(
        [
            db.Team(id="team-a", organization_id="org-1", name="Line Crew A", site_id="site-a"),
            db.Team(id="team-b", organization_id="org-1", name="Crew B", site_id="site-b"),
        ]
    )
    session.add_all(
        [
            score("site-a", 4.0, ago(hours=5), [factor("old", 4.0)]),
            score(
                "site-a",
                7.5,
                ago(minutes=5),
                [
                    factor("small", 0.5),
                    factor("lightning", 3.0),
                    factor("heat", 1.5),
                    factor("flood", 1.0),
                ],
            ),
            score("site-c", 9.0, ago(minutes=10), [factor("heat", 9.0)]),
        ]
    )
    session.add_all(
        [
            db.Alert(
                id="alert-1",
                site_id="site-a",
                rule="lightning_stop_work",
                state="active",
                triggered_at=ago(minutes=12),
                latest_event_at=ago(minutes=3),
                clear_after=NOW + timedelta(minutes=27),
                distance_miles=4.2,
                trigger_observation_ids=["obs-ltg"],
                evidence=[{"id": "obs-ltg", "kind": "observation", "label": "Strike"}],
                simulated=True,
            ),
            db.Alert(
                id="alert-2",
                site_id="site-a",
                rule="flood",
                state="cleared",
                triggered_at=ago(hours=3),
                latest_event_at=ago(hours=3),
                is_prototype_rule=True,
            ),
            db.Acknowledgement(
                id="ack-1", alert_id="alert-1", user_id="crew-1", acknowledged_at=ago(minutes=10)
            ),
        ]
    )
    obs = dict(site_id="site-a", source="NWS", lat=25.76, lon=-80.49)
    session.add_all(
        [
            db.Observation(
                id="obs-fresh",
                hazard_type="weather",
                value="93.9",
                unit="°F",
                label="Temperature",
                observed_at=ago(minutes=20),
                fetched_at=ago(minutes=15),
                data_state="observed",
                **obs,
            ),
            db.Observation(
                id="obs-old",
                hazard_type="weather",
                value="90.0",
                unit="°F",
                label="Temperature",
                observed_at=ago(hours=3),
                fetched_at=ago(hours=3),
                data_state="observed",
                **obs,
            ),
            db.Observation(
                id="obs-expired",
                hazard_type="weather",
                value="88.0",
                observed_at=ago(hours=30),
                data_state="observed",
                **obs,
            ),
            db.Observation(
                id="obs-forecast",
                hazard_type="forecast",
                value="99.0",
                unit="°F",
                label="Temperature",
                observed_at=ago(hours=26),
                valid_at=NOW + timedelta(hours=2),
                fetched_at=ago(minutes=15),
                data_state="forecast",
                **obs,
            ),
            db.Observation(
                id="obs-flood",
                hazard_type="flood_alert",
                value="Flood Watch",
                label="Flood Watch",
                observed_at=ago(minutes=90),
                fetched_at=ago(minutes=15),
                data_state="observed",
                **obs,
            ),
        ]
    )
    session.add(
        db.CrewReport(
            id="report-1",
            organization_id="org-1",
            team_id="team-a",
            site_id="site-a",
            reporter_id="crew-1",
            category="broken_pole_downed_line",
            hazard_present=True,
            lat=25.761,
            lon=-80.491,
            review_status="pending",
            created_at=ago(minutes=6),
        )
    )
    notice = dict(
        source="crew_report",
        source_ref="report-1",
        radius_source="default",
        status="potential",
        created_at=ago(minutes=6),
    )
    session.add_all(
        [
            db.HazardNotice(
                id="notice-near",
                hazard_label="broken electrical pole",
                lat=25.77,
                lon=-80.49,
                radius_miles=1,
                **notice,
            ),
            db.HazardNotice(
                id="notice-far",
                hazard_label="wildlife",
                lat=26.5,
                lon=-80.49,
                radius_miles=1,
                **notice,
            ),
        ]
    )
    session.commit()


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    db.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        seed(session)

    def override_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_now] = lambda: NOW
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


# ---- T041 ----


def test_list_validates_against_contract(client: TestClient) -> None:
    response = client.get("/api/sites")
    assert response.status_code == 200
    sites = TypeAdapter(list[SiteSummary]).validate_python(response.json())
    assert len(sites) == 4


def test_list_orders_assigned_first_then_risk_then_unscored(client: TestClient) -> None:
    ids = [s["id"] for s in client.get("/api/sites").json()]
    # site-a (team, 7.5), site-b (team, unscored), site-c (no team, 9.0), site-d (no team, unscored)
    assert ids == ["site-a", "site-b", "site-c", "site-d"]


def test_list_includes_assigned_team(client: TestClient) -> None:
    by_id = {s["id"]: s for s in client.get("/api/sites").json()}
    assert by_id["site-a"]["assigned_team"] == {
        "id": "team-a",
        "name": "Line Crew A",
        "organization_id": "org-1",
    }
    assert by_id["site-c"]["assigned_team"] is None


def test_list_uses_latest_score_and_top_three_factors(client: TestClient) -> None:
    alpha = next(s for s in client.get("/api/sites").json() if s["id"] == "site-a")
    assert alpha["risk_score"] == 7.5
    assert [f["factor"] for f in alpha["top_factors"]] == ["lightning", "heat", "flood"]
    assert alpha["active_alerts"] == 1
    assert alpha["model_version"] == "rules-0.1"


def test_unscored_site_is_null_not_zero_risk(client: TestClient) -> None:
    bravo = next(s for s in client.get("/api/sites").json() if s["id"] == "site-b")
    assert bravo["risk_score"] is None
    assert bravo["risk_level"] is None
    assert bravo["updated_at"] is None
    assert bravo["data_completeness"] == 0.0
    assert bravo["model_version"] == "unscored"


def test_empty_database_returns_empty_list(client: TestClient) -> None:
    def empty_db() -> Iterator[Session]:
        engine = create_engine("sqlite://")
        db.Base.metadata.create_all(engine)
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = empty_db
    assert client.get("/api/sites").json() == []


# ---- T042 ----


def test_detail_validates_and_includes_site_fields(client: TestClient) -> None:
    response = client.get("/api/sites/site-a")
    assert response.status_code == 200
    detail = SiteDetail.model_validate(response.json())
    assert detail.source == SOURCE
    assert detail.location_type == "power_plant"
    assert detail.score is not None and detail.score.risk_score == 7.5
    assert detail.score.previous_score is None


def test_unknown_site_returns_404(client: TestClient) -> None:
    response = client.get("/api/sites/does-not-exist")
    assert response.status_code == 404


def test_detail_observations_window_and_freshness(client: TestClient) -> None:
    observations = {o["id"]: o for o in client.get("/api/sites/site-a").json()["observations"]}
    assert set(observations) == {"obs-fresh", "obs-old", "obs-forecast", "obs-flood"}
    assert observations["obs-fresh"]["data_state"] == "observed"
    assert observations["obs-fresh"]["value"] == 93.9
    assert observations["obs-old"]["data_state"] == "stale"
    assert observations["obs-forecast"]["data_state"] == "forecast"
    assert observations["obs-flood"]["value"] == "Flood Watch"


def test_detail_shows_active_alerts_with_acknowledgements(client: TestClient) -> None:
    alerts = client.get("/api/sites/site-a").json()["alerts"]
    assert [a["id"] for a in alerts] == ["alert-1"]
    assert alerts[0]["acknowledgements"][0]["user_id"] == "crew-1"
    assert alerts[0]["simulated"] is True


def test_detail_includes_reports_and_covering_notices(client: TestClient) -> None:
    detail = client.get("/api/sites/site-a").json()
    assert [r["id"] for r in detail["reports"]] == ["report-1"]
    assert [n["id"] for n in detail["notices"]] == ["notice-near"]
    assert detail["notices"][0]["instruction"] is None


def test_unscored_detail_has_no_score(client: TestClient) -> None:
    detail = client.get("/api/sites/site-b").json()
    assert detail["score"] is None
    assert detail["risk_score"] is None
    assert detail["observations"] == [] and detail["alerts"] == []


def test_missing_database_url_returns_503(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    app.dependency_overrides.clear()
    response = TestClient(app).get("/api/sites")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database is not configured"}
