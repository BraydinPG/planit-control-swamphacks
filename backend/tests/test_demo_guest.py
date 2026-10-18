"""Public "Try demo" guests: read-only access to the demo organization (DEMO_GUEST_ENABLED)."""

from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_now
from app.db import models as db
from app.demo import DEMO_ORG_ID, DEMO_SITE_ID
from app.demo.freshen import ensure_guest_memberships
from app.main import app
from app.outlook import get_event_outlook_service
from tests import auth_fakes
from tests.test_demo_anomalies import anomalies as anomalies  # noqa: F401
from tests.test_demo_anomalies import factory as factory  # noqa: F401
from tests.test_demo_seed import NOW, OUTLOOKS

CREW = {"X-Demo-Role": "crew"}
SUPERVISOR = {"X-Demo-Role": "supervisor"}


@pytest.fixture
def demo(anomalies):  # noqa: F811
    """The seeded demo with guests linked, plus another organization's briefing."""
    factory = anomalies[0]
    with factory() as session:
        assert ensure_guest_memberships(session)
        session.add(
            db.Briefing(
                id="briefing-other", site_id="site-real", organization_id="org-other",
                forecast_window_start=NOW, forecast_window_end=NOW + timedelta(hours=12),
                summary="Other organization", risk_level="low", hazards=[],
                recommended_actions=[], evidence=[], unknowns=[], generated_by="fallback",
                created_at=NOW,
            )
        )  # fmt: skip
        session.commit()
    return factory


def client_for(factory, enabled: bool = True) -> TestClient:
    def override_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_now] = lambda: NOW + timedelta(minutes=1)
    app.dependency_overrides[get_event_outlook_service] = lambda: OUTLOOKS
    auth_fakes.install(app, auth_fakes.settings(demo_guest_enabled=enabled))
    return TestClient(app)


@pytest.fixture
def guest(demo) -> Iterator[TestClient]:
    try:
        yield client_for(demo)
    finally:
        app.dependency_overrides.clear()


def test_guests_are_refused_unless_enabled(demo) -> None:
    try:
        client = client_for(demo, enabled=False)
        assert client.get("/api/sites", headers=SUPERVISOR).status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_an_unknown_guest_role_is_unauthorized(guest) -> None:
    assert guest.get("/api/sites", headers={"X-Demo-Role": "admin"}).status_code == 401
    assert guest.get("/api/sites").status_code == 401


def test_guests_can_only_read(guest) -> None:
    for headers in (CREW, SUPERVISOR):
        writes = [
            guest.post("/api/reports", headers=headers, data={"site_id": DEMO_SITE_ID}),
            guest.post("/api/alerts/any/acknowledge", headers=headers),
            guest.post("/api/join", headers=headers, json={"code": "ABC"}),
            guest.patch("/api/organization", headers=headers, json={"name": "X"}),
            guest.delete("/api/join-codes/ABC", headers=headers),
            guest.post("/api/hazards/any/confirm", headers=headers),
        ]
        assert [r.status_code for r in writes] == [403] * len(writes)
        assert "read-only" in writes[0].json()["detail"]
        assert guest.get("/api/team", headers=headers).status_code == 403
        assert guest.get("/api/supervisor-invites", headers=headers).status_code == 403


def test_guest_crew_sees_only_the_everglades_team(guest) -> None:
    me = guest.get("/api/me", headers=CREW).json()
    assert (me["role"], me["organization_id"], me["site_id"]) == ("crew", DEMO_ORG_ID, DEMO_SITE_ID)
    assert [s["id"] for s in guest.get("/api/sites", headers=CREW).json()] == [DEMO_SITE_ID]
    assert guest.get("/api/sites/demo-flood", headers=CREW).status_code in (403, 404)
    assert guest.get(f"/api/sites/{DEMO_SITE_ID}", headers=CREW).status_code == 200
    reports = guest.get("/api/reports", headers=CREW).json()
    assert reports and {r["site_id"] for r in reports} == {DEMO_SITE_ID}
    assert guest.get(f"/api/sites/{DEMO_SITE_ID}/briefing", headers=CREW).status_code != 403


def test_guest_supervisor_sees_every_site_but_only_demo_reports_and_briefings(guest) -> None:
    sites = {s["id"] for s in guest.get("/api/sites", headers=SUPERVISOR).json()}
    assert {"site-real", "demo-flood", DEMO_SITE_ID} <= sites
    reports = guest.get("/api/reports", headers=SUPERVISOR).json()
    assert reports and all(r["site_id"] != "site-real" for r in reports)
    briefings = guest.get("/api/briefings", headers=SUPERVISOR).json()
    assert briefings and all(b["site_id"] != "site-real" for b in briefings)


def test_guest_memberships_are_idempotent(demo) -> None:
    with demo() as session:
        assert ensure_guest_memberships(session)
        guests = select(func.count()).where(db.Membership.user_id.like("demo-guest|%"))
        assert session.scalar(guests) == 2


def test_guest_memberships_skip_an_unseeded_database() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine("sqlite://", poolclass=StaticPool)
    db.Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        assert ensure_guest_memberships(session) is False
        assert session.scalar(select(func.count()).select_from(db.Membership)) == 0
    engine.dispose()
