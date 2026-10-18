"""Report creation/listing (T053) and supervisor absent-report review (T054).

`POST /api/reports` takes a multipart form: `site_id`, `category`, `hazard_present`,
`lat`, `lon`, optional `note`, `location_source` (`device`, `site`, or `pin`; default
`site`), `location_accuracy_m` (device only), and a `photo` file. A photo is required when
the hazard is marked present and optional when it is marked absent. Photos pass the T052
type and size checks before anything is stored. After the report is saved, Braydin's
Gemini analysis (T060) runs in the background and fills the report's `enrichment`.

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

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import get_now
from app.api.sites import DbSession, report_schema, visible_site_ids
from app.db import models as db
from app.gemini import GeminiClient, get_gemini_client
from app.gemini.report_analysis import run_report_analysis
from app.schemas import (
    CrewReport,
    LocationSource,
    MatCondition,
    ReportCategory,
    ReportCreate,
    ReportReview,
)
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
Gemini = Annotated[GeminiClient, Depends(get_gemini_client)]
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
    client: Gemini,
    background: BackgroundTasks,
    site_id: Annotated[str, Form()],
    category: Annotated[ReportCategory, Form()],
    hazard_present: Annotated[bool, Form()],
    lat: Annotated[float, Form()],
    lon: Annotated[float, Form()],
    note: Annotated[str | None, Form()] = None,
    location_source: Annotated[LocationSource, Form()] = LocationSource.SITE,
    location_accuracy_m: Annotated[float | None, Form()] = None,
    mat_condition: Annotated[MatCondition | None, Form()] = None,
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
            location_source=location_source,
            location_accuracy_m=location_accuracy_m,
            mat_condition=mat_condition,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=422, detail=exc.errors(include_url=False, include_context=False)
        ) from exc

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
        location_source=form.location_source,
        location_accuracy_m=form.location_accuracy_m,
        mat_condition=form.mat_condition,
    )
    # T060: Gemini's analysis runs after the response, so the crew member never waits on it.
    background.add_task(
        run_report_analysis, session.get_bind(), created.report.id, photos, client, now
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


PHOTO_MEDIA_TYPES = {
    "jpg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "heic": "image/heic",
}


@router.get(
    "/{report_id}/photo",
    response_class=Response,
    responses={200: {"content": {m: {} for m in PHOTO_MEDIA_TYPES.values()}}},
)
def report_photo(
    report_id: str, user: AuthenticatedUser, session: DbSession, photos: Photos
) -> Response:
    """A report's photo for anyone who may see the report. The stored object stays private."""
    report = session.get(db.CrewReport, report_id)
    if report is None or not _can_see(session, user, report):
        raise HTTPException(status_code=404, detail="Report not found")
    if not report.photo_url:
        raise HTTPException(status_code=404, detail="This report has no photo")
    try:
        data = photos.load(report.photo_url)
    except Exception as exc:  # a missing object, an invalid key, or storage down
        raise HTTPException(status_code=404, detail="The photo isn't in storage") from exc
    media_type = PHOTO_MEDIA_TYPES[report.photo_url.rsplit(".", 1)[1]]
    return Response(
        data,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"},
    )


def _can_see(session, user: CurrentUser, report: db.CrewReport) -> bool:
    """The same visibility as GET /api/reports."""
    if user.can(roles.READ_ALL_SITES):
        membership = membership_for(session, user)
        return membership is not None and report.organization_id == membership.organization_id
    return report.site_id in (visible_site_ids(session, user) or set())


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
