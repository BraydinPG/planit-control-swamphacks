"""Boundary and real-product tests; no network, training or private configuration."""

import base64
import copy
import hashlib
import json
import socket
from dataclasses import replace
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from ml.backend_adapter import ActiveEventPredictor
from ml.event_outlooks.examples import (
    FIXTURES,
    REPLAY_POLICY,
    evaluate_examples,
    examples,
)
from ml.event_outlooks.official import parse_nhc, parse_oaf
from ml.event_outlooks.schema import DurationForecast, OutlookBatch, OutlookRequest
from ml.event_outlooks.service import EventOutlookAdapter


class MustNotPredict:
    def predict_for_site(self, *_):
        raise AssertionError("Rejected evidence must never reach a model")


@pytest.fixture(scope="module")
def inputs():
    with patch.object(
        socket, "create_connection", side_effect=AssertionError("offline only")
    ):
        return examples()


def request(inputs, name="flash-flood"):
    return copy.deepcopy(next(c["request"] for c in inputs[0] if c["name"] == name))


def result(payload, inputs, *, policy=REPLAY_POLICY, predictor=None):
    return EventOutlookAdapter(
        trust_policy=policy,
        predictor=predictor or MustNotPredict(),
        official_products=inputs[1],
    ).build(payload)


def reason(payload, inputs, **kwargs):
    card = result(payload, inputs, **kwargs).event_outlooks[0]
    assert card.status != "available"
    assert card.evidence_status == "rejected_for_forecast"
    assert card.site_hazard_probability is None
    return card.forecast.reason_code


@pytest.mark.parametrize(
    "change,expected",
    [
        ({"event_start_utc": None}, "event_start_missing"),
        ({"event_start_utc": "2024-09-28T00:00:00Z"}, "invalid_event_start"),
        ({"event_definition": "wrong-target"}, "target_definition_mismatch"),
        ({"event_type": "Strong Wind"}, "unsupported_target"),
        ({"event_type": "Ice Storm"}, "unsupported_target"),
        ({"event_type": "Heavy Snow"}, "unsupported_target"),
        ({"event_type": "Thunderstorm Wind"}, "unsupported_target"),
        ({"event_type": "Wildfire"}, "unsupported_target"),
    ],
)
def test_invalid_target_does_not_dispatch(inputs, change, expected):
    payload = request(inputs)
    payload["events"][0].update(change)
    assert reason(payload, inputs) == expected


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("status", "unconfirmed", "no_confirmed_active_event"),
        ("status", "resolved", "no_confirmed_active_event"),
        ("basis", "warning_only", "independent_confirmation_required"),
        ("basis", "none", "independent_confirmation_required"),
        ("source_id", "forged-crew-confirmation", "untrusted_confirmation"),
        ("confirmed_at_utc", None, "confirmation_time_missing"),
        ("available_at_utc", "2024-09-27T06:00:00Z", "late_confirmation"),
        ("available_at_utc", "2024-09-27T04:00:00Z", "late_confirmation"),
    ],
)
def test_confirmation_and_warning_gates(inputs, field, value, expected):
    payload = request(inputs)
    payload["events"][0]["confirmation"][field] = value
    assert reason(payload, inputs) == expected


def test_replay_policy_is_server_owned(inputs):
    assert (
        reason(
            request(inputs), inputs, policy=replace(REPLAY_POLICY, allow_replay=False)
        )
        == "replay_not_enabled"
    )
    payload = request(inputs)
    payload["events"][0]["confirmation"]["status"] = "confirmed_active"
    assert reason(payload, inputs) == "replay_mislabeled"
    payload["trust_policy"] = {"allow_replay": True}
    with pytest.raises(ValidationError):
        OutlookRequest.model_validate(payload)


@pytest.mark.parametrize(
    "change",
    [
        {"site_id": "eia860m-FL-6584"},
        {"method": "unknown"},
        {"source_id": "forged-map"},
    ],
)
def test_site_association_not_guessed(inputs, change):
    payload = request(inputs)
    payload["events"][0]["association"].update(change)
    assert reason(payload, inputs) == "site_association_unverified"


@pytest.mark.parametrize(
    "when,available,expected",
    [
        ("2024-09-27T06:00:00Z", "2024-09-27T06:00:00Z", "future_or_late_evidence"),
        ("2024-09-27T04:00:00Z", "2024-09-27T06:00:00Z", "future_or_late_evidence"),
        ("2024-09-27T05:00:00Z", "2024-09-27T04:00:00Z", "future_or_late_evidence"),
    ],
)
def test_observation_vintage(inputs, when, available, expected):
    payload = request(inputs)
    payload["events"][0]["observations"] = [
        {
            "id": "observed",
            "source_id": "demo-continuous-observation",
            "valid_time_utc": when,
            "available_at_utc": available,
        }
    ]
    assert reason(payload, inputs) == expected


def test_real_confirmation_needs_fresh_local_evidence(inputs):
    payload = request(inputs)
    event = payload["events"][0]
    event["confirmation"].update(
        status="confirmed_active", basis="independent_observation"
    )
    event["association"]["method"] = "site_verified"
    assert reason(payload, inputs) == "local_confirmation_missing"
    event["observations"] = [
        {
            "id": "old-reading",
            "source_id": "demo-continuous-observation",
            "valid_time_utc": "2024-09-27T03:00:00Z",
            "available_at_utc": "2024-09-27T03:00:00Z",
        }
    ]
    assert reason(payload, inputs) == "stale_local_confirmation"
    event["observations"][0].update(
        valid_time_utc=payload["as_of_utc"],
        available_at_utc=payload["as_of_utc"],
        source_id="forged-observation",
    )
    assert reason(payload, inputs) == "untrusted_observation"


@pytest.mark.parametrize(
    "change",
    [
        {"lat": True},
        {"lat": 95},
        {"lon": -181},
        {"lat": float("nan")},
        {"id": "../../secret"},
        {"id": "site; shell-command"},
        {"id": ""},
    ],
)
def test_malformed_site_is_validation_error(inputs, change):
    payload = request(inputs)
    payload["site"].update(change)
    with pytest.raises(ValidationError):
        result(payload, inputs)


def test_multiple_events_preserve_order_identity_and_no_mutation(inputs):
    payload = request(inputs, "multiple-events")
    before = copy.deepcopy(payload)
    batch = result(payload, inputs)
    assert [c.event_id for c in batch.event_outlooks] == [
        c["event_id"] for c in payload["events"]
    ]
    assert payload == before
    assert not batch.affects_site_score and not batch.affects_alerts_or_lightning_timer
    assert batch.work_authorization == "outside_advisory_authority"
    assert all(c.site_hazard_probability is None for c in batch.event_outlooks)
    payload["events"].append(copy.deepcopy(payload["events"][0]))
    with pytest.raises(ValidationError, match="Duplicate event"):
        result(payload, inputs)


def test_empty_and_warning_only_are_not_zero_risk(inputs):
    assert (
        result(request(inputs, "no-confirmed-event"), inputs).status == "not_applicable"
    )
    assert (
        reason(request(inputs, "warning-only-unconfirmed"), inputs)
        == "no_confirmed_active_event"
    )


@pytest.mark.parametrize(
    "name", ["nhc-product-unavailable", "usgs-product-unavailable"]
)
def test_no_official_product_does_not_invent_duration(inputs, name):
    assert reason(request(inputs, name), inputs) == "official_forecast_missing"


def test_real_nhc_track_keeps_units_scope_and_issue_vintage(inputs):
    payload = request(inputs, "nhc-helene-issued")
    batch = result(payload, inputs)
    card = batch.event_outlooks[0]
    assert card.status == "available" and card.is_simulated and not card.research_only
    f = card.forecast
    assert f.cyclone_id == "AL092024"
    assert f.source.issued_at_utc == "2024-09-27T03:00:00Z"
    assert f.initial_position.max_sustained_wind_kt == 120
    assert f.forecast_points[0].max_sustained_wind_kt == 55
    assert len(f.forecast_points) == 5
    assert f.site_wind_forecast is None
    assert not hasattr(f, "remaining_duration_hours")
    assert f.source.available_at_utc is None
    assert f.source.retrieved_at_utc > card.as_of_utc  # archive replay only
    payload["as_of_utc"] = "2024-09-27T09:00:00Z"
    assert reason(payload, inputs) == "official_forecast_stale"


def test_future_issued_forecast_and_historical_retrieval_are_not_live(inputs):
    payload = request(inputs, "nhc-helene-issued")
    payload["as_of_utc"] = "2024-09-27T02:00:00Z"
    payload["events"][0]["confirmation"].update(
        confirmed_at_utc=payload["as_of_utc"], available_at_utc=payload["as_of_utc"]
    )
    assert reason(payload, inputs) == "future_issued_forecast"
    payload = request(inputs, "nhc-helene-issued")
    payload["events"][0]["confirmation"].update(
        status="confirmed_active", basis="official_event_record"
    )
    payload["events"][0]["association"]["method"] = "regional_context"
    assert reason(payload, inputs) == "historical_availability_unverified"


def test_cyclone_phase_and_identity_must_match_issued_product(inputs):
    payload = request(inputs, "nhc-helene-issued")
    payload["events"][0]["event_type"] = "Tropical Depression"
    assert reason(payload, inputs) == "official_event_type_mismatch"
    payload["events"][0]["event_id"] = "AL102024"
    assert reason(payload, inputs) == "official_event_mismatch"


def test_corrupt_official_product_is_a_partial_card_not_a_batch_failure(inputs):
    payload = request(inputs, "multiple-events")
    storm = request(inputs, "nhc-helene-issued")["events"][0]
    payload["events"].append(storm)
    products = {
        **inputs[1],
        "helene-015": inputs[1]["helene-015"].model_copy(
            update={"forecast_points": []}
        ),
    }
    batch = EventOutlookAdapter(
        trust_policy=REPLAY_POLICY,
        predictor=MustNotPredict(),
        official_products=products,
    ).build(payload)
    assert len(batch.event_outlooks) == 5
    assert batch.event_outlooks[-1].forecast.reason_code == "official_product_invalid"


def test_real_aftershock_windows_are_regional_not_quake_duration(inputs):
    payload = request(inputs, "usgs-aftershock-issued")
    card = result(payload, inputs).event_outlooks[0]
    assert card.status == "available"
    f = card.forecast
    assert f.mainshock.event_id == "ci38457511" and f.mainshock.magnitude == 7.1
    assert f.mainshock.time_utc == "2019-07-06T03:19:53.040000Z"
    assert f.region.radius_km == 60 and len(f.windows) == 4
    assert f.windows[0].bins[0].probability_at_least_one == 0.01844
    assert f.earthquake_remaining_duration is None
    assert not hasattr(f, "remaining_duration_hours")
    payload["site"]["lat"] = 24.56
    assert reason(payload, inputs) == "outside_aftershock_region"
    payload = request(inputs, "usgs-aftershock-issued")
    payload["events"][0]["event_start_utc"] = "2019-07-06T00:00:00Z"
    assert reason(payload, inputs) == "mainshock_time_mismatch"


def test_ended_oaf_windows_are_removed_without_rescaling_probabilities(inputs):
    payload = request(inputs, "usgs-aftershock-issued")
    payload["as_of_utc"] = "2026-09-05T04:00:00Z"
    card = result(payload, inputs).event_outlooks[0]
    assert len(card.forecast.windows) == 3
    assert card.forecast.windows[0].label == "1 Week"


def receipt(name):
    return json.loads((FIXTURES / (name + ".receipt.json")).read_text())


def test_nhc_corrupt_body_or_truncated_track_fails():
    raw = (FIXTURES / "helene-fst-015.txt").read_bytes()
    meta = receipt("helene-fst-015.txt")
    with pytest.raises(ValueError, match="checksum"):
        parse_nhc(raw.replace(b"120 KT", b"121 KT"), meta)
    body = raw.replace(b"MAX WIND  55 KT...GUSTS  75 KT.", b"MAX WIND MISSING")
    meta.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
    with pytest.raises(ValueError, match="truncated"):
        parse_nhc(body, meta)


@pytest.mark.parametrize(
    "change",
    [
        lambda f: f["model"]["parameters"].update(regionType="unknown"),
        lambda f: f["forecast"][0]["bins"][0].update(probability=1.5),
        lambda f: f["forecast"][0].update(timeEnd=0),
        lambda f: f["model"]["parameters"].update(magMain=4.0),
    ],
)
def test_malformed_official_aftershock_product_fails(change):
    f = json.loads((FIXTURES / "ridgecrest-oaf.json").read_bytes())
    d = json.loads((FIXTURES / "ridgecrest-detail.json").read_bytes())
    change(f)
    body = json.dumps(f).encode()
    meta = receipt("ridgecrest-oaf.json")
    meta.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
    d["properties"]["products"]["oaf"][0]["contents"]["forecast.json"]["sha256"] = (
        base64.b64encode(hashlib.sha256(body).digest()).decode()
    )
    detail = json.dumps(d).encode()
    dm = receipt("ridgecrest-detail.json")
    dm.update(bytes=len(detail), sha256=hashlib.sha256(detail).hexdigest())
    with pytest.raises((ValueError, ValidationError)):
        parse_oaf(body, meta, detail, dm)


def test_missing_corrupt_artifact_loader_is_not_deserialized(inputs, tmp_path):
    for name, body in (("missing", None), ("corrupt", b"not a pickle")):
        path = tmp_path / (name + ".joblib")
        if body:
            path.write_bytes(body)
        with patch(
            "ml.train.joblib.load", side_effect=AssertionError("must verify hash first")
        ):
            predictor = ActiveEventPredictor(path, expected_sha256="0" * 64)
        assert (
            reason(request(inputs, "flood"), inputs, predictor=predictor)
            == "model_unavailable"
        )


def test_missing_quantiles_stay_null_and_extra_authority_is_rejected():
    f = DurationForecast(
        target_definition="fixture",
        model_version="fixture",
        estimator="fixture",
        model_card="fixture",
        persistence=[{"horizon_hours": 1, "recorded_event_ongoing_probability": 0.5}],
        remaining_duration_hours={"p10": 1.0, "median": None, "p90": None},
    )
    assert f.model_dump()["remaining_duration_hours"] == {
        "p10": 1.0,
        "median": None,
        "p90": None,
    }
    with pytest.raises(ValidationError):
        DurationForecast.model_validate({**f.model_dump(), "work_clearance": True})


def test_preview_products_and_replays_repeat_without_network(inputs):
    # No artifacts required: missing ones produce deterministic typed unavailable cards.
    with patch.object(
        socket, "create_connection", side_effect=AssertionError("offline only")
    ):
        first = evaluate_examples(*inputs)
        second = evaluate_examples(*inputs)
    assert first == second
    for item in first:
        OutlookBatch.model_validate_json(json.dumps(item["response"], allow_nan=False))
    assert len(first) >= 10


def test_model_output_horizons_must_match_reviewed_registry(inputs):
    class WrongHorizon:
        def predict_for_site(self, *_):
            return {
                "status": "ok",
                "outcomes": {"recorded_event_ongoing_probability": {"6h": 0.5}},
            }

    assert (
        reason(request(inputs), inputs, predictor=WrongHorizon()) == "prediction_failed"
    )


def test_actual_qualified_artifacts_when_provisioned(inputs):
    from ml.config import MODEL_PATH
    from ml.dispatch import read_registry, resolve_artifact

    if not MODEL_PATH.exists() or any(
        not resolve_artifact(e).exists()
        for e in read_registry()["events"].values()
        if e.get("artifact") and e.get("prediction_eligible")
    ):
        pytest.skip(
            "Optional real-artifact integration; clean checkout uses unavailable cards"
        )
    outputs = {o["name"]: o["response"] for o in evaluate_examples(*inputs)}
    for name, horizons in (
        ("flood", [6, 12, 24]),
        ("flash-flood", [1, 3, 6]),
        ("high-wind", [6, 12, 24]),
        ("heavy-rain", [1, 3, 6]),
        ("winter-storm", [6, 12, 24]),
        ("heat-station-replay", [1, 3, 6]),
    ):
        c = outputs[name]["event_outlooks"][0]
        assert c["status"] == "available", c
        assert [p["horizon_hours"] for p in c["forecast"]["persistence"]] == horizons
        assert not c["production_eligibility"]
    assert outputs["multiple-events"]["status"] == "partial"
