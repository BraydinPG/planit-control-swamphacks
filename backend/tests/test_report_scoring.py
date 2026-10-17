"""T055: human confirmation atomically refreshes only eligible site report factors."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.db import models as db
from app.schemas import ReportCategory
from app.security import CurrentUser, roles
from app.services.hazards import confirm_hazard
from app.services.reports import Reporter, create_report
from app.services.scoring import score_site
from tests.auth_fakes import supervisor
from tests.test_hazards_api import absent, confirm, review
from tests.test_reports_api import HOME, NOW, seed, submit
from tests.test_reports_api import client as client
from tests.test_reports_api import h as h


def factors(score):
    return [f for f in score.factor_contributions if f["factor"] == "crew_report"]


def stored_report(id, status="pending", present=True, severity=None, age=1):
    return db.CrewReport(
        id=id,
        organization_id="org-1",
        team_id="team-a",
        site_id="site-a",
        reporter_id="auth0|crew-a",
        category="other",
        hazard_present=present,
        lat=HOME[0],
        lon=HOME[1],
        review_status=status,
        confirmed_category="other" if status == "confirmed" else None,
        confirmed_severity=severity,
        reviewed_by="auth0|supervisor-1" if status != "pending" else None,
        reviewed_at=NOW - timedelta(minutes=age) if status != "pending" else None,
        created_at=NOW - timedelta(minutes=age),
    )


def test_confirmed_present_report_updates_stored_score_and_site_reads(h, client):
    with h.factory() as session:
        initial = score_site(session, "site-a", NOW - timedelta(minutes=1))
    assert initial.risk_score == 0
    report = submit(client).json()
    assert len(h.rows(db.HazardScore)) == 1  # Pending and potential do not raise the score.
    assert confirm(client, report["notice_id"]).status_code == 200
    scores = sorted(h.rows(db.HazardScore), key=lambda s: s.created_at)
    assert len(scores) == 2
    current = scores[-1]
    assert current.risk_score == 1.0 and current.previous_score == initial.risk_score
    assert factors(current)[0]["evidence_id"] == report["id"]
    assert factors(current)[0]["data_state"] == "crew_reported"
    detail = client.get("/api/sites/site-a", headers=supervisor()).json()
    assert detail["risk_score"] == detail["score"]["risk_score"] == 1.0
    summary = next(
        s for s in client.get("/api/sites", headers=supervisor()).json() if s["id"] == "site-a"
    )
    assert summary["risk_score"] == 1.0
    assert any(f["evidence_id"] == report["id"] for f in summary["top_factors"])
    assert any(
        e.action == "score.refresh.confirmed_report" and e.entity == report["id"]
        for e in h.rows(db.AuditEvent)
    )


def test_multiple_confirmations_at_the_same_time_keep_both_contributions(h, client):
    reports = [submit(client).json(), submit(client, category="wildlife").json()]
    for report in reports:
        assert confirm(client, report["notice_id"]).status_code == 200
    scores = sorted(h.rows(db.HazardScore), key=lambda s: s.created_at)
    assert [s.risk_score for s in scores] == [1.0, 2.0]
    assert scores[1].previous_score == 1.0
    assert scores[0].created_at < scores[1].created_at
    assert {f["evidence_id"] for f in factors(scores[-1])} == {r["id"] for r in reports}
    assert client.get("/api/sites/site-a", headers=supervisor()).json()["risk_score"] == 2.0
    assert confirm(client, reports[0]["notice_id"]).status_code == 409
    assert len(h.rows(db.HazardScore)) == 2


def test_scoring_ignores_pending_rejected_absent_and_other_sites(h, client):
    with h.factory() as session:
        session.add_all(
            [
                stored_report("confirmed-present", "confirmed", severity="high"),
                stored_report("pending"),
                stored_report("rejected", "rejected"),
                stored_report("confirmed-absent", "confirmed", present=False, severity="high"),
            ]
        )
        other = stored_report("other-site", "confirmed", severity="high")
        other.site_id, other.team_id = "site-b", "team-b"
        session.add(other)
        session.commit()
        score = score_site(session, "site-a", NOW)
    assert score.risk_score == 1.5
    assert [f.evidence_id for f in score.factor_contributions if f.factor == "crew_report"] == [
        "confirmed-present"
    ]


def test_older_confirmed_reports_are_not_hidden_by_ui_display_limit(h, client):
    with h.factory() as session:
        session.add(stored_report("older-confirmed", "confirmed", age=120))
        session.add_all([stored_report(f"newer-pending-{i}", age=1) for i in range(55)])
        session.commit()
    report = submit(client).json()
    assert confirm(client, report["notice_id"]).status_code == 200
    [score] = h.rows(db.HazardScore)
    assert score.risk_score == 2.0
    assert {f["evidence_id"] for f in factors(score)} == {"older-confirmed", report["id"]}


@pytest.mark.parametrize("decision", ["confirmed", "rejected"])
def test_absent_review_does_not_refresh_or_raise_a_score(h, client, decision):
    with h.factory() as session:
        score_site(session, "site-a", NOW - timedelta(minutes=1))
    before = [(s.id, s.risk_score) for s in h.rows(db.HazardScore)]
    report = absent(client)
    assert review(client, report["id"], decision=decision, severity="high").status_code == 200
    assert [(s.id, s.risk_score) for s in h.rows(db.HazardScore)] == before
    assert h.rows(db.HazardNotice) == []


def test_active_lightning_and_other_site_scores_are_unchanged(h, client):
    with h.factory() as session:
        session.add(
            db.Alert(
                id="lightning-active",
                site_id="site-a",
                rule="lightning_stop_work",
                state="active",
                triggered_at=NOW - timedelta(minutes=5),
                latest_event_at=NOW - timedelta(minutes=1),
                clear_after=NOW + timedelta(minutes=29),
                distance_miles=4.0,
                simulated=True,
            )
        )
        session.commit()
        score_site(session, "site-a", NOW - timedelta(seconds=1))
        score_site(session, "site-b", NOW - timedelta(seconds=1))
    alert_before = [(a.id, a.state, a.latest_event_at, a.clear_after) for a in h.rows(db.Alert)]
    other_before = [(s.id, s.risk_score) for s in h.rows(db.HazardScore) if s.site_id == "site-b"]
    report = submit(client).json()
    assert confirm(client, report["notice_id"], supervisor("auth0|supervisor-2")).status_code == 200
    latest = max(
        (s for s in h.rows(db.HazardScore) if s.site_id == "site-a"), key=lambda s: s.created_at
    )
    assert latest.risk_score == 4.0
    assert [
        (a.id, a.state, a.latest_event_at, a.clear_after) for a in h.rows(db.Alert)
    ] == alert_before
    assert [
        (s.id, s.risk_score) for s in h.rows(db.HazardScore) if s.site_id == "site-b"
    ] == other_before


def test_scoring_failure_rolls_back_confirmation_and_report(h, client, monkeypatch):
    report = submit(client).json()

    def fail(*args, **kwargs):
        raise RuntimeError("Synthetic scoring failure")

    monkeypatch.setattr("app.services.hazards.score_site", fail)
    with pytest.raises(RuntimeError, match="Synthetic scoring failure"):
        confirm(client, report["notice_id"])
    assert h.rows(db.HazardNotice)[0].status == "potential"
    assert h.rows(db.CrewReport)[0].review_status == "pending"
    assert h.rows(db.HazardScore) == []


def test_audit_failure_rolls_back_the_new_score_too(h, client):
    report = submit(client).json()

    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO audit_events"):
            raise RuntimeError("Synthetic audit failure after scoring")

    event.listen(h.engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="Synthetic audit failure after scoring"):
            confirm(client, report["notice_id"])
    finally:
        event.remove(h.engine, "before_cursor_execute", fail)
    assert h.rows(db.HazardNotice)[0].status == "potential"
    assert h.rows(db.CrewReport)[0].review_status == "pending"
    assert h.rows(db.HazardScore) == []


def test_concurrent_distinct_confirmations_preserve_both_factors(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'score-race.db').as_posix()}")
    db.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    user = CurrentUser("auth0|supervisor-1", "supervisor", roles.SUPERVISOR_PERMISSIONS)
    with factory() as session:
        seed(session)
        ids = []
        for _ in range(2):
            created = create_report(
                session,
                Reporter("auth0|crew-a", "org-1", "team-a"),
                session.get(db.Site, "site-a"),
                ReportCategory.OTHER,
                True,
                *HOME,
                None,
                "photos/test.jpg",
                NOW,
            )
            ids.append(created.notice.id)
    gate = Barrier(2, timeout=10)

    def before_update(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE hazard_notices"):
            gate.wait()

    event.listen(engine, "before_cursor_execute", before_update)

    def attempt(id):
        with factory() as session:
            return confirm_hazard(session, id, user, NOW).id

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert set(pool.map(attempt, ids)) == set(ids)
        with factory() as session:
            scores = list(
                session.scalars(select(db.HazardScore).order_by(db.HazardScore.created_at))
            )
            assert [s.risk_score for s in scores] == [1.0, 2.0]
            assert len(factors(scores[-1])) == 2
    finally:
        engine.dispose()
