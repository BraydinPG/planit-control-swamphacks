"""The server slides the demo sites forward in time so they always look just seeded."""

import asyncio
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_now
from app.db import models as db
from app.demo import DEMO_SITE_ID, freshen
from app.demo.anomalies import ANOMALIES
from app.demo.freshen import keep_demo_fresh
from app.main import app
from app.outlook import get_event_outlook_service
from app.schemas import ReportCategory
from app.services import refresh
from app.services.hazards import confirm_hazard
from app.services.reports import Reporter, create_report
from tests import auth_fakes
from tests.auth_fakes import supervisor
from tests.test_demo_anomalies import anomalies as anomalies  # noqa: F401
from tests.test_demo_anomalies import factory as factory  # noqa: F401
from tests.test_demo_seed import NOW, OUTLOOKS, SUPERVISOR

DEMO_SITES = [f"demo-{a.key}" for a in ANOMALIES] + [DEMO_SITE_ID]
STOP_WORK_SITES = {"demo-flash-flood", "demo-heavy-rain", "demo-hurricane", DEMO_SITE_ID}
LATER = (timedelta(hours=2), timedelta(hours=30), timedelta(days=7))
TABLES = (
    db.Observation,
    db.Alert,
    db.Acknowledgement,
    db.CrewReport,
    db.HazardNotice,
    db.NoticeAssessment,
)


@pytest.fixture
def demo(anomalies):  # noqa: F811
    """The seeded demo plus a real site with its own reading, alert and score."""
    factory = anomalies[0]
    with factory() as session:
        session.add_all(
            [
                db.Observation(
                    id="real-reading", site_id="site-real", source="NWS", hazard_type="weather",
                    value="80", unit="°F", lat=30.0, lon=-90.0, observed_at=NOW,
                    data_state="observed", simulated=False, label="Temperature",
                    fetched_at=NOW - timedelta(minutes=30),
                ),
                db.Alert(
                    id="real-alert", site_id="site-real", rule="lightning_stop_work",
                    state="active", triggered_at=NOW, latest_event_at=NOW,
                    clear_after=NOW + timedelta(minutes=30),
                ),
                db.HazardScore(
                    id="real-score", site_id="site-real", risk_score=3.0, risk_level="low",
                    factor_contributions=[], model_version="v", model_is_fallback=False,
                    confidence=1.0, data_completeness=1.0, created_at=NOW,
                ),
            ]
        )  # fmt: skip
        session.commit()
    return factory


@pytest.fixture
def at(demo) -> Iterator[dict]:
    """A client whose clock is `at["now"]`."""
    clock = {"now": NOW + timedelta(minutes=1)}

    def override_db() -> Iterator[Session]:
        with demo() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_now] = lambda: clock["now"]
    app.dependency_overrides[get_event_outlook_service] = lambda: OUTLOOKS
    auth_fakes.install(app)
    clock["client"] = TestClient(app)
    try:
        yield clock
    finally:
        app.dependency_overrides.clear()


def slide(factory, now: datetime) -> dict[str, timedelta]:
    with factory() as session:
        return keep_demo_fresh(session, now)


def view(clock: dict, now: datetime) -> dict:
    """What a supervisor sees at each demo site at `now`, with times as ages."""
    clock["now"] = now

    def age(value: str | None) -> timedelta | None:
        return None if value is None else now - datetime.fromisoformat(value)

    pages = {}
    for site_id in DEMO_SITES:
        response = clock["client"].get(f"/api/sites/{site_id}", headers=supervisor(SUPERVISOR))
        d = response.json()
        pages[site_id] = {
            "readings": sorted(
                (o["id"], o["data_state"], age(o["observed_at"]), age(o["fetched_at"]))
                for o in d["observations"]
            ),
            "alerts": sorted(
                (a["id"], a["state"], age(a["latest_event_at"]), age(a["clear_after"]))
                for a in d["alerts"]
            ),
            "score": (
                d["score"]["risk_score"],
                d["score"]["data_completeness"],
                sorted(
                    (f["factor"], f["contribution"]) for f in d["score"]["factor_contributions"]
                ),
            ),
            "updated": age(d["score"]["created_at"]),
            "notices": sorted(
                (
                    n["id"],
                    n["hazard_label"],
                    n["status"],
                    age(n["confirmed_at"]),
                    age(n["created_at"]),
                )
                for n in d["notices"]
            ),
            "outlooks": sorted(
                (c["notice_id"], c["event_type"], c["status"], age(c["event_start_utc"]))
                for c in d["event_outlooks"]
                if c["notice_id"]  # the others are archived examples with fixed dates
            ),
            "reports": sorted(
                (r["id"], r["review_status"], age(r["created_at"])) for r in d["reports"]
            ),
        }
    return pages


def rows(factory, condition=None) -> dict:
    with factory() as session:
        return {
            model.__tablename__: sorted(
                (tuple((c.name, getattr(r, c.key)) for c in model.__table__.columns))
                for r in session.scalars(select(model))
                if condition is None or condition(r)
            )
            for model in (*TABLES, db.HazardScore)
        }


def test_demo_pages_stay_as_seeded_for_days(demo, at) -> None:
    seeded = view(at, NOW + timedelta(minutes=1))
    pages = []
    for later in LATER:
        moved = slide(demo, NOW + later)
        assert set(moved) == set(DEMO_SITES)
        pages.append(view(at, NOW + later + timedelta(minutes=1)))

    # Every slide shows exactly the same demo: same readings, timers, ages and scores.
    assert pages[0] == pages[1] == pages[2]
    page = pages[-1]
    shifts = {}
    for site_id in DEMO_SITES:
        p, s = page[site_id], seeded[site_id]
        assert {state for _, state, _, _ in p["readings"]} <= {"observed", "forecast"}, site_id
        assert [r[0] for r in p["readings"]] == [r[0] for r in s["readings"]], site_id
        assert p["score"] == s["score"], site_id
        assert p["updated"] == timedelta(minutes=1)
        assert [n[:3] for n in p["notices"]] == [n[:3] for n in s["notices"]], site_id
        assert [c[:3] for c in p["outlooks"]] == [c[:3] for c in s["outlooks"]], site_id
        assert all(a[1] == "active" and a[3] < timedelta(0) for a in p["alerts"]), site_id
        # The first slide brings the newest reading up to now: a few minutes younger once.
        younger = {
            s_age - p_age
            for (*_, s_age, _), (*_, p_age, _) in zip(s["readings"], p["readings"], strict=True)
        }
        [shifts[site_id]] = younger
        assert timedelta(0) <= shifts[site_id] <= timedelta(minutes=5), site_id
    assert {s for s in DEMO_SITES if page[s]["alerts"]} == STOP_WORK_SITES
    flood = [c for c in page["demo-flood"]["outlooks"] if c[0] == "demo-anomaly-flood"]
    assert [c[2] for c in flood] == ["available"]
    [seeded_flood] = [c for c in seeded["demo-flood"]["outlooks"] if c[0] == "demo-anomaly-flood"]
    assert flood[0][3] == seeded_flood[3] - shifts["demo-flood"]  # "began 6 h ago" holds


def test_real_sites_are_untouched(demo) -> None:
    def real(row) -> bool:
        return getattr(row, "site_id", None) == "site-real" or getattr(row, "id", "").startswith(
            "real"
        )

    before = rows(demo, real)
    assert before["observations"] and before["alerts"] and before["hazard_scores"]
    slide(demo, NOW + timedelta(hours=30))
    assert rows(demo, real) == before


def test_sliding_twice_at_the_same_time_changes_nothing(demo) -> None:
    def counts():
        with demo() as session:
            return {
                m.__tablename__: session.scalar(select(func.count()).select_from(m)) for m in TABLES
            }

    seeded = counts()
    slide(demo, NOW + timedelta(hours=2))
    once = rows(demo)
    assert slide(demo, NOW + timedelta(hours=2)) == {}
    assert rows(demo) == once
    for later in LATER:
        slide(demo, NOW + later)
        assert counts() == seeded


def test_a_testers_own_report_confirmation_and_acknowledgement_ride_along(demo, at) -> None:
    with demo() as session:
        report = create_report(
            session, Reporter("auth0|tester", "demo-org", "demo-team-flood"),
            session.get(db.Site, "demo-flood"), ReportCategory.BROKEN_POLE_DOWNED_LINE, True,
            30.4515, -91.1871, None, "photos/t.jpg", NOW + timedelta(minutes=3),
        ).report  # fmt: skip
        notice_id = report.notice_id
        confirm_hazard(session, notice_id, _supervisor(SUPERVISOR), NOW + timedelta(minutes=4))
        alert = session.scalars(
            select(db.Alert).where(db.Alert.site_id == "demo-flash-flood")
        ).one()
        session.add(
            db.Acknowledgement(
                id="ack-tester", alert_id=alert.id, user_id="auth0|tester",
                acknowledged_at=NOW - timedelta(minutes=3),
            )
        )  # fmt: skip
        session.commit()

    first = slide(demo, NOW + timedelta(hours=2))
    later = slide(demo, NOW + timedelta(hours=30))
    with demo() as session:
        # Done after the seed's newest reading: it reads "just now", never in the future.
        report = session.get(db.CrewReport, report.id)
        assert _utc(report.created_at) == NOW + timedelta(hours=30)
        notice = session.get(db.HazardNotice, notice_id)
        assert _utc(notice.confirmed_at) == NOW + timedelta(hours=30)
        assessment = session.get(db.NoticeAssessment, (notice_id, "demo-org"))
        assert _utc(assessment.confirmed_at) == NOW + timedelta(hours=30)
        # Older ones move with the rest of the site.
        ack = session.get(db.Acknowledgement, "ack-tester")
        moved = first["demo-flash-flood"] + later["demo-flash-flood"]
        assert _utc(ack.acknowledged_at) == NOW - timedelta(minutes=3) + moved
        assert session.scalars(select(db.Alert).where(db.Alert.id == ack.alert_id)).one()
    page = view(at, NOW + timedelta(hours=30, minutes=1))["demo-flood"]
    assert report.id in [r[0] for r in page["reports"]]
    assert (notice_id, "confirmed") in [(n[0], n[2]) for n in page["notices"]]


def test_a_failing_site_rolls_back_alone(demo, monkeypatch) -> None:
    real_score = freshen.score_site

    def score(session, site_id, now):
        if site_id == "demo-heat":
            raise RuntimeError("boom")
        return real_score(session, site_id, now)

    monkeypatch.setattr(freshen, "score_site", score)
    before = rows(demo, lambda r: getattr(r, "site_id", None) == "demo-heat")
    moved = slide(demo, NOW + timedelta(hours=2))
    assert set(moved) == set(DEMO_SITES) - {"demo-heat"}
    assert rows(demo, lambda r: getattr(r, "site_id", None) == "demo-heat") == before


def test_a_failing_slide_never_stops_the_live_rounds(monkeypatch) -> None:
    live_rounds = []
    demo_ran = threading.Event()

    def broken(session, now):
        demo_ran.set()
        raise RuntimeError("demo broke")

    def refresh_all(session, now, cancel=None):
        assert demo_ran.wait(5)  # the demo slide failed first; the live round still runs
        live_rounds.append(now)
        stop.set()
        return refresh.RefreshResult()

    @contextmanager
    def session():
        yield None

    stop = asyncio.Event()
    monkeypatch.setattr(freshen, "keep_demo_fresh", broken)
    monkeypatch.setattr(refresh, "refresh_all", refresh_all)
    monkeypatch.setattr("app.db.get_session", session)
    asyncio.run(asyncio.wait_for(refresh.run_forever(stop), timeout=5))
    assert len(live_rounds) == 1


def _supervisor(user_id: str):
    from app.security import CurrentUser, roles

    return CurrentUser(user_id, "supervisor", roles.SUPERVISOR_PERMISSIONS)


def _utc(value: datetime) -> datetime:
    return freshen._aware(value)
