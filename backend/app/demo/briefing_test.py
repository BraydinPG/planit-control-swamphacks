"""A second organization that checks the 6 PM briefing schedule on its own (T058A).

`python -m app.demo briefing-test` gives one real, live-data site a team in its own
organization, supervised by `BRIEFING_TEST_SUPERVISOR_USER_ID` (an Auth0 user ID kept in
the uncommitted backend/.env). It removes that site's stored briefings, so the next 6 PM
site-local run of the schedule, on the one backend with `BRIEFING_SCHEDULE_ENABLED`,
writes a new one with no seed involved. The supervisor then sees it under Briefings.

It never touches the demo organization. Running it again resets the same rows.
"""

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.db import models as db

TEST_ORG_ID = "briefing-test-org"
TEST_TEAM_ID = "briefing-test-team"
TEST_MEMBERSHIP_ID = "briefing-test-supervisor"
# Greenland Energy Center, Jacksonville FL: Eastern time, so its 6 PM comes first.
TEST_SITE_ID = "eia860m-FL-56799"
TEST_TIMEZONE = "America/New_York"


@dataclass(frozen=True)
class BriefingTest:
    site_id: str
    site_name: str
    next_run_local: datetime


def setup_briefing_test(
    session: Session, supervisor_user_id: str, now: datetime, site_id: str = TEST_SITE_ID
) -> BriefingTest:
    """Create or reset the test organization; return when the schedule will brief it."""
    if not supervisor_user_id or supervisor_user_id.startswith("demo|"):
        raise ValueError("Set BRIEFING_TEST_SUPERVISOR_USER_ID to a real Auth0 user ID")
    site = session.get(db.Site, site_id)
    if site is None:
        raise LookupError(f"Site {site_id} is missing. Import the EIA-860M sites first.")
    taken = session.scalar(
        select(db.Team.organization_id).where(
            db.Team.site_id == site_id, db.Team.organization_id != TEST_ORG_ID
        )
    )
    if taken is not None:
        raise ValueError(f"Site {site_id} already has a team in another organization")
    if site.timezone is None:
        site.timezone = TEST_TIMEZONE  # what the NWS point lookup returns for Jacksonville

    session.execute(
        delete(db.Membership).where(
            or_(
                db.Membership.organization_id == TEST_ORG_ID,
                db.Membership.user_id == supervisor_user_id,
            )
        )
    )
    session.execute(delete(db.Team).where(db.Team.organization_id == TEST_ORG_ID))
    session.execute(delete(db.Briefing).where(db.Briefing.site_id == site_id))
    session.flush()
    session.merge(db.Organization(id=TEST_ORG_ID, name="Briefing Schedule Test (Braydin)"))
    session.flush()
    session.add(
        db.Team(
            id=TEST_TEAM_ID,
            organization_id=TEST_ORG_ID,
            name="Briefing test team",
            site_id=site_id,
        )
    )
    session.flush()
    session.add(
        db.Membership(
            id=TEST_MEMBERSHIP_ID,
            user_id=supervisor_user_id,
            organization_id=TEST_ORG_ID,
            role="supervisor",
        )
    )
    session.commit()
    return BriefingTest(site.id, site.name, next_six_pm(now, ZoneInfo(site.timezone)))


def next_six_pm(now: datetime, tz: ZoneInfo) -> datetime:
    """When the schedule will brief the site: 18:00 local today, or now when already past.

    A site is due from 18:00 until midnight, so after 6 PM the next check (within
    `BRIEFING_CHECK_SECONDS`) writes the briefing right away.
    """
    local = now.astimezone(tz)
    six_pm = datetime.combine(local.date(), time(18), tzinfo=tz)
    return max(local, six_pm)
