"""Crew report creation, and the notice an accepted report sends (T053).

- A report is stored as pending with the reporter, team, organization, category,
  hazard-present answer, coordinates, photo reference (T052 storage key), optional note,
  and time. It sends nothing yet: its organization's supervisor accepts or rejects it
  first (user decision, 2026-10-18).
- When the supervisor accepts a report marked present, `publish_report_notice` sends one
  notice for it. The reporting organization's copy is confirmed by that acceptance; every
  other organization with a team inside the radius receives it as "potential {hazard}" and
  confirms for itself (T054/T054A). A rejected report, or one marked absent, sends nothing.

Notice radius:
- Asks Braydin's Gemini radius function when `app.gemini` publishes one (see
  `_gemini_radius`). It accepts only a positive radius up to 50 miles.
- Otherwise, including when Gemini is unresponsive, uses the category's prototype default
  from spec.md section 5, stored with `radius_source="default"`.

Recipients: every team assigned to a site inside the radius, and every supervisor of
those teams' organizations, across organizations. A notice is "sent" by appearing on
those sites' detail (`GET /api/sites/{id}` `notices`), and each delivery is audited.
There is no push or email notification.
"""

from dataclasses import dataclass
from datetime import datetime
from math import asin, cos, radians, sin, sqrt
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as db
from app.schemas import (
    Evidence,
    EvidenceKind,
    LocationSource,
    MatCondition,
    NoticeSource,
    NoticeStatus,
    RadiusSource,
    ReportCategory,
    ReviewStatus,
)
from app.services.alerts import audit

MAX_RADIUS_MILES = 50.0

# spec.md section 5 defaults (prototype distances, not official policy).
DEFAULT_RADIUS_MILES = {
    ReportCategory.BROKEN_POLE_DOWNED_LINE: 1.0,
    ReportCategory.ON_SITE_FIRE: 1.0,
    ReportCategory.ACCESS_MAT_DETERIORATION: 1.0,
    ReportCategory.WILDLIFE: 1.0,
    ReportCategory.FLOODING: 5.0,
    ReportCategory.OTHER: 1.0,
}
HAZARD_LABELS = {
    ReportCategory.BROKEN_POLE_DOWNED_LINE: "broken electrical pole or downed line",
    ReportCategory.ON_SITE_FIRE: "on-site fire",
    ReportCategory.ACCESS_MAT_DETERIORATION: "access mat deterioration",
    ReportCategory.WILDLIFE: "wildlife",
    ReportCategory.FLOODING: "flooding",
    ReportCategory.OTHER: "hazard",
}


@dataclass(frozen=True)
class Reporter:
    user_id: str
    organization_id: str
    team_id: str


@dataclass(frozen=True)
class Recipients:
    team_ids: list[str]
    supervisor_ids: list[str]


@dataclass(frozen=True)
class CreatedReport:
    report: db.CrewReport
    notice: db.HazardNotice | None
    recipients: Recipients


def create_report(
    session: Session,
    reporter: Reporter,
    site: db.Site,
    category: ReportCategory,
    hazard_present: bool,
    lat: float,
    lon: float,
    note: str | None,
    photo_key: str | None,
    now: datetime,
    *,
    location_source: LocationSource = LocationSource.SITE,
    location_accuracy_m: float | None = None,
    mat_condition: MatCondition | None = None,
) -> CreatedReport:
    report = db.CrewReport(
        id=f"report:{uuid4().hex}",
        organization_id=reporter.organization_id,
        team_id=reporter.team_id,
        site_id=site.id,
        reporter_id=reporter.user_id,
        category=category,
        hazard_present=hazard_present,
        note=note or None,
        photo_url=photo_key,
        lat=lat,
        lon=lon,
        location_source=location_source,
        location_accuracy_m=location_accuracy_m,
        mat_condition=mat_condition,
        site_distance_miles=round(miles_between(site.lat, site.lon, lat, lon), 3),
        review_status=ReviewStatus.PENDING,
        created_at=now,
    )
    session.add(report)
    audit(session, reporter.user_id, "report.create", report.id, now)
    session.commit()
    return CreatedReport(report, None, Recipients([], []))


def publish_report_notice(
    session: Session, report: db.CrewReport, supervisor_id: str, now: datetime
) -> tuple[db.HazardNotice, db.NoticeAssessment, Recipients]:
    """The notice for an accepted present report. Does not commit.

    Gemini picks the radius (`notice_radius`), or the category default when it is
    unavailable or invalid. The notice is confirmed for the reporting organization by
    the acceptance; teams and supervisors of every organization inside the radius are
    notified, and each other organization confirms for itself.
    """
    category = ReportCategory(report.confirmed_category or report.category)
    radius, source = notice_radius(category, report)
    notice = db.HazardNotice(
        id=f"notice:{uuid4().hex}",
        hazard_label=HAZARD_LABELS[category],
        source=NoticeSource.CREW_REPORT,
        source_ref=report.id,
        lat=report.lat,
        lon=report.lon,
        radius_miles=radius,
        radius_source=source,
        status=NoticeStatus.CONFIRMED,
        created_at=now,
        confirmed_by=supervisor_id,
        confirmed_at=now,
        evidence=[
            Evidence(
                id=report.id,
                kind=EvidenceKind.REPORT,
                label=f"Crew report: {HAZARD_LABELS[category]}",
                observed_at=report.created_at,
            ).model_dump(mode="json")
        ],
    )
    report.notice_id = notice.id
    session.add(notice)
    session.flush()
    assessment = db.NoticeAssessment(
        notice_id=notice.id,
        organization_id=report.organization_id,
        confirmed_by=supervisor_id,
        confirmed_at=now,
    )
    session.add(assessment)
    recipients = notice_recipients(session, notice)
    audit(session, supervisor_id, "notice.create", notice.id, now)
    for team_id in recipients.team_ids:
        audit(session, "system:notices", "notice.deliver", f"{notice.id}->{team_id}", now)
    # Snapshot actual recipients: later team moves must not grant confirmation access.
    # The accepting supervisor always holds a receipt, even if their site is outside.
    for recipient in sorted({*recipients.supervisor_ids, supervisor_id}):
        audit(
            session,
            "system:notices",
            "notice.supervisor.deliver",
            f"{notice.id}->{recipient}",
            now,
        )
    audit(session, supervisor_id, "notice.confirm", notice.id, now)
    session.flush()
    return notice, assessment, recipients


def notice_radius(category: ReportCategory, report: db.CrewReport) -> tuple[float, RadiusSource]:
    """Gemini's radius when available and valid, else the category's labeled default."""
    suggested = _gemini_radius(category, report)
    if suggested is not None and 0 < suggested <= MAX_RADIUS_MILES:
        return float(suggested), RadiusSource.GEMINI
    return DEFAULT_RADIUS_MILES[category], RadiusSource.DEFAULT


def notice_team_organizations(session: Session, notice: db.HazardNotice) -> list[tuple[str, str]]:
    """(team_id, organization_id) for every team assigned to a site inside the radius."""
    teams = session.execute(
        select(db.Team.id, db.Team.organization_id, db.Site.lat, db.Site.lon).join(
            db.Site, db.Team.site_id == db.Site.id
        )
    ).all()
    return [
        (team_id, org_id)
        for team_id, org_id, lat, lon in teams
        if miles_between(notice.lat, notice.lon, lat, lon) <= notice.radius_miles
    ]


def notice_recipients(session: Session, notice: db.HazardNotice) -> Recipients:
    """Teams assigned to sites inside the radius, and their organizations' supervisors."""
    inside = notice_team_organizations(session, notice)
    orgs = {org_id for _, org_id in inside}
    supervisors = (
        session.scalars(
            select(db.Membership.user_id).where(
                db.Membership.role == "supervisor", db.Membership.organization_id.in_(orgs)
            )
        ).all()
        if orgs
        else []
    )
    return Recipients(sorted(t for t, _ in inside), sorted(supervisors))


def miles_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * 3958.8 * asin(min(1.0, sqrt(a)))


def _gemini_radius(category: ReportCategory, report: db.CrewReport) -> float | None:
    """Braydin's radius function, once `app.gemini` publishes `suggest_notice_radius`.

    Expected: `suggest_notice_radius(hazard_label, lat, lon, source, evidence) -> float | None`,
    returning None when Gemini is unresponsive. Any error or missing function means "use
    the default".
    """
    try:
        from app import gemini

        suggest = getattr(gemini, "suggest_notice_radius", None)
        if suggest is None:
            return None
        value = suggest(HAZARD_LABELS[category], report.lat, report.lon, "crew_report", [report.id])
        return float(value) if isinstance(value, int | float) else None
    except Exception:
        return None
