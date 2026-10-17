"""T060: Gemini's supports/contradicts analysis of a crew report, and T053A report location."""

import json
from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import null, update

import app.gemini as gemini
from app.api.deps import get_db, get_now
from app.db import models as db
from app.gemini.report_analysis import run_report_analysis
from app.main import app
from app.storage import get_photo_store
from tests import auth_fakes
from tests.test_reports_api import HOME, JPEG, NEAR, NOW, Harness, submit

SUPPORTS = {
    "verdict": "supports",
    "summary": "The photo shows a leaning pole with a sagging line, matching the report.",
    "supporting": [
        {"statement": "A pole leans and a conductor sags.", "evidence_ids": ["photo"]},
    ],
    "contradicting": [],
    "also_visible": ["Standing water near the pole"],
    "suggested_category": "broken_pole_downed_line",
    "severity_suggestion": "high",
    "confidence": 0.8,
    "unknowns": ["Whether the line is energized."],
}


class FakeGemini:
    """Records each call and answers with `reply` (dict as JSON, a string, or raises)."""

    def __init__(self, reply: dict | str | Exception = SUPPORTS) -> None:
        self.reply = reply
        self.prompts: list[str] = []
        self.images: list[list] = []

    def transport(self, prompt: str, schema: type[BaseModel], images=()) -> str:
        self.prompts.append(prompt)
        self.images.append(list(images))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply if isinstance(self.reply, str) else json.dumps(self.reply)

    def client(self) -> gemini.GeminiClient:
        return gemini.GeminiClient("test-key", "test-model", 5.0, transport=self.transport)


@pytest.fixture
def h(tmp_path) -> Iterator[Harness]:
    harness = Harness(tmp_path)
    app.dependency_overrides[get_db] = harness.override_db
    app.dependency_overrides[get_now] = lambda: NOW
    app.dependency_overrides[get_photo_store] = lambda: harness.photos
    auth_fakes.install(app)
    try:
        yield harness
    finally:
        app.dependency_overrides.clear()
        harness.engine.dispose()


def run(h, fake: FakeGemini | None, **fields) -> dict:
    """Submit a report (the analysis runs as a background task) and return it re-read."""
    client = fake.client() if fake else gemini.GeminiClient(None, None, 1)
    app.dependency_overrides[gemini.get_gemini_client] = lambda: client
    response = submit(TestClient(app), **fields)
    assert response.status_code == 201, response.text
    with h.factory() as session:
        row = session.get(db.CrewReport, response.json()["id"])
        return {"response": response.json(), "row": row}


# ---- the analysis ----


def test_access_mat_analysis_accepts_category_without_overwriting_crew_assessment(h) -> None:
    fake = FakeGemini({**SUPPORTS, "suggested_category": "access_mat_deterioration"})
    note = "Mat 12: crew stage D, broken timber."
    result = run(h, fake, category="access_mat_deterioration", note=note)
    row = result["row"]
    assert row.category == "access_mat_deterioration"
    assert row.note == note
    assert row.review_status == "pending"
    assert row.enrichment["suggested_category"] == "access_mat_deterioration"
    assert "load capacity" in fake.prompts[0]
    assert "approved grading rubric" in fake.prompts[0]


def test_supported_report_stores_a_complete_analysis(h) -> None:
    fake = FakeGemini()
    result = run(h, fake)
    assert result["response"]["enrichment"] is None  # the crew member never waits on Gemini
    analysis = result["row"].enrichment
    assert analysis["status"] == "complete"
    assert analysis["verdict"] == "supports"
    assert analysis["supporting"][0]["evidence_ids"] == ["photo"]
    assert analysis["generated_by"] == "gemini"
    assert analysis["needs_review"] is True
    assert {"photo", "crew:category", "crew:hazard_present"} <= {
        e["id"] for e in analysis["evidence"]
    }


def test_analysis_never_changes_the_report(h) -> None:
    fake = FakeGemini({**SUPPORTS, "suggested_category": "on_site_fire"})
    row = run(h, fake)["row"]
    assert (row.review_status, row.category, row.confirmed_category) == (
        "pending",
        "broken_pole_downed_line",
        None,
    )
    assert row.enrichment["suggested_category"] == "on_site_fire"


def test_contradicting_report(h) -> None:
    reply = {
        **SUPPORTS,
        "verdict": "contradicts",
        "summary": "The photo shows an upright pole and intact lines.",
        "supporting": [],
        "contradicting": [{"statement": "The pole is upright.", "evidence_ids": ["photo"]}],
    }
    assert run(h, FakeGemini(reply))["row"].enrichment["verdict"] == "contradicts"


def test_photo_is_sent_and_location_is_not(h) -> None:
    fake = FakeGemini()
    run(h, fake, note="Pole down by the gate")
    (image,) = fake.images[0]
    assert (image.data, image.mime_type) == (JPEG, "image/jpeg")
    prompt = fake.prompts[0]
    assert "Crew member's note: Pole down by the gate" in prompt
    assert str(HOME[0]) not in prompt and str(HOME[1]) not in prompt


def test_report_without_a_photo_is_analyzed_from_the_data(h) -> None:
    fake = FakeGemini({**SUPPORTS, "supporting": [
        {"statement": "Crew says no fire.", "evidence_ids": ["crew:hazard_present"]}
    ]})  # fmt: skip
    row = run(h, fake, photo=None, hazard_present="false", category="on_site_fire")["row"]
    assert fake.images == [[]]
    assert row.enrichment["status"] == "complete"
    assert row.enrichment["unknowns"][0].startswith("No photo was read")


def test_site_alerts_and_readings_are_evidence(h) -> None:
    with h.factory() as session:
        session.add(
            db.Alert(
                id="alert-1", site_id="site-a", rule="lightning_stop_work", state="active",
                triggered_at=NOW - timedelta(minutes=5), latest_event_at=NOW - timedelta(minutes=5),
                clear_after=NOW + timedelta(minutes=25), distance_miles=4.0,
            )
        )  # fmt: skip
        session.add(
            db.Observation(
                id="obs-flood", site_id="site-a", source="NWS", hazard_type="flood_alert",
                value="Flood Warning", unit=None, label="Flood Warning", lat=HOME[0],
                lon=HOME[1], observed_at=NOW - timedelta(minutes=10),
                fetched_at=NOW - timedelta(minutes=10), data_state="observed", simulated=False,
            )
        )  # fmt: skip
        session.commit()
    fake = FakeGemini()
    run(h, fake)
    assert "alert-1" in fake.prompts[0]
    assert "obs-flood" in fake.prompts[0]
    assert "Flood Warning" in fake.prompts[0]


@pytest.mark.parametrize(
    ("reply", "reason"),
    [
        ({**SUPPORTS, "supporting": [{"statement": "x", "evidence_ids": ["nope"]}]}, "invalid"),
        ({**SUPPORTS, "supporting": []}, "invalid"),
        ({**SUPPORTS, "verdict": "contradicts"}, "invalid"),
        ({**SUPPORTS, "summary": "The site is safe to work."}, "invalid"),
        ({**SUPPORTS, "unknowns": ["Clear the stop-work alert once dry."]}, "invalid"),
        ("not json", "invalid"),
        (TimeoutError(), "timeout"),
        (RuntimeError("boom"), "error"),
    ],
)
def test_bad_or_failed_analysis_is_stored_as_unavailable(h, reply, reason) -> None:
    analysis = run(h, FakeGemini(reply))["row"].enrichment
    assert analysis["status"] == "unavailable"
    assert analysis["unavailable_reason"].startswith(reason)
    assert analysis["verdict"] is None
    assert analysis["generated_by"] == "fallback"


def test_unconfigured_gemini_leaves_the_report_standing(h) -> None:
    row = run(h, None)["row"]
    assert row.enrichment["status"] == "unavailable"
    assert row.enrichment["unavailable_reason"] == "missing_config"
    assert row.review_status == "pending"


def test_unreadable_photo_is_noted(h) -> None:
    result = run(h, FakeGemini())
    report_id = result["row"].id

    class Broken:
        def load(self, key: str) -> bytes:
            raise OSError("gone")

    with h.factory() as session:  # SQL NULL, as a newly saved report has
        session.execute(
            update(db.CrewReport).where(db.CrewReport.id == report_id).values(enrichment=null())
        )
        session.commit()
    run_report_analysis(h.engine, report_id, Broken(), FakeGemini().client(), NOW)
    with h.factory() as session:
        unknowns = session.get(db.CrewReport, report_id).enrichment["unknowns"]
    assert any("photo could not be loaded" in u for u in unknowns)


def test_existing_analysis_is_never_overwritten(h) -> None:
    report_id = run(h, FakeGemini())["row"].id
    run_report_analysis(h.engine, report_id, h.photos, FakeGemini(TimeoutError()).client(), NOW)
    with h.factory() as session:
        assert session.get(db.CrewReport, report_id).enrichment["status"] == "complete"


def test_missing_report_is_ignored(h) -> None:
    run_report_analysis(h.engine, "report:nope", h.photos, FakeGemini().client(), NOW)


# ---- T053A: location source, accuracy, and site distance ----


def test_device_location_is_stored_with_accuracy_and_distance(h) -> None:
    result = run(
        h, None, lat=str(NEAR[0]), lon=str(NEAR[1]), location_source="device",
        location_accuracy_m="12.5",
    )  # fmt: skip
    report = result["response"]
    assert (report["location_source"], report["location_accuracy_m"]) == ("device", 12.5)
    assert report["site_distance_miles"] == pytest.approx(0.5, abs=0.05)


def test_location_defaults_to_the_site(h) -> None:
    report = run(h, None)["response"]
    assert (report["location_source"], report["location_accuracy_m"]) == ("site", None)
    assert report["site_distance_miles"] == 0.0


def test_pin_location(h) -> None:
    report = run(h, None, location_source="pin")["response"]
    assert report["location_source"] == "pin"


@pytest.mark.parametrize(
    "fields",
    [
        {"location_source": "site", "location_accuracy_m": "10"},
        {"location_source": "pin", "location_accuracy_m": "10"},
        {"location_source": "device", "location_accuracy_m": "-1"},
        {"location_source": "gps"},
    ],
)
def test_invalid_location_fields_are_rejected(h, fields) -> None:
    app.dependency_overrides[gemini.get_gemini_client] = lambda: gemini.GeminiClient(None, None, 1)
    response = submit(TestClient(app), **fields)
    assert response.status_code == 422


def test_location_reads_back_from_the_report_list(h) -> None:
    run(h, None, location_source="device", location_accuracy_m="8")
    rows = TestClient(app).get("/api/reports", headers=auth_fakes.crew("auth0|crew-a")).json()
    assert (rows[0]["location_source"], rows[0]["location_accuracy_m"]) == ("device", 8.0)
