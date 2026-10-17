"""T087 acceptance: actual offline outputs, identity, chronology and safe rendering."""

import copy
from datetime import timedelta
from html.parser import HTMLParser
import json

import pytest
from pydantic import ValidationError

from ml.backend_adapter import ActiveEventPredictor
from ml.schemas import parse_utc
from ml.worker.comprehensive_schema import ComprehensiveOutlook, ComprehensiveRequest
from ml.worker_preview import (
    CRITICAL,
    catalog,
    evaluate_request,
    example_html,
    generate,
    preview_request,
)


class MissingArtifacts:
    def predict_for_site(self, site, event):
        return {
            "status": "unavailable",
            "model_version": "fixture-no-artifacts",
            "outcomes": {},
        }


@pytest.fixture(scope="module")
def inputs():
    return catalog()


def test_full_offline_preview_validates_all_saved_requests_and_responses(
    tmp_path, inputs
):
    report = generate(tmp_path, predictor=MissingArtifacts())
    assert report["validated_outputs"] == 150 and len(report["sites"]) == 50
    assert report["sites_with_captured_environmental_evidence"] == 2
    assert report["sites_with_captured_notices"] == 10
    assert (
        not report["is_actual_incident"] and not report["local_probability_validated"]
    )
    for file in tmp_path.glob("*-response.json"):
        response = ComprehensiveOutlook.model_validate_json(
            file.read_text(encoding="utf-8")
        )
        request_file = file.with_name(file.name.replace("-response", "-request"))
        request = ComprehensiveRequest.model_validate_json(
            request_file.read_text(encoding="utf-8")
        )
        assert request.site_context == response.site
        assert (
            response.site.id in {s.id for s in inputs[0]}
            and not response.site.is_fixture
        )
        assert request.event_context.event_status == "historical_replay"
        assert response.is_demo_or_simulated and response.confirmation.is_fixture
        assert response.not_work_clearance and not response.production_eligibility
        assert response.event_outlook.status == "unavailable"
        assert all(h.probability is None for h in response.site_hazards)
        assert all(
            h.probability is None and h.severity is None and h.needs_field_verification
            for h in response.worksite_hazards
        )
        assert all(
            h.status == "unknown"
            for h in response.worksite_hazards
            if h.hazard_id in CRITICAL
        )
        if "-missing-" in file.name:
            assert not response.evidence
            assert {s.state for s in response.source_availability} >= {
                "unavailable",
                "fixture_only",
            }
        else:
            assert response.evidence and all(
                not a.evidence.is_fixture for a in response.evidence
            )
    page = (tmp_path / "site-001.html").read_text(encoding="utf-8")
    assert "real captured source" in page and "Field verification" in page
    assert "fixed replay time, not today" in page
    assert "Layer A" in page and "Layer B" in page
    assert "No work authorization" in (tmp_path / "preview.txt").read_text(
        encoding="utf-8"
    )
    assert (
        json.loads((tmp_path / "response.schema.json").read_text())["properties"][
            "contract_version"
        ]["const"]
        == "2.1.0"
    )


@pytest.mark.parametrize(
    "site_id",
    [
        "../../escape",
        "<script>alert(1)</script>",
        "eia860m-XX-1",
        "eia860m-FL-999999999",
    ],
)
def test_invalid_site_never_creates_output(tmp_path, inputs, site_id):
    target = tmp_path / "new"
    with pytest.raises(ValueError):
        preview_request(site_id, "flood", inputs=inputs)
    with pytest.raises(ValueError):
        generate(target, site_id=site_id)
    assert not target.exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("lat", 999.0),
        ("lon", 0.0),
        ("name", "forged plant"),
        ("source_version", "fake"),
    ],
)
def test_candidate_coordinates_and_identity_are_reconciled(inputs, field, value):
    request = preview_request(inputs[0][0].id, "flood", inputs=inputs)
    request["site_context"][field] = value
    with pytest.raises((ValueError, ValidationError)):
        evaluate_request(request, inputs=inputs, predictor=MissingArtifacts())


@pytest.mark.parametrize("field", ["issued_at", "available_at"])
def test_future_issue_or_availability_rejected_without_losing_other_evidence(
    inputs, field
):
    request = preview_request(inputs[0][0].id, "flood", inputs=inputs)
    baseline = copy.deepcopy(request)
    row = next(e for e in request["evidence"] if e["method"] == "issued_forecast")
    future = (
        parse_utc(request["event_context"]["as_of_utc"], "asof") + timedelta(hours=1)
    ).isoformat()
    row[field] = future
    if field == "available_at":
        row["ingested_at"] = future
    response = evaluate_request(request, inputs=inputs, predictor=MissingArtifacts())
    assessment = next(
        a
        for a in response["evidence"]
        if a["evidence"]["evidence_id"] == row["evidence_id"]
    )
    reason = (
        "available_after_as_of" if field == "available_at" else "issued_at_after_as_of"
    )
    assert not assessment["accepted"] and reason in assessment["reasons"]
    assert any(a["accepted"] for a in response["evidence"])
    assert baseline != request


def test_unsupported_event_and_real_missing_artifact_have_typed_fallback(
    inputs, tmp_path
):
    request = preview_request(inputs[0][0].id, "flood", inputs=inputs)
    predictor = ActiveEventPredictor(
        tmp_path / "absent.joblib", expected_sha256="absent"
    )
    assert (
        evaluate_request(request, inputs=inputs, predictor=predictor)["event_outlook"][
            "status"
        ]
        == "unavailable"
    )
    request["event_context"]["event_type"] = "Tornado"
    result = evaluate_request(request, inputs=inputs, predictor=predictor)
    assert result["event_outlook"]["status"] == "unavailable"
    assert not result["event_outlook"]["ongoing_probability"]


def test_preview_rejects_claimed_live_activation_and_client_trust(inputs):
    request = preview_request(inputs[0][0].id, "missing", inputs=inputs)
    request["event_context"]["event_status"] = "confirmed_active"
    with pytest.raises((ValueError, PermissionError)):
        evaluate_request(request, inputs=inputs)
    request["trust_policy"] = {"allow_fixture_reports": True}
    with pytest.raises(ValidationError):
        evaluate_request(request, inputs=inputs)


class LocalPage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.active_tags = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "a":
            self.links.append(values["href"])
        if tag in {"script", "iframe", "form", "img", "link"} or any(
            k.startswith("on") for k in values
        ):
            self.active_tags.append(tag)


def test_static_html_escapes_source_prose_and_links_only_to_generated_files(
    tmp_path, inputs
):
    generate(tmp_path, site_id=inputs[0][0].id, predictor=MissingArtifacts())
    for file in tmp_path.glob("*.html"):
        parsed = LocalPage()
        parsed.feed(file.read_text(encoding="utf-8"))
        assert not parsed.active_tags
        for link in parsed.links:
            assert link.startswith("#") or (tmp_path / link).is_file()
    request = preview_request(inputs[0][0].id, "flood", inputs=inputs)
    response = evaluate_request(request, inputs=inputs, predictor=MissingArtifacts())
    attack = '</td><script>alert("x")</script><img src=x onerror=alert(1)>'
    response["evidence"][0]["evidence"]["publisher"] = attack
    page = example_html("Flood", request, response, "site-001-flood")
    parsed = LocalPage()
    parsed.feed(page)
    assert not parsed.active_tags and "&lt;script&gt;" in page and attack not in page


def test_require_models_does_not_report_success_without_artifacts(tmp_path, inputs):
    with pytest.raises(ValueError, match="Pinned duration model unavailable"):
        generate(
            tmp_path,
            site_id=inputs[0][0].id,
            predictor=MissingArtifacts(),
            require_models=True,
        )
    assert not (tmp_path / "acceptance.json").exists()
