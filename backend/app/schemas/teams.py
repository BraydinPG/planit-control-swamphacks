"""Organizations, their owner and supervisor, teams, join codes and claimed sites."""

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
    """`XXXX-XXXX`. The owner's code: whoever redeems it becomes the organization's
    supervisor. One active code per organization; it works once and expires."""

    code: str = Field(pattern=r"^[A-Z2-9]{4}-[A-Z2-9]{4}$")
    created_at: datetime
    expires_at: datetime


class SupervisorSignup(Schema):
    """Body for `POST /api/onboarding/supervisor`: redeem the owner's supervisor code."""

    code: str = Field(min_length=8, max_length=20)


class OrganizationCreate(Schema):
    """Body for `POST /api/organizations`. The names are kept for records, never shown."""

    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    organization_name: str = Field(min_length=1, max_length=80)


class ClaimedSite(Schema):
    """A site the organization claimed, and the team on it, if any."""

    site_id: str
    site_name: str
    team_id: str | None = None


class TeamRoster(Schema):
    id: str
    name: str
    site_id: str | None
    site_name: str | None
    members: list[TeamMember]
    join_codes: list[JoinCode] = Field(description="Active codes only.")


class OrganizationTeams(Schema):
    """`GET /api/team`: the organization, its supervisor, every team and its claimed sites.

    The supervisor and the owner can read it. `is_owner` says the caller owns it, and
    `is_supervisor` that the caller is its supervisor.
    """

    organization_id: str
    organization_name: str
    supervisors: list[TeamMember]
    teams: list[TeamRoster]
    claimed_sites: list[ClaimedSite] = []
    unavailable_site_ids: list[str] = Field(
        default=[], description="Sites another organization claimed or has a team on."
    )
    is_owner: bool = False
    is_supervisor: bool = False


class Account(Schema):
    """`GET /api/me` and `POST /api/join`: where the signed-in account belongs.

    `organization_id` is null until the account creates an organization (its owner),
    redeems a supervisor code, or joins a team with a join code (crew).
    """

    role: Literal["crew", "supervisor"]
    is_owner: bool = False
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
    site_id: str | None = Field(
        default=None, description="A site the organization claimed that has no team yet."
    )


class TeamUpdate(Schema):
    """Body for `PATCH /api/teams/{id}`. Send `site_id: null` to unassign the site."""

    name: str | None = Field(default=None, min_length=1, max_length=80)
    site_id: str | None = None


class OrganizationUpdate(Schema):
    """Body for `PATCH /api/organization`: the supervisor renames their organization."""

    name: str = Field(min_length=1, max_length=80)
