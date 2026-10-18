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
    body = {"name": " Night Crew ", "site_id": "site-b"}
    unclaimed = client.post("/api/teams", json=body, headers=SUPERVISOR)
    assert unclaimed.status_code == 409
    assert unclaimed.json()["detail"]["reason"] == "not_claimed"
    claim = client.post("/api/organization/sites/site-b", headers=SUPERVISOR)
    assert claim.status_code == 204
    response = client.post("/api/teams", json=body, headers=SUPERVISOR)
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


def test_supervisor_removes_a_member_who_can_then_rejoin(client, h) -> None:
    newcomer = person("auth0|crew|with|pipes")
    assert (
        client.post("/api/join", json={"code": make_code(client)}, headers=newcomer).status_code
        == 200
    )
    path = "/api/teams/team-a/members/auth0|crew|with|pipes"
    # Another organization's supervisor and crew can't remove anyone.
    assert client.delete(path, headers=OTHER_SUPERVISOR).status_code == 404
    assert client.delete(path, headers=newcomer).status_code == 403
    assert client.delete(path).status_code == 401
    assert client.delete(path, headers=SUPERVISOR).status_code == 204
    assert client.delete(path, headers=SUPERVISOR).status_code == 404
    with h() as s:
        assert (
            s.scalar(select(db.Membership).where(db.Membership.user_id == "auth0|crew|with|pipes"))
            is None
        )
        audit = s.scalars(
            select(db.AuditEvent).where(db.AuditEvent.action == "team.member.remove")
        ).all()
        assert [a.entity for a in audit] == ["team-a:auth0|crew|with|pipes"]
    assert client.get("/api/me", headers=newcomer).json()["organization_id"] is None
    # A removed member sees no team site and can join again with a new code.
    assert client.get("/api/sites", headers=newcomer).json() == []
    assert (
        client.post("/api/join", json={"code": make_code(client)}, headers=newcomer).status_code
        == 200
    )


def test_removing_a_member_needs_them_on_that_team(client) -> None:
    newcomer = person("auth0|on-a")
    client.post("/api/join", json={"code": make_code(client)}, headers=newcomer)
    assert (
        client.delete("/api/teams/team-b/members/auth0|on-a", headers=SUPERVISOR).status_code == 404
    )
    assert (
        client.delete("/api/teams/team-a/members/auth0|sup-1", headers=SUPERVISOR).status_code
        == 404
    )


# ---- owners, the supervisor code, and site claims ----


class FakeManagement:
    def __init__(self) -> None:
        self.assigned: list[tuple[str, str]] = []
        self.removed: list[tuple[str, str]] = []
        self.fail = False

    def _check(self) -> None:
        from app.security.management import ManagementUnavailable

        if self.fail:
            raise ManagementUnavailable("synthetic Auth0 failure")

    def assign_role(self, user_id: str, role_name: str) -> None:
        self._check()
        self.assigned.append((user_id, role_name))

    def remove_role(self, user_id: str, role_name: str) -> None:
        self._check()
        self.removed.append((user_id, role_name))


@pytest.fixture
def management(h):
    from app.security.management import get_auth0_management

    fake = FakeManagement()
    app.dependency_overrides[get_auth0_management] = lambda: fake
    return fake


OWNER = person("auth0|owner")
NEW_ORG = {"first_name": "Olive", "last_name": "Owner", "organization_name": " Gulf Line Co "}


def found(client, headers=OWNER) -> str:
    response = client.post("/api/organizations", json=NEW_ORG, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["organization_id"]


def supervisor_code(client, headers=OWNER) -> str:
    response = client.post("/api/supervisor-invites", headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["code"]


def redeem(client, code: str, headers) -> object:
    return client.post("/api/onboarding/supervisor", json={"code": code}, headers=headers)


def test_anyone_creates_an_organization_and_owns_it(client, h) -> None:
    org_id = found(client)
    me = client.get("/api/me", headers=OWNER).json()
    assert me["is_owner"] is True and me["organization_name"] == "Gulf Line Co"
    assert me["team_id"] is None and me["role"] == "crew"
    with h() as s:
        org = s.get(db.Organization, org_id)
        assert (org.owner_id, org.owner_name) == ("auth0|owner", "Olive Owner")
    # One organization per account; members can't start another.
    assert client.post("/api/organizations", json=NEW_ORG, headers=OWNER).status_code == 409
    assert client.post("/api/organizations", json=NEW_ORG, headers=SUPERVISOR).status_code == 409
    blank = client.post(
        "/api/organizations", json={**NEW_ORG, "first_name": "  "}, headers=person("auth0|z")
    )
    assert blank.status_code == 422
    # The owner reads the roster, but supervisor work needs a supervisor.
    roster = client.get("/api/team", headers=OWNER).json()
    assert roster["is_owner"] and not roster["is_supervisor"] and roster["supervisors"] == []
    assert client.post("/api/teams", json={"name": "T"}, headers=OWNER).status_code == 403
    # Owners don't join teams as crew.
    joined = client.post("/api/join", json={"code": make_code(client)}, headers=OWNER)
    assert joined.status_code == 409 and joined.json()["detail"]["reason"] == "owner"


def test_owner_supervises_with_their_own_code_then_hands_it_over(client, h, management) -> None:
    found(client)
    code = supervisor_code(client)
    assert [i["code"] for i in client.get("/api/supervisor-invites", headers=OWNER).json()] == [
        code
    ]
    # A newer code replaces the old one.
    newer = supervisor_code(client)
    assert [i["code"] for i in client.get("/api/supervisor-invites", headers=OWNER).json()] == [
        newer
    ]
    assert redeem(client, code, person("auth0|x")).status_code == 404
    taken = redeem(client, newer.lower().replace("-", ""), OWNER)
    assert taken.status_code == 200, taken.text
    assert taken.json()["role"] == "supervisor" and taken.json()["is_owner"] is True
    assert management.assigned == [("auth0|owner", "supervisor")]
    owner_sup = person("auth0|owner", "supervisor")
    roster = client.get("/api/team", headers=owner_sup).json()
    assert roster["is_owner"] and roster["is_supervisor"]
    # One supervisor: another code can't add a second.
    third = supervisor_code(client, owner_sup)
    second = redeem(client, third, person("auth0|second"))
    assert second.status_code == 409 and second.json()["detail"]["reason"] == "has_supervisor"
    # The owner steps down; Auth0 drops the role; someone else redeems the code.
    assert client.delete("/api/organization/supervisor", headers=owner_sup).status_code == 204
    assert management.removed == [("auth0|owner", "supervisor")]
    assert client.get("/api/me", headers=OWNER).json()["is_owner"] is True
    ok = redeem(client, third, person("auth0|delegate"))
    assert ok.status_code == 200, ok.text
    # The owner can remove the delegate too.
    assert client.delete("/api/organization/supervisor", headers=OWNER).status_code == 204
    assert management.removed[-1] == ("auth0|delegate", "supervisor")
    with h() as s:
        assert s.scalar(
            select(db.Membership).where(db.Membership.user_id == "auth0|delegate")
        ) is None  # fmt: skip


def test_only_the_owner_hands_out_or_removes_supervision(client, management) -> None:
    found(client)
    for headers in (SUPERVISOR, person("auth0|crew-x"), person("auth0|nobody", "supervisor")):
        assert client.post("/api/supervisor-invites", headers=headers).status_code == 403
        assert client.delete("/api/organization/supervisor", headers=headers).status_code == 403
    code = supervisor_code(client)
    assert client.delete(f"/api/supervisor-invites/{code}", headers=SUPERVISOR).status_code == 403
    assert client.delete(f"/api/supervisor-invites/{code}", headers=OWNER).status_code == 204
    assert redeem(client, code, person("auth0|late")).status_code == 404
    # Nobody to remove.
    assert client.delete("/api/organization/supervisor", headers=OWNER).status_code == 404


def test_supervisor_codes_fail_closed(client, h, management) -> None:
    found(client)
    code = supervisor_code(client)
    assert redeem(client, "ABCD-2345", person("auth0|hopeful")).status_code == 404
    assert redeem(client, code, {}).status_code == 401
    # Already on a team.
    joined = person("auth0|joined")
    client.post("/api/join", json={"code": make_code(client)}, headers=joined)
    taken = redeem(client, code, joined)
    assert taken.status_code == 409 and taken.json()["detail"]["reason"] == "already_member"
    # Auth0 failure changes nothing: the code stays usable.
    management.fail = True
    assert redeem(client, code, person("auth0|hopeful")).status_code == 502
    with h() as s:
        assert s.get(db.SupervisorInvite, code).used_by is None
    management.fail = False
    assert redeem(client, code, person("auth0|hopeful")).status_code == 200
    assert redeem(client, code, person("auth0|again")).status_code == 404  # spent
    # Expired codes and keys from before owners existed.
    expired = supervisor_code(client)
    with h() as s:
        s.get(db.SupervisorInvite, expired).expires_at = NOW - timedelta(seconds=1)
        s.add(
            db.SupervisorInvite(
                code="OLDK-2345", created_by="auth0|sup-1", created_at=NOW,
                expires_at=NOW + timedelta(days=1),
            )
        )  # fmt: skip
        s.commit()
    assert redeem(client, expired, person("auth0|b")).status_code == 410
    old = redeem(client, "OLDK-2345", person("auth0|b"))
    assert old.status_code == 410 and old.json()["detail"]["reason"] == "old_key"


def test_without_the_auth0_role_manager_it_explains_itself(client) -> None:
    from app.security.management import get_auth0_management

    app.dependency_overrides[get_auth0_management] = lambda: None
    found(client)
    response = redeem(client, supervisor_code(client), person("auth0|c"))
    assert response.status_code == 503
    assert response.json()["detail"]["reason"] == "not_configured"


def test_owner_removes_teams_and_members_but_not_supervisor_work(client, h) -> None:
    with h() as s:
        s.get(db.Organization, "org-1").owner_id = "auth0|owner"
        s.commit()
    crew = person("auth0|c1")
    client.post("/api/join", json={"code": make_code(client, team="team-b")}, headers=crew)
    roster = client.get("/api/team", headers=OWNER).json()
    assert roster["is_owner"] and not roster["is_supervisor"]
    assert client.delete("/api/teams/team-b/members/auth0|c1", headers=OWNER).status_code == 204
    assert client.delete("/api/teams/team-b", headers=OWNER).status_code == 204
    assert client.post("/api/teams/team-a/join-codes", headers=OWNER).status_code == 403
    assert client.post("/api/organization/sites/site-a", headers=OWNER).status_code == 403


def test_sites_are_claimed_once_and_released_without_a_team(client, h) -> None:
    with h() as s:
        s.add(
            db.Site(id="site-c", name="Charlie", lat=26, lon=-80, location_type="power_plant",
                    source="test")
        )  # fmt: skip
        s.commit()
    assert client.post("/api/organization/sites/site-c", headers=SUPERVISOR).status_code == 204
    roster = client.get("/api/team", headers=SUPERVISOR).json()
    claimed = {c["site_id"]: c["team_id"] for c in roster["claimed_sites"]}
    assert claimed == {"site-a": "team-a", "site-c": None}  # site-a: its team held it before
    other = client.get("/api/team", headers=OTHER_SUPERVISOR).json()
    assert {"site-a", "site-c"} <= set(other["unavailable_site_ids"])
    taken = client.post("/api/organization/sites/site-c", headers=OTHER_SUPERVISOR)
    assert taken.status_code == 409 and taken.json()["detail"]["reason"] == "claimed"
    held = client.delete("/api/organization/sites/site-a", headers=SUPERVISOR)
    assert held.status_code == 409 and held.json()["detail"]["reason"] == "has_team"
    # Moving the team off keeps site-a claimed; then it can be released.
    client.patch("/api/teams/team-a", json={"site_id": "site-c"}, headers=SUPERVISOR)
    assert client.delete("/api/organization/sites/site-a", headers=SUPERVISOR).status_code == 204
    assert (
        client.post("/api/organization/sites/site-a", headers=OTHER_SUPERVISOR).status_code == 204
    )
    assert client.delete("/api/organization/sites/nope", headers=SUPERVISOR).status_code == 404
