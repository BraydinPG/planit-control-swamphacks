"""T051A: existing refresh/alert/persistence integration, offline in-memory DB only."""

from sqlalchemy import select

from app.db import models as db
from app.schemas import HazardType
from app.services.refresh import Feed, refresh_all
from tests.score_scenarios import NOW, active_alert
from tests.test_refresh import reading, strike_feed
from tests.test_refresh import session as session


def test_refresh_rescores_after_authoritative_lightning_transition(session):
    from datetime import timedelta

    # First ingestion triggers the existing deterministic rule, then scores its alert.
    refresh_all(session, NOW, [strike_feed(4.2, NOW)])
    first = session.scalars(select(db.HazardScore).where(db.HazardScore.site_id == "site-a")).one()
    assert first.risk_score == 3

    def quiet(sites, now):
        return [
            reading(
                s,
                HazardType.LIGHTNING_STRIKE,
                now,
                source="GOES GLM",
                label="Synthetic healthy no-flash result",
            )
            for s in sites
        ]

    # The original rule alone decides clearance after 30 strike-free minutes; the
    # scorer reads that state on the existing refresh path. No new scheduler/route.
    later = NOW + timedelta(minutes=31)
    refresh_all(session, later, [Feed("GOES GLM", HazardType.LIGHTNING_STRIKE, quiet)])
    scores = list(
        session.scalars(
            select(db.HazardScore)
            .where(db.HazardScore.site_id == "site-a")
            .order_by(db.HazardScore.created_at)
        )
    )
    alert = session.scalars(select(db.Alert).where(db.Alert.site_id == "site-a")).one()
    assert alert.state == "cleared"
    assert [s.risk_score for s in scores] == [3, 0]
    assert scores[-1].previous_score == 3
    assert scores[-1].factor_contributions[0]["contribution"] == 0


def test_score_consumer_does_not_infer_alert_clearance_from_elapsed_clock(session):
    from datetime import timedelta

    from app.services.scoring import score_site

    alert = active_alert(site_id="site-a", clear_after=NOW - timedelta(minutes=1))
    session.add(
        db.Alert(
            **{
                k: v
                for k, v in alert.model_dump().items()
                if k not in {"evidence", "acknowledgements"}
            }
        )
    )
    session.commit()
    result = score_site(session, "site-a", NOW)
    persisted = session.scalars(select(db.Alert).where(db.Alert.id == alert.id)).one()
    assert result.risk_score == 3 and result.data_completeness == 0
    assert persisted.state == "active" and persisted.clear_after.replace(tzinfo=NOW.tzinfo) < NOW
