"""Briefing routes (T058A). Briefings are read here; only the 6 PM schedule creates them.

- `GET /api/sites/{site_id}/briefing`: the site's latest briefing. Crew: their team's site.
  Supervisor: team sites in their own organization.
- `GET /api/briefings`: supervisor (`read:org_briefings`) only; the latest briefing for
  every team site in their organization.
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
OrgSupervisor = Annotated[CurrentUser, Depends(require_permission(roles.READ_ORG_BRIEFINGS))]


@router.get("/api/sites/{site_id}/briefing", response_model=Briefing)
def site_briefing(site_id: str, user: AuthenticatedUser, session: DbSession) -> Briefing:
    if not _may_read(session, user, site_id):
        raise HTTPException(status_code=403, detail="This site's briefing is not available to you")
    rows = _latest(session, [site_id])
    if not rows:
        raise HTTPException(status_code=404, detail=NO_BRIEFING)
    return to_schema(rows[0])


@router.get("/api/briefings", response_model=list[Briefing])
def organization_briefings(user: OrgSupervisor, session: DbSession) -> list[Briefing]:
    site_ids = _organization_site_ids(session, user)
    return [to_schema(row) for row in _latest(session, sorted(site_ids))]


def _may_read(session: Session, user: CurrentUser, site_id: str) -> bool:
    if user.can(roles.READ_ORG_BRIEFINGS):
        return site_id in _organization_site_ids(session, user)
    visible = visible_site_ids(session, user)
    return visible is None or site_id in visible


def _organization_site_ids(session: Session, user: CurrentUser) -> set[str]:
    membership = membership_for(session, user)
    if membership is None:
        return set()
    return set(
        session.scalars(
            select(db.Team.site_id).where(
                db.Team.organization_id == membership.organization_id,
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
