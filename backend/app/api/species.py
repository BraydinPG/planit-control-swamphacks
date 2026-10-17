"""`GET /api/sites/{id}/species`: regional species context for a team's site.

Read-only field awareness. Only sites with an assigned team get species context. Access
matches `GET /api/sites/{id}`: supervisors read any site, crew only their team's site.
The response never touches the score, alerts, report review, or clearance.

When there is nothing to show, the 404 carries `{"detail": {"reason", "message"}}` like
the briefing routes: `no_team`.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, get_now
from app.api.sites import load_notices, load_reports, visible_site_ids
from app.db import models as db
from app.schemas import SiteSpeciesContext
from app.security import AuthenticatedUser
from app.species.service import SpeciesContextService, get_species_service

router = APIRouter(prefix="/api/sites", tags=["species"])

DbSession = Annotated[Session, Depends(get_db)]
Now = Annotated[datetime, Depends(get_now)]
Species = Annotated[SpeciesContextService, Depends(get_species_service)]

REASONS = {
    "no_team": "Species context is shown only for sites with an assigned team.",
}


@router.get("/{site_id}/species", response_model=SiteSpeciesContext)
def site_species(
    site_id: str,
    user: AuthenticatedUser,
    session: DbSession,
    now: Now,
    species: Species,
) -> SiteSpeciesContext:
    visible = visible_site_ids(session, user)
    if visible is not None and site_id not in visible:
        raise HTTPException(status_code=403, detail="This site is not assigned to your team")
    site = session.scalar(
        select(db.Site).where(db.Site.id == site_id).options(selectinload(db.Site.assigned_team))
    )
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    if site.assigned_team is None:
        raise HTTPException(
            status_code=404, detail={"reason": "no_team", "message": REASONS["no_team"]}
        )
    return species.context(
        site,
        now,
        reports=load_reports(session, site_id, viewer=user),
        notices=load_notices(session, site, viewer=user),
    )
