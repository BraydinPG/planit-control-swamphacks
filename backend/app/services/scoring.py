"""Compute and store a site's score from its stored data (T051).

Reads the site's recent Observations (freshness applied), active alerts, and crew reports
through the same loaders `GET /api/sites/{id}` uses, then saves a new `HazardScore` row.
`GET /api/sites` shows the newest row. The refresh loop that fetches feeds and calls this
on a schedule is separate work.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.sites import load_active_alerts, load_observations, load_reports
from app.db import models as db
from app.rules.score import compute_score
from app.rules.settings import RuleSettings
from app.schemas import HazardScore


def score_site(
    session: Session, site_id: str, now: datetime, settings: RuleSettings | None = None
) -> HazardScore:
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
    score = compute_score(
        site_id,
        load_observations(session, site_id, now),
        load_active_alerts(session, site_id),
        load_reports(session, site_id),
        now,
        previous,
        settings,
        site=session.get(db.Site, site_id),
    )
    session.add(
        db.HazardScore(
            id=f"score:{site_id}:{now.isoformat()}",
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
    session.commit()
    return score
