"""PlanIT Control roles and permissions (spec.md section 8, AGENTS.md role policy).

Auth0 holds the same roles and permissions (auth/SETUP.md). `ROLE_PERMISSIONS` is the
fallback when an access token carries a role but no `permissions` claim.

Permissions say what kind of action a role may take. Scope checks such as "own
organization only", "assigned site only", or "any notified supervisor" depend on data,
so routes apply them after the permission check (see `membership_for`).
"""

from typing import Literal

Role = Literal["crew", "supervisor"]
ROLES: tuple[Role, ...] = ("crew", "supervisor")

# Custom claim added by the Auth0 post-login Action in auth/SETUP.md.
DEFAULT_ROLES_CLAIM = "https://planit-control/roles"

READ_ASSIGNED_SITES = "read:assigned_sites"
ACKNOWLEDGE_ALERTS = "acknowledge:alerts"
SUBMIT_REPORTS = "submit:reports"
READ_ALL_SITES = "read:all_sites"
REVIEW_REPORTS = "review:reports"
CONFIRM_HAZARDS = "confirm:hazards"
SEND_INSTRUCTIONS = "send:instructions"
READ_ORG_BRIEFINGS = "read:org_briefings"

# Crew may read their organization's briefings too (Braydin, 2026-10-17).
CREW_PERMISSIONS = frozenset(
    {READ_ASSIGNED_SITES, ACKNOWLEDGE_ALERTS, SUBMIT_REPORTS, READ_ORG_BRIEFINGS}
)
SUPERVISOR_PERMISSIONS = CREW_PERMISSIONS | {
    READ_ALL_SITES,
    REVIEW_REPORTS,
    CONFIRM_HAZARDS,
    SEND_INSTRUCTIONS,
}
ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    "crew": CREW_PERMISSIONS,
    "supervisor": frozenset(SUPERVISOR_PERMISSIONS),
}

PERMISSION_DESCRIPTIONS = {
    READ_ASSIGNED_SITES: "Read assigned sites and alerts",
    ACKNOWLEDGE_ALERTS: "Acknowledge alerts",
    SUBMIT_REPORTS: "Submit hazard reports",
    READ_ALL_SITES: "Read all sites, assigned teams, and the full map",
    REVIEW_REPORTS: "Review reports that no hazard is present (own organization)",
    CONFIRM_HAZARDS: "Confirm a potential hazard from a received notice",
    SEND_INSTRUCTIONS: "Edit and send the instruction for a confirmed hazard",
    READ_ORG_BRIEFINGS: "Read the latest briefings for every team site (own organization)",
}
