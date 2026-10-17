"""Demo scenario seed (T069). Every row is simulated and labeled so.

Run from backend/ (reads backend/.env):

    python -m app.demo seed        # restore the demo; safe to run again
    python -m app.demo strike 2    # replay lightning step 2 (resets the countdown)

`seed` first removes the previous demo rows, then writes the same scenario relative to
the time it runs:

- One Everglades-style site (`demo-everglades`), not an EIA-860M location, with one
  organization and one team assigned to it.
- `memberships` linking the Auth0 demo crew and supervisor accounts, read from
  `DEMO_CREW_USER_ID` and `DEMO_SUPERVISOR_USER_ID` (Auth0 user IDs, kept in the
  uncommitted backend/.env). Without them, the seed uses `demo|crew` and
  `demo|supervisor`, which no real account can sign in as. Teammates join the same team
  as crew through `DEMO_EXTRA_CREW_USER_IDS` (comma-separated Auth0 user IDs).
- Simulated NWS-shaped heat, humidity, rain-chance, and Flood Warning readings.
- A confirmed wildlife crew report, with the supervisor's sent instruction.
- A confirmed flood notice built from that simulated Flood Warning, so the site detail
  shows the flood's expected remaining duration (T050, T036B). Its instruction is left
  unsent, so the demo supervisor can send one.
- Lightning replay step 1 inside 10 miles: an active, simulated stop-work alert with its
  30-minute countdown. `strike 2` replays step 2 and resets the countdown.
- The stored score, and the next-day briefing produced by the same function the 6 PM
  schedule calls (Gemini off, so it is the deterministic template).

Only rows tied to the demo site, organization, team, demo notices, and the two demo
accounts are removed. EIA-860M sites and other organizations are untouched. Audit events
are never deleted. The seed adds its own `demo.seed` event.

Live feeds: the refresh loop skips the demo site (`location_type="demo_site"`), so its
scripted readings, score, and alert stay as seeded while every other site gets live data.
Re-run `seed` before presenting to restart the 30-minute countdown and tomorrow's briefing.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.db import models as db
from app.gemini.briefings import generate_site_briefing, next_workday
from app.gemini.client import GeminiClient
from app.ingestion import nws_weather
from app.ingestion.geo import destination, direction_from, distance_miles
from app.ingestion.lightning import StrikeStore, replay_steps
from app.outlook import EventOutlookService
from app.schemas import (
    Briefing,
    DataState,
    Evidence,
    EvidenceKind,
    HazardType,
    NoticeSource,
    NoticeStatus,
    Observation,
    RadiusSource,
    ReportCategory,
    ReviewStatus,
    Severity,
)
from app.services.alerts import apply_lightning_rule, audit
from app.services.refresh import DEMO_LOCATION_TYPE, observation_row
from app.services.reports import DEFAULT_RADIUS_MILES, HAZARD_LABELS, notice_recipients
from app.services.scoring import score_site

DEMO_ORG_ID = "demo-org"
DEMO_TEAM_ID = "demo-team"
DEMO_SITE_ID = "demo-everglades"
WILDLIFE_REPORT_ID = "demo-report-wildlife"
WILDLIFE_NOTICE_ID = "demo-notice-wildlife"
FLOOD_NOTICE_ID = "demo-notice-flood"
FLASH_FLOOD_NOTICE_ID = "demo-notice-flash-flood"
FLASH_FLOOD_ALERT_ID = "demo-nws-flash-flood-warning"
FLOOD_ALERT_ID = "demo-nws-flood-warning"
CREW_MEMBERSHIP_ID = "demo-membership-crew"
SUPERVISOR_MEMBERSHIP_ID = "demo-membership-supervisor"
PLACEHOLDER_CREW = "demo|crew"
PLACEHOLDER_SUPERVISOR = "demo|supervisor"
SEED_ACTOR = "system:demo-seed"

SITE_LAT, SITE_LON = 25.3950, -80.5830  # inland of Florida City, near Everglades NP
SITE_TIMEZONE = "America/New_York"
SIMULATED = "simulated demo replay"

# Observed now (heat index pushes the heat factor) and tomorrow's forecast peaks.
CURRENT_WEATHER = (
    (nws_weather.TEMPERATURE, 94.0, "°F"),
    (nws_weather.RELATIVE_HUMIDITY, 68.0, "%"),
    (nws_weather.HEAT_INDEX, 112.0, "°F"),
)
FORECAST = (  # (local hour tomorrow, label, value, unit)
    (10, nws_weather.HEAT_INDEX, 104.0, "°F"),
    (14, nws_weather.HEAT_INDEX, 113.0, "°F"),
    (14, nws_weather.TEMPERATURE, 95.0, "°F"),
    (16, nws_weather.PRECIPITATION_PROBABILITY, 80.0, "%"),
)
WILDLIFE_NOTE = "Simulated demo report: alligator on the levee access road by the culvert."
WILDLIFE_INSTRUCTION = (
    "Use the north gate. Keep clear of the levee access road until wildlife control "
    "has removed the alligator. (Simulated demo instruction.)"
)


@dataclass(frozen=True)
class DemoAccounts:
    crew_user_id: str = PLACEHOLDER_CREW
    supervisor_user_id: str = PLACEHOLDER_SUPERVISOR
    # More crew members on the demo team, e.g. each teammate's own account.
    extra_crew_user_ids: tuple[str, ...] = ()

    @property
    def user_ids(self) -> list[str]:
        return [self.crew_user_id, self.supervisor_user_id, *self.extra_crew_user_ids]

    @property
    def linked(self) -> bool:
        """True when both are real Auth0 accounts, not the placeholders."""
        return (
            self.crew_user_id != PLACEHOLDER_CREW
            and self.supervisor_user_id != PLACEHOLDER_SUPERVISOR
        )


@dataclass(frozen=True)
class SeedResult:
    site_id: str
    alert_id: str
    risk_score: float
    risk_level: str
    briefing: Briefing
    accounts_linked: bool


def seed_demo(
    session: Session,
    now: datetime,
    accounts: DemoAccounts,
    outlooks: EventOutlookService | None = None,
) -> SeedResult:
    """Remove the previous demo rows and write the scenario relative to `now`."""
    if now.tzinfo is None:
        raise ValueError("now must include a timezone")
    if accounts.crew_user_id == accounts.supervisor_user_id:
        raise ValueError("The crew and supervisor demo accounts must be different users")
    if len(set(accounts.user_ids)) != len(accounts.user_ids):
        raise ValueError("Each demo account can appear only once")
    now = now.astimezone(UTC)
    _remove_previous(session, accounts)

    site = _site_and_people(session, accounts)
    readings = _readings(now - timedelta(minutes=5))
    for o in readings:
        session.add(observation_row(o))
    _wildlife_report(session, accounts, now)
    _flood_notice(session, accounts, now)
    session.commit()

    strike = _strike(site, 0, now - timedelta(minutes=4))
    session.add(observation_row(strike))
    session.commit()
    lightning = apply_lightning_rule(session, site.id, [strike], now)

    score = score_site(session, site.id, now, observations=[*readings, strike])
    briefing = generate_site_briefing(
        session,
        site,
        ZoneInfo(SITE_TIMEZONE),
        now,
        GeminiClient(None, None, 1),  # Gemini off: the deterministic template briefing
        _forecasts(now),
        outlooks,
    )
    audit(session, SEED_ACTOR, "demo.seed", DEMO_SITE_ID, now)
    session.commit()
    return SeedResult(
        site_id=site.id,
        alert_id=lightning.alert.id,
        risk_score=score.risk_score,
        risk_level=score.risk_level,
        briefing=briefing,
        accounts_linked=accounts.linked,
    )


def replay_lightning(session: Session, step: int, now: datetime) -> str:
    """Store replay step `step` (1-based) at the demo site and apply the stop-work rule.

    Works while the API runs: the alert is stored, so the next read shows the new
    countdown. Returns the rule's transition (`triggered` or `reset`).
    """
    steps = replay_steps()
    if not 1 <= step <= len(steps):
        raise ValueError(f"Replay step must be 1 to {len(steps)}")
    site = session.get(db.Site, DEMO_SITE_ID)
    if site is None:
        raise LookupError("The demo site is missing. Run `python -m app.demo seed` first.")
    strike = _strike(site, step - 1, now.astimezone(UTC))
    session.merge(observation_row(strike))
    session.commit()
    result = apply_lightning_rule(session, site.id, [strike], now)
    score_site(session, site.id, now)
    return result.transition.value


# ---- scenario parts ----


def _site_and_people(session: Session, accounts: DemoAccounts) -> db.Site:
    session.merge(db.Organization(id=DEMO_ORG_ID, name="Demo Utility Co. (simulated)"))
    site = session.merge(
        db.Site(
            id=DEMO_SITE_ID,
            name="Everglades Field Site (demo)",
            lat=SITE_LAT,
            lon=SITE_LON,
            location_type=DEMO_LOCATION_TYPE,
            source="Demo scenario (simulated; not an EIA-860M location)",
            region="FL",
            timezone=SITE_TIMEZONE,
        )
    )
    session.flush()
    session.add(
        db.Team(
            id=DEMO_TEAM_ID,
            organization_id=DEMO_ORG_ID,
            name="Everglades Line Crew (demo)",
            site_id=DEMO_SITE_ID,
        )
    )
    session.flush()
    session.add_all(
        [
            db.Membership(
                id=CREW_MEMBERSHIP_ID,
                user_id=accounts.crew_user_id,
                organization_id=DEMO_ORG_ID,
                team_id=DEMO_TEAM_ID,
                role="crew",
            ),
            db.Membership(
                id=SUPERVISOR_MEMBERSHIP_ID,
                user_id=accounts.supervisor_user_id,
                organization_id=DEMO_ORG_ID,
                role="supervisor",
            ),
            *(
                db.Membership(
                    id=f"{CREW_MEMBERSHIP_ID}-{n}",
                    user_id=user_id,
                    organization_id=DEMO_ORG_ID,
                    team_id=DEMO_TEAM_ID,
                    role="crew",
                )
                for n, user_id in enumerate(accounts.extra_crew_user_ids, start=2)
            ),
        ]
    )
    session.flush()
    return site


def _readings(fetched_at: datetime) -> list[Observation]:
    """Current simulated NWS-shaped readings: heat, humidity, and a Flood Warning."""
    observed = fetched_at - timedelta(minutes=5)
    common = {
        "site_id": DEMO_SITE_ID,
        "source": nws_weather.SOURCE,
        "lat": SITE_LAT,
        "lon": SITE_LON,
        "data_state": DataState.SIMULATED,
        "simulated": True,
        "fetched_at": fetched_at,
    }
    weather = [
        Observation(
            id=f"demo-weather:{label.lower().replace(' ', '-')}",
            hazard_type=HazardType.WEATHER,
            value=value,
            unit=unit,
            observed_at=observed,
            label=label,
            source_ref="demo-station",
            **common,
        )
        for label, value, unit in CURRENT_WEATHER
    ]
    flood = Observation(
        id=FLOOD_ALERT_ID,
        hazard_type=HazardType.FLOOD_ALERT,
        value="Flood Warning",
        observed_at=fetched_at - timedelta(hours=3),
        valid_at=fetched_at + timedelta(hours=12),
        label=f"Flood Warning ({SIMULATED})",
        source_ref=FLOOD_ALERT_ID,
        **common,
    )
    return [*weather, flood]


def _forecasts(now: datetime):
    """Tomorrow's simulated forecast peaks, handed to the briefing like the NWS source."""
    tz = ZoneInfo(SITE_TIMEZONE)
    workday, _, _ = next_workday(now, tz)
    issued = now - timedelta(minutes=30)
    rows = [
        Observation(
            id=f"demo-forecast:{label.lower().replace(' ', '-')}:{hour:02d}",
            site_id=DEMO_SITE_ID,
            source=f"NWS ({SIMULATED})",
            hazard_type=HazardType.FORECAST,
            value=value,
            unit=unit,
            lat=SITE_LAT,
            lon=SITE_LON,
            observed_at=issued,
            valid_at=datetime(workday.year, workday.month, workday.day, hour, tzinfo=tz),
            data_state=DataState.FORECAST,
            simulated=True,
            label=label,
        )
        for hour, label, value, unit in FORECAST
    ]
    return lambda site, at: rows


def _wildlife_report(session: Session, accounts: DemoAccounts, now: datetime) -> None:
    created = now - timedelta(hours=2)
    confirmed = created + timedelta(minutes=10)
    lat, lon = destination(SITE_LAT, SITE_LON, 120, 0.2)
    session.add(
        db.CrewReport(
            id=WILDLIFE_REPORT_ID,
            organization_id=DEMO_ORG_ID,
            team_id=DEMO_TEAM_ID,
            site_id=DEMO_SITE_ID,
            reporter_id=accounts.crew_user_id,
            category=ReportCategory.WILDLIFE,
            hazard_present=True,
            note=WILDLIFE_NOTE,
            photo_url=None,  # no photo is committed for the demo
            lat=round(lat, 5),
            lon=round(lon, 5),
            review_status=ReviewStatus.CONFIRMED,
            reviewed_by=accounts.supervisor_user_id,
            reviewed_at=confirmed,
            confirmed_category=ReportCategory.WILDLIFE,
            confirmed_severity=Severity.MODERATE,
            notice_id=WILDLIFE_NOTICE_ID,
            created_at=created,
        )
    )
    notice = db.HazardNotice(
        id=WILDLIFE_NOTICE_ID,
        hazard_label=HAZARD_LABELS[ReportCategory.WILDLIFE],
        source=NoticeSource.CREW_REPORT,
        source_ref=WILDLIFE_REPORT_ID,
        lat=round(lat, 5),
        lon=round(lon, 5),
        radius_miles=DEFAULT_RADIUS_MILES[ReportCategory.WILDLIFE],
        radius_source=RadiusSource.DEFAULT,
        status=NoticeStatus.CONFIRMED,
        created_at=created,
        confirmed_by=accounts.supervisor_user_id,
        confirmed_at=confirmed,
        instruction=WILDLIFE_INSTRUCTION,
        instruction_sent_at=confirmed + timedelta(minutes=2),
        evidence=[
            _evidence(WILDLIFE_REPORT_ID, EvidenceKind.REPORT, "Crew report: wildlife", created)
        ],
    )
    session.add(notice)
    session.flush()
    _deliver(session, notice, accounts, created)
    audit(session, accounts.supervisor_user_id, "report.confirm", WILDLIFE_REPORT_ID, confirmed)


def _flood_notice(session: Session, accounts: DemoAccounts, now: datetime) -> None:
    created = now - timedelta(minutes=90)
    notice = db.HazardNotice(
        id=FLOOD_NOTICE_ID,
        hazard_label=HAZARD_LABELS[ReportCategory.FLOODING],
        source=NoticeSource.FEED,
        source_ref=FLOOD_ALERT_ID,
        lat=SITE_LAT,
        lon=SITE_LON,
        radius_miles=DEFAULT_RADIUS_MILES[ReportCategory.FLOODING],
        radius_source=RadiusSource.DEFAULT,
        status=NoticeStatus.CONFIRMED,
        created_at=created,
        confirmed_by=accounts.supervisor_user_id,
        confirmed_at=created + timedelta(minutes=10),
        evidence=[
            # "simulated" in the label makes the outlook a labeled historical replay.
            _evidence(
                FLOOD_ALERT_ID,
                EvidenceKind.OBSERVATION,
                f"NWS Flood Warning ({SIMULATED})",
                now - timedelta(hours=3, minutes=5),
            ),
            # T050A: the outlook conditions on a trusted event start, never on the
            # notice's creation or the warning's issue time.
            _evidence(
                f"{FLOOD_NOTICE_ID}:start",
                EvidenceKind.EVENT_START,
                f"Flood began ({SIMULATED})",
                now - timedelta(hours=2, minutes=50),
            ),
        ],
    )
    session.add(notice)
    session.flush()
    _deliver(session, notice, accounts, created)

    # A second, separate event: a Flash Flood is its own target with its own model.
    flash = db.HazardNotice(
        id=FLASH_FLOOD_NOTICE_ID,
        hazard_label=HAZARD_LABELS[ReportCategory.FLOODING],
        source=NoticeSource.FEED,
        source_ref=FLASH_FLOOD_ALERT_ID,
        lat=SITE_LAT,
        lon=SITE_LON,
        radius_miles=DEFAULT_RADIUS_MILES[ReportCategory.FLOODING],
        radius_source=RadiusSource.DEFAULT,
        status=NoticeStatus.CONFIRMED,
        created_at=now - timedelta(minutes=45),
        confirmed_by=accounts.supervisor_user_id,
        confirmed_at=now - timedelta(minutes=35),
        evidence=[
            _evidence(
                FLASH_FLOOD_ALERT_ID,
                EvidenceKind.OBSERVATION,
                f"NWS Flash Flood Warning ({SIMULATED})",
                now - timedelta(minutes=70),
            ),
            _evidence(
                f"{FLASH_FLOOD_NOTICE_ID}:start",
                EvidenceKind.EVENT_START,
                f"Flash flooding began ({SIMULATED})",
                now - timedelta(minutes=65),
            ),
        ],
    )
    session.add(flash)
    session.flush()
    _deliver(session, flash, accounts, flash.created_at)


def _deliver(
    session: Session, notice: db.HazardNotice, accounts: DemoAccounts, at: datetime
) -> None:
    """The same delivery receipts the notice services write, plus the confirmation."""
    recipients = notice_recipients(session, notice)
    for team_id in recipients.team_ids:
        audit(session, "system:notices", "notice.deliver", f"{notice.id}->{team_id}", at)
    for supervisor_id in recipients.supervisor_ids:
        audit(
            session,
            "system:notices",
            "notice.supervisor.deliver",
            f"{notice.id}->{supervisor_id}",
            at,
        )
    audit(session, accounts.supervisor_user_id, "notice.confirm", notice.id, notice.confirmed_at)
    if notice.instruction_sent_at:
        audit(
            session,
            accounts.supervisor_user_id,
            "notice.instruction.send",
            notice.id,
            notice.instruction_sent_at,
        )
        for team_id in recipients.team_ids:
            audit(
                session,
                accounts.supervisor_user_id,
                "notice.instruction.deliver",
                f"{notice.id}->{team_id}",
                notice.instruction_sent_at,
            )


def _strike(site: db.Site, index: int, at: datetime) -> Observation:
    """Replay step `index` (0-based) shaped like the lightning feed's per-site reading."""
    item = replay_steps()[index]
    lat, lon = destination(site.lat, site.lon, item["bearing_deg"], item["distance_mi"])
    strike = StrikeStore().submit(lat, lon, at, simulated=True)  # normalizes only
    miles = distance_miles(site.lat, site.lon, strike.lat, strike.lon)
    direction = direction_from(site.lat, site.lon, strike.lat, strike.lon)
    return strike.model_copy(
        update={
            "id": f"{strike.id}:{site.id}",
            "site_id": site.id,
            "value": round(miles, 1),
            "unit": "mi",
            "label": f"Strike {miles:.1f} mi {direction} (replay)",
            "source_ref": strike.id,
            "fetched_at": at,
        }
    )


def _evidence(id: str, kind: EvidenceKind, label: str, at: datetime) -> dict:
    return Evidence(id=id, kind=kind, label=label, observed_at=at).model_dump(mode="json")


def _remove_previous(session: Session, accounts: DemoAccounts) -> None:
    """Delete the last run's demo rows, children first. Audit events are kept."""
    alert_ids = select(db.Alert.id).where(db.Alert.site_id == DEMO_SITE_ID)
    report_ids = select(db.CrewReport.id).where(db.CrewReport.site_id == DEMO_SITE_ID)
    session.execute(delete(db.Acknowledgement).where(db.Acknowledgement.alert_id.in_(alert_ids)))
    # Demo notices and those from rehearsal reports at the demo site. Feed notices are
    # regional events other sites share, so they stay.
    session.execute(
        delete(db.HazardNotice).where(
            or_(
                db.HazardNotice.id.in_(
                    [WILDLIFE_NOTICE_ID, FLOOD_NOTICE_ID, FLASH_FLOOD_NOTICE_ID]
                ),
                db.HazardNotice.source_ref.in_(report_ids),
            )
        )
    )
    for model in (db.Alert, db.Observation, db.HazardScore, db.HazardPrediction, db.CrewReport):
        session.execute(delete(model).where(model.site_id == DEMO_SITE_ID))
    session.execute(
        delete(db.Briefing).where(
            or_(db.Briefing.site_id == DEMO_SITE_ID, db.Briefing.organization_id == DEMO_ORG_ID)
        )
    )
    session.execute(
        delete(db.Membership).where(
            or_(
                db.Membership.organization_id == DEMO_ORG_ID,
                db.Membership.user_id.in_(accounts.user_ids),
            )
        )
    )
    session.execute(delete(db.Team).where(db.Team.organization_id == DEMO_ORG_ID))
    session.flush()
