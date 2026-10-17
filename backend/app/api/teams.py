"""Team onboarding with join codes, and the supervisor's team roster.

- `GET /api/me`: the caller's organization, team, and site, or nulls when the account has
  not joined one. It also refreshes the name and email shown on the roster.
- `POST /api/join`: a crew account that belongs to no organization joins the team behind
  a valid code. Supervisor accounts are linked by an administrator instead.
- `GET /api/team`: the supervisor's organization: its supervisors and, for every team,
  the site, the members, and the active join codes.
- `POST /api/teams/{team_id}/join-codes`: a supervisor creates a code for a team in their
  organization. Codes look like `XXXX-XXXX` and expire after seven days.
- `DELETE /api/join-codes/{code}`: a supervisor revokes one of their organization's codes.
  People who already joined keep their membership.
- `POST /api/teams`, `PATCH /api/teams/{team_id}`, `DELETE /api/teams/{team_id}`: a
  supervisor adds, renames, moves (site), or removes teams in their organization. A site
  has at most one team; a team with members can't be removed.

Every change is written to the audit log. A code only ever grants crew access to one team.
"""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_now
from app.api.sites import DbSession
from app.db import models as db
from app.schemas import (
    Account,
    JoinCode,
    JoinRequest,
    OrganizationTeams,
    TeamCreate,
    TeamMember,
    TeamRoster,
    TeamUpdate,
)
from app.security import AuthenticatedUser, CurrentUser, membership_for, require_role
from app.services.alerts import audit

router = APIRouter(tags=["teams"])

Now = Annotated[datetime, Depends(get_now)]
Supervisor = Annotated[CurrentUser, Depends(require_role("supervisor"))]

CODE_LIFETIME = timedelta(days=7)
# No 0/O, 1/I/L: codes are read aloud and typed on phones.
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


@router.get("/api/me", response_model=Account)
def me(user: AuthenticatedUser, session: DbSession) -> Account:
    membership = membership_for(session, user)
    if membership is not None and _refresh_profile(membership, user):
        session.commit()
    return _account(user, membership)


@router.post("/api/join", response_model=Account)
def join(body: JoinRequest, user: AuthenticatedUser, session: DbSession, now: Now) -> Account:
    if user.role != "crew":
        raise _refuse(409, "supervisor", "Supervisor accounts are linked by an administrator.")
    if membership_for(session, user) is not None:
        raise _refuse(409, "already_member", "This account already belongs to a team.")
    code = session.get(db.JoinCode, normalize(body.code))
    if code is None or code.revoked_at is not None:
        raise _refuse(404, "invalid_code", "That code isn't valid. Check it with your supervisor.")
    if _aware(code.expires_at) <= now:
        raise _refuse(410, "expired", "That code has expired. Ask your supervisor for a new one.")
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
    return _account(user, membership)


@router.get("/api/team", response_model=OrganizationTeams)
def team(user: Supervisor, session: DbSession, now: Now) -> OrganizationTeams:
    membership = _organization_of(session, user)
    if _refresh_profile(membership, user):
        session.commit()
    org = membership.organization
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
    return OrganizationTeams(
        organization_id=org.id,
        organization_name=org.name,
        supervisors=[_member(m) for m in members if m.role == "supervisor"],
        teams=[_roster(t, members, codes, now) for t in teams],
    )


@router.post("/api/teams", response_model=TeamRoster, status_code=201)
def create_team(body: TeamCreate, user: Supervisor, session: DbSession, now: Now) -> TeamRoster:
    membership = _organization_of(session, user)
    team = db.Team(
        id=f"team:{uuid4().hex}",
        organization_id=membership.organization_id,
        name=body.name.strip(),
        site_id=_free_site(session, body.site_id, None),
    )
    session.add(team)
    audit(session, user.sub, "team.create", team.id, now)
    session.commit()
    return _roster(team, [], [], now)


@router.patch("/api/teams/{team_id}", response_model=TeamRoster)
def update_team(
    team_id: str, body: TeamUpdate, user: Supervisor, session: DbSession, now: Now
) -> TeamRoster:
    team = _team_of(session, user, team_id)
    if body.name is not None:
        team.name = body.name.strip()
    if "site_id" in body.model_fields_set:
        team.site_id = _free_site(session, body.site_id, team.id)
    audit(session, user.sub, "team.update", team.id, now)
    session.commit()
    members = session.scalars(select(db.Membership).where(db.Membership.team_id == team.id)).all()
    codes = session.scalars(
        select(db.JoinCode).where(db.JoinCode.team_id == team.id, db.JoinCode.revoked_at.is_(None))
    ).all()
    return _roster(team, list(members), list(codes), now)


@router.delete("/api/teams/{team_id}", status_code=204)
def delete_team(team_id: str, user: Supervisor, session: DbSession, now: Now) -> Response:
    team = _team_of(session, user, team_id)
    if session.scalar(select(db.Membership.id).where(db.Membership.team_id == team.id).limit(1)):
        raise _refuse(409, "has_members", "Move or remove this team's members first.")
    if session.scalar(select(db.CrewReport.id).where(db.CrewReport.team_id == team.id).limit(1)):
        raise _refuse(
            409,
            "has_reports",
            "This team's reports are on record, so it can't be removed. Unassign its site instead.",
        )
    for code in session.scalars(select(db.JoinCode).where(db.JoinCode.team_id == team.id)):
        session.delete(code)  # its codes stop working with it
    session.delete(team)
    audit(session, user.sub, "team.delete", team_id, now)
    session.commit()
    return Response(status_code=204)


@router.post("/api/teams/{team_id}/join-codes", response_model=JoinCode, status_code=201)
def create_join_code(team_id: str, user: Supervisor, session: DbSession, now: Now) -> JoinCode:
    membership = _organization_of(session, user)
    team = session.get(db.Team, team_id)
    if team is None or team.organization_id != membership.organization_id:
        raise HTTPException(404, "Team not found in your organization")
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
def revoke_join_code(code: str, user: Supervisor, session: DbSession, now: Now) -> Response:
    membership = _organization_of(session, user)
    row = session.get(db.JoinCode, normalize(code))
    if row is None or row.organization_id != membership.organization_id:
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
        if session.get(db.JoinCode, code) is None:
            return code
    raise HTTPException(503, "Could not create a unique join code; try again")


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


def _team_of(session: Session, user: CurrentUser, team_id: str) -> db.Team:
    membership = _organization_of(session, user)
    team = session.get(db.Team, team_id)
    if team is None or team.organization_id != membership.organization_id:
        raise HTTPException(404, "Team not found in your organization")
    return team


def _free_site(session: Session, site_id: str | None, team_id: str | None) -> str | None:
    """The site, if it exists and no other team has it. One team per site (spec.md)."""
    if site_id is None:
        return None
    if session.get(db.Site, site_id) is None:
        raise _refuse(404, "site_not_found", "That site doesn't exist.")
    holder = session.scalar(select(db.Team.id).where(db.Team.site_id == site_id))
    if holder is not None and holder != team_id:
        raise _refuse(409, "site_taken", "That site already has a team.")
    return site_id


def _organization_of(session: Session, user: CurrentUser) -> db.Membership:
    membership = membership_for(session, user)
    if membership is None:
        raise _refuse(403, "not_linked", "Your account isn't linked to an organization yet.")
    return membership


def _refresh_profile(membership: db.Membership, user: CurrentUser) -> bool:
    """Copy the token's name and email onto the roster; True when anything changed."""
    changed = False
    for field, value in (("email", user.email), ("display_name", user.name)):
        if value and getattr(membership, field) != value:
            setattr(membership, field, value)
            changed = True
    return changed


def _account(user: CurrentUser, membership: db.Membership | None) -> Account:
    if membership is None:
        return Account(role=user.role)
    team = membership.team
    return Account(
        role=user.role,
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
