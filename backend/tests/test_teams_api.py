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


# ---- managing teams: a supervisor runs several ----


def test_supervisor_adds_teams_at_free_sites(client, h) -> None:
    with h() as s:
        s.add(
            db.Site(
                id="site-b", name="Bravo Plant", lat=26.0, lon=-80.2,
                location_type="power_plant", source="test",
            )
        )  # fmt: skip
        s.commit()
    response = client.post(
        "/api/teams", json={"name": " Night Crew ", "site_id": "site-b"}, headers=SUPERVISOR
    )
    assert response.status_code == 201, response.text
    team = response.json()
    assert (team["name"], team["site_name"], team["members"]) == ("Night Crew", "Bravo Plant", [])
    teams = client.get("/api/team", headers=SUPERVISOR).json()["teams"]
    assert {t["name"] for t in teams} == {"Line Crew A", "Crew B", "Night Crew"}
    # Its own join code puts new crew on it.
    code = make_code(client, team=team["id"])
    joined = client.post("/api/join", json={"code": code}, headers=person("auth0|night"))
    assert joined.json()["team_id"] == team["id"]


def test_a_site_has_at_most_one_team(client) -> None:
    response = client.post(
        "/api/teams", json={"name": "Second", "site_id": "site-a"}, headers=SUPERVISOR
    )
    assert response.status_code == 409
    assert response.json()["detail"]["reason"] == "site_taken"


def test_rename_move_and_unassign(client) -> None:
    renamed = client.patch("/api/teams/team-b", json={"name": "Crew Bee"}, headers=SUPERVISOR)
    assert renamed.json()["name"] == "Crew Bee" and renamed.json()["site_id"] is None
    moved = client.patch("/api/teams/team-a", json={"site_id": None}, headers=SUPERVISOR)
    assert moved.json()["site_id"] is None  # site-a is free again
    app.dependency_overrides[get_now] = lambda: NOW + timedelta(minutes=1)  # a later edit
    claimed = client.patch("/api/teams/team-b", json={"site_id": "site-a"}, headers=SUPERVISOR)
    assert claimed.json()["site_name"] == "Alpha Plant"


def test_only_empty_teams_are_removed(client, h) -> None:
    code = make_code(client, team="team-b")
    client.post("/api/join", json={"code": code}, headers=person("auth0|bee"))
    response = client.delete("/api/teams/team-b", headers=SUPERVISOR)
    assert response.json()["detail"]["reason"] == "has_members"
    empty = client.post("/api/teams", json={"name": "Temp"}, headers=SUPERVISOR).json()
    temp_code = make_code(client, team=empty["id"])
    assert client.delete(f"/api/teams/{empty['id']}", headers=SUPERVISOR).status_code == 204
    gone = client.post("/api/join", json={"code": temp_code}, headers=person("auth0|late"))
    assert gone.status_code == 404  # its codes went with it


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("patch", "/api/teams/team-x", {"name": "Mine now"}),
        ("delete", "/api/teams/team-x", None),
    ],
)
def test_other_organizations_teams_are_off_limits(client, method, path, body) -> None:
    kwargs = {"json": body} if body else {}
    response = getattr(client, method)(path, headers=SUPERVISOR, **kwargs)
    assert response.status_code == 404


def test_crew_cannot_manage_teams(client) -> None:
    assert (
        client.post("/api/teams", json={"name": "X"}, headers=person("auth0|c")).status_code == 403
    )


def test_supervisor_renames_their_organization(client) -> None:
    response = client.patch("/api/organization", json={"name": " Gator Power "}, headers=SUPERVISOR)
    assert response.status_code == 200, response.text
    assert response.json()["organization_name"] == "Gator Power"
    assert client.get("/api/team", headers=SUPERVISOR).json()["organization_name"] == "Gator Power"
    # Only their own organization, and never crew.
    other = client.get("/api/team", headers=OTHER_SUPERVISOR).json()
    assert other["organization_name"] == "Coastal"
    crew = client.patch("/api/organization", json={"name": "X"}, headers=person("auth0|c"))
    assert crew.status_code == 403
    blank = client.patch("/api/organization", json={"name": ""}, headers=SUPERVISOR)
    assert blank.status_code == 422
