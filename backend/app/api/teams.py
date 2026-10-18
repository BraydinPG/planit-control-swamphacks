"""Organizations: their owner and supervisor, teams, join codes, and claimed sites.

An organization has an **owner** (whoever created it), at most **one supervisor**, teams,
and crew. Anyone signed in with no organization can create one.

- `GET /api/me`: the caller's organization, team, site, and whether they own it, or nulls
  when the account belongs to none. It also refreshes the name and email on the roster.
- `POST /api/organizations`: create an organization and become its owner (first and last
  name are kept for records, never shown). The owner has no Auth0 role for this.
- Owner: `POST|GET /api/supervisor-invites`, `DELETE /api/supervisor-invites/{code}` make,
  list, and revoke the organization's supervisor code (one active at a time).
  `DELETE /api/organization/supervisor` removes the supervisor (possibly the owner
  themselves) and takes the Auth0 Supervisor role away, so another account can redeem a
  new code.
- `POST /api/onboarding/supervisor`: redeem a supervisor code. The account gets the Auth0
  Supervisor role and becomes the organization's supervisor. The owner can redeem their
  own code to supervise.
- Supervisor: `POST|DELETE /api/organization/sites/{site_id}` claim or release a site
  for the organization; `POST /api/teams` and `PATCH /api/teams/{id}` add, rename, and
  move teams onto claimed sites; `POST /api/teams/{id}/join-codes` and
  `DELETE /api/join-codes/{code}` make and revoke crew join codes.
- Owner or supervisor: `GET /api/team` (the roster), `PATCH /api/organization` (rename),
  `DELETE /api/teams/{id}`, and `DELETE /api/teams/{id}/members/{user_id}`.
- `POST /api/join`: a crew account that belongs to no organization joins the team behind
  a valid join code.

Every change is written to the audit log. A join code only ever grants crew access to one
team; a supervisor code only makes its organization's one supervisor.
"""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import get_now
from app.api.sites import DbSession
from app.db import models as db
from app.schemas import (
    Account,
    ClaimedSite,
    JoinCode,
    JoinRequest,
    OrganizationCreate,
    OrganizationTeams,
    OrganizationUpdate,
    SupervisorInvite,
    SupervisorSignup,
    TeamCreate,
    TeamMember,
    TeamRoster,
    TeamUpdate,
)
from app.security import AuthenticatedUser, CurrentUser, membership_for
from app.security.management import (
    Auth0Management,
    ManagementUnavailable,
    get_auth0_management,
)
from app.services.alerts import audit

router = APIRouter(tags=["teams"])

Now = Annotated[datetime, Depends(get_now)]
Management = Annotated[Auth0Management | None, Depends(get_auth0_management)]

CODE_LIFETIME = timedelta(days=7)
# No 0/O, 1/I/L: codes are read aloud and typed on phones.
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
INVALID_SUPERVISOR_CODE = "That supervisor code isn't valid. Ask the organization's owner for it."


@router.get("/api/me", response_model=Account)
def me(user: AuthenticatedUser, session: DbSession) -> Account:
    membership = membership_for(session, user)
    if membership is not None and _refresh_profile(membership, user):
        session.commit()
    return _account(user, membership, _owned(session, user))


@router.post("/api/organizations", response_model=Account, status_code=201)
def create_organization(
    body: OrganizationCreate, user: AuthenticatedUser, session: DbSession, now: Now
) -> Account:
    """Create an organization and become its owner. Supervising it takes a supervisor code."""
    if membership_for(session, user) is not None or _owned(session, user) is not None:
        raise _refuse(409, "already_member", "This account already belongs to an organization.")
    first, last, name = (
        body.first_name.strip(),
        body.last_name.strip(),
        body.organization_name.strip(),
    )
    if not (first and last and name):
        raise _refuse(
            422, "missing", "Fill in your first and last name and the organization's name."
        )
    organization = db.Organization(
        id=f"org:{uuid4().hex}", name=name, owner_id=user.sub, owner_name=f"{first} {last}"
    )
    session.add(organization)
    audit(session, user.sub, "organization.create", organization.id, now)
    session.commit()
    return _account(user, None, organization)


@router.post("/api/join", response_model=Account)
def join(body: JoinRequest, user: AuthenticatedUser, session: DbSession, now: Now) -> Account:
    if user.role != "crew":
        raise _refuse(
            409, "supervisor", "Supervisor accounts can't join a team as crew with a join code."
        )
    if membership_for(session, user) is not None:
        raise _refuse(409, "already_member", "This account already belongs to a team.")
    code = session.get(db.JoinCode, normalize(body.code))
    if code is None or code.revoked_at is not None:
        raise _refuse(404, "invalid_code", "That code isn't valid. Check it with your supervisor.")
    if _aware(code.expires_at) <= now:
        raise _refuse(410, "expired", "That code has expired. Ask your supervisor for a new one.")
    # An owner runs their organization from its page; joining a team would hide it.
    if _owned(session, user) is not None:
        raise _refuse(409, "owner", "You own an organization, so you can't join a team as crew.")
    membership = db.Membership(
        id=f"membership:{uuid4().hex}",
        user_id=user.sub,
        organization_id=code.organization_id,
        team_id=code.team_id,
        role="crew",
        joined_at=now,
    )
    _refresh_profile(membership, user)
    session.add(membership)
    audit(session, user.sub, "team.join", f"{code.team_id} via {code.code}", now)
    session.commit()
    return _account(user, membership, None)


@router.post("/api/onboarding/supervisor", response_model=Account)
def become_supervisor(
    body: SupervisorSignup,
    user: AuthenticatedUser,
    session: DbSession,
    now: Now,
    management: Management,
) -> Account:
    """Redeem a supervisor code and become the organization's one supervisor.

    Auth0 gets the Supervisor role first; the code and membership are saved only if that
    worked, so a failure changes nothing. The new role reaches the browser on the next
    sign-in.
    """
    if membership_for(session, user) is not None:
        raise _refuse(
            409,
            "already_member",
            "This account is already on a team or supervising. Ask your organization's owner "
            "to remove it first.",
        )
    invite = session.get(db.SupervisorInvite, normalize(body.code))
    if invite is None or invite.revoked_at is not None or invite.used_by is not None:
        raise _refuse(404, "invalid_code", INVALID_SUPERVISOR_CODE)
    if _aware(invite.expires_at) <= now:
        raise _refuse(410, "expired", "That supervisor code has expired. Ask for a new one.")
    organization = (
        session.get(db.Organization, invite.organization_id) if invite.organization_id else None
    )
    if organization is None:
        raise _refuse(
            410,
            "old_key",
            "That key is from the old sign-up. Create an organization instead, or ask an "
            "organization's owner for its supervisor code.",
        )
    owned = _owned(session, user)
    if owned is not None and owned.id != organization.id:
        raise _refuse(
            409, "owner_elsewhere", "You own another organization, so you can only supervise it."
        )
    if _supervisor_of(session, organization.id) is not None:
        raise _refuse(
            409,
            "has_supervisor",
            "This organization already has a supervisor. Its owner must remove them first.",
        )
    if management is None:
        raise _refuse(
            503,
            "not_configured",
            "Supervisor sign-up isn't set up on this server yet (Auth0 role manager missing).",
        )
    # Claim the code in this transaction, so two accounts can't both use it.
    claimed = session.execute(
        update(db.SupervisorInvite)
        .where(
            db.SupervisorInvite.code == invite.code,
            db.SupervisorInvite.used_by.is_(None),
            db.SupervisorInvite.revoked_at.is_(None),
        )
        .values(used_by=user.sub, used_at=now)
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:
        session.rollback()
        raise _refuse(404, "invalid_code", INVALID_SUPERVISOR_CODE)
    try:
        management.assign_role(user.sub, "supervisor")
    except ManagementUnavailable:
        session.rollback()
        raise _refuse(
            502,
            "auth0_unavailable",
            "Auth0 couldn't give this account the supervisor role. Try again.",
        ) from None
    membership = db.Membership(
        id=f"membership:{uuid4().hex}",
        user_id=user.sub,
        organization_id=organization.id,
        team_id=None,
        role="supervisor",
        joined_at=now,
    )
    _refresh_profile(membership, user)
    session.add(membership)
    audit(session, user.sub, "supervisor.onboard", f"{organization.id} via {invite.code}", now)
    session.commit()
    session.refresh(membership)
    account = _account(user, membership, owned)
    return account.model_copy(update={"role": "supervisor"})


@router.delete("/api/organization/supervisor", status_code=204)
def remove_supervisor(
    user: AuthenticatedUser, session: DbSession, now: Now, management: Management
) -> Response:
    """The owner removes the supervisor, or steps down when they supervise themselves.

    Auth0 drops the Supervisor role first; the membership is removed only if that worked.
    Their teams, codes, and records stay with the organization.
    """
    access = _owner(session, user)
    supervisor = _supervisor_of(session, access.organization.id)
    if supervisor is None:
        raise HTTPException(404, "This organization has no supervisor")
    if management is None:
        raise _refuse(
            503,
            "not_configured",
            "Removing a supervisor isn't set up on this server yet (Auth0 role manager missing).",
        )
    try:
        management.remove_role(supervisor.user_id, "supervisor")
    except ManagementUnavailable:
        raise _refuse(
            502, "auth0_unavailable", "Auth0 couldn't take the supervisor role away. Try again."
        ) from None
    session.delete(supervisor)
    audit(
        session,
        user.sub,
        "supervisor.remove",
        f"{access.organization.id}:{supervisor.user_id}",
        now,
    )
    session.commit()
    return Response(status_code=204)


@router.post("/api/supervisor-invites", response_model=SupervisorInvite, status_code=201)
def create_supervisor_invite(
    user: AuthenticatedUser, session: DbSession, now: Now
) -> SupervisorInvite:
    """The owner's supervisor code. A new code replaces the one before it."""
    access = _owner(session, user)
    for old in _active_invites(session, access.organization.id, now):
        old.revoked_at = now
    row = db.SupervisorInvite(
        code=_unused_code(session),
        organization_id=access.organization.id,
        created_by=user.sub,
        created_at=now,
        expires_at=now + CODE_LIFETIME,
    )
    session.add(row)
    audit(session, user.sub, "supervisor_invite.create", row.code, now)
    session.commit()
    return _invite(row)


@router.get("/api/supervisor-invites", response_model=list[SupervisorInvite])
def list_supervisor_invites(
    user: AuthenticatedUser, session: DbSession, now: Now
) -> list[SupervisorInvite]:
    """The organization's supervisor code, while it can still be used."""
    access = _owner(session, user)
    return [_invite(r) for r in _active_invites(session, access.organization.id, now)]


@router.delete("/api/supervisor-invites/{code}", status_code=204)
def revoke_supervisor_invite(
    code: str, user: AuthenticatedUser, session: DbSession, now: Now
) -> Response:
    access = _owner(session, user)
    row = session.get(db.SupervisorInvite, normalize(code))
    if row is None or row.organization_id != access.organization.id:
        raise HTTPException(404, "Supervisor code not found")
    if row.revoked_at is None and row.used_by is None:
        row.revoked_at = now
        audit(session, user.sub, "supervisor_invite.revoke", row.code, now)
        session.commit()
    return Response(status_code=204)


@router.get("/api/team", response_model=OrganizationTeams)
def team(user: AuthenticatedUser, session: DbSession, now: Now) -> OrganizationTeams:
    access = _manager(session, user)
    if access.membership is not None and _refresh_profile(access.membership, user):
        session.commit()
    org = access.organization
    members = session.scalars(
        select(db.Membership).where(db.Membership.organization_id == org.id)
    ).all()
    codes = session.scalars(
        select(db.JoinCode)
        .where(db.JoinCode.organization_id == org.id, db.JoinCode.revoked_at.is_(None))
        .order_by(db.JoinCode.created_at.desc())
    ).all()
    teams = session.scalars(
        select(db.Team).where(db.Team.organization_id == org.id).order_by(db.Team.name)
    ).all()
    held = {t.site_id: t.id for t in teams if t.site_id}
    claimed = _claimed(session, org.id)
    names = dict(
        session.execute(select(db.Site.id, db.Site.name).where(db.Site.id.in_(claimed))).all()
    )
    return OrganizationTeams(
        organization_id=org.id,
        organization_name=org.name,
        supervisors=[_member(m) for m in members if m.role == "supervisor"],
        teams=[_roster(t, members, codes, now) for t in teams],
        claimed_sites=sorted(
            (
                ClaimedSite(site_id=s, site_name=names.get(s, s), team_id=held.get(s))
                for s in claimed
            ),
            key=lambda c: c.site_name.lower(),
        ),
        unavailable_site_ids=sorted(_taken_elsewhere(session, org.id)),
        is_owner=access.is_owner,
        is_supervisor=access.is_supervisor,
    )


@router.patch("/api/organization", response_model=OrganizationTeams)
def rename_organization(
    body: OrganizationUpdate, user: AuthenticatedUser, session: DbSession, now: Now
) -> OrganizationTeams:
    access = _manager(session, user)
    access.organization.name = body.name.strip()
    audit(session, user.sub, "organization.rename", access.organization.id, now)
    session.commit()
    return team(user, session, now)


@router.post("/api/organization/sites/{site_id:path}", status_code=204)
def claim_site(site_id: str, user: AuthenticatedUser, session: DbSession, now: Now) -> Response:
    """The supervisor claims a site for the organization, so its teams can be put there."""
    access = _supervisor(session, user)
    org_id = access.organization.id
    if session.get(db.Site, site_id) is None:
        raise _refuse(404, "site_not_found", "That site doesn't exist.")
    if site_id in _claimed(session, org_id):
        return Response(status_code=204)
    if site_id in _taken_elsewhere(session, org_id):
        raise _refuse(409, "claimed", "Another organization already claimed that site.")
    session.add(
        db.OrganizationSite(
            site_id=site_id, organization_id=org_id, claimed_by=user.sub, claimed_at=now
        )
    )
    audit(session, user.sub, "site.claim", f"{org_id}:{site_id}", now)
    session.commit()
    return Response(status_code=204)


@router.delete("/api/organization/sites/{site_id:path}", status_code=204)
def release_site(site_id: str, user: AuthenticatedUser, session: DbSession, now: Now) -> Response:
    access = _supervisor(session, user)
    org_id = access.organization.id
    held = session.scalar(
        select(db.Team.id).where(db.Team.organization_id == org_id, db.Team.site_id == site_id)
    )
    if held is not None:
        raise _refuse(409, "has_team", "Move the team on this site to another site first.")
    row = session.get(db.OrganizationSite, site_id)
    if row is None or row.organization_id != org_id:
        raise HTTPException(404, "Your organization hasn't claimed that site")
    session.delete(row)
    audit(session, user.sub, "site.release", f"{org_id}:{site_id}", now)
    session.commit()
    return Response(status_code=204)


@router.post("/api/teams", response_model=TeamRoster, status_code=201)
def create_team(
    body: TeamCreate, user: AuthenticatedUser, session: DbSession, now: Now
) -> TeamRoster:
    access = _supervisor(session, user)
    team = db.Team(
        id=f"team:{uuid4().hex}",
        organization_id=access.organization.id,
        name=body.name.strip(),
        site_id=_team_site(session, access.organization.id, body.site_id, None),
    )
    session.add(team)
    audit(session, user.sub, "team.create", team.id, now)
    session.commit()
    return _roster(team, [], [], now)


@router.patch("/api/teams/{team_id}", response_model=TeamRoster)
def update_team(
    team_id: str, body: TeamUpdate, user: AuthenticatedUser, session: DbSession, now: Now
) -> TeamRoster:
    access = _supervisor(session, user)
    team = _team_of(session, access, team_id)
    if body.name is not None:
        team.name = body.name.strip()
    if "site_id" in body.model_fields_set:
        new_site = _team_site(session, team.organization_id, body.site_id, team.id)
        # A site the team leaves stays claimed, even one it held before claims existed.
        if team.site_id and team.site_id != new_site:
            _keep_claim(session, team.organization_id, team.site_id, user.sub, now)
        team.site_id = new_site
    audit(session, user.sub, "team.update", team.id, now)
    session.commit()
    members = session.scalars(select(db.Membership).where(db.Membership.team_id == team.id)).all()
    codes = session.scalars(
        select(db.JoinCode).where(db.JoinCode.team_id == team.id, db.JoinCode.revoked_at.is_(None))
    ).all()
    return _roster(team, list(members), list(codes), now)


@router.delete("/api/teams/{team_id}", status_code=204)
def delete_team(team_id: str, user: AuthenticatedUser, session: DbSession, now: Now) -> Response:
    access = _manager(session, user)
    team = _team_of(session, access, team_id)
    if session.scalar(select(db.Membership.id).where(db.Membership.team_id == team.id).limit(1)):
        raise _refuse(409, "has_members", "Move or remove this team's members first.")
    if session.scalar(select(db.CrewReport.id).where(db.CrewReport.team_id == team.id).limit(1)):
        raise _refuse(
            409,
            "has_reports",
            "This team's reports are on record, so it can't be removed. Unassign its site instead.",
        )
    if team.site_id:
        _keep_claim(session, team.organization_id, team.site_id, user.sub, now)
    for code in session.scalars(select(db.JoinCode).where(db.JoinCode.team_id == team.id)):
        session.delete(code)  # its codes stop working with it
    session.delete(team)
    audit(session, user.sub, "team.delete", team_id, now)
    session.commit()
    return Response(status_code=204)


@router.delete("/api/teams/{team_id}/members/{user_id:path}", status_code=204)
def remove_member(
    team_id: str, user_id: str, user: AuthenticatedUser, session: DbSession, now: Now
) -> Response:
    """Take a crew member off one of the organization's teams.

    Their reports stay on record. They can join a team again with a new join code.
    """
    access = _manager(session, user)
    team = _team_of(session, access, team_id)
    member = session.scalar(
        select(db.Membership).where(
            db.Membership.user_id == user_id, db.Membership.team_id == team.id
        )
    )
    if member is None:
        raise HTTPException(404, "That person isn't on this team")
    session.delete(member)
    audit(session, user.sub, "team.member.remove", f"{team.id}:{user_id}", now)
    session.commit()
    return Response(status_code=204)


@router.post("/api/teams/{team_id}/join-codes", response_model=JoinCode, status_code=201)
def create_join_code(
    team_id: str, user: AuthenticatedUser, session: DbSession, now: Now
) -> JoinCode:
    access = _supervisor(session, user)
    team = _team_of(session, access, team_id)
    code = db.JoinCode(
        code=_unused_code(session),
        organization_id=team.organization_id,
        team_id=team.id,
        created_by=user.sub,
        created_at=now,
        expires_at=now + CODE_LIFETIME,
    )
    session.add(code)
    audit(session, user.sub, "join_code.create", f"{team.id}:{code.code}", now)
    session.commit()
    return _code(code)


@router.delete("/api/join-codes/{code}", status_code=204)
def revoke_join_code(code: str, user: AuthenticatedUser, session: DbSession, now: Now) -> Response:
    access = _supervisor(session, user)
    row = session.get(db.JoinCode, normalize(code))
    if row is None or row.organization_id != access.organization.id:
        raise HTTPException(404, "Join code not found in your organization")
    if row.revoked_at is None:
        row.revoked_at = now
        audit(session, user.sub, "join_code.revoke", f"{row.team_id}:{row.code}", now)
        session.commit()
    return Response(status_code=204)


def normalize(code: str) -> str:
    """`gtr4 f7km`, `GTR4F7KM`, and `GTR4-F7KM` are the same code."""
    letters = "".join(ch for ch in code.upper() if ch.isalnum())
    return f"{letters[:4]}-{letters[4:]}" if len(letters) == 8 else letters


def new_code() -> str:
    letters = "".join(secrets.choice(ALPHABET) for _ in range(8))
    return f"{letters[:4]}-{letters[4:]}"


def _unused_code(session: Session) -> str:
    for _ in range(10):
        code = new_code()
        if (
            session.get(db.JoinCode, code) is None
            and session.get(db.SupervisorInvite, code) is None
        ):
            return code
    raise HTTPException(503, "Could not create a unique join code; try again")


@dataclass
class Access:
    """Which organization the caller acts for, and as what."""

    organization: db.Organization
    membership: db.Membership | None
    is_owner: bool
    is_supervisor: bool


def _access(session: Session, user: CurrentUser) -> Access:
    membership = membership_for(session, user)
    owned = _owned(session, user)
    organization = membership.organization if membership is not None else owned
    if organization is None:
        raise _refuse(403, "not_linked", "Your account isn't linked to an organization yet.")
    return Access(
        organization=organization,
        membership=membership,
        is_owner=owned is not None and owned.id == organization.id,
        # The Auth0 role and the membership must agree.
        is_supervisor=(
            membership is not None and membership.role == "supervisor" and user.role == "supervisor"
        ),
    )


def _owner(session: Session, user: CurrentUser) -> Access:
    access = _access(session, user)
    if not access.is_owner:
        raise _refuse(403, "not_owner", "Only the organization's owner can do this.")
    return access


def _supervisor(session: Session, user: CurrentUser) -> Access:
    access = _access(session, user)
    if not access.is_supervisor:
        raise _refuse(403, "not_supervisor", "Only your organization's supervisor can do this.")
    return access


def _manager(session: Session, user: CurrentUser) -> Access:
    access = _access(session, user)
    if not (access.is_owner or access.is_supervisor):
        raise _refuse(
            403, "not_manager", "Only your organization's owner or supervisor can do this."
        )
    return access


def _owned(session: Session, user: CurrentUser) -> db.Organization | None:
    return session.scalar(
        select(db.Organization).where(db.Organization.owner_id == user.sub).limit(1)
    )


def _supervisor_of(session: Session, organization_id: str) -> db.Membership | None:
    return session.scalar(
        select(db.Membership)
        .where(
            db.Membership.organization_id == organization_id,
            db.Membership.role == "supervisor",
        )
        .limit(1)
    )


def _active_invites(session: Session, organization_id: str, now: datetime):
    rows = session.scalars(
        select(db.SupervisorInvite)
        .where(
            db.SupervisorInvite.organization_id == organization_id,
            db.SupervisorInvite.used_by.is_(None),
            db.SupervisorInvite.revoked_at.is_(None),
        )
        .order_by(db.SupervisorInvite.created_at.desc())
    ).all()
    return [r for r in rows if _aware(r.expires_at) > now]


def _claimed(session: Session, organization_id: str) -> set[str]:
    """Sites the organization claimed, plus any its teams held before claims existed."""
    claims = session.scalars(
        select(db.OrganizationSite.site_id).where(
            db.OrganizationSite.organization_id == organization_id
        )
    )
    held = session.scalars(
        select(db.Team.site_id).where(
            db.Team.organization_id == organization_id, db.Team.site_id.is_not(None)
        )
    )
    return {*claims, *held}


def _taken_elsewhere(session: Session, organization_id: str) -> set[str]:
    """Sites another organization claimed or has a team on."""
    claims = session.scalars(
        select(db.OrganizationSite.site_id).where(
            db.OrganizationSite.organization_id != organization_id
        )
    )
    held = session.scalars(
        select(db.Team.site_id).where(
            db.Team.organization_id != organization_id, db.Team.site_id.is_not(None)
        )
    )
    return {*claims, *held}


def _keep_claim(
    session: Session, organization_id: str, site_id: str, user_id: str, now: datetime
) -> None:
    if session.get(db.OrganizationSite, site_id) is None:
        session.add(
            db.OrganizationSite(
                site_id=site_id, organization_id=organization_id, claimed_by=user_id, claimed_at=now
            )
        )


def _roster(
    team: db.Team, members: list[db.Membership], codes: list[db.JoinCode], now: datetime
) -> TeamRoster:
    return TeamRoster(
        id=team.id,
        name=team.name,
        site_id=team.site_id,
        site_name=team.site.name if team.site else None,
        members=sorted(
            (_member(m) for m in members if m.team_id == team.id),
            key=lambda m: (m.name or m.email or m.user_id).lower(),
        ),
        join_codes=[_code(c) for c in codes if c.team_id == team.id and _aware(c.expires_at) > now],
    )


def _team_of(session: Session, access: Access, team_id: str) -> db.Team:
    team = session.get(db.Team, team_id)
    if team is None or team.organization_id != access.organization.id:
        raise HTTPException(404, "Team not found in your organization")
    return team


def _team_site(
    session: Session, organization_id: str, site_id: str | None, team_id: str | None
) -> str | None:
    """The site, if the organization claimed it and no other team has it (one team per site)."""
    if site_id is None:
        return None
    if session.get(db.Site, site_id) is None:
        raise _refuse(404, "site_not_found", "That site doesn't exist.")
    holder = session.scalar(select(db.Team.id).where(db.Team.site_id == site_id))
    if holder is not None and holder != team_id:
        raise _refuse(409, "site_taken", "That site already has a team.")
    if site_id not in _claimed(session, organization_id):
        raise _refuse(409, "not_claimed", "Claim that site for your organization first.")
    return site_id


def _refresh_profile(membership: db.Membership, user: CurrentUser) -> bool:
    """Copy the token's name and email onto the roster; True when anything changed."""
    changed = False
    for field, value in (("email", user.email), ("display_name", user.name)):
        if value and getattr(membership, field) != value:
            setattr(membership, field, value)
            changed = True
    return changed


def _account(
    user: CurrentUser, membership: db.Membership | None, owned: db.Organization | None
) -> Account:
    if membership is None:
        if owned is None:
            return Account(role=user.role)
        return Account(
            role=user.role, is_owner=True, organization_id=owned.id, organization_name=owned.name
        )
    team = membership.team
    return Account(
        role=user.role,
        is_owner=owned is not None and owned.id == membership.organization_id,
        organization_id=membership.organization_id,
        organization_name=membership.organization.name,
        team_id=team.id if team else None,
        team_name=team.name if team else None,
        site_id=team.site_id if team else None,
    )


def _member(m: db.Membership) -> TeamMember:
    return TeamMember(
        user_id=m.user_id,
        name=m.display_name,
        email=m.email,
        role=m.role,
        joined_at=_aware(m.joined_at) if m.joined_at else None,
    )


def _invite(row: db.SupervisorInvite) -> SupervisorInvite:
    return SupervisorInvite(
        code=row.code, created_at=_aware(row.created_at), expires_at=_aware(row.expires_at)
    )


def _code(c: db.JoinCode) -> JoinCode:
    return JoinCode(
        code=c.code,
        team_id=c.team_id,
        created_at=_aware(c.created_at),
        expires_at=_aware(c.expires_at),
    )


def _refuse(status: int, reason: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"reason": reason, "message": message})


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
