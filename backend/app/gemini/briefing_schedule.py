"""6 PM site-local briefing schedule (T058A).

Every BRIEFING_CHECK_SECONDS, each site with an assigned team is checked, but only when
the team's organization has at least one supervisor to review it. Unassigned sites and
organizations without a supervisor get no briefings. Once it is
18:00 or later in the site's time zone and that site has no briefing for the next
workday, one is generated and stored. A server that was down at 6 PM catches up later
the same evening; a briefing is never generated twice for the same workday, and never
on request.

Time zones come from the NWS point lookup (`timeZone`) and are saved in `sites.timezone`.
When NWS cannot be reached, the state's main time zone is used for that run without
being saved, so the next run tries NWS again.
"""

import logging
import socket
import threading
from collections.abc import Callable
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as db
from app.gemini.briefings import ForecastSource, briefing_id, generate_site_briefing, next_workday
from app.gemini.client import GeminiClient, get_gemini_client
from app.ingestion.nws import NwsClient
from app.ingestion.settings import get_ingestion_settings
from app.outlook import EventOutlookService, get_event_outlook_service
from app.schemas import Briefing, DataState, HazardType
from app.services.alerts import audit

logger = logging.getLogger(__name__)

BRIEFING_TIME = time(18)
SCHEDULE_ACTOR = f"system:briefing-schedule@{socket.gethostname()[:60]}"

# Main time zone per state, used only when the NWS lookup fails.
STATE_TIMEZONES = {
    "AK": "America/Anchorage", "AL": "America/Chicago", "AR": "America/Chicago",
    "AZ": "America/Phoenix", "CA": "America/Los_Angeles", "CO": "America/Denver",
    "CT": "America/New_York", "DC": "America/New_York", "DE": "America/New_York",
    "FL": "America/New_York", "GA": "America/New_York", "HI": "Pacific/Honolulu",
    "IA": "America/Chicago", "ID": "America/Boise", "IL": "America/Chicago",
    "IN": "America/Indiana/Indianapolis", "KS": "America/Chicago", "KY": "America/New_York",
    "LA": "America/Chicago", "MA": "America/New_York", "MD": "America/New_York",
    "ME": "America/New_York", "MI": "America/Detroit", "MN": "America/Chicago",
    "MO": "America/Chicago", "MS": "America/Chicago", "MT": "America/Denver",
    "NC": "America/New_York", "ND": "America/Chicago", "NE": "America/Chicago",
    "NH": "America/New_York", "NJ": "America/New_York", "NM": "America/Denver",
    "NV": "America/Los_Angeles", "NY": "America/New_York", "OH": "America/New_York",
    "OK": "America/Chicago", "OR": "America/Los_Angeles", "PA": "America/New_York",
    "RI": "America/New_York", "SC": "America/New_York", "SD": "America/Chicago",
    "TN": "America/Chicago", "TX": "America/Chicago", "UT": "America/Denver",
    "VA": "America/New_York", "VT": "America/New_York", "WA": "America/Los_Angeles",
    "WI": "America/Chicago", "WV": "America/New_York", "WY": "America/Denver",
}  # fmt: skip

PointLookup = Callable[[db.Site], dict]


class BriefingSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Off by default: every backend shares one database, so exactly one of them (the
    # deployed server, or one named laptop) turns this on. Otherwise backends race to write
    # the same briefings, and the first one wins whatever its own feeds could fetch.
    briefing_schedule_enabled: bool = False
    briefing_check_seconds: float = 60.0
    # The 6 PM run needs forecasts through 19:00 tomorrow: about 25 hours, plus margin.
    briefing_forecast_hours: int = 36


def site_timezone(session: Session, site: db.Site, lookup: PointLookup | None) -> ZoneInfo | None:
    """The site's IANA time zone: stored, then NWS (and stored), then the state fallback."""
    if site.timezone:
        zone = _zone(site.timezone)
        if zone is not None:
            return zone
    if lookup is not None:
        try:
            name = lookup(site).get("timeZone")
        except Exception as exc:  # NWS down or not configured: fall back below
            logger.info("NWS time zone lookup failed for %s: %s", site.id, type(exc).__name__)
            name = None
        zone = _zone(name) if isinstance(name, str) else None
        if zone is not None:
            site.timezone = name
            session.commit()
            return zone
    return _zone(STATE_TIMEZONES.get(site.region or "", ""))


def is_due(now: datetime, tz: ZoneInfo) -> bool:
    """True from 18:00 site-local time until midnight."""
    return now.astimezone(tz).time() >= BRIEFING_TIME


def run_due_briefings(
    session: Session,
    now: datetime,
    gemini: GeminiClient,
    forecasts: ForecastSource,
    lookup: PointLookup | None,
    outlooks: EventOutlookService | None = None,
) -> list[Briefing]:
    """Generate every briefing that is due. One failing site never blocks the others."""
    generated: list[Briefing] = []
    supervised = select(db.Membership.organization_id).where(db.Membership.role == "supervisor")
    sites = session.scalars(
        select(db.Site)
        .join(db.Team, db.Team.site_id == db.Site.id)
        .where(db.Team.organization_id.in_(supervised))
        .order_by(db.Site.id)
    ).all()
    for site in sites:
        try:
            tz = site_timezone(session, site, lookup)
            if tz is None:
                logger.warning("No time zone for %s; briefing skipped", site.id)
                continue
            if not is_due(now, tz):
                continue
            workday, _, _ = next_workday(now, tz)
            if session.get(db.Briefing, briefing_id(site.id, workday)) is not None:
                continue
            briefing = generate_site_briefing(session, site, tz, now, gemini, forecasts, outlooks)
            # spec.md section 10: log scheduled briefing generation, and which backend did it.
            audit(session, SCHEDULE_ACTOR, "briefing.generate", briefing.id, now)
            session.commit()
            generated.append(briefing)
        except Exception:
            session.rollback()
            logger.exception("Briefing for %s failed; it will be retried", site.id)
    return generated


def nws_forecast_source(hours: int) -> ForecastSource:
    """Forecast readings from Rudra's NWS weather feed, with a longer horizon."""
    from app.ingestion.nws_weather import NwsWeatherFeed

    feed = NwsWeatherFeed.from_settings(get_ingestion_settings())
    feed.forecast_hours = hours

    def forecasts(site: db.Site, now: datetime):
        return [
            o
            for o in feed.fetch([site], now)
            if o.hazard_type == HazardType.FORECAST and o.data_state == DataState.FORECAST
        ]

    return forecasts


class BriefingScheduler:
    """Background thread that runs `run_due_briefings` on an interval."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        gemini: GeminiClient,
        forecasts: ForecastSource,
        lookup: PointLookup | None,
        interval_seconds: float = 60.0,
        outlooks: EventOutlookService | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.gemini = gemini
        self.forecasts = forecasts
        self.lookup = lookup
        self.interval_seconds = interval_seconds
        self.outlooks = outlooks
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="briefing-schedule", daemon=True)

    def start(self) -> "BriefingScheduler":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()

    def run_once(self, now: datetime | None = None) -> list[Briefing]:
        session = self.session_factory()
        try:
            return run_due_briefings(
                session,
                now or datetime.now(UTC),
                self.gemini,
                self.forecasts,
                self.lookup,
                self.outlooks,
            )
        finally:
            session.close()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception:  # never let one bad run stop the schedule
                logger.exception("Briefing schedule run failed")
            self._stop.wait(self.interval_seconds)


def start_briefing_scheduler() -> BriefingScheduler | None:
    """Start the schedule at app startup. Off when disabled or without a database."""
    settings = BriefingSettings()
    if not settings.briefing_schedule_enabled:
        logger.info("Briefing schedule disabled (BRIEFING_SCHEDULE_ENABLED=false)")
        return None
    from app.db import DatabaseSettingsError, get_database_url, get_session

    try:
        get_database_url()
    except DatabaseSettingsError:
        logger.warning("Briefing schedule not started: DATABASE_URL is not configured")
        return None
    nws = NwsClient.from_settings(get_ingestion_settings())
    return BriefingScheduler(
        get_session,
        get_gemini_client(),
        nws_forecast_source(settings.briefing_forecast_hours),
        nws.point,
        settings.briefing_check_seconds,
        get_event_outlook_service(),
    ).start()


def _zone(name: str | None) -> ZoneInfo | None:
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None
