"""T054A: drafts are suggestions; only the confirmer's submitted text is delivered."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.db import models as db
from app.gemini import GeminiClient, get_gemini_client
from app.main import app
from app.schemas import ReportCategory
from app.security import CurrentUser, roles
from app.services.hazards import confirm_hazard
from app.services.instructions import send_instruction
from app.services.reports import Reporter, create_report
from tests.auth_fakes import bearer, crew, supervisor, token
from tests.test_hazards_api import confirm
from tests.test_reports_api import HOME, NOW, seed, submit
from tests.test_reports_api import client as client
from tests.test_reports_api import h as h


def send(client, notice_id, text="Keep clear of the damaged pole.", headers=None):
    return client.post(
        f"/api/hazards/{notice_id}/instruction",
        json={"instruction": text},
        headers=headers or supervisor(),
    )


def provider(transport):
    app.dependency_overrides[get_gemini_client] = lambda: GeminiClient("fake", "fake", 1, transport)


def valid_draft(report_id, text="Keep clear of the damaged pole."):
    return json.dumps({"suggested_instruction": text, "evidence": [report_id], "unknowns": []})


def test_confirm_calls_helper_with_evidence_but_never_sends(h, client):
    report = submit(client).json()
    calls = []

    def transport(prompt, schema):
        calls.append(prompt)
        # Confirmed state was committed before the external request.
        assert h.rows(db.HazardNotice)[0].status == "confirmed"
        return valid_draft(report["id"])

    provider(transport)
    response = confirm(client, report["notice_id"])
    assert response.status_code == 200
    result = response.json()
    assert result["suggested_instruction"] == "Keep clear of the damaged pole."
    assert result["generated_by"] == "gemini"
    assert len(calls) == 1 and report["id"] in calls[0]
    assert '"radius_miles": 1.0' in calls[0]
    [notice] = h.rows(db.HazardNotice)
    assert notice.suggested_instruction == result["suggested_instruction"]
    assert notice.instruction is None and notice.instruction_sent_at is None
    assert not any(e.action == "notice.instruction.deliver" for e in h.rows(db.AuditEvent))


def test_potential_notice_never_has_a_draft_or_instruction(h, client):
    report = submit(client).json()
    provider(lambda *args: pytest.fail("Unconfirmed send must not call Gemini"))
    assert send(client, report["notice_id"]).status_code == 409
    [notice] = h.rows(db.HazardNotice)
    assert notice.suggested_instruction is None and notice.instruction is None
    detail = client.get("/api/sites/site-a", headers=crew()).json()
    assert detail["notices"][0]["instruction"] is None


def test_crew_and_other_supervisors_never_receive_the_unsent_draft(h, client):
    report = submit(client).json()
    provider(lambda *args: valid_draft(report["id"]))
    assert confirm(client, report["notice_id"]).status_code == 200
    for headers in [crew(), supervisor("auth0|supervisor-2")]:
        detail = client.get("/api/sites/site-a", headers=headers).json()
        assert detail["notices"][0]["suggested_instruction"] is None
        assert detail["notices"][0]["instruction"] is None
    own = client.get("/api/sites/site-a", headers=supervisor()).json()
    assert own["notices"][0]["suggested_instruction"] == "Keep clear of the damaged pole."


def test_only_final_edited_text_reaches_every_team_inside_radius(h, client):
    report = submit(client).json()
    provider(lambda *args: valid_draft(report["id"]))
    confirm(client, report["notice_id"])
    final = "Stay behind the marked barrier and contact the supervisor."
    scores_before = [(s.id, s.risk_score) for s in h.rows(db.HazardScore)]
    response = send(client, report["notice_id"], final)
    assert response.status_code == 200
    assert response.json()["instruction"] == final
    assert response.json()["instruction_sent_at"].startswith("2026-10-17T18:00")
    for site_id, headers in [
        ("site-a", crew()),
        ("site-near", supervisor()),
        ("site-x", supervisor("auth0|supervisor-2")),
    ]:
        notices = client.get(f"/api/sites/{site_id}", headers=headers).json()["notices"]
        assert notices[0]["instruction"] == final
    assert client.get("/api/sites/site-b", headers=supervisor()).json()["notices"] == []
    deliveries = sorted(
        e.entity for e in h.rows(db.AuditEvent) if e.action == "notice.instruction.deliver"
    )
    assert deliveries == [
        f"{report['notice_id']}->{team}" for team in ["team-a", "team-n", "team-x"]
    ]
    assert [(s.id, s.risk_score) for s in h.rows(db.HazardScore)] == scores_before
    assert h.rows(db.Alert) == []


@pytest.mark.parametrize(
    "headers",
    [
        crew(),
        supervisor("auth0|supervisor-2"),
        supervisor("auth0|stranger"),
        bearer(token(["supervisor"], permissions=[], sub="auth0|supervisor-1")),
        bearer(token(["crew"], permissions=[roles.SEND_INSTRUCTIONS], sub="auth0|supervisor-1")),
    ],
)
def test_only_the_confirming_supervisor_with_permission_can_send(h, client, headers):
    report = submit(client).json()
    confirm(client, report["notice_id"])
    assert send(client, report["notice_id"], headers=headers).status_code == 403
    assert h.rows(db.HazardNotice)[0].instruction is None


def test_no_token_and_unknown_notice(h, client):
    assert (
        client.post("/api/hazards/missing/instruction", json={"instruction": "Wait"}).status_code
        == 401
    )
    assert send(client, "missing").status_code == 404


@pytest.mark.parametrize("text", ["", "   ", "\n\t", "x" * 501])
def test_invalid_final_text_is_rejected(h, client, text):
    report = submit(client).json()
    confirm(client, report["notice_id"])
    assert send(client, report["notice_id"], text).status_code == 422
    assert h.rows(db.HazardNotice)[0].instruction is None


def test_sent_instruction_cannot_be_overwritten_or_delivered_twice(h, client):
    report = submit(client).json()
    confirm(client, report["notice_id"])
    assert send(client, report["notice_id"], "Hold position.").status_code == 200
    assert send(client, report["notice_id"], "Different text.").status_code == 409
    assert h.rows(db.HazardNotice)[0].instruction == "Hold position."
    assert len([e for e in h.rows(db.AuditEvent) if e.action == "notice.instruction.send"]) == 1


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        json.dumps({"suggested_instruction": "Wait", "evidence": ["invented"], "unknowns": []}),
        json.dumps({"suggested_instruction": "Wait", "evidence": [], "unknowns": []}),
        json.dumps({"suggested_instruction": "   ", "evidence": ["invented"], "unknowns": []}),
        json.dumps(
            {
                "suggested_instruction": "Wait",
                "evidence": ["invented"],
                "unknowns": [],
                "send": True,
            }
        ),
    ],
)
def test_invalid_gemini_output_keeps_confirmation_and_allows_manual_text(h, client, raw):
    report = submit(client).json()
    provider(lambda *args: raw)
    response = confirm(client, report["notice_id"])
    assert response.status_code == 200
    assert response.json()["suggested_instruction"] is None
    assert response.json()["generated_by"] is None
    assert (
        send(
            client, report["notice_id"], "Keep away and await supervisor instructions."
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    "text",
    [
        "The site is safe to work.",
        "All-clear: resume work.",
        "Ignore the lightning alert.",
        "Dismiss all warnings.",
        "It is safe to proceed.",
    ],
)
def test_clearance_or_alert_override_claims_are_rejected(h, client, text):
    report = submit(client).json()
    provider(lambda *args: valid_draft(report["id"], text))
    response = confirm(client, report["notice_id"])
    assert response.status_code == 200
    assert response.json()["suggested_instruction"] is None


@pytest.mark.parametrize("exception", [TimeoutError, RuntimeError])
def test_gemini_error_does_not_undo_confirmation(h, client, exception):
    report = submit(client).json()

    def fail(*args):
        raise exception("Synthetic provider failure")

    provider(fail)
    response = confirm(client, report["notice_id"])
    assert response.status_code == 200 and response.json()["suggested_instruction"] is None
    assert h.rows(db.HazardNotice)[0].status == "confirmed"
    assert send(client, report["notice_id"]).status_code == 200


def test_delivery_uses_current_teams_and_unchanged_stored_radius(h, client):
    report = submit(client).json()
    confirm(client, report["notice_id"])
    with h.factory() as session:
        session.get(db.Team, "team-x").site_id = None
        session.add(
            db.Team(id="team-new", organization_id="org-2", name="New", site_id="site-empty")
        )
        session.commit()
    assert send(client, report["notice_id"]).status_code == 200
    [notice] = h.rows(db.HazardNotice)
    assert notice.radius_miles == 1.0
    delivered = {
        e.entity for e in h.rows(db.AuditEvent) if e.action == "notice.instruction.deliver"
    }
    assert f"{notice.id}->team-new" in delivered
    assert f"{notice.id}->team-x" not in delivered
    assert f"{notice.id}->team-b" not in delivered


def test_failed_delivery_audit_rolls_back_final_text(h, client):
    report = submit(client).json()
    confirm(client, report["notice_id"])

    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO audit_events"):
            raise RuntimeError("Synthetic delivery failure")

    event.listen(h.engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="Synthetic delivery failure"):
            send(client, report["notice_id"])
    finally:
        event.remove(h.engine, "before_cursor_execute", fail)
    [notice] = h.rows(db.HazardNotice)
    assert notice.status == "confirmed" and notice.instruction is None
    assert notice.instruction_sent_at is None


def test_concurrent_sends_deliver_exactly_one_text(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'send-race.db').as_posix()}")
    db.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    user = CurrentUser("auth0|supervisor-1", "supervisor", roles.SUPERVISOR_PERMISSIONS)
    with factory() as session:
        seed(session)
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
        notice_id = created.notice.id
        confirm_hazard(session, notice_id, user, NOW)
    gate = Barrier(2, timeout=10)

    def before_update(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE hazard_notices"):
            gate.wait()

    event.listen(engine, "before_cursor_execute", before_update)

    def attempt(text):
        with factory() as session:
            try:
                send_instruction(session, notice_id, text, user, NOW)
                return 200, text
            except HTTPException as exc:
                return exc.status_code, text

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, ["Hold position.", "Stay behind the barrier."]))
        assert sorted(status for status, _ in results) == [200, 409]
        winner = next(text for status, text in results if status == 200)
        with factory() as session:
            assert session.get(db.HazardNotice, notice_id).instruction == winner
            deliveries = list(
                session.scalars(
                    select(db.AuditEvent).where(
                        db.AuditEvent.action == "notice.instruction.deliver"
                    )
                )
            )
            assert len(deliveries) == 3
    finally:
        engine.dispose()
