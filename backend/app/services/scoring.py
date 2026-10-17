"""Compute and store a site's score from its stored data (T051).

Reads the site's recent Observations (freshness applied) and active alerts through the
site-detail loaders, plus all confirmed-present reports without the UI's display limit,
then saves a new `HazardScore` row. T055 can join a report-confirmation transaction.
`GET /api/sites` shows the newest row.

The refresh loop (`app.services.refresh`, T049B) passes `observations`: the readings it
just fetched, which hold each feed's current state. Other callers, such as a report
confirmation (T055), score from stored history. That history also holds older "none" rows
and expired alerts, so `current_readings` keeps only each feed's latest fetch (T076).
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.sites import load_active_alerts, load_observations, report_schema
from app.db import models as db
from app.rules.score import compute_score
from app.rules.settings import RuleSettings
from app.schemas import HazardScore, HazardType, Observation, ReviewStatus


def current_readings(observations: list[Observation]) -> list[Observation]:
    """Each feed's readings from its latest fetch. Older fetches are history, not state.

    A feed is its hazard type and source. Lightning is one feed whatever its source,
    because its "none" reading switches between replay and GOES GLM. Rows without
    `fetched_at` (not stored by the refresh loop) are kept.
    """

    def feed(o: Observation) -> tuple:
        if o.hazard_type == HazardType.LIGHTNING_STRIKE:
            return (o.hazard_type,)
        return (o.hazard_type, o.source)

    latest: dict[tuple, datetime] = {}
    for o in observations:
        if o.fetched_at is not None:
            key = feed(o)
            latest[key] = max(latest.get(key, o.fetched_at), o.fetched_at)
    return [o for o in observations if o.fetched_at is None or o.fetched_at == latest[feed(o)]]


def score_site(
    session: Session,
    site_id: str,
    now: datetime,
    settings: RuleSettings | None = None,
    observations: list[Observation] | None = None,
    *,
    commit: bool = True,
) -> HazardScore:
    """Persist one refresh; commit=False joins the caller's confirmation transaction.

    Serialize refreshes per site on PostgreSQL so concurrent confirmations retain
    every committed contribution. Scoring must not use the UI's 50-report display limit.
    """
    session.execute(select(db.Site.id).where(db.Site.id == site_id).with_for_update())
    previous_row = session.scalars(
        select(db.HazardScore)
        .where(db.HazardScore.site_id == site_id)
        .order_by(db.HazardScore.created_at.desc())
        .limit(1)
    ).first()
    previous = None
    if previous_row is not None:
        previous = HazardScore(
            site_id=previous_row.site_id,
            risk_score=previous_row.risk_score,
            risk_level=previous_row.risk_level,
            factor_contributions=previous_row.factor_contributions,
            model_version=previous_row.model_version,
            model_is_fallback=previous_row.model_is_fallback,
            confidence=previous_row.confidence,
            data_completeness=previous_row.data_completeness,
            created_at=previous_row.created_at,
        )
    reports = session.scalars(
        select(db.CrewReport).where(
            db.CrewReport.site_id == site_id,
            db.CrewReport.review_status == ReviewStatus.CONFIRMED,
            db.CrewReport.hazard_present.is_(True),
        )
    ).all()
    score = compute_score(
        site_id,
        observations
        if observations is not None
        else current_readings(load_observations(session, site_id, now)),
        load_active_alerts(session, site_id),
        [report_schema(report) for report in reports],
        now,
        previous,
        settings,
        site=session.get(db.Site, site_id),
    )
    # Multiple confirmations may share a request timestamp. Keep versions uniquely
    # ordered for existing latest-score reads without changing the canonical API.
    if previous_row is not None:
        previous_at = previous_row.created_at
        if previous_at.tzinfo is None:
            previous_at = previous_at.replace(tzinfo=UTC)
        if score.created_at <= previous_at:
            score = score.model_copy(update={"created_at": previous_at + timedelta(microseconds=1)})
    session.add(
        db.HazardScore(
            id=f"score:{site_id}:{uuid4().hex}",
            site_id=site_id,
            risk_score=score.risk_score,
            risk_level=score.risk_level,
            factor_contributions=[f.model_dump(mode="json") for f in score.factor_contributions],
            model_version=score.model_version,
            model_is_fallback=score.model_is_fallback,
            confidence=score.confidence,
            data_completeness=score.data_completeness,
            previous_score=score.previous_score,
            created_at=score.created_at,
        )
    )
    if commit:
        session.commit()
    else:
        session.flush()
    return score
