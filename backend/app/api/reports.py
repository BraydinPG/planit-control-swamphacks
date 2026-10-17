"""Report creation/listing (T053) and supervisor absent-report review (T054).

`POST /api/reports` takes a multipart form: `site_id`, `category`, `hazard_present`,
`lat`, `lon`, optional `note`, and a `photo` file. A photo is required when the hazard is
marked present and optional when it is marked absent. Photos pass the T052 type and size
checks before anything is stored.

Access (spec.md section 8):
- Submitting needs `submit:reports`. Crew report only for their team's site, as their
  team. A supervisor may report for any site assigned to a team in their organization.
- `GET /api/reports` shows crew their team's site reports, and supervisors their
  organization's reports.
- `POST /api/reports/{id}/review` is restricted to the reporting organization's
  supervisor and reports marked absent. Present reports use hazard confirmation.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import get_now
from app.api.sites import DbSession, report_schema, visible_site_ids
from app.db import models as db
from app.schemas import CrewReport, ReportCategory, ReportCreate, ReportReview
from app.security import (
    AuthenticatedUser,
    CurrentUser,
    membership_for,
    require_permission,
    require_role,
    roles,
)
from app.services.hazards import review_absent_report
from app.services.reports import Reporter, create_report
from app.storage import InvalidPhoto, PhotoStore, get_photo_store, read_limited, save_photo

router = APIRouter(prefix="/api/reports", tags=["reports"])

Now = Annotated[datetime, Depends(get_now)]
Submitter = Annotated[CurrentUser, Depends(require_permission(roles.SUBMIT_REPORTS))]
Photos = Annotated[PhotoStore, Depends(get_photo_store)]
REPORT_LIMIT = 200
Reviewer = Annotated[CurrentUser, Depends(require_permission(roles.REVIEW_REPORTS))]


@router.post(
    "/{report_id}/review",
    response_model=CrewReport,
    dependencies=[Depends(require_role("supervisor"))],
)
def review_report(
    report_id: str, review: ReportReview, user: Reviewer, session: DbSession, now: Now
) -> CrewReport:
    return report_schema(review_absent_report(session, report_id, review, user, now))


@router.post("", response_model=CrewReport, status_code=201)
def submit_report(
    user: Submitter,
    session: DbSession,
    now: Now,
    photos: Photos,
    site_id: Annotated[str, Form()],
    category: Annotated[ReportCategory, Form()],
    hazard_present: Annotated[bool, Form()],
    lat: Annotated[float, Form()],
    lon: Annotated[float, Form()],
    note: Annotated[str | None, Form()] = None,
    photo: Annotated[UploadFile | None, File()] = None,
) -> CrewReport:
    try:
        form = ReportCreate(
            site_id=site_id,
            category=category,
            hazard_present=hazard_present,
            lat=lat,
            lon=lon,
            note=note or None,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False)) from exc

    site = session.scalar(
        select(db.Site)
        .where(db.Site.id == form.site_id)
        .options(selectinload(db.Site.assigned_team))
    )
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    reporter = _reporter(session, user, site)

    has_photo = photo is not None and bool(photo.filename)
    if form.hazard_present and not has_photo:
        raise HTTPException(
            status_code=422, detail="A photo is required when the hazard is present"
        )
    photo_key = None
    if has_photo:
        try:
            data = read_limited(photo.file)
            photo_key = save_photo(photos, data, photo.content_type).key
        except InvalidPhoto as exc:
            raise HTTPException(
                status_code=422, detail={"reason": exc.reason, "message": str(exc)}
            ) from exc

    created = create_report(
        session,
        reporter,
        site,
        form.category,
        form.hazard_present,
        form.lat,
        form.lon,
        form.note,
        photo_key,
        now,
    )
    return report_schema(created.report)


@router.get("", response_model=list[CrewReport])
def list_reports(
    user: AuthenticatedUser,
    session: DbSession,
    site_id: Annotated[str | None, Query(description="Only this site's reports")] = None,
) -> list[CrewReport]:
    """Reports the caller may see, newest first."""
    query = select(db.CrewReport).order_by(db.CrewReport.created_at.desc()).limit(REPORT_LIMIT)
    if user.can(roles.READ_ALL_SITES):
        membership = membership_for(session, user)
        if membership is None:
            return []
        query = query.where(db.CrewReport.organization_id == membership.organization_id)
    else:
        visible = visible_site_ids(session, user)
        query = query.where(db.CrewReport.site_id.in_(visible or set()))
    if site_id is not None:
        query = query.where(db.CrewReport.site_id == site_id)
    return [report_schema(r) for r in session.scalars(query).all()]


def _reporter(session, user: CurrentUser, site: db.Site) -> Reporter:
    """Who is reporting, and for which team. The server decides; the form can't override it."""
    membership = membership_for(session, user)
    if membership is None:
        raise HTTPException(status_code=403, detail="Your account is not linked to a team")
    if membership.team_id is not None:  # crew
        team = membership.team
        if team is None or team.site_id != site.id:
            raise HTTPException(status_code=403, detail="You can only report for your team's site")
        return Reporter(user.sub, membership.organization_id, team.id)
    team = site.assigned_team  # supervisor reporting on one of their organization's sites
    if team is None or team.organization_id != membership.organization_id:
        raise HTTPException(status_code=403, detail="This site has no team in your organization")
    return Reporter(user.sub, membership.organization_id, team.id)
