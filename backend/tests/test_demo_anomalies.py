"""`python -m app.demo anomalies`: crew reports cleared, one demo site per anomaly type."""

import json
from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_now
from app.db import models as db
from app.demo import DEMO_SITE_ID, seed_demo
from app.demo.anomalies import ANOMALIES, seed_anomalies
from app.main import app
from app.outlook import get_event_outlook_service
from app.schemas import ReportCategory
from app.services.reports import Reporter, create_report
from tests import auth_fakes
from tests.auth_fakes import crew, supervisor
from tests.test_demo_seed import ACCOUNTS, CREW, NOW, OUTLOOKS, SUPERVISOR
from tests.test_demo_seed import factory as factory  # noqa: F401


@pytest.fixture
def anomalies(factory, tmp_path):
    with factory() as session:
        seed_demo(session, NOW - timedelta(minutes=10), ACCOUNTS, OUTLOOKS)
        # A rehearsal crew report somewhere else must be cleared too.
        session.add(db.Organization(id="org-other", name="Other"))
        session.add(
            db.Site(id="site-real", name="Real", lat=30.0, lon=-90.0, location_type="power_plant",
                    source="EIA-860M (representative)")
        )  # fmt: skip
        session.flush()
        session.add(
            db.Team(id="team-other", organization_id="org-other", name="T", site_id="site-real")
        )
        session.commit()
        create_report(
            session, Reporter("auth0|someone", "org-other", "team-other"),
            session.get(db.Site, "site-real"), ReportCategory.OTHER, True, 30.0, -90.0,
            None, "photos/x.jpg", NOW - timedelta(minutes=5),
        )  # fmt: skip
        results = seed_anomalies(session, NOW, tmp_path, outlooks=OUTLOOKS)
    return factory, results, tmp_path


@pytest.fixture
def client(anomalies) -> Iterator[TestClient]:
    factory = anomalies[0]

    def override_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_now] = lambda: NOW + timedelta(minutes=1)
    app.dependency_overrides[get_event_outlook_service] = lambda: OUTLOOKS
    auth_fakes.install(app)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_crew_reports_are_cleared_and_backed_up_except_the_everglades_scenario(anomalies) -> None:
    factory, _, backups = anomalies
    with factory() as session:
        reports = list(session.scalars(select(db.CrewReport)))
        assert [(r.id, r.site_id) for r in reports] == [("demo-report-wildlife", DEMO_SITE_ID)]
    [backup] = list(backups.glob("demo-reset-*.json"))
    saved = json.loads(backup.read_text())
    assert {r["site_id"] for r in saved["crew_reports"]} == {"site-real"}


def test_every_anomaly_scores_like_the_live_rules(anomalies) -> None:
    _, results, _ = anomalies
    scores = {r.site_id: r.risk_score for r in results}
    assert len(scores) == len(ANOMALIES) + 1
    for site_id in ("demo-flood", "demo-flash-flood", "demo-heat", "demo-hurricane",
                    "demo-earthquake", "demo-heavy-rain", DEMO_SITE_ID):  # fmt: skip
        assert scores[site_id] > 0, site_id
    # No live feed or rule scores wind or snow, so those stay honest.
    assert scores["demo-high-wind"] == 0 and scores["demo-winter-storm"] == 0


def test_each_site_shows_a_confirmed_event_and_its_duration_card(client) -> None:
    for a in ANOMALIES:
        detail = client.get(f"/api/sites/demo-{a.key}", headers=supervisor(SUPERVISOR)).json()
        [notice] = [n for n in detail["notices"] if n["id"] == f"demo-anomaly-{a.key}"]
        assert notice["status"] == "confirmed" and notice["instruction"] is None
        cards = [c for c in detail["event_outlooks"] if c["notice_id"] == notice["id"]]
        assert cards, a.key
        assert all(o["simulated"] for o in detail["observations"]), a.key
    expected = {
        "flood": "Flood",
        "flash-flood": "Flash Flood",
        "heat": "Heat Index Exceedance",
        "high-wind": "High Wind",
        "heavy-rain": "Heavy Rain",
        "winter-storm": "Winter Storm",
        "hurricane": "Hurricane (Typhoon)",
        "earthquake": "Earthquake",
    }
    for key, event_type in expected.items():
        detail = client.get(f"/api/sites/demo-{key}", headers=supervisor(SUPERVISOR)).json()
        own = [c for c in detail["event_outlooks"] if c["notice_id"] == f"demo-anomaly-{key}"]
        assert [c["event_type"] for c in own] == [event_type], key


def test_the_everglades_wildlife_scenario_is_restored(client) -> None:
    detail = client.get(f"/api/sites/{DEMO_SITE_ID}", headers=crew(CREW)).json()
    [alert] = detail["alerts"]
    assert alert["rule"] == "lightning_stop_work" and alert["state"] == "active"
    [report] = detail["reports"]
    assert (report["category"], report["review_status"]) == ("wildlife", "confirmed")
    notices = {n["id"]: n for n in detail["notices"]}
    assert notices["demo-notice-wildlife"]["instruction"]
    assert notices["demo-notice-flood"]["status"] == "confirmed"
    assert notices["demo-notice-flash-flood"]["status"] == "confirmed"
    factors = {f["factor"] for f in detail["score"]["factor_contributions"]}
    assert {"lightning", "heat_index", "flood"} <= factors
    assert any(f.startswith("crew_report") for f in factors)
    briefing = client.get(f"/api/sites/{DEMO_SITE_ID}/briefing", headers=crew(CREW))
    assert briefing.status_code == 200
    # The anomaly sites never reach the Everglades notices (different places).
    assert all(n["id"].startswith("demo-notice-") for n in detail["notices"])


def test_rudras_seed_still_runs_after_a_notice_is_confirmed_per_organization(anomalies) -> None:
    factory = anomalies[0]
    from app.demo import seed_demo

    with factory() as session:
        session.add(
            db.NoticeAssessment(
                notice_id="demo-notice-flood", organization_id="demo-org",
                confirmed_by=SUPERVISOR, confirmed_at=NOW,
            )
        )  # fmt: skip
        session.commit()
        seed_demo(session, NOW + timedelta(minutes=9), ACCOUNTS, OUTLOOKS)
        assert session.get(db.HazardNotice, "demo-notice-flood") is not None


def test_running_again_gives_the_same_demo(anomalies, tmp_path) -> None:
    factory, first, _ = anomalies
    with factory() as session:
        again = seed_anomalies(
            session, NOW + timedelta(minutes=5), tmp_path / "again", outlooks=OUTLOOKS
        )
        assert session.scalar(select(func.count()).select_from(db.HazardNotice).where(
            db.HazardNotice.id.like("demo-anomaly-%"))) == len(ANOMALIES)  # fmt: skip
        assert session.scalar(select(func.count()).select_from(db.CrewReport)) == 1
    assert [(r.site_id, r.risk_score) for r in again] == [(r.site_id, r.risk_score) for r in first]
