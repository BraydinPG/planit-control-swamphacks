"""`GET /api/sites` (T041) and `GET /api/sites/{id}` (T042).

Read-only views over Braydin's Tiger Data models. A site without a computed score
returns null `risk_score`, `risk_level`, and `updated_at` ("not scored yet"), never
zero risk.

Access (T062, spec.md section 8): every request needs a valid Auth0 token. A supervisor
(`read:all_sites`) sees every site. Crew (`read:assigned_sites`) see only the site assigned
to their team, through their `memberships` row; with no membership they see none.
"""

from datetime import UTC, datetime, timedelta
from math import asin, cos, radians, sin, sqrt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, get_now
from app.db import models as db
from app.ingestion.settings import get_ingestion_settings
from app.outlook import EventOutlookService, event_context_from_notice, get_event_outlook_service
from app.schemas import (
    Acknowledgement,
    Alert,
    AlertState,
    CrewReport,
    DataState,
    EventOutlook,
    FactorContribution,
    HazardNotice,
    HazardScore,
    Observation,
    SiteDetail,
    SiteSummary,
    TeamRef,
)
from app.security import AuthenticatedUser, CurrentUser, membership_for, roles

router = APIRouter(prefix="/api/sites", tags=["sites"])

UNSCORED_MODEL_VERSION = "unscored"
TOP_FACTOR_COUNT = 3
OBSERVATION_WINDOW = timedelta(hours=24)
OBSERVATION_LIMIT = 500
REPORT_LIMIT = 50
NOTICE_LIMIT = 20

DbSession = Annotated[Session, Depends(get_db)]
Now = Annotated[datetime, Depends(get_now)]
OutlookService = Annotated[EventOutlookService, Depends(get_event_outlook_service)]


@router.get("", response_model=list[SiteSummary])
def list_sites(user: AuthenticatedUser, session: DbSession) -> list[SiteSummary]:
    query = select(db.Site).options(selectinload(db.Site.assigned_team))
    visible = visible_site_ids(session, user)
    if visible is not None:
        query = query.where(db.Site.id.in_(visible))
    sites = session.scalars(query).all()
    scores = _latest_scores(session)
    alert_counts = dict(
        session.execute(
            select(db.Alert.site_id, func.count())
            .where(db.Alert.state == AlertState.ACTIVE)
            .group_by(db.Alert.site_id)
        ).all()
    )
    summaries = [_summary(s, scores.get(s.id), alert_counts.get(s.id, 0)) for s in sites]
    return sorted(summaries, key=_sort_key)


@router.get("/{site_id}", response_model=SiteDetail)
def get_site(
    site_id: str,
    user: AuthenticatedUser,
    session: DbSession,
    now: Now,
    outlooks: OutlookService,
) -> SiteDetail:
    visible = visible_site_ids(session, user)
    if visible is not None and site_id not in visible:
        raise HTTPException(status_code=403, detail="This site is not assigned to your team")
    site = session.scalar(
        select(db.Site).where(db.Site.id == site_id).options(selectinload(db.Site.assigned_team))
    )
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    score = _latest_scores(session, site_id).get(site_id)
    alerts = load_active_alerts(session, site_id)
    summary = _summary(site, score, len(alerts))
    notices = _notices(session, site, viewer=user)
    return SiteDetail(
        **summary.model_dump(),
        location_type=site.location_type,
        source=site.source,
        region=site.region,
        observations=load_observations(session, site_id, now),
        score=_score(score) if score else None,
        alerts=alerts,
        reports=load_reports(session, site_id, viewer=user),
        notices=notices,
        event_outlook=_event_outlook(outlooks, summary, notices, now),
    )


def _event_outlook(
    outlooks: EventOutlookService,
    site: SiteSummary,
    notices: list[HazardNotice],
    now: datetime,
) -> EventOutlook | None:
    """T050 advisory for the newest confirmed flood notice covering the site, else None.

    Computed after the score and alerts and never fed back into them.
    """
    for notice in sorted(notices, key=lambda n: n.confirmed_at or n.created_at, reverse=True):
        context = event_context_from_notice(notice, site, now)
        if context is not None:
            return outlooks.outlook(site, context)
    return None


def visible_site_ids(session: Session, user: CurrentUser) -> set[str] | None:
    """Sites the caller may read: None means every site."""
    if user.can(roles.READ_ALL_SITES):
        return None
    if not user.can(roles.READ_ASSIGNED_SITES):
        raise HTTPException(status_code=403, detail="Missing permission: read:assigned_sites")
    membership = membership_for(session, user)
    team = membership.team if membership else None
    return {team.site_id} if team and team.site_id else set()


def _sort_key(site: SiteSummary) -> tuple:
    """Assigned first, then scored by risk descending, then unscored, then name."""
    return (
        site.assigned_team is None,
        site.risk_score is None,
        -(site.risk_score or 0),
        site.name,
    )


def _summary(site: db.Site, score: db.HazardScore | None, active_alerts: int) -> SiteSummary:
    team = site.assigned_team
    factors = (
        [FactorContribution.model_validate(f) for f in score.factor_contributions] if score else []
    )
    return SiteSummary(
        id=site.id,
        name=site.name,
        lat=site.lat,
        lon=site.lon,
        assigned_team=TeamRef(id=team.id, name=team.name, organization_id=team.organization_id)
        if team
        else None,
        risk_score=score.risk_score if score else None,
        risk_level=score.risk_level if score else None,
        updated_at=_aware(score.created_at) if score else None,
        active_alerts=active_alerts,
        top_factors=sorted(factors, key=lambda f: -abs(f.contribution))[:TOP_FACTOR_COUNT],
        data_completeness=score.data_completeness if score else 0.0,
        model_version=score.model_version if score else UNSCORED_MODEL_VERSION,
    )


def _latest_scores(session: Session, site_id: str | None = None) -> dict[str, db.HazardScore]:
    newest = select(db.HazardScore.site_id, func.max(db.HazardScore.created_at).label("at"))
    if site_id is not None:
        newest = newest.where(db.HazardScore.site_id == site_id)
    newest = newest.group_by(db.HazardScore.site_id).subquery()
    rows = session.scalars(
        select(db.HazardScore).join(
            newest,
            (db.HazardScore.site_id == newest.c.site_id)
            & (db.HazardScore.created_at == newest.c.at),
        )
    ).all()
    return {row.site_id: row for row in rows}


def _score(row: db.HazardScore) -> HazardScore:
    return HazardScore(
        site_id=row.site_id,
        risk_score=row.risk_score,
        risk_level=row.risk_level,
        factor_contributions=row.factor_contributions,
        model_version=row.model_version,
        model_is_fallback=row.model_is_fallback,
        confidence=row.confidence,
        data_completeness=row.data_completeness,
        previous_score=row.previous_score,
        created_at=_aware(row.created_at),
    )


def load_observations(session: Session, site_id: str, now: datetime) -> list[Observation]:
    """Readings observed in the last 24 hours plus forecasts still ahead, newest first."""
    rows = session.scalars(
        select(db.Observation)
        .where(db.Observation.site_id == site_id)
        .where(
            or_(
                db.Observation.observed_at >= now - OBSERVATION_WINDOW,
                db.Observation.valid_at >= now,
            )
        )
        .order_by(db.Observation.observed_at.desc())
        .limit(OBSERVATION_LIMIT)
    ).all()
    stale_after = get_ingestion_settings().stale_after
    return [_observation(row, now, stale_after) for row in rows]


def _observation(row: db.Observation, now: datetime, stale_after: timedelta) -> Observation:
    """Apply freshness at read time: a stored "observed" reading can be stale by now."""
    fetched = _aware(row.fetched_at or row.observed_at)
    state = row.data_state
    if state in (DataState.OBSERVED, DataState.FORECAST) and now - fetched > stale_after:
        state = DataState.STALE
    return Observation(
        id=row.id,
        site_id=row.site_id,
        source=row.source,
        hazard_type=row.hazard_type,
        value=_value(row.value),
        unit=row.unit,
        lat=row.lat,
        lon=row.lon,
        observed_at=_aware(row.observed_at),
        valid_at=_aware(row.valid_at) if row.valid_at else None,
        data_state=state,
        simulated=row.simulated,
        label=row.label,
        source_ref=row.source_ref,
        fetched_at=_aware(row.fetched_at) if row.fetched_at else None,
    )


def load_active_alerts(session: Session, site_id: str) -> list[Alert]:
    rows = session.scalars(
        select(db.Alert)
        .where(db.Alert.site_id == site_id, db.Alert.state == AlertState.ACTIVE)
        .order_by(db.Alert.triggered_at.desc())
    ).all()
    return alert_schemas(session, list(rows))


def alert_schemas(session: Session, rows: list[db.Alert]) -> list[Alert]:
    """Alert rows as API objects, each with its acknowledgements."""
    acks: dict[str, list[Acknowledgement]] = {}
    if rows:
        for ack in session.scalars(
            select(db.Acknowledgement).where(db.Acknowledgement.alert_id.in_([r.id for r in rows]))
        ):
            acks.setdefault(ack.alert_id, []).append(
                Acknowledgement(
                    id=ack.id,
                    alert_id=ack.alert_id,
                    user_id=ack.user_id,
                    acknowledged_at=_aware(ack.acknowledged_at),
                )
            )
    return [
        Alert(
            id=row.id,
            site_id=row.site_id,
            rule=row.rule,
            state=row.state,
            triggered_at=_aware(row.triggered_at),
            latest_event_at=_aware(row.latest_event_at),
            clear_after=_aware(row.clear_after) if row.clear_after else None,
            distance_miles=row.distance_miles,
            trigger_observation_ids=row.trigger_observation_ids or [],
            evidence=row.evidence or [],
            simulated=row.simulated,
            is_prototype_rule=row.is_prototype_rule,
            acknowledgements=acks.get(row.id, []),
        )
        for row in rows
    ]


def load_reports(
    session: Session, site_id: str, *, viewer: CurrentUser | None = None
) -> list[CrewReport]:
    query = select(db.CrewReport).where(db.CrewReport.site_id == site_id)
    if viewer is not None:
        membership = membership_for(session, viewer)
        organization_id = membership.organization_id if membership else None
        query = query.where(
            or_(
                db.CrewReport.hazard_present.is_(True),
                db.CrewReport.organization_id == organization_id,
            )
        )
    rows = session.scalars(
        query.order_by(db.CrewReport.created_at.desc()).limit(REPORT_LIMIT)
    ).all()
    return [report_schema(r) for r in rows]


def report_schema(r: db.CrewReport) -> CrewReport:
    """A crew report row as an API object."""
    return CrewReport(
        id=r.id,
        organization_id=r.organization_id,
        team_id=r.team_id,
        site_id=r.site_id,
        reporter_id=r.reporter_id,
        category=r.category,
        hazard_present=r.hazard_present,
        note=r.note,
        photo_url=r.photo_url,
        lat=r.lat,
        lon=r.lon,
        review_status=r.review_status,
        reviewed_by=r.reviewed_by,
        reviewed_at=_aware(r.reviewed_at) if r.reviewed_at else None,
        confirmed_category=r.confirmed_category,
        confirmed_severity=r.confirmed_severity,
        enrichment=r.enrichment,
        notice_id=r.notice_id,
        created_at=_aware(r.created_at),
    )


def _notices(
    session: Session, site: db.Site, *, viewer: CurrentUser | None = None
) -> list[HazardNotice]:
    """Notices whose radius covers the site. Notices store coordinates, not a site ID."""
    rows = session.scalars(
        select(db.HazardNotice).order_by(db.HazardNotice.created_at.desc())
    ).all()
    covering = [n for n in rows if _miles(site.lat, site.lon, n.lat, n.lon) <= n.radius_miles][
        :NOTICE_LIMIT
    ]
    return [
        HazardNotice(
            id=n.id,
            hazard_label=n.hazard_label,
            source=n.source,
            source_ref=n.source_ref,
            lat=n.lat,
            lon=n.lon,
            radius_miles=n.radius_miles,
            radius_source=n.radius_source,
            status=n.status,
            created_at=_aware(n.created_at),
            confirmed_by=n.confirmed_by,
            confirmed_at=_aware(n.confirmed_at) if n.confirmed_at else None,
            suggested_instruction=(
                n.suggested_instruction
                if viewer and viewer.role == "supervisor" and viewer.sub == n.confirmed_by
                else None
            ),
            instruction=n.instruction,
            instruction_sent_at=_aware(n.instruction_sent_at) if n.instruction_sent_at else None,
            evidence=n.evidence or [],
        )
        for n in covering
    ]


def _miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in statute miles."""
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * 3958.8 * asin(sqrt(a))


def _value(raw: str | None) -> float | str | None:
    """DB stores values as text. Numbers come back as floats; labels stay text."""
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return raw


def _aware(value: datetime) -> datetime:
    """Treat naive timestamps from the driver as UTC."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)
