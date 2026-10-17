"""Join codes and the supervisor's team roster."""

import re
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db, get_now
from app.api.teams import ALPHABET, new_code, normalize
from app.db import models as db
from app.main import app
from app.security import roles
from tests import auth_fakes
from tests.auth_fakes import ROLES_CLAIM, bearer, token

NOW = datetime(2026, 10, 17, 18, 0, tzinfo=UTC)
PROFILE = ROLES_CLAIM.rsplit("/", 1)[0] + "/"


def person(sub: str, role: str = "crew", permissions: list[str] | None = None, **profile) -> dict:
    claims = {PROFILE + k: v for k, v in profile.items()}
    if permissions is None:
        permissions = sorted(
            roles.SUPERVISOR_PERMISSIONS if role == "supervisor" else roles.CREW_PERMISSIONS
        )
    return bearer(token([role], permissions, sub=sub, **claims))


SUPERVISOR = person("auth0|sup-1", "supervisor", name="Sam Super", email="sam@example.com")
OTHER_SUPERVISOR = person("auth0|sup-2", "supervisor")


@pytest.fixture
def h() -> Iterator[sessionmaker]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    db.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as s:
        s.add_all(
            [
                db.Organization(id="org-1", name="Sunbelt"),
                db.Organization(id="org-2", name="Coastal"),
                db.Site(
                    id="site-a", name="Alpha Plant", lat=25.7, lon=-80.4,
                    location_type="power_plant", source="test",
                ),
            ]
        )  # fmt: skip
        s.flush()
        s.add_all(
            [
                db.Team(id="team-a", organization_id="org-1", name="Line Crew A", site_id="site-a"),
                db.Team(id="team-b", organization_id="org-1", name="Crew B"),
                db.Team(id="team-x", organization_id="org-2", name="Coastal Crew"),
            ]
        )
        s.flush()
        s.add_all(
            [
                db.Membership(
                    id="m-s1", user_id="auth0|sup-1", organization_id="org-1", role="supervisor"
                ),
                db.Membership(
                    id="m-s2", user_id="auth0|sup-2", organization_id="org-2", role="supervisor"
                ),
            ]
        )
        s.commit()

    def override() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override
    app.dependency_overrides[get_now] = lambda: NOW
    auth_fakes.install(app)
    try:
        yield factory
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


@pytest.fixture
def client(h) -> TestClient:
    return TestClient(app)


def make_code(client, team="team-a", headers=SUPERVISOR) -> str:
    response = client.post(f"/api/teams/{team}/join-codes", headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["code"]


# ---- codes ----


def test_codes_are_xxxx_xxxx_without_confusable_characters() -> None:
    for _ in range(200):
        code = new_code()
        assert re.fullmatch(r"[A-Z2-9]{4}-[A-Z2-9]{4}", code)
        assert not set(code.replace("-", "")) - set(ALPHABET)
        assert not set("01OIL") & set(code)


@pytest.mark.parametrize("typed", ["gtr4f7km", " GTR4 F7KM ", "gtr4-f7km", "GTR4-F7KM"])
def test_typed_codes_are_forgiven(typed: str) -> None:
    assert normalize(typed) == "GTR4-F7KM"


def test_supervisor_creates_a_week_long_code(client) -> None:
    response = client.post("/api/teams/team-a/join-codes", headers=SUPERVISOR)
    body = response.json()
    assert response.status_code == 201
    assert body["team_id"] == "team-a"
    assert body["expires_at"].startswith((NOW + timedelta(days=7)).date().isoformat())


@pytest.mark.parametrize(
    ("team", "headers", "status"),
    [
        ("team-x", SUPERVISOR, 404),  # another organization's team
        ("team-a", person("auth0|crew"), 403),  # crew cannot make codes
        ("team-a", None, 401),
    ],
)
def test_only_the_organizations_supervisor_creates_codes(client, team, headers, status) -> None:
    assert client.post(f"/api/teams/{team}/join-codes", headers=headers).status_code == status


# ---- joining ----


def test_new_crew_account_joins_with_a_code(client, h) -> None:
    code = make_code(client)
    newcomer = person("auth0|new", name="Nia New", email="nia@example.com")
    assert client.get("/api/me", headers=newcomer).json()["organization_id"] is None
    response = client.post("/api/join", json={"code": code.lower()}, headers=newcomer)
    assert response.status_code == 200, response.text
    account = response.json()
    assert (account["organization_id"], account["team_id"], account["site_id"]) == (
        "org-1",
        "team-a",
        "site-a",
    )
    # Joined crew now see their team's site.
    sites = client.get("/api/sites", headers=newcomer).json()
    assert [s["id"] for s in sites] == ["site-a"]
    with h() as s:
        member = s.scalars(select(db.Membership).where(db.Membership.user_id == "auth0|new")).one()
        assert (member.role, member.display_name, member.email) == (
            "crew",
            "Nia New",
            "nia@example.com",
        )
        assert member.joined_at is not None


def test_new_account_with_default_crew_role_and_no_permissions_can_join(client) -> None:
    # The Auth0 Action gives new accounts the crew role before any are assigned in Auth0.
    code = make_code(client)
    newcomer = person("auth0|brand-new", permissions=[])
    assert client.post("/api/join", json={"code": code}, headers=newcomer).status_code == 200
    assert client.get("/api/sites", headers=newcomer).status_code == 200


def test_supervisor_without_permissions_is_not_given_any(client) -> None:
    bare = person("auth0|sup-1", "supervisor", permissions=[])
    assert client.post("/api/teams/team-a/join-codes", headers=bare).status_code == 201
    assert client.get("/api/sites", headers=bare).status_code == 403


@pytest.mark.parametrize(
    ("setup", "status", "reason"),
    [
        ("unknown", 404, "invalid_code"),
        ("revoked", 404, "invalid_code"),
        ("expired", 410, "expired"),
        ("member", 409, "already_member"),
        ("supervisor", 409, "supervisor"),
    ],
)
def test_bad_joins_explain_themselves(client, h, setup, status, reason) -> None:
    code = make_code(client)
    headers = person("auth0|new")
    if setup == "unknown":
        code = "ZZZZ-ZZZZ"
    elif setup == "revoked":
        client.delete(f"/api/join-codes/{code}", headers=SUPERVISOR)
    elif setup == "expired":
        app.dependency_overrides[get_now] = lambda: NOW + timedelta(days=7, seconds=1)
    elif setup == "member":
        client.post("/api/join", json={"code": code}, headers=headers)
    elif setup == "supervisor":
        headers = person("auth0|sup-3", "supervisor")
    response = client.post("/api/join", json={"code": code}, headers=headers)
    assert response.status_code == status
    assert response.json()["detail"]["reason"] == reason


def test_revoking_keeps_people_who_already_joined(client) -> None:
    code = make_code(client)
    client.post("/api/join", json={"code": code}, headers=person("auth0|early"))
    assert client.delete(f"/api/join-codes/{code}", headers=SUPERVISOR).status_code == 204
    roster = client.get("/api/team", headers=SUPERVISOR).json()
    team = next(t for t in roster["teams"] if t["id"] == "team-a")
    assert [m["user_id"] for m in team["members"]] == ["auth0|early"]
    assert team["join_codes"] == []


def test_other_organization_cannot_revoke(client) -> None:
    code = make_code(client)
    assert client.delete(f"/api/join-codes/{code}", headers=OTHER_SUPERVISOR).status_code == 404


# ---- roster ----


def test_supervisor_sees_exactly_who_is_on_each_team(client) -> None:
    code_a = make_code(client)
    make_code(client, team="team-b")
    for sub, name in [("auth0|zed", "Zed"), ("auth0|amy", "Amy")]:
        client.post("/api/join", json={"code": code_a}, headers=person(sub, name=name))
    roster = client.get("/api/team", headers=SUPERVISOR).json()
    assert roster["organization_name"] == "Sunbelt"
    assert [(s["name"], s["email"]) for s in roster["supervisors"]] == [
        ("Sam Super", "sam@example.com")
    ]
    teams = {t["id"]: t for t in roster["teams"]}
    assert set(teams) == {"team-a", "team-b"}  # never another organization's team
    assert [m["name"] for m in teams["team-a"]["members"]] == ["Amy", "Zed"]
    assert teams["team-a"]["site_name"] == "Alpha Plant"
    assert len(teams["team-a"]["join_codes"]) == 1
    assert teams["team-b"]["members"] == [] and len(teams["team-b"]["join_codes"]) == 1


def test_expired_codes_drop_off_the_roster(client) -> None:
    make_code(client)
    app.dependency_overrides[get_now] = lambda: NOW + timedelta(days=8)
    teams = client.get("/api/team", headers=SUPERVISOR).json()["teams"]
    assert all(t["join_codes"] == [] for t in teams)


def test_crew_cannot_read_the_roster(client) -> None:
    assert client.get("/api/team", headers=person("auth0|crew")).status_code == 403


def test_profile_refreshes_from_the_token(client, h) -> None:
    code = make_code(client)
    client.post("/api/join", json={"code": code}, headers=person("auth0|p", name="Old"))
    client.get("/api/me", headers=person("auth0|p", name="New Name", email="p@example.com"))
    with h() as s:
        member = s.scalars(select(db.Membership).where(db.Membership.user_id == "auth0|p")).one()
        assert (member.display_name, member.email) == ("New Name", "p@example.com")
