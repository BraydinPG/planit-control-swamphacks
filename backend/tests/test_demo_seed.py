"""T069: one command restores the demo, and both demo accounts see it."""

from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db, get_now
from app.db import models as db
from app.demo import DEMO_ORG_ID, DEMO_SITE_ID, DemoAccounts, replay_lightning, seed_demo
from app.demo.__main__ import DemoSettings
from app.main import app
from app.outlook import EventOutlookService, get_event_outlook_service
from tests import auth_fakes
from tests.auth_fakes import crew, supervisor

NOW = datetime(2026, 10, 17, 18, 30, tzinfo=UTC)
CREW = "auth0|demo-crew"
SUPERVISOR = "auth0|demo-supervisor"
ACCOUNTS = DemoAccounts(CREW, SUPERVISOR)


def predictor(site: dict, context: dict) -> dict:
    """Stand-in for Cache's model: echoes the event it was asked about."""
    return {
        "status": "ok",
        "event_id": context["event_id"],
        "event_type": context["event_type"],
        "as_of_utc": context["as_of_utc"],
        "generated_at_utc": context["as_of_utc"],
        "outcomes": {"remaining_duration_hours": {"p10": 4.0, "median": 18.0, "p90": 40.0}},
        "model_version": "test-model",
        "is_simulated": context["is_simulated"],
    }


OUTLOOKS = EventOutlookService(predictor)


@pytest.fixture
def factory() -> Iterator[sessionmaker]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    db.Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def seeded(factory) -> sessionmaker:
    with factory() as session:
        seed_demo(session, NOW, ACCOUNTS, OUTLOOKS)
    return factory


@pytest.fixture
def client(seeded) -> Iterator[TestClient]:
    def override_db() -> Iterator[Session]:
        with seeded() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_now] = lambda: NOW + timedelta(minutes=1)
    app.dependency_overrides[get_event_outlook_service] = lambda: OUTLOOKS
    auth_fakes.install(app)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def counts(factory) -> dict[str, int]:
    with factory() as session:
        return {
            model.__tablename__: session.scalar(select(func.count()).select_from(model))
            for model in (
                db.Organization,
                db.Site,
                db.Team,
                db.Membership,
                db.Observation,
                db.Alert,
                db.CrewReport,
                db.HazardNotice,
                db.HazardScore,
                db.Briefing,
            )
        }


# ---- done check: both demo accounts see their site, briefing, and flood duration ----


@pytest.mark.parametrize(
    "headers", [crew(CREW), supervisor(SUPERVISOR)], ids=["crew", "supervisor"]
)
def test_both_demo_accounts_see_site_briefing_and_flood_duration(client, headers) -> None:
    sites = client.get("/api/sites", headers=headers).json()
    assert sites[0]["id"] == DEMO_SITE_ID
    assert sites[0]["assigned_team"]["id"] == "demo-team"

    detail = client.get(f"/api/sites/{DEMO_SITE_ID}", headers=headers).json()
    outlook = detail["event_outlook"]
    assert outlook["status"] == "ok"
    assert outlook["event_id"] == "demo-notice-flood"
    assert outlook["remaining_hours_median"] == 18.0
    assert outlook["is_simulated"] is True

    briefing = client.get(f"/api/sites/{DEMO_SITE_ID}/briefing", headers=headers)
    assert briefing.status_code == 200
    assert briefing.json()["forecast_window_start"].startswith("2026-10-18T11:00")  # 07:00 EDT
    org = client.get("/api/briefings", headers=headers).json()
    assert [b["site_id"] for b in org] == [DEMO_SITE_ID]


def test_site_detail_shows_the_scenario(client) -> None:
    detail = client.get(f"/api/sites/{DEMO_SITE_ID}", headers=crew(CREW)).json()
    [report] = detail["reports"]
    assert (report["category"], report["review_status"]) == ("wildlife", "confirmed")
    assert report["note"] == "Alligator on the levee access road by the culvert."
    notices = {n["id"]: n for n in detail["notices"]}
    assert notices["demo-notice-wildlife"]["instruction"]
    assert notices["demo-notice-flood"]["status"] == "confirmed"
    assert notices["demo-notice-flood"]["instruction"] is None  # left for the demo supervisor
    [alert] = detail["alerts"]
    assert alert["rule"] == "lightning_stop_work" and alert["simulated"] is True
    assert alert["distance_miles"] == pytest.approx(6.8, abs=0.1)

    factors = {f["factor"]: f for f in detail["score"]["factor_contributions"]}
    assert factors["lightning"]["contribution"] == 3.0
    assert factors["heat_index"]["contribution"] > 0
    assert factors["flood"]["contribution"] == 2.0
    assert any(f.startswith("crew_report") for f in factors)
    assert detail["score"]["data_completeness"] == 0.0  # replay is never live coverage
    assert all(o["simulated"] for o in detail["observations"])


def test_briefing_is_the_schedule_template_and_cites_the_scenario(client) -> None:
    briefing = client.get(f"/api/sites/{DEMO_SITE_ID}/briefing", headers=supervisor(SUPERVISOR))
    body = briefing.json()
    assert body["generated_by"] == "fallback"
    evidence = {e["id"] for e in body["evidence"]}
    assert "demo-report-wildlife" in evidence
    assert any(e.startswith("ltg-alert:") for e in evidence)
    assert any(e.startswith("demo-forecast:") for e in evidence)
    labels = " ".join(e["label"] for e in body["evidence"])
    assert "simulated" in labels


def test_demo_supervisor_can_send_the_flood_instruction(client) -> None:
    response = client.post(
        "/api/hazards/demo-notice-flood/instruction",
        json={"instruction": "Move equipment to the north pad."},
        headers=supervisor(SUPERVISOR),
    )
    assert response.status_code == 200, response.text
    assert response.json()["instruction"] == "Move equipment to the north pad."


def test_other_accounts_see_nothing(client) -> None:
    stranger = crew("auth0|stranger")
    assert client.get(f"/api/sites/{DEMO_SITE_ID}", headers=stranger).status_code == 403
    assert client.get("/api/briefings", headers=supervisor("auth0|stranger")).status_code == 403


# ---- one command restores the same demo ----


def test_running_again_restores_the_same_scenario(seeded) -> None:
    first = counts(seeded)
    with seeded() as session:
        replay_lightning(session, 2, NOW + timedelta(minutes=5))
        session.add(
            db.CrewReport(
                id="rehearsal-report",
                organization_id=DEMO_ORG_ID,
                team_id="demo-team",
                site_id=DEMO_SITE_ID,
                reporter_id=CREW,
                category="other",
                hazard_present=False,
                lat=25.39,
                lon=-80.58,
                review_status="pending",
                created_at=NOW,
            )
        )
        session.commit()
        seed_demo(session, NOW + timedelta(hours=1), ACCOUNTS, OUTLOOKS)
    assert counts(seeded) == first
    with seeded() as session:
        assert session.get(db.CrewReport, "rehearsal-report") is None
        [alert] = session.scalars(select(db.Alert)).all()
        assert alert.state == "active"


def test_seed_leaves_other_sites_and_organizations_alone(factory) -> None:
    with factory() as session:
        session.add_all(
            [
                db.Organization(id="org-other", name="Other"),
                db.Site(
                    id="eia860m-FL-1",
                    name="Plant",
                    lat=27.0,
                    lon=-82.0,
                    location_type="power_plant",
                    source="EIA-860M August 2026 (representative power plant location)",
                ),
            ]
        )
        session.flush()
        session.add(db.Team(id="team-other", organization_id="org-other", name="T", site_id=None))
        session.flush()
        session.add_all(
            [
                db.Membership(
                    id="m-other",
                    user_id="auth0|other",
                    organization_id="org-other",
                    role="supervisor",
                ),
                # A demo account linked elsewhere by hand is moved to the demo organization.
                db.Membership(
                    id="m-hand", user_id=SUPERVISOR, organization_id="org-other", role="supervisor"
                ),
            ]
        )
        session.commit()
        seed_demo(session, NOW, ACCOUNTS, OUTLOOKS)
        assert session.get(db.Site, "eia860m-FL-1") is not None
        assert session.get(db.Team, "team-other") is not None
        assert session.get(db.Membership, "m-other") is not None
        memberships = session.scalars(
            select(db.Membership).where(db.Membership.user_id == SUPERVISOR)
        ).all()
        assert [(m.organization_id, m.role) for m in memberships] == [(DEMO_ORG_ID, "supervisor")]


# ---- lightning replay ----


def test_strike_two_resets_the_countdown(seeded) -> None:
    with seeded() as session:
        [before] = session.scalars(select(db.Alert)).all()
        later = NOW + timedelta(minutes=10)
        assert replay_lightning(session, 2, later) == "reset"
        session.expire_all()
        [after] = session.scalars(select(db.Alert)).all()
    assert after.id == before.id
    assert after.clear_after.replace(tzinfo=UTC) == later + timedelta(minutes=30)
    assert after.distance_miles == pytest.approx(4.2, abs=0.1)


def test_strike_outside_10_miles_does_not_reset(seeded) -> None:
    with seeded() as session:
        assert replay_lightning(session, 3, NOW + timedelta(minutes=10)) == "unchanged"


def test_strike_needs_a_seeded_site_and_a_valid_step(factory, seeded) -> None:
    with seeded() as session:
        with pytest.raises(ValueError):
            replay_lightning(session, 4, NOW)
    engine = create_engine("sqlite://")
    db.Base.metadata.create_all(engine)
    with Session(engine) as empty, pytest.raises(LookupError):
        replay_lightning(empty, 1, NOW)


# ---- accounts ----


def test_accounts_come_from_settings_with_placeholders() -> None:
    assert not DemoSettings(_env_file=None).accounts().linked
    configured = DemoSettings(
        demo_crew_user_id=" auth0|a ", demo_supervisor_user_id="auth0|b", _env_file=None
    )
    assert configured.accounts() == DemoAccounts("auth0|a", "auth0|b")
    assert configured.accounts().linked


def test_same_account_for_both_roles_is_refused(factory) -> None:
    with factory() as session, pytest.raises(ValueError):
        seed_demo(session, NOW, DemoAccounts(CREW, CREW), OUTLOOKS)


def test_everything_seeded_is_labeled_simulated(seeded) -> None:
    with seeded() as session:
        site = session.get(db.Site, DEMO_SITE_ID)
        assert "simulated" in site.source and "EIA-860M" in site.source  # "not an EIA..."
        assert "simulated" in session.get(db.Organization, DEMO_ORG_ID).name
        observations = session.scalars(select(db.Observation)).all()
        assert observations and all(o.simulated for o in observations)
        assert Counter(o.hazard_type for o in observations) == {
            "weather": 3,
            "flood_alert": 1,
            "lightning_strike": 1,
        }


# ---- teammates as crew, and the separate 6 PM briefing-test organization ----


def test_teammates_join_the_demo_team_as_crew(factory) -> None:
    accounts = DemoAccounts(CREW, SUPERVISOR, ("auth0|rudra", "auth0|cache"))
    with factory() as session:
        seed_demo(session, NOW, accounts, OUTLOOKS)
        later = NOW + timedelta(minutes=1)
        seed_demo(session, later, accounts, OUTLOOKS)  # re-running keeps one row each
        rows = session.scalars(select(db.Membership).order_by(db.Membership.user_id)).all()
    assert [(m.user_id, m.role, m.team_id) for m in rows] == [
        ("auth0|cache", "crew", "demo-team"),
        ("auth0|demo-crew", "crew", "demo-team"),
        ("auth0|demo-supervisor", "supervisor", None),
        ("auth0|rudra", "crew", "demo-team"),
    ]


def test_extra_crew_come_from_settings() -> None:
    settings = DemoSettings(
        demo_crew_user_id="auth0|a",
        demo_supervisor_user_id="auth0|b",
        demo_extra_crew_user_ids=" auth0|c, ,auth0|d ",
        _env_file=None,
    )
    assert settings.accounts().extra_crew_user_ids == ("auth0|c", "auth0|d")


def test_an_account_listed_twice_is_refused(factory) -> None:
    with factory() as session, pytest.raises(ValueError):
        seed_demo(session, NOW, DemoAccounts(CREW, SUPERVISOR, (CREW,)), OUTLOOKS)


def eia_site(session, site_id="eia860m-FL-56799") -> None:
    session.add(
        db.Site(
            id=site_id, name="Greenland Energy Center", lat=30.2, lon=-81.5,
            location_type="power_plant", source="EIA-860M (representative)", region="FL",
        )
    )  # fmt: skip
    session.commit()


def test_briefing_test_org_gets_a_team_supervisor_and_no_briefing(seeded) -> None:
    from app.demo.briefing_test import TEST_ORG_ID, setup_briefing_test

    with seeded() as session:
        eia_site(session)
        session.add(
            db.Briefing(
                id="briefing:eia860m-FL-56799:old", site_id="eia860m-FL-56799",
                forecast_window_start=NOW, forecast_window_end=NOW + timedelta(hours=12),
                summary="old", risk_level="low", hazards=[], recommended_actions=[],
                evidence=[], unknowns=[], generated_by="fallback", created_at=NOW,
            )
        )  # fmt: skip
        session.commit()
        test = setup_briefing_test(session, "auth0|braydin-test", NOW)
        setup_briefing_test(session, "auth0|braydin-test", NOW)  # resets cleanly
        member = session.scalars(
            select(db.Membership).where(db.Membership.user_id == "auth0|braydin-test")
        ).one()
        assert (member.organization_id, member.role) == (TEST_ORG_ID, "supervisor")
        assert (
            session.scalar(select(db.Team.site_id).where(db.Team.organization_id == TEST_ORG_ID))
            == test.site_id
        )
        assert (
            session.scalars(select(db.Briefing).where(db.Briefing.site_id == test.site_id)).all()
            == []
        )
        assert session.get(db.Site, test.site_id).timezone == "America/New_York"
        # The demo organization is untouched.
        demo = session.scalars(
            select(db.Membership).where(db.Membership.organization_id == DEMO_ORG_ID)
        ).all()
        assert {m.user_id for m in demo} == {CREW, SUPERVISOR}
    # NOW is 14:30 in Jacksonville, so the schedule briefs it at 18:00 site time.
    assert (test.next_run_local.hour, test.next_run_local.minute) == (18, 0)


def test_the_six_pm_schedule_briefs_the_test_org_by_itself(seeded) -> None:
    from app.demo.briefing_test import setup_briefing_test
    from app.gemini.briefing_schedule import run_due_briefings
    from app.gemini.client import GeminiClient

    with seeded() as session:
        eia_site(session)
        test = setup_briefing_test(session, "auth0|braydin-test", NOW)
        before = run_due_briefings(session, NOW, GeminiClient(None, None, 1), lambda s, n: [], None)
        assert test.site_id not in {b.site_id for b in before}  # 14:30 local: not due
        at_six = NOW.replace(hour=22, minute=1)  # 18:01 EDT
        after = run_due_briefings(
            session, at_six, GeminiClient(None, None, 1), lambda s, n: [], None
        )
    assert test.site_id in {b.site_id for b in after}


@pytest.mark.parametrize("bad", ["", "demo|supervisor"])
def test_briefing_test_needs_a_real_account(seeded, bad) -> None:
    from app.demo.briefing_test import setup_briefing_test

    with seeded() as session, pytest.raises(ValueError):
        eia_site(session)
        setup_briefing_test(session, bad, NOW)


def test_briefing_test_refuses_a_site_another_org_uses(seeded) -> None:
    from app.demo.briefing_test import setup_briefing_test

    with seeded() as session, pytest.raises(ValueError):
        setup_briefing_test(session, "auth0|braydin-test", NOW, site_id=DEMO_SITE_ID)
