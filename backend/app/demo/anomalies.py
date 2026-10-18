"""`python -m app.demo anomalies`: one labeled demo site per weather anomaly type.

The user asked for seeded data that shows every data-dependent feature for each anomaly
the model covers, while behaving like the live system:

- Each site's readings have the same shape as the live feeds (NWS weather and alerts, NHC,
  USGS, lightning replay), labeled simulated, so the real scoring rules read them.
- Each event gets a notice with the real delivery receipts, and the demo supervisor
  confirms it through the real per-organization path (`confirm_hazard`), which is what
  lets its duration outlook appear. Instructions are left for a supervisor to send.
- Lightning goes through the real stop-work rule and 30-minute timer, and the warnings and
  earthquake through the prototype tiered stop-work rules (T049C). Kerrville's Flash
  Flood Warning (tier 1) hides its lightning (tier 2); Mobile merges the hurricane and
  flash flood (tier 1); Macon merges lightning and a Severe Thunderstorm Warning (tier 2).
- Scores come from the real algorithm. Briefings come from the 6 PM schedule.

It also removes every crew report outside the Everglades site (and its notices) so the
team can file their own. The Everglades site keeps Rudra's T069 wildlife scenario
(`app/demo/scenario.py`), which this command restores from his own building blocks with
the demo accounts already linked in the database: the confirmed alligator report and its
instruction, heat, the flood and flash-flood notices, lightning stop-work, and a briefing.
The species panel there shows the live USFWS animals and critical-habitat boundaries.
Live feeds skip demo sites (`location_type="demo_site"`), so nothing here is overwritten.
Rows removed are first written to a backup file.
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.db import models as db
from app.demo import scenario
from app.demo.scenario import (
    CREW_MEMBERSHIP_ID,
    DEMO_ORG_ID,
    DEMO_SITE_ID,
    FLASH_FLOOD_NOTICE_ID,
    FLOOD_NOTICE_ID,
    SUPERVISOR_MEMBERSHIP_ID,
    WILDLIFE_NOTICE_ID,
    DemoAccounts,
    _strike,
)
from app.gemini.briefings import generate_site_briefing
from app.gemini.client import GeminiClient
from app.ingestion import nws_alerts, nws_weather, severe_storms
from app.ingestion.geo import destination, direction_from, distance_miles
from app.ingestion.lightning import LIVE_SOURCE as LIVE_LIGHTNING
from app.ingestion.lightning import StrikeStore
from app.outlook import EventOutlookService
from app.schemas import (
    DataState,
    Evidence,
    EvidenceKind,
    HazardType,
    NoticeSource,
    NoticeStatus,
    Observation,
    RadiusSource,
)
from app.security import CurrentUser, roles
from app.services.alerts import apply_lightning_rule, apply_stop_work_rules, audit
from app.services.hazards import confirm_hazard
from app.services.refresh import DEMO_LOCATION_TYPE, observation_row
from app.services.reports import notice_recipients
from app.services.scoring import score_site

SEED_ACTOR = "system:demo-anomalies"
SCENARIO_SOURCE = "Scenario site (not an EIA-860M location)"


@dataclass(frozen=True)
class Anomaly:
    key: str  # site/team/notice id suffix
    name: str
    state: str
    lat: float
    lon: float
    timezone: str
    weather: tuple[float, float, float]  # temperature °F, humidity %, heat index °F
    hazard_label: str = ""  # notice label; the outlook adapter's event type for weather
    product: str = ""  # the simulated NWS/NHC/USGS product named in the evidence
    started_hours_ago: float = 2.0
    radius_miles: float = 10.0
    flood_alert: str | None = None  # NWS flood product at the site, if any
    storm_alert: str | None = None  # NWS tornado / severe thunderstorm product, if any
    extra: tuple[str, ...] = field(default=())  # "hurricane", "earthquake"
    # Thunderstorm lightning that realistically comes with the event: (miles, bearing
    # degrees, minutes ago). Nothing requires it; it's simply what such storms look like.
    lightning: tuple[float, float, int] | None = None


ANOMALIES = (
    Anomaly(
        "flood",
        "Baton Rouge Field Site (demo)",
        "LA",
        30.4515,
        -91.1871,
        "America/Chicago",
        (78, 92, 79),
        "flooding",
        "NWS Flood Warning",
        6.0,
        5.0,
        flood_alert="Flood Warning",
    ),
    Anomaly(
        "flash-flood",
        "Kerrville Field Site (demo)",
        "TX",
        30.0474,
        -99.1403,
        "America/Chicago",
        (74, 96, 74),
        "flooding",
        "NWS Flash Flood Warning",
        1.5,
        5.0,
        flood_alert="Flash Flood Warning",
        lightning=(3.0, 270.0, 6),  # the thunderstorm producing the flash flood
    ),
    Anomaly(
        "heat",
        "Phoenix Field Site (demo)",
        "AZ",
        33.4484,
        -112.0740,
        "America/Phoenix",
        (111, 14, 114),
        "Heat Index Exceedance",
        "NWS Excessive Heat Warning",
        3.0,
    ),
    Anomaly(
        "high-wind",
        "Casper Field Site (demo)",
        "WY",
        42.8666,
        -106.3131,
        "America/Denver",
        (48, 30, 48),
        "High Wind",
        "NWS High Wind Warning",
        2.0,
    ),
    Anomaly(
        "heavy-rain",
        "Macon Field Site (demo)",
        "GA",
        32.8407,
        -83.6324,
        "America/New_York",
        (70, 97, 70),
        "Heavy Rain",
        "NWS Flood Watch for heavy rain",
        2.0,
        flood_alert="Flood Watch",
        # Embedded thunderstorms in the rain band. Lightning and the Severe Thunderstorm
        # Warning share danger tier 2, so the interface merges them into one stop-work alert.
        storm_alert="Severe Thunderstorm Warning",
        lightning=(9.0, 200.0, 12),
    ),
    Anomaly(
        "winter-storm",
        "Duluth Field Site (demo)",
        "MN",
        46.7867,
        -92.1005,
        "America/Chicago",
        (24, 88, 24),
        "Winter Storm",
        "NWS Winter Storm Warning",
        4.0,
    ),
    Anomaly(
        "hurricane",
        "Mobile Field Site (demo)",
        "AL",
        30.6954,
        -88.0399,
        "America/Chicago",
        (84, 85, 94),
        "hurricane",
        "NHC advisory and NWS Hurricane Warning",
        5.0,
        50.0,
        flood_alert="Flash Flood Warning",  # the storm's rain
        extra=("hurricane",),
        lightning=(6.0, 150.0, 15),  # an outer rain band
    ),
    Anomaly(
        "earthquake",
        "Ridgecrest Field Site (demo)",
        "CA",
        35.6225,
        -117.6709,
        "America/Los_Angeles",
        (68, 25, 68),
        "earthquake",
        "USGS M5.4 earthquake",
        0.5,  # inside the prototype 60-minute earthquake stop-work window
        25.0,
        extra=("earthquake",),
    ),
)


@dataclass(frozen=True)
class AnomalyResult:
    site_id: str
    label: str
    risk_score: float
    risk_level: str


def seed_anomalies(
    session: Session,
    now: datetime,
    backup_dir: Path,
    gemini: GeminiClient | None = None,
    outlooks: EventOutlookService | None = None,
) -> list[AnomalyResult]:
    now = now.astimezone(UTC)
    supervisor_id = _demo_supervisor(session)
    _backup_and_clear(session, backup_dir, now)
    supervisor = CurrentUser(supervisor_id, "supervisor", roles.SUPERVISOR_PERMISSIONS)

    results = []
    for a in ANOMALIES:
        site = _site_and_team(session, a)
        readings = _readings(site, a, now)
        for o in readings:
            session.add(observation_row(o))
        session.commit()
        notice = _notice(session, site, a, readings, now)
        confirm_hazard(session, notice.id, supervisor, now)
        if a.lightning:
            miles, bearing, minutes_ago = a.lightning
            strike = _strike_at(site, miles, bearing, now - timedelta(minutes=minutes_ago))
            readings = [*readings, strike]
        else:
            readings = [*readings, _no_lightning(site, now)]
        session.add(observation_row(readings[-1]))
        session.commit()
        # Every stop-work rule, as the live refresh runs them (T049C tiers).
        apply_stop_work_rules(session, site, readings, now)
        score = score_site(session, site.id, now, observations=readings)
        results.append(AnomalyResult(site.id, a.hazard_label, score.risk_score, score.risk_level))

    score = restore_everglades(session, now, gemini or GeminiClient(None, None, 1), outlooks)
    results.append(AnomalyResult(DEMO_SITE_ID, "wildlife", score.risk_score, score.risk_level))
    audit(session, SEED_ACTOR, "demo.anomalies", ",".join(r.site_id for r in results), now)
    session.commit()
    return results


def _demo_supervisor(session: Session) -> str:
    membership = session.get(db.Membership, SUPERVISOR_MEMBERSHIP_ID)
    if membership is None or membership.organization_id != DEMO_ORG_ID:
        raise ValueError("Run `python -m app.demo seed` first: the demo supervisor isn't linked")
    return membership.user_id


def _linked_accounts(session: Session) -> DemoAccounts:
    """The demo accounts as they're linked now, so restoring never relinks anyone."""
    crew = session.get(db.Membership, CREW_MEMBERSHIP_ID)
    if crew is None:
        raise ValueError("Run `python -m app.demo seed` first: the demo crew account isn't linked")
    extras = session.scalars(
        select(db.Membership.user_id)
        .where(db.Membership.id.like(f"{CREW_MEMBERSHIP_ID}-%"))
        .order_by(db.Membership.id)
    ).all()
    return DemoAccounts(crew.user_id, _demo_supervisor(session), tuple(extras))


def restore_everglades(
    session: Session,
    now: datetime,
    gemini: GeminiClient,
    outlooks: EventOutlookService | None = None,
) -> db.HazardScore:
    """Rebuild Rudra's Everglades wildlife scenario (T069) at `now`, from his own pieces,
    without touching teams or memberships."""
    accounts = _linked_accounts(session)
    _clear_sites(session, [DEMO_SITE_ID], everglades=True)
    site = session.get(db.Site, DEMO_SITE_ID)
    site.source = SCENARIO_SOURCE  # the site's name is the one place that says "(demo)"
    readings = [_as_live(o) for o in scenario._readings(now - timedelta(minutes=5))]
    for o in readings:
        session.add(observation_row(o))
    scenario._wildlife_report(session, accounts, now)
    scenario._flood_notice(session, accounts, now)
    # Rudra's scenario adds a second flooding notice (Flash Flood) to show both models;
    # Kerrville shows the flash flood, and a site never lists the same hazard twice.
    session.execute(delete(db.HazardNotice).where(db.HazardNotice.id == FLASH_FLOOD_NOTICE_ID))
    session.commit()
    strike = _as_live(_strike(site, 0, now - timedelta(minutes=4)))
    session.add(observation_row(strike))
    session.commit()
    apply_lightning_rule(session, site.id, [strike], now)
    score = score_site(session, site.id, now, observations=[*readings, strike])
    generate_site_briefing(
        session,
        site,
        ZoneInfo(scenario.SITE_TIMEZONE),
        now,
        gemini,
        _live_source(scenario._forecasts(now)),
        outlooks,
    )
    audit(session, SEED_ACTOR, "demo.everglades.restore", DEMO_SITE_ID, now)
    session.commit()
    return score


def _site_id(a: Anomaly) -> str:
    return f"demo-{a.key}"


def _site_and_team(session: Session, a: Anomaly) -> db.Site:
    site = session.merge(
        db.Site(
            id=_site_id(a),
            name=a.name,
            lat=a.lat,
            lon=a.lon,
            location_type=DEMO_LOCATION_TYPE,
            source=SCENARIO_SOURCE,
            region=a.state,
            timezone=a.timezone,
        )
    )
    session.flush()
    session.merge(
        db.Team(
            id=f"demo-team-{a.key}",
            organization_id=DEMO_ORG_ID,
            name=f"{a.state} {a.key.replace('-', ' ').title()} Crew",
            site_id=site.id,
        )
    )
    session.flush()
    return site


def _common(site: db.Site, now: datetime) -> dict:
    return {
        "site_id": site.id,
        "lat": site.lat,
        "lon": site.lon,
        "data_state": DataState.OBSERVED,
        "simulated": False,
        "fetched_at": now - timedelta(minutes=2),
    }


def _weather(site: db.Site, values: tuple[float, float, float], now: datetime) -> list[Observation]:
    temperature, humidity, heat_index = values
    rows = (
        (nws_weather.TEMPERATURE, temperature, "°F"),
        (nws_weather.RELATIVE_HUMIDITY, humidity, "%"),
        (nws_weather.HEAT_INDEX, heat_index, "°F"),
    )
    return [
        Observation(
            id=f"{site.id}:weather:{label.lower().replace(' ', '-')}",
            source=nws_weather.SOURCE,
            hazard_type=HazardType.WEATHER,
            value=value,
            unit=unit,
            observed_at=now - timedelta(minutes=10),
            label=label,
            source_ref=f"{site.id}-station",
            **_common(site, now),
        )
        for label, value, unit in rows
    ]


def _readings(site: db.Site, a: Anomaly, now: datetime) -> list[Observation]:
    readings = _weather(site, a.weather, now)
    common = _common(site, now)
    readings.append(
        Observation(
            id=f"{site.id}:flood-alert",
            source="NWS",
            hazard_type=HazardType.FLOOD_ALERT,
            value=a.flood_alert,
            observed_at=now - timedelta(hours=a.started_hours_ago, minutes=10),
            valid_at=now + timedelta(hours=12) if a.flood_alert else None,
            label=a.flood_alert or nws_alerts.NO_ACTIVE_ALERTS,
            source_ref=f"{site.id}:flood-alert",
            **common,
        )
    )
    readings.append(
        Observation(
            id=f"{site.id}:storm-alert",
            source="NWS",
            hazard_type=HazardType.SEVERE_STORM,
            value=a.storm_alert,
            observed_at=now - timedelta(minutes=40),
            valid_at=now + timedelta(hours=1) if a.storm_alert else None,
            label=a.storm_alert or severe_storms.NO_ACTIVE_ALERTS,
            source_ref=f"{site.id}:storm-alert",
            **common,
        )
    )
    if "hurricane" in a.extra:
        lat, lon = destination(site.lat, site.lon, 180.0, 35.0)  # storm center 35 mi south
        readings += [
            Observation(
                id=f"{site.id}:nhc",
                source="NHC",
                hazard_type=HazardType.HURRICANE,
                value=90.0,
                unit="kt",
                observed_at=now - timedelta(minutes=30),
                label="Hurricane (90 kt)",
                source_ref="demo-al99",
                **{**common, "lat": lat, "lon": lon},
            ),
            Observation(
                id=f"{site.id}:nws-tropical",
                source="NWS",
                hazard_type=HazardType.HURRICANE,
                value="Hurricane Warning",
                observed_at=now - timedelta(hours=a.started_hours_ago),
                valid_at=now + timedelta(hours=24),
                label="Hurricane Warning",
                source_ref=f"{site.id}:hurricane-warning",
                **common,
            ),
        ]
    if "earthquake" in a.extra:
        lat, lon = destination(site.lat, site.lon, 45.0, 6.0)  # epicenter 6 mi NE
        readings.append(
            Observation(
                id=f"{site.id}:quake",
                source="USGS",
                hazard_type=HazardType.EARTHQUAKE,
                value=5.4,
                unit="mw",
                observed_at=now - timedelta(hours=a.started_hours_ago),
                label="M5.4 earthquake 6 mi NE",
                source_ref="demo-usgs-ci99",
                **{**common, "lat": lat, "lon": lon},
            )
        )
    return readings


def _notice(
    session: Session, site: db.Site, a: Anomaly, readings: list[Observation], now: datetime
) -> db.HazardNotice:
    """A feed notice shaped like the live ones, with the delivery receipts they get."""
    source = next(
        (o for o in readings if o.hazard_type in {HazardType.HURRICANE, HazardType.EARTHQUAKE}),
        next((o for o in readings if o.hazard_type == HazardType.FLOOD_ALERT and o.value), None),
    )
    started = now - timedelta(hours=a.started_hours_ago)
    notice = db.HazardNotice(
        id=_notice_id(a),
        hazard_label=a.hazard_label,
        source=NoticeSource.FEED,
        source_ref=source.id if source else f"{site.id}:{a.key}-product",
        lat=site.lat,
        lon=site.lon,
        radius_miles=a.radius_miles,
        radius_source=RadiusSource.DEFAULT,
        status=NoticeStatus.POTENTIAL,
        created_at=started + timedelta(minutes=5),
        evidence=[
            # The demo site makes any outlook a labeled replay (app/outlook/events.py).
            _evidence(
                source.id if source else f"{site.id}:{a.key}-product",
                EvidenceKind.OBSERVATION,
                a.product,
                started,
            ),
            # The outlook conditions on a trusted event start, never the notice time.
            _evidence(
                f"{_notice_id(a)}:start",
                EvidenceKind.EVENT_START,
                f"{a.hazard_label.capitalize()} began",
                started,
            ),
        ],
    )
    session.add(notice)
    session.flush()
    recipients = notice_recipients(session, notice)
    for team_id in recipients.team_ids:
        audit(
            session,
            "system:notices",
            "notice.deliver",
            f"{notice.id}->{team_id}",
            notice.created_at,
        )
    for supervisor_id in recipients.supervisor_ids:
        audit(
            session,
            "system:notices",
            "notice.supervisor.deliver",
            f"{notice.id}->{supervisor_id}",
            notice.created_at,
        )
    session.commit()
    return notice


def _notice_id(a: Anomaly) -> str:
    return f"demo-anomaly-{a.key}"


def _as_live(o: Observation) -> Observation:
    """A scenario reading shown exactly like a live one. The demo site itself, never the
    reading, marks it: its name says "(demo)" and live feeds skip `demo_site` sites."""
    update = {"simulated": False}
    if o.data_state is DataState.SIMULATED:
        update["data_state"] = DataState.OBSERVED
    if o.hazard_type == HazardType.LIGHTNING_STRIKE:
        update["source"] = LIVE_LIGHTNING
        update["label"] = (o.label or "").replace(" (replay)", "")
    return o.model_copy(update=update)


def _live_source(source):
    return lambda site, at: [_as_live(o) for o in source(site, at)]


def _no_lightning(site: db.Site, now: datetime) -> Observation:
    """The live feed's "no strikes" reading, for scenario sites without a storm."""
    return Observation(
        id=f"ltg:{site.id}:none:{now.isoformat()}",
        site_id=site.id,
        source=LIVE_LIGHTNING,
        hazard_type=HazardType.LIGHTNING_STRIKE,
        value=None,
        label="No lightning within 30 mi in the last 60 min (GOES GLM)",
        lat=site.lat,
        lon=site.lon,
        observed_at=now - timedelta(minutes=1),
        fetched_at=now - timedelta(minutes=1),
        data_state=DataState.OBSERVED,
        simulated=False,
    )


def _strike_at(site: db.Site, miles: float, bearing: float, at: datetime) -> Observation:
    """A strike at a set distance, shaped like the live lightning feed's site reading."""
    lat, lon = destination(site.lat, site.lon, bearing, miles)
    strike = _as_live(StrikeStore().submit(lat, lon, at, simulated=True))  # normalizes only
    distance = distance_miles(site.lat, site.lon, strike.lat, strike.lon)
    direction = direction_from(site.lat, site.lon, strike.lat, strike.lon)
    return strike.model_copy(
        update={
            "id": f"{strike.id}:{site.id}",
            "site_id": site.id,
            "value": round(distance, 1),
            "unit": "mi",
            "label": f"Strike {distance:.1f} mi {direction}",
            "source_ref": strike.id,
            "fetched_at": at,
        }
    )


def _evidence(id: str, kind: EvidenceKind, label: str, at: datetime) -> dict:
    return Evidence(id=id, kind=kind, label=label, observed_at=at).model_dump(mode="json")


EVERGLADES_NOTICES = (WILDLIFE_NOTICE_ID, FLOOD_NOTICE_ID, FLASH_FLOOD_NOTICE_ID)


def _backup_and_clear(session: Session, backup_dir: Path, now: datetime) -> Path:
    """Write the rows about to be removed to a JSON file, then remove them, children first.

    Removed: every crew report outside the Everglades site and its notices, and the anomaly
    sites' rows. The Everglades scenario is rebuilt separately by `restore_everglades`.
    """
    anomaly_sites = [_site_id(a) for a in ANOMALIES]
    report_ids = list(
        session.scalars(select(db.CrewReport.id).where(db.CrewReport.site_id != DEMO_SITE_ID))
    )
    notice_ids = _anomaly_notice_ids(session) + list(
        session.scalars(
            select(db.HazardNotice.id).where(
                db.HazardNotice.source == NoticeSource.CREW_REPORT,
                db.HazardNotice.source_ref.in_(report_ids),
            )
        )
    )
    alert_ids = list(
        session.scalars(select(db.Alert.id).where(db.Alert.site_id.in_(anomaly_sites)))
    )

    def rows(model, condition):
        return [
            {c.name: _plain(getattr(r, c.key)) for c in model.__table__.columns}
            for r in session.scalars(select(model).where(condition))
        ]

    backup = {
        "crew_reports": rows(db.CrewReport, db.CrewReport.id.in_(report_ids)),
        "hazard_notices": rows(db.HazardNotice, db.HazardNotice.id.in_(notice_ids)),
        "notice_assessments": rows(
            db.NoticeAssessment, db.NoticeAssessment.notice_id.in_(notice_ids)
        ),
        "alerts": rows(db.Alert, db.Alert.id.in_(alert_ids)),
    }
    backup_dir.mkdir(parents=True, exist_ok=True)
    path = backup_dir / f"demo-reset-{now:%Y%m%dT%H%M%SZ}.json"
    path.write_text(json.dumps(backup, indent=1))

    session.execute(
        delete(db.NoticeAssessment).where(db.NoticeAssessment.notice_id.in_(notice_ids))
    )
    session.execute(delete(db.CrewReport).where(db.CrewReport.id.in_(report_ids)))
    session.execute(delete(db.HazardNotice).where(db.HazardNotice.id.in_(notice_ids)))
    _clear_sites(session, anomaly_sites)
    session.commit()
    return path


def _anomaly_notice_ids(session: Session) -> list[str]:
    """This command's notices, including ones from its first version, which used
    `demo-notice-{key}` ids; those are told apart from the Everglades scenario's by place."""
    ids = list(
        session.scalars(select(db.HazardNotice.id).where(db.HazardNotice.id.like("demo-anomaly-%")))
    )
    for a in ANOMALIES:
        old = session.get(db.HazardNotice, f"demo-notice-{a.key}")
        if old is not None and abs(old.lat - a.lat) < 1e-6 and abs(old.lon - a.lon) < 1e-6:
            ids.append(old.id)
    return ids


def _clear_sites(session: Session, site_ids: list[str], everglades: bool = False) -> None:
    """Readings, alerts, scores and briefings at these sites; for the Everglades site also
    its scenario's reports and notices. Briefings at anomaly sites come back from the 6 PM
    schedule; the Everglades restore writes its own."""
    if everglades:
        report_ids = list(
            session.scalars(select(db.CrewReport.id).where(db.CrewReport.site_id.in_(site_ids)))
        )
        notice_ids = list(
            session.scalars(
                select(db.HazardNotice.id).where(
                    or_(
                        db.HazardNotice.id.in_(EVERGLADES_NOTICES),
                        db.HazardNotice.source_ref.in_(report_ids),
                    )
                )
            )
        )
        session.execute(
            delete(db.NoticeAssessment).where(db.NoticeAssessment.notice_id.in_(notice_ids))
        )
        session.execute(delete(db.CrewReport).where(db.CrewReport.id.in_(report_ids)))
        session.execute(delete(db.HazardNotice).where(db.HazardNotice.id.in_(notice_ids)))
    alert_ids = select(db.Alert.id).where(db.Alert.site_id.in_(site_ids))
    session.execute(delete(db.Acknowledgement).where(db.Acknowledgement.alert_id.in_(alert_ids)))
    for model in (db.Alert, db.Observation, db.HazardScore, db.HazardPrediction, db.Briefing):
        session.execute(delete(model).where(model.site_id.in_(site_ids)))
    session.flush()


def _plain(value):
    return value.isoformat() if isinstance(value, datetime) else value
