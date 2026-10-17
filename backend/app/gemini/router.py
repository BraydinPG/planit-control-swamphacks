"""Briefing routes (T058A). Briefings are read here; only the 6 PM schedule creates them.

- `GET /api/sites/{site_id}/briefing`: the site's latest briefing. Crew read their team's
  site; supervisors read team sites in their own organization.
- `GET /api/briefings`: anyone with `read:org_briefings` (crew and supervisors); the latest
  briefing for every team site in their organization.

When there is no briefing to show, the 403 or 404 says why, as
`{"detail": {"reason": ..., "message": ...}}` (see `REASONS`). The frontend shows the
message, so an empty database or a missing supervisor never reads as "permission denied".
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.sites import DbSession, visible_site_ids
from app.db import models as db
from app.gemini.briefings import to_schema
from app.schemas import Briefing
from app.security import (
    AuthenticatedUser,
    CurrentUser,
    membership_for,
    require_permission,
    roles,
)

router = APIRouter(tags=["briefings"])

NO_BRIEFING = "No briefing yet. Briefings are generated at 6 PM site-local time."
REASONS = {
    "not_your_site": "This site is not assigned to your team.",
    "no_team": "This site has no assigned team, so no briefing is generated for it.",
    "not_linked": "Your account isn't linked to an organization yet, so briefings can't be shown.",
    "other_organization": "This site belongs to another organization.",
    "no_supervisor": "No supervisor is assigned to this organization, so no briefing is generated.",
    "no_supervisor_org": (
        "No supervisor is assigned to your organization, so no briefings are generated."
    ),
    "not_generated": NO_BRIEFING,
}
OrgReader = Annotated[CurrentUser, Depends(require_permission(roles.READ_ORG_BRIEFINGS))]


@router.get("/api/sites/{site_id}/briefing", response_model=Briefing)
def site_briefing(site_id: str, user: AuthenticatedUser, session: DbSession) -> Briefing:
    site = session.get(db.Site, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    visible = visible_site_ids(session, user)
    if visible is not None and site_id not in visible:
        raise _unavailable(403, "not_your_site")
    team = site.assigned_team
    if team is None:
        raise _unavailable(404, "no_team")
    membership = membership_for(session, user)
    if membership is None:
        raise _unavailable(403, "not_linked")
    if membership.organization_id != team.organization_id:
        raise _unavailable(403, "other_organization")
    if not _has_supervisor(session, team.organization_id):
        raise _unavailable(404, "no_supervisor")
    rows = _latest(session, [site_id])
    if not rows:
        raise _unavailable(404, "not_generated")
    return to_schema(rows[0])


@router.get("/api/briefings", response_model=list[Briefing])
def organization_briefings(user: OrgReader, session: DbSession) -> list[Briefing]:
    membership = membership_for(session, user)
    if membership is None:
        raise _unavailable(403, "not_linked")
    if not _has_supervisor(session, membership.organization_id):
        raise _unavailable(404, "no_supervisor_org")
    site_ids = _organization_site_ids(session, membership.organization_id)
    return [to_schema(row) for row in _latest(session, sorted(site_ids))]


def _unavailable(status: int, reason: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"reason": reason, "message": REASONS[reason]})


def _has_supervisor(session: Session, organization_id: str) -> bool:
    return (
        session.scalar(
            select(db.Membership.id)
            .where(
                db.Membership.organization_id == organization_id,
                db.Membership.role == "supervisor",
            )
            .limit(1)
        )
        is not None
    )


def _organization_site_ids(session: Session, organization_id: str) -> set[str]:
    return set(
        session.scalars(
            select(db.Team.site_id).where(
                db.Team.organization_id == organization_id,
                db.Team.site_id.is_not(None),
            )
        )
    )


def _latest(session: Session, site_ids: list[str]) -> list[db.Briefing]:
    """Newest briefing per site, in site id order."""
    if not site_ids:
        return []
    newest = (
        select(db.Briefing.site_id, func.max(db.Briefing.created_at).label("at"))
        .where(db.Briefing.site_id.in_(site_ids))
        .group_by(db.Briefing.site_id)
        .subquery()
    )
    return list(
        session.scalars(
            select(db.Briefing)
            .join(
                newest,
                (db.Briefing.site_id == newest.c.site_id) & (db.Briefing.created_at == newest.c.at),
            )
            .order_by(db.Briefing.site_id)
        )
    )
