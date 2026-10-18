"""Team onboarding with join codes, and the supervisor's team roster."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import Schema


class TeamMember(Schema):
    """One person on the roster. Name and email come from their Auth0 sign-in."""

    user_id: str
    name: str | None = None
    email: str | None = None
    role: Literal["crew", "supervisor"]
    joined_at: datetime | None = None


class JoinCode(Schema):
    """`XXXX-XXXX`. Lets a crew account join one team until it expires or is revoked."""

    code: str = Field(pattern=r"^[A-Z2-9]{4}-[A-Z2-9]{4}$")
    team_id: str
    created_at: datetime
    expires_at: datetime


class SupervisorInvite(Schema):
    """`XXXX-XXXX`. Lets one new account become a supervisor and start its own organization."""

    code: str = Field(pattern=r"^[A-Z2-9]{4}-[A-Z2-9]{4}$")
    created_at: datetime
    expires_at: datetime


class SupervisorSignup(Schema):
    """Become a supervisor with an invite key and name the new organization."""

    code: str = Field(min_length=8, max_length=20)
    organization_name: str = Field(min_length=1, max_length=80)


class TeamRoster(Schema):
    id: str
    name: str
    site_id: str | None
    site_name: str | None
    members: list[TeamMember]
    join_codes: list[JoinCode] = Field(description="Active codes only.")


class OrganizationTeams(Schema):
    """`GET /api/team`: the supervisor's organization, its supervisors, and every team."""

    organization_id: str
    organization_name: str
    supervisors: list[TeamMember]
    teams: list[TeamRoster]


class Account(Schema):
    """`GET /api/me` and `POST /api/join`: where the signed-in account belongs.

    `organization_id` is null until the account joins a team (crew) or is linked by an
    administrator (supervisors).
    """

    role: Literal["crew", "supervisor"]
    organization_id: str | None = None
    organization_name: str | None = None
    team_id: str | None = None
    team_name: str | None = None
    site_id: str | None = None


class JoinRequest(Schema):
    """Body for `POST /api/join`. Case, spaces, and a missing dash are forgiven."""

    code: str = Field(min_length=8, max_length=20)


class TeamCreate(Schema):
    """Body for `POST /api/teams`: a supervisor adds a team to their organization."""

    name: str = Field(min_length=1, max_length=80)
    site_id: str | None = Field(default=None, description="A site with no team yet.")


class TeamUpdate(Schema):
    """Body for `PATCH /api/teams/{id}`. Send `site_id: null` to unassign the site."""

    name: str | None = Field(default=None, min_length=1, max_length=80)
    site_id: str | None = None


class OrganizationUpdate(Schema):
    """Body for `PATCH /api/organization`: the supervisor renames their organization."""

    name: str = Field(min_length=1, max_length=80)
