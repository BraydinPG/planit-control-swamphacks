"""T049A: prototype hurricane and earthquake rules, factors, and potential notices."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import pi

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.gemini as gemini
from app.db import models as db
from app.rules.regional import (
    earthquake_detections,
    earthquake_factor,
    hurricane_detections,
    hurricane_factor,
)
from app.rules.score import compute_score
from app.rules.settings import RuleSettings
from app.schemas import DataState, HazardType, Observation
from app.security import CurrentUser, roles
from app.services.feed_notices import send_feed_notices
from app.services.hazards import confirm_hazard

NOW = datetime(2026, 10, 17, 18, 0, tzinfo=UTC)
SETTINGS = RuleSettings(_env_file=None)
MILES_PER_DEG_LAT = 3958.8 * pi / 180
SITE_LAT, SITE_LON = 25.76, -80.49


@dataclass(frozen=True)
class Site:
    id: str = "site-a"
    lat: float = SITE_LAT
    lon: float = SITE_LON


SITE = Site()


def north(miles: float) -> tuple[float, float]:
    return SITE_LAT + miles / MILES_PER_DEG_LAT, SITE_LON


def storm(miles: float, knots: float | None = 90.0, state=DataState.OBSERVED, sid="AL09"):
    lat, lon = north(miles)
    return Observation(
        id=f"nhc:site-a:{sid}:{NOW.isoformat()}",
        site_id="site-a",
        source="NHC",
        hazard_type=HazardType.HURRICANE,
        value=knots,
        unit="kt",
        label=f"Hurricane Test, {knots} kt, {miles:.0f} mi N of site",
        source_ref=sid,
        lat=lat,
        lon=lon,
        observed_at=NOW - timedelta(minutes=10),
        data_state=state,
    )


def nws(event: str | None, state=DataState.OBSERVED) -> Observation:
    return Observation(
        id=f"nws-tropical:site-a:{event}",
        site_id="site-a",
        source="NWS",
        hazard_type=HazardType.HURRICANE,
        value=event,
        label=event or "No active NWS hurricane or tropical storm alerts",
        source_ref=f"urn:{event}" if event else None,
        lat=SITE_LAT,
        lon=SITE_LON,
        observed_at=NOW - timedelta(minutes=5),
        data_state=state,
    )


def quake(miles: float, magnitude: float | None, state=DataState.OBSERVED, eid="us7000x"):
    lat, lon = north(miles)
    return Observation(
        id=f"usgs-eq:site-a:{eid}",
        site_id="site-a",
        source="USGS",
        hazard_type=HazardType.EARTHQUAKE,
        value=magnitude,
        unit="mw" if magnitude is not None else None,
        label=f"M{magnitude} test quake" if magnitude is not None else "No earthquakes",
        source_ref=eid,
        lat=lat,
        lon=lon,
        observed_at=NOW - timedelta(minutes=20),
        data_state=state,
    )


# Hurricane rule


@pytest.mark.parametrize(("miles", "fires"), [(10.0, True), (49.9, True), (50.1, False)])
def test_nhc_storm_distance(miles, fires) -> None:
    assert bool(hurricane_detections(SITE, [storm(miles)], SETTINGS)) is fires


def test_nhc_storm_distance_is_a_setting() -> None:
    wide = RuleSettings(_env_file=None, hurricane_storm_distance_miles=120.0)
    assert hurricane_detections(SITE, [storm(100.0)], wide)
    assert not hurricane_detections(SITE, [storm(100.0)], SETTINGS)


@pytest.mark.parametrize(
    ("event", "fires"),
    [
        ("Hurricane Warning", True),
        ("Tropical Storm Warning", True),
        ("Hurricane Watch", False),
        ("Tropical Storm Watch", False),
        (None, False),
    ],
)
def test_nws_warnings_fire_and_watches_do_not(event, fires) -> None:
    assert bool(hurricane_detections(SITE, [nws(event)], SETTINGS)) is fires


def test_unavailable_hurricane_reading_never_fires() -> None:
    assert not hurricane_detections(SITE, [storm(5.0, state=DataState.UNAVAILABLE)], SETTINGS)


def test_other_sites_readings_are_ignored() -> None:
    other = storm(5.0).model_copy(update={"site_id": "site-b"})
    assert not hurricane_detections(SITE, [other], SETTINGS)


# Earthquake rule


@pytest.mark.parametrize(
    ("miles", "magnitude", "fires"),
    [
        (10.0, 4.0, True),  # at the magnitude threshold
        (10.0, 3.9, False),
        (24.9, 5.0, True),
        (25.1, 5.0, False),
        (10.0, None, False),  # "none found" reading
    ],
)
def test_earthquake_magnitude_and_distance(miles, magnitude, fires) -> None:
    assert bool(earthquake_detections(SITE, [quake(miles, magnitude)], SETTINGS)) is fires


def test_earthquake_settings_are_configurable() -> None:
    loose = RuleSettings(_env_file=None, earthquake_min_magnitude=3.0, earthquake_distance_miles=60)
    assert earthquake_detections(SITE, [quake(55.0, 3.2)], loose)


# Factors


def test_factors_are_prototype_and_add_points() -> None:
    hurricane = hurricane_factor(SITE, [nws("Hurricane Warning")], SETTINGS)
    earthquake = earthquake_factor(SITE, [quake(10.0, 4.5)], SETTINGS)
    assert hurricane.contribution == SETTINGS.hurricane_points
    assert earthquake.contribution == SETTINGS.earthquake_points
    assert hurricane.is_prototype and earthquake.is_prototype
    assert "prototype" in hurricane.label and "prototype" in earthquake.label
    assert hurricane.source == "NWS" and earthquake.source == "USGS"
    assert earthquake.observed_at == NOW - timedelta(minutes=20)


def test_outside_settings_factor_adds_nothing() -> None:
    hurricane = hurricane_factor(SITE, [storm(80.0)], SETTINGS)
    earthquake = earthquake_factor(SITE, [quake(10.0, 3.0)], SETTINGS)
    assert hurricane.contribution == 0.0 and earthquake.contribution == 0.0


def test_stale_reading_still_counts_and_stays_labeled() -> None:
    factor = hurricane_factor(SITE, [storm(10.0, state=DataState.STALE)], SETTINGS)
    assert factor.contribution == SETTINGS.hurricane_points
    assert factor.data_state is DataState.STALE


def test_unavailable_feed_is_visible_not_zero_risk() -> None:
    factor = earthquake_factor(SITE, [quake(0.0, None, state=DataState.UNAVAILABLE)], SETTINGS)
    assert factor.contribution == 0.0
    assert factor.data_state is DataState.UNAVAILABLE
    assert "unknown" in factor.label


def test_no_feed_or_no_site_gives_no_factor() -> None:
    assert hurricane_factor(SITE, [], SETTINGS) is None
    assert earthquake_factor(None, [quake(10.0, 5.0)], SETTINGS) is None


def test_score_includes_regional_factors_without_changing_completeness() -> None:
    observations = [nws("Hurricane Warning"), quake(10.0, 4.5)]
    with_site = compute_score("site-a", observations, [], [], NOW, settings=SETTINGS, site=SITE)
    without = compute_score("site-a", observations, [], [], NOW, settings=SETTINGS)
    points = {f.factor: f.contribution for f in with_site.factor_contributions}
    assert points["hurricane"] == 2.0 and points["earthquake"] == 1.5
    assert with_site.risk_score == 3.5
    assert with_site.data_completeness == without.data_completeness
    assert "hurricane" not in {f.factor for f in without.factor_contributions}


# Potential notices


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    db.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as s:
        s.add(db.Organization(id="org-1", name="Sunbelt"))
        for site_id, (lat, lon) in {"site-a": (SITE_LAT, SITE_LON), "site-far": north(200)}.items():
            s.add(
                db.Site(
                    id=site_id,
                    name=site_id,
                    lat=lat,
                    lon=lon,
                    location_type="power_plant",
                    source="EIA-860M (representative)",
                )
            )
        s.flush()
        s.add_all(
            [
                db.Team(id="team-a", organization_id="org-1", name="Crew A", site_id="site-a"),
                db.Team(id="team-f", organization_id="org-1", name="Crew F", site_id="site-far"),
                db.Membership(
                    id="m-s", user_id="auth0|sup", organization_id="org-1", role="supervisor"
                ),
            ]
        )
        s.commit()
        yield s
    engine.dispose()


def notices(session: Session) -> list[db.HazardNotice]:
    return list(session.scalars(select(db.HazardNotice)))


def test_earthquake_sends_potential_notice_without_instruction(session) -> None:
    sent = send_feed_notices(session, SITE, [quake(10.0, 4.8)], NOW, SETTINGS)
    assert len(sent) == 1
    notice, recipients = sent[0]
    assert notice.hazard_label == "earthquake"
    assert notice.source == "feed" and notice.status == "potential"
    assert notice.instruction is None and notice.suggested_instruction is None
    assert notice.radius_miles == 25.0 and notice.radius_source == "default"
    assert recipients.team_ids == ["team-a"]
    assert recipients.supervisor_ids == ["auth0|sup"]


def test_hurricane_default_radius_is_50_miles(session) -> None:
    [(notice, _)] = send_feed_notices(session, SITE, [nws("Hurricane Warning")], NOW, SETTINGS)
    assert notice.hazard_label == "hurricane"
    assert notice.radius_miles == 50.0 and notice.radius_source == "default"
    assert (notice.lat, notice.lon) == (SITE_LAT, SITE_LON)


def test_outside_settings_send_no_notice(session) -> None:
    observations = [storm(80.0), nws("Hurricane Watch"), quake(10.0, 3.0), quake(40.0, 6.0)]
    assert send_feed_notices(session, SITE, observations, NOW, SETTINGS) == []
    assert notices(session) == []


@pytest.mark.parametrize("state", [DataState.STALE, DataState.UNAVAILABLE])
def test_stale_or_unavailable_reading_sends_no_notice(session, state) -> None:
    assert send_feed_notices(session, SITE, [storm(10.0, state=state)], NOW, SETTINGS) == []


def test_same_event_is_sent_once(session) -> None:
    send_feed_notices(session, SITE, [quake(10.0, 4.8)], NOW, SETTINGS)
    later = NOW + timedelta(minutes=5)
    assert send_feed_notices(session, SITE, [quake(10.0, 4.8)], later, SETTINGS) == []
    assert len(notices(session)) == 1


def test_valid_gemini_radius_is_used(session, monkeypatch) -> None:
    monkeypatch.setattr(gemini, "suggest_notice_radius", lambda *args: 12.0, raising=False)
    [(notice, _)] = send_feed_notices(session, SITE, [quake(10.0, 4.8)], NOW, SETTINGS)
    assert notice.radius_miles == 12.0 and notice.radius_source == "gemini"


@pytest.mark.parametrize("bad", [0, -3, 51, None, "wide"])
def test_invalid_gemini_radius_uses_default(session, monkeypatch, bad) -> None:
    monkeypatch.setattr(gemini, "suggest_notice_radius", lambda *args: bad, raising=False)
    [(notice, _)] = send_feed_notices(session, SITE, [storm(10.0)], NOW, SETTINGS)
    assert notice.radius_miles == 50.0 and notice.radius_source == "default"


def test_notice_delivery_is_audited(session) -> None:
    [(notice, _)] = send_feed_notices(session, SITE, [quake(10.0, 4.8)], NOW, SETTINGS)
    actions = {(e.actor, e.action, e.entity) for e in session.scalars(select(db.AuditEvent))}
    assert ("system:rules", "notice.create", notice.id) in actions
    assert ("system:rules", "notice.deliver", f"{notice.id}->team-a") in actions
    assert ("system:notices", "notice.supervisor.deliver", f"{notice.id}->auth0|sup") in actions


def test_detected_feed_notice_can_be_confirmed_by_its_recorded_recipient(session) -> None:
    [(notice, _)] = send_feed_notices(session, SITE, [quake(10.0, 4.8)], NOW, SETTINGS)
    user = CurrentUser("auth0|sup", "supervisor", roles.SUPERVISOR_PERMISSIONS)
    confirmed, _ = confirm_hazard(session, notice.id, user, NOW)
    assert confirmed.status == "confirmed" and confirmed.confirmed_by == user.sub
    assert list(session.scalars(select(db.CrewReport))) == []
    assert list(session.scalars(select(db.HazardScore))) == []
