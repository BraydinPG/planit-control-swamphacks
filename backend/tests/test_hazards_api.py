"""T054: receipt-scoped confirmation and organization-scoped absent reviews."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.db import models as db
from app.schemas import ReportCategory
from app.security import CurrentUser, roles
from app.services.hazards import confirm_hazard
from app.services.reports import Reporter, create_report
from tests.auth_fakes import bearer, crew, supervisor, token
from tests.test_reports_api import (
    HOME,
    NOW,
    legacy_notice,
    seed,
    submit,
    submit_accepted,
    submit_legacy,
)
from tests.test_reports_api import client as client
from tests.test_reports_api import h as h


def confirm(client, notice_id, headers=None):
    return client.post(f"/api/hazards/{notice_id}/confirm", headers=headers or supervisor())


def review(client, report_id, headers=None, **body):
    return client.post(
        f"/api/reports/{report_id}/review",
        json={"decision": "confirmed", **body},
        headers=headers or supervisor(),
    )


def absent(client):
    return submit(client, hazard_present="false", photo=None).json()


def test_notified_supervisors_are_snapshotted(h, client):
    report = submit_accepted(client)
    receipts = [e.entity for e in h.rows(db.AuditEvent) if e.action == "notice.supervisor.deliver"]
    assert sorted(receipts) == [
        f"{report['notice_id']}->auth0|supervisor-1",
        f"{report['notice_id']}->auth0|supervisor-2",
    ]


def test_accepting_a_present_report_confirms_it_and_its_notice(h, client):
    sub = "auth0|supervisor-1"
    report = submit(client).json()
    response = review(client, report["id"], supervisor(sub), severity="high")
    assert response.status_code == 200
    result = response.json()
    assert result["review_status"] == "confirmed" and result["reviewed_by"] == sub
    assert result["confirmed_category"] == result["category"]
    assert result["confirmed_severity"] == "high"
    seen = client.get("/api/sites/site-a", headers=supervisor(sub)).json()["notices"][0]
    assert seen["id"] == result["notice_id"]
    assert seen["status"] == "confirmed" and seen["confirmed_by"] == sub
    assert seen["confirmed_at"].startswith("2026-10-17T18:00")
    assert seen["instruction"] is None
    actions = {(e.action, e.entity, e.actor) for e in h.rows(db.AuditEvent)}
    assert ("notice.confirm", result["notice_id"], sub) in actions
    assert ("report.review.confirmed", report["id"], sub) in actions
    assert len(h.rows(db.HazardScore)) == 1 and h.rows(db.Alert) == []


def test_accepting_a_report_filed_with_its_notice_confirms_that_notice(h, client):
    report = submit_legacy(h, client)
    response = review(client, report["id"], severity="low")
    assert response.status_code == 200
    assert response.json()["notice_id"] == report["notice_id"]
    assert response.json()["confirmed_severity"] == "low"
    [notice] = h.rows(db.HazardNotice)
    assert notice.status == "confirmed" and notice.confirmed_by == "auth0|supervisor-1"
    [assessment] = h.rows(db.NoticeAssessment)
    assert assessment.organization_id == "org-1"


def test_another_organization_confirms_only_for_itself(h, client):
    report = submit_legacy(h, client)
    response = confirm(client, report["notice_id"], supervisor("auth0|supervisor-2"))
    assert response.status_code == 200
    assert response.json()["notice"]["status"] == "confirmed"
    assert response.json()["notice"]["confirmed_by"] == "auth0|supervisor-2"
    [assessment] = h.rows(db.NoticeAssessment)
    assert (assessment.organization_id, assessment.confirmed_by) == ("org-2", "auth0|supervisor-2")
    # The reporting organization still decides on its own report and sees it as potential.
    [stored] = h.rows(db.CrewReport)
    assert stored.review_status == "pending" and stored.reviewed_by is None
    assert h.rows(db.HazardScore) == []
    own = client.get("/api/sites/site-a", headers=supervisor()).json()["notices"][0]
    assert own["status"] == "potential" and own["confirmed_by"] is None
    theirs = client.get("/api/sites/site-x", headers=supervisor("auth0|supervisor-2")).json()
    assert theirs["notices"][0]["status"] == "confirmed"
    # Then the reporting organization confirms for itself, which confirms the report.
    assert confirm(client, report["notice_id"]).status_code == 200
    [stored] = h.rows(db.CrewReport)
    assert stored.review_status == "confirmed" and stored.reviewed_by == "auth0|supervisor-1"
    assert len(h.rows(db.NoticeAssessment)) == 2


def test_an_older_confirmed_notice_keeps_its_confirmation(h, client):
    """Notices confirmed before per-organization assessments read confirmed for everyone,
    and a later organization's confirmation stores the original instead of erasing it."""
    report = submit_legacy(h, client)
    with h.factory() as session:
        notice = session.get(db.HazardNotice, report["notice_id"])
        notice.status, notice.confirmed_by, notice.confirmed_at = (
            "confirmed",
            "auth0|supervisor-1",
            NOW,
        )
        notice.instruction, notice.instruction_sent_at = "Legacy text.", NOW
        session.commit()
    for site_id, headers in [("site-a", crew()), ("site-x", supervisor("auth0|supervisor-2"))]:
        seen = client.get(f"/api/sites/{site_id}", headers=headers).json()["notices"][0]
        assert seen["status"] == "confirmed" and seen["instruction"] == "Legacy text."
    assert confirm(client, report["notice_id"], supervisor("auth0|supervisor-2")).status_code == 200
    stored = {
        (a.organization_id, a.confirmed_by, a.instruction) for a in h.rows(db.NoticeAssessment)
    }
    assert stored == {
        ("org-1", "auth0|supervisor-1", "Legacy text."),
        ("org-2", "auth0|supervisor-2", None),
    }
    own = client.get("/api/sites/site-a", headers=crew()).json()["notices"][0]
    assert own["instruction"] == "Legacy text."


@pytest.mark.parametrize("action", ["confirm", "review"])
def test_actions_require_authentication_and_supervisor_permission(h, client, action):
    report = submit_accepted(client) if action == "confirm" else absent(client)
    path = (
        f"/api/hazards/{report['notice_id']}/confirm"
        if action == "confirm"
        else f"/api/reports/{report['id']}/review"
    )
    body = {} if action == "confirm" else {"decision": "confirmed"}
    assert client.post(path, json=body).status_code == 401
    assert client.post(path, json=body, headers=crew()).status_code == 403
    missing_permission = bearer(token(["supervisor"], permissions=[], sub="auth0|supervisor-1"))
    assert client.post(path, json=body, headers=missing_permission).status_code == 403
    # A permission alone must not let a crew-role token perform supervisor actions.
    unusual_crew = bearer(token(["crew"], permissions=list(roles.SUPERVISOR_PERMISSIONS)))
    assert client.post(path, json=body, headers=unusual_crew).status_code == 403


def test_unnotified_supervisor_cannot_confirm(h, client):
    with h.factory() as session:
        session.add(db.Organization(id="org-far", name="Outside radius"))
        session.add(
            db.Membership(
                id="m-far",
                user_id="auth0|supervisor-far",
                organization_id="org-far",
                role="supervisor",
            )
        )
        session.commit()
    report = submit_legacy(h, client)
    assert (
        confirm(client, report["notice_id"], supervisor("auth0|supervisor-far")).status_code == 403
    )
    assert h.rows(db.HazardNotice)[0].status == "potential"
    assert h.rows(db.CrewReport)[0].review_status == "pending"


def test_later_team_move_does_not_change_recipient_authority(h, client):
    report = submit_legacy(h, client)
    with h.factory() as session:
        session.get(db.Team, "team-x").site_id = None
        session.add(
            db.Membership(
                id="m-new",
                user_id="auth0|new-supervisor",
                organization_id="org-1",
                role="supervisor",
            )
        )
        session.commit()
    assert (
        confirm(client, report["notice_id"], supervisor("auth0|new-supervisor")).status_code == 403
    )
    assert confirm(client, report["notice_id"], supervisor("auth0|supervisor-2")).status_code == 200


def test_missing_notice_and_report_return_404(h, client):
    assert confirm(client, "missing").status_code == 404
    assert review(client, "missing").status_code == 404


def test_each_organization_confirms_once(h, client):
    report = submit_legacy(h, client)
    assert confirm(client, report["notice_id"]).status_code == 200
    assert confirm(client, report["notice_id"]).status_code == 409
    assert confirm(client, report["notice_id"], supervisor("auth0|supervisor-2")).status_code == 200
    assert confirm(client, report["notice_id"], supervisor("auth0|supervisor-2")).status_code == 409
    [stored] = h.rows(db.HazardNotice)
    assert stored.confirmed_by == "auth0|supervisor-1"  # first confirmation anywhere
    assert len([e for e in h.rows(db.AuditEvent) if e.action == "notice.confirm"]) == 2
    [report_row] = h.rows(db.CrewReport)
    assert report_row.reviewed_by == "auth0|supervisor-1"


def test_legacy_notice_without_receipt_fails_closed(h, client):
    report = submit_legacy(h, client)
    with h.factory() as session:
        session.query(db.AuditEvent).filter_by(action="notice.supervisor.deliver").delete()
        session.commit()
    assert confirm(client, report["notice_id"]).status_code == 403


def test_invalid_link_rolls_back_notice_confirmation(h, client):
    report = submit_legacy(h, client)
    with h.factory() as session:
        session.get(db.CrewReport, report["id"]).hazard_present = False
        session.commit()
    assert confirm(client, report["notice_id"]).status_code == 409
    [notice] = h.rows(db.HazardNotice)
    assert notice.status == "potential" and notice.confirmed_by is None
    assert not any(e.action == "notice.confirm" for e in h.rows(db.AuditEvent))


def test_already_reviewed_link_rolls_back_notice_claim(h, client):
    report = submit_legacy(h, client)
    with h.factory() as session:
        session.get(db.CrewReport, report["id"]).review_status = "rejected"
        session.commit()
    assert confirm(client, report["notice_id"]).status_code == 409
    [notice] = h.rows(db.HazardNotice)
    assert notice.status == "potential" and notice.confirmed_by is None
    assert h.rows(db.CrewReport)[0].review_status == "rejected"


def test_source_notice_can_be_confirmed_without_a_crew_report(h, client):
    report = submit_legacy(h, client)
    with h.factory() as session:
        notice = session.get(db.HazardNotice, report["notice_id"])
        notice.source = "feed"
        notice.source_ref = "observation:example"
        session.commit()
    assert confirm(client, report["notice_id"]).status_code == 200
    # Feed confirmation must not accidentally confirm an unrelated report.
    assert h.rows(db.CrewReport)[0].review_status == "pending"


def test_audit_failure_rolls_back_notice_and_report(h, client):
    report = submit_legacy(h, client)

    def fail_audit(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO audit_events"):
            raise RuntimeError("Synthetic audit failure")

    event.listen(h.engine, "before_cursor_execute", fail_audit)
    try:
        with pytest.raises(RuntimeError, match="Synthetic audit failure"):
            confirm(client, report["notice_id"])
    finally:
        event.remove(h.engine, "before_cursor_execute", fail_audit)
    assert h.rows(db.HazardNotice)[0].status == "potential"
    assert h.rows(db.CrewReport)[0].review_status == "pending"


@pytest.mark.parametrize("decision", ["confirmed", "rejected"])
def test_own_organization_reviews_absent_report(h, client, decision):
    report = absent(client)
    response = review(
        client,
        report["id"],
        decision=decision,
        category="on_site_fire",
        severity="high",
        note="Checked",
    )
    assert response.status_code == 200
    result = response.json()
    assert result["review_status"] == decision
    assert result["reviewed_by"] == "auth0|supervisor-1"
    assert result["reviewed_at"].startswith("2026-10-17T18:00")
    assert result["hazard_present"] is False
    assert result["confirmed_category"] == ("on_site_fire" if decision == "confirmed" else None)
    assert h.rows(db.HazardNotice) == [] and h.rows(db.HazardScore) == []
    notes = [e for e in h.rows(db.AuditEvent) if e.action == "report.review.note"]
    assert json.loads(notes[0].entity) == {"report_id": report["id"], "note": "Checked"}
    assert any(e.action == f"report.review.{decision}" for e in h.rows(db.AuditEvent))


def test_absent_report_stays_with_its_organization(h, client):
    report = absent(client)
    outsider = supervisor("auth0|supervisor-2")
    assert review(client, report["id"], outsider).status_code == 403
    assert client.get("/api/reports", headers=outsider).json() == []
    detail = client.get("/api/sites/site-a", headers=outsider).json()
    assert detail["reports"] == []
    own = client.get("/api/sites/site-a", headers=supervisor()).json()
    assert [r["id"] for r in own["reports"]] == [report["id"]]


def test_missing_membership_cannot_review(h, client):
    report = absent(client)
    assert review(client, report["id"], supervisor("auth0|stranger")).status_code == 403


def test_another_organization_cannot_accept_or_reject_the_report(h, client):
    report = submit(client).json()
    for decision in ("confirmed", "rejected"):
        outsider = supervisor("auth0|supervisor-2")
        assert review(client, report["id"], outsider, decision=decision).status_code == 403
    assert h.rows(db.CrewReport)[0].review_status == "pending"
    assert h.rows(db.HazardNotice) == []


def test_review_is_final_and_invalid_body_is_rejected(h, client):
    report = absent(client)
    assert review(client, report["id"], decision="unknown").status_code == 422
    assert review(client, report["id"], note="x" * 1001).status_code == 422
    assert review(client, report["id"]).status_code == 200
    assert review(client, report["id"], decision="rejected").status_code == 409
    assert h.rows(db.CrewReport)[0].review_status == "confirmed"


def test_concurrent_confirmations_have_exactly_one_winner(tmp_path):
    # Separate DB connections/transactions exercise the atomic claim, not just retries.
    # Two supervisors of the same organization race; each organization confirms once.
    engine = create_engine(f"sqlite:///{(tmp_path / 'race.db').as_posix()}")
    db.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        seed(session)
        session.add(
            db.Membership(
                id="m-s1b",
                user_id="auth0|supervisor-1b",
                organization_id="org-1",
                role="supervisor",
            )
        )
        session.commit()
        report = create_report(
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
        notice_id = legacy_notice(session, report.report.id)
    gate = Barrier(2, timeout=10)

    def before_update(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO notice_assessments"):
            gate.wait()

    event.listen(engine, "before_cursor_execute", before_update)

    def attempt(sub):
        user = CurrentUser(sub, "supervisor", roles.SUPERVISOR_PERMISSIONS)
        with factory() as session:
            try:
                confirm_hazard(session, notice_id, user, NOW)
                return 200, sub
            except HTTPException as exc:
                return exc.status_code, sub

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, ["auth0|supervisor-1", "auth0|supervisor-1b"]))
        assert sorted(status for status, _ in results) == [200, 409]
        winner = next(sub for status, sub in results if status == 200)
        with factory() as session:
            assert session.get(db.HazardNotice, notice_id).confirmed_by == winner
            assert session.scalar(select(db.CrewReport)).reviewed_by == winner
            assert (
                len(
                    list(
                        session.scalars(
                            select(db.AuditEvent).where(db.AuditEvent.action == "notice.confirm")
                        )
                    )
                )
                == 1
            )
    finally:
        engine.dispose()
