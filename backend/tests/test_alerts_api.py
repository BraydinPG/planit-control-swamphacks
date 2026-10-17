"""T048: alert listing and acknowledgement, with state persisted across requests."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db, get_now
from app.db import models as db
from app.main import app
from app.rules.lightning import ALL_CLEAR, Transition
from app.schemas import DataState, HazardType, Observation
from app.security import roles
from app.services.alerts import apply_lightning_rule
from tests import auth_fakes
from tests.auth_fakes import bearer, crew, supervisor, token

T0 = datetime(2026, 10, 17, 18, 0, tzinfo=UTC)


def strike(miles: float | None, at: datetime, site: str = "site-a", **extra) -> Observation:
    fields = dict(
        id=f"ltg:{site}:{at.isoformat()}:{miles}",
        site_id=site,
        source="lightning-replay",
        hazard_type=HazardType.LIGHTNING_STRIKE,
        value=miles,
        unit="mi",
        lat=25.8,
        lon=-80.5,
        observed_at=at,
        data_state=DataState.SIMULATED,
        simulated=True,
        label=f"Strike {miles} mi (replay)" if miles is not None else "No replayed strikes",
    )
    return Observation(**(fields | extra))


def seed(session: Session) -> None:
    session.add(db.Organization(id="org-1", name="Sunbelt Utility"))
    for site_id in ("site-a", "site-b"):
        session.add(
            db.Site(
                id=site_id,
                name=site_id,
                lat=25.76,
                lon=-80.49,
                location_type="power_plant",
                source="EIA-860M (representative)",
            )
        )
    session.flush()
    session.add_all(
        [
            db.Team(id="team-a", organization_id="org-1", name="Crew A", site_id="site-a"),
            db.Team(id="team-b", organization_id="org-1", name="Crew B", site_id="site-b"),
        ]
    )
    session.flush()
    session.add_all(
        [
            db.Membership(
                id="m-a",
                user_id="auth0|crew-a",
                organization_id="org-1",
                team_id="team-a",
                role="crew",
            ),
            db.Membership(
                id="m-b",
                user_id="auth0|crew-b",
                organization_id="org-1",
                team_id="team-b",
                role="crew",
            ),
            db.Membership(
                id="m-s", user_id="auth0|supervisor-1", organization_id="org-1", role="supervisor"
            ),
        ]
    )
    session.commit()


class Harness:
    """A fresh session per request, so state must persist in the database to be seen."""

    def __init__(self) -> None:
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        db.Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.now = T0
        with self.factory() as session:
            seed(session)

    def apply(self, observations: list[Observation], site: str = "site-a"):
        with self.factory() as session:
            return apply_lightning_rule(session, site, observations, self.now)

    def override_db(self) -> Iterator[Session]:
        with self.factory() as session:
            yield session


@pytest.fixture
def h() -> Iterator[Harness]:
    harness = Harness()
    app.dependency_overrides[get_db] = harness.override_db
    app.dependency_overrides[get_now] = lambda: harness.now
    auth_fakes.install(app)
    try:
        yield harness
    finally:
        app.dependency_overrides.clear()
        harness.engine.dispose()


@pytest.fixture
def client(h: Harness) -> TestClient:
    return TestClient(app, headers=supervisor())


# ---- rule results persist ----


def test_triggered_alert_is_persisted_and_listed(h: Harness, client: TestClient) -> None:
    result = h.apply([strike(6.8, T0)])
    assert result.transition is Transition.TRIGGERED
    [alert] = client.get("/api/alerts").json()
    assert alert["id"] == result.alert.id
    assert alert["state"] == "active"
    assert alert["rule"] == "lightning_stop_work"
    assert alert["clear_after"] == (T0 + ALL_CLEAR).isoformat().replace("+00:00", "Z")
    assert alert["simulated"] is True
    assert alert["evidence"][0]["id"] == f"ltg:site-a:{T0.isoformat()}:6.8"


def test_reset_persists_new_clear_after_on_the_same_alert(h, client) -> None:
    first = h.apply([strike(6.8, T0)]).alert
    h.now = T0 + timedelta(minutes=12)
    result = h.apply([strike(6.8, T0), strike(4.2, h.now)])
    assert result.transition is Transition.RESET
    [alert] = client.get("/api/alerts").json()
    assert alert["id"] == first.id
    assert alert["latest_event_at"].startswith("2026-10-17T18:12")
    assert alert["clear_after"].startswith("2026-10-17T18:42")
    assert len(alert["trigger_observation_ids"]) == 2


def test_cleared_state_persists(h, client) -> None:
    h.apply([strike(6.8, T0)])
    h.now = T0 + ALL_CLEAR
    assert h.apply([strike(None, h.now)]).transition is Transition.CLEARED
    assert client.get("/api/alerts").json() == []
    [cleared] = client.get("/api/alerts", params={"state": "cleared"}).json()
    assert cleared["state"] == "cleared"


def test_held_alert_writes_nothing_and_stays_active(h, client) -> None:
    h.apply([strike(6.8, T0)])
    h.now = T0 + ALL_CLEAR + timedelta(minutes=5)
    result = h.apply([strike(None, h.now, data_state=DataState.UNAVAILABLE)])
    assert result.transition is Transition.HELD
    [alert] = client.get("/api/alerts").json()
    assert alert["state"] == "active"


def test_rule_transitions_are_audited(h) -> None:
    h.apply([strike(6.8, T0)])
    h.now = T0 + timedelta(minutes=5)
    h.apply([strike(4.0, h.now)])
    h.now += ALL_CLEAR
    h.apply([strike(None, h.now)])
    with h.factory() as session:
        actions = [e.action for e in session.scalars(select(db.AuditEvent))]
    assert sorted(actions) == ["alert.cleared", "alert.reset", "alert.triggered"]


# ---- listing ----


def test_filters_by_site_and_state(h, client) -> None:
    h.apply([strike(6.8, T0)])
    h.apply([strike(5.0, T0, site="site-b")], site="site-b")
    assert len(client.get("/api/alerts").json()) == 2
    [only_b] = client.get("/api/alerts", params={"site_id": "site-b"}).json()
    assert only_b["site_id"] == "site-b"
    assert len(client.get("/api/alerts", params={"state": "all"}).json()) == 2


def test_crew_see_only_their_teams_alerts(h, client) -> None:
    h.apply([strike(6.8, T0)])
    h.apply([strike(5.0, T0, site="site-b")], site="site-b")
    alerts = client.get("/api/alerts", headers=crew("auth0|crew-a")).json()
    assert [a["site_id"] for a in alerts] == ["site-a"]


def test_listing_requires_a_token(h) -> None:
    assert TestClient(app).get("/api/alerts").status_code == 401


# ---- acknowledgement ----


def test_acknowledgement_persists_user_and_time(h, client) -> None:
    alert_id = h.apply([strike(6.8, T0)]).alert.id
    h.now = T0 + timedelta(minutes=2)
    response = client.post(f"/api/alerts/{alert_id}/acknowledge", headers=crew("auth0|crew-a"))
    assert response.status_code == 200
    [ack] = response.json()["acknowledgements"]
    assert ack["user_id"] == "auth0|crew-a"
    assert ack["acknowledged_at"].startswith("2026-10-17T18:02")
    # A later, separate request still sees it.
    [listed] = client.get("/api/alerts").json()
    assert listed["acknowledgements"] == [ack]


def test_repeat_acknowledgement_is_not_duplicated(h, client) -> None:
    alert_id = h.apply([strike(6.8, T0)]).alert.id
    for _ in range(2):
        client.post(f"/api/alerts/{alert_id}/acknowledge", headers=crew("auth0|crew-a"))
    supervisor_ack = client.post(f"/api/alerts/{alert_id}/acknowledge")
    users = [a["user_id"] for a in supervisor_ack.json()["acknowledgements"]]
    assert sorted(users) == ["auth0|crew-a", "auth0|supervisor-1"]


def test_acknowledgement_survives_a_timer_reset(h, client) -> None:
    alert_id = h.apply([strike(6.8, T0)]).alert.id
    client.post(f"/api/alerts/{alert_id}/acknowledge", headers=crew("auth0|crew-a"))
    h.now = T0 + timedelta(minutes=10)
    h.apply([strike(3.0, h.now)])
    [alert] = client.get("/api/alerts").json()
    assert [a["user_id"] for a in alert["acknowledgements"]] == ["auth0|crew-a"]


def test_crew_cannot_acknowledge_another_teams_alert(h, client) -> None:
    alert_id = h.apply([strike(5.0, T0, site="site-b")], site="site-b").alert.id
    response = client.post(f"/api/alerts/{alert_id}/acknowledge", headers=crew("auth0|crew-a"))
    assert response.status_code == 403


def test_acknowledge_needs_the_permission(h, client) -> None:
    alert_id = h.apply([strike(6.8, T0)]).alert.id
    limited = bearer(token(["crew"], permissions=[roles.READ_ASSIGNED_SITES], sub="auth0|crew-a"))
    response = client.post(f"/api/alerts/{alert_id}/acknowledge", headers=limited)
    assert response.status_code == 403


def test_unknown_alert_is_404_and_cleared_alert_is_409(h, client) -> None:
    assert client.post("/api/alerts/nope/acknowledge").status_code == 404
    alert_id = h.apply([strike(6.8, T0)]).alert.id
    h.now = T0 + ALL_CLEAR
    h.apply([strike(None, h.now)])
    assert client.post(f"/api/alerts/{alert_id}/acknowledge").status_code == 409


def test_acknowledgement_is_audited(h, client) -> None:
    alert_id = h.apply([strike(6.8, T0)]).alert.id
    client.post(f"/api/alerts/{alert_id}/acknowledge", headers=crew("auth0|crew-a"))
    with h.factory() as session:
        events = list(
            session.scalars(
                select(db.AuditEvent).where(db.AuditEvent.action == "alert.acknowledge")
            )
        )
    assert [(e.actor, e.entity) for e in events] == [("auth0|crew-a", alert_id)]
