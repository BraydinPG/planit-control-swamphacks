"""Offline failure-boundary and scientific-target tests; no downloaded data needed."""

import copy
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ml.backend_adapter import ActiveEventPredictor
from ml.dispatch import predict_expansion, resolve_artifact
from ml.event_types import NOAA_EVENT_TYPES
from ml.features import build_active_snapshots
from ml.hurricane import FEATURES, predict_replay, track_snapshots
from ml.monte_carlo import simulate_model
from ml.multidisaster import purged_expansion_split
from ml.predict import predict_active_event, predict_site
from ml.schemas import validate_event_context
from ml.sources.archive_cache import fetch_cached
from ml.sources.hurdat import lifecycle_events, parse_hurdat
from ml.sources.stations import HEAT_DEFINITION, heat_index_f, parse_station, relative_humidity, threshold_episodes
from ml.sources.wildfire import normalize_firms_csv
from ml.tests.test_prediction import active_context, training_events
from ml.train import fit_models


@pytest.fixture(scope="module")
def expansion_model():
    rows = [{**r, "event_type": "Flash Flood"} for r in training_events() * 3]
    return fit_models(rows, minimum_events=1, minimum_episodes=1, event_type="Flash Flood")


def entry(model):
    return {"status": "evaluated_research", "prediction_eligible": True, "category": "flash_flood",
            "event_type": "Flash Flood", "event_definition": "noaa_positive_continuous_recorded_interval",
            "minimum_event_age_hours": 1, "supported_horizons_hours": [1, 3, 6],
            "selected_estimator": "kaplan_meier", "artifact_model_version": model.model_version,
            "artifact_sha256": "fixture", "artifact": "multidisaster/flash_flood.joblib",
            "data_version": "fixture_only", "target": "synthetic conditional persistence", "limitations": ["Fixture only; never clearance."]}


def context():
    return {**active_context(), "event_type": "Flash Flood", "event_definition": "noaa_positive_continuous_recorded_interval"}


def test_fifteen_types_preserve_distinct_targets():
    assert len(NOAA_EVENT_TYPES) == 15
    assert NOAA_EVENT_TYPES["High Wind"].category != NOAA_EVENT_TYPES["Strong Wind"].category
    assert not NOAA_EVENT_TYPES["Thunderstorm Wind"].candidate
    assert not NOAA_EVENT_TYPES["Heat"].candidate


def test_short_horizons_dispatch_and_compatibility(expansion_model):
    registry = {"events": {"Flash Flood": entry(expansion_model)}}
    with patch("ml.dispatch.read_registry", return_value=registry):
        result = predict_active_event(context(), model=expansion_model)
        adapted = predict_site({"active_event_context": context()}, model=expansion_model)
    assert result["status"] == "ok"
    assert list(result["outcomes"]["recorded_event_ongoing_probability"]) == ["1h", "3h", "6h"]
    assert result["event_category"] == "flash_flood"
    assert result["data_version"] == "fixture_only"
    assert result["research_only"] and not result["operational_evaluation_eligible"]
    assert adapted["hazard_probabilities"].keys() == {"active_event_persists_1", "active_event_persists_3", "active_event_persists_6"}
    assert not adapted["data_quality"]["include_model_component_in_site_score"]
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("change", [
    {"event_definition": "different_outcome"}, {"event_start_utc": None},
    {"as_of_utc": "2024-06-01T00:30:00Z"}, {"location": None},
    {"event_status": "confirmed_active"},
    {"evidence": [{"id": "future", "source": "fixture", "available_at_utc": "2024-06-02T00:00:00Z"}]},
])
def test_expansion_requires_matching_current_evidence(expansion_model, change):
    registry = {"events": {"Flash Flood": entry(expansion_model)}}
    with patch("ml.dispatch.read_registry", return_value=registry):
        result = predict_active_event({**context(), **change}, model=expansion_model)
    assert result["status"] == "unavailable"
    assert result["outcomes"] == {}


def test_failed_gate_never_loads_artifact(expansion_model):
    record = {**entry(expansion_model), "prediction_eligible": False, "status": "trained_not_qualified"}
    with patch("ml.dispatch.load_entry_model", side_effect=AssertionError("must not load")):
        result = predict_expansion(validate_event_context(context()), registry={"events": {"Flash Flood": record}})
    assert result["outcomes"] == {}


def test_caller_extensions_are_not_echoed_as_evidence_or_location(expansion_model):
    registry = {"events": {"Flash Flood": entry(expansion_model)}}
    ctx = context()
    ctx["location"] = {**ctx["location"], "unvalidated": float("nan")}
    ctx["evidence"] = [{"id": "fixture", "source": "fixture", "available_at_utc": ctx["as_of_utc"], "unvalidated": float("nan")}]
    with patch("ml.dispatch.read_registry", return_value=registry):
        result = predict_active_event(ctx, model=expansion_model)
    assert result["status"] == "ok"
    assert "unvalidated" not in result["applicable_location"]
    assert "unvalidated" not in result["evidence_quality"]["evidence_references"][0]
    json.dumps(result, allow_nan=False)


def test_type_isolation_and_backend_cache(expansion_model):
    registry = {"events": {"Flash Flood": entry(expansion_model)}}
    flood = fit_models(training_events(), minimum_events=1, minimum_episodes=1)
    assert predict_expansion(validate_event_context(context()), registry=registry, model=flood)["status"] == "unavailable"
    with patch("ml.backend_adapter.load_models", return_value=flood), patch("ml.dispatch.read_registry", return_value=registry):
        predictor = ActiveEventPredictor()
    site = {"id": "fixture-site", "lat": 28, "lon": -82, "risk_score": 8, "active_alerts": 1}
    before = copy.deepcopy(site)
    with patch("ml.dispatch.load_entry_model", return_value=expansion_model) as loader:
        assert predictor.predict_for_site(site, context())["status"] == "ok"
        assert predictor.predict_for_site(site, context())["status"] == "ok"
    assert loader.call_count == 1 and site == before


def test_registry_cannot_escape_artifact_directory():
    with pytest.raises(ValueError):
        resolve_artifact({"artifact": "../outside.joblib"})


def test_embargo_removes_whole_connected_group():
    rows = [
        {"event_id": "a", "episode_id": "joined", "start_utc": "2023-12-28T00:00:00Z", "end_utc": "2023-12-29T00:00:00Z"},
        {"event_id": "b", "episode_id": "joined", "start_utc": "2023-06-01T00:00:00Z", "end_utc": "2023-06-02T00:00:00Z"},
        {"event_id": "c", "episode_id": "test", "start_utc": "2025-06-01T00:00:00Z", "end_utc": "2025-06-02T00:00:00Z"},
    ]
    splits = purged_expansion_split(rows)
    assert {r["event_id"] for r in splits["excluded"]} == {"a", "b"}
    assert [r["event_id"] for r in splits["test"]] == ["c"]


def test_heat_formula_units_and_missing_measurements(tmp_path):
    assert heat_index_f(90, 70) == pytest.approx(105.9220206)
    assert relative_humidity(30, 30) == pytest.approx(100)
    with pytest.raises(ValueError):
        relative_humidity(30, 31)
    path = tmp_path / "station.gz"
    with gzip.open(path, "wt") as stream:
        stream.write("2024 6 1 0 300 200 10000 180 50 0 -9999 -9999\n")
        stream.write("2024 6 1 1 -9999 200 10000 180 -9999 0 -9999 -9999\n")
    rows, quality = parse_station(path, "fixture-station")
    assert rows[0]["temperature_c"] == 30 and rows[0]["wind_speed_m_s"] == 5
    assert rows[1]["heat_index_f"] is None and rows[1]["wind_speed_m_s"] is None
    assert quality["missing_heat_measurement"] == 1


def test_heat_gaps_are_not_resolution_and_crossing_is_hourly():
    start = datetime(2024, 6, 1, tzinfo=timezone.utc)
    def row(hour, value):
        return {"valid_time_utc": (start+timedelta(hours=hour)).isoformat(), "heat_index_f": value, "station_id": "fixture"}
    rows = [row(0, 95), row(1, 80), row(2, 95), row(4, 95), row(5, 80), row(6, 95), row(7, 80), row(8, 95)]
    events, counts = threshold_episodes(rows, {"lat": 28, "lon": -82, "name": "fixture"})
    assert len(events) == 1 and events[0]["duration_hours"] == 1
    assert counts["left_censored_episodes_excluded"] == 2
    assert counts["right_censored_episodes_excluded"] == 2


def test_hurdat_missing_codes_and_unknown_end(tmp_path):
    path = tmp_path / "hurdat.txt"
    path.write_text("AL012024, FIXTURE, 2,\n20240601, 0000, , TS, 20.0N, 60.0W, -99, -999,\n20240601, 0600, , TS, 20.1N, 60.1W, 40, 1000,\n", encoding="ascii")
    storms, quality = parse_hurdat(path)
    assert storms[0]["points"][0]["max_wind_kt"] is None
    assert quality["missing_pressure"] == quality["missing_wind"] == 1
    events, quality = lifecycle_events(storms)
    assert events == [] and quality["unknown_lifecycle_end_excluded"] == 1


def test_hurricane_label_does_not_enter_predictors():
    start = datetime(2024, 6, 1, tzinfo=timezone.utc)
    points = [{"valid_time_utc": (start+timedelta(hours=h)).isoformat(), "status": "TS", "lat": 20, "lon": -60,
               "max_wind_kt": wind, "min_pressure_hpa": 1000} for h, wind in ((0, 40), (6, 45), (30, 60))]
    storms = [{"storm_id": "AL012024", "year": 2024, "points": points}]
    first, _ = track_snapshots(storms)
    points[-1]["max_wind_kt"] = 25
    second, _ = track_snapshots(storms)
    assert first[0]["label"] == "worsening" and second[0]["label"] == "improving"
    assert first[0]["features"] == second[0]["features"]
    assert set(first[0]["features"]) == set(FEATURES)
    with pytest.raises(ValueError, match="retrospective"):
        predict_replay(first[0]["features"], None, data_state="retrospective_best_track", event_status="confirmed_active")


def test_firms_detection_is_not_containment(tmp_path):
    path = tmp_path / "firms.csv"
    path.write_text("latitude,longitude,acq_date,acq_time,satellite,confidence\n28,-82,2024-06-01,1230,N,nominal\n", encoding="utf-8")
    row = normalize_firms_csv(path, collection_version="synthetic_fixture")[0]
    assert row["containment"] is None and row["incident_id"] is None
    assert row["source_kind"] == "satellite_thermal_detection"


def test_cache_rejects_changed_or_unreceipted_sources(tmp_path):
    path = tmp_path / "file.txt"
    path.write_bytes(b"fixture")
    with pytest.raises(ValueError, match="Unreceipted"):
        fetch_cached("https://www.nhc.noaa.gov/file.txt", tmp_path, filename="file.txt")
    receipt = {"url": "https://www.nhc.noaa.gov/file.txt", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    path.with_name("file.txt.receipt.json").write_text(json.dumps(receipt))
    with patch("ml.sources.archive_cache.urlopen", side_effect=AssertionError("network")):
        assert fetch_cached(receipt["url"], tmp_path, filename="file.txt")[1]["cached"]
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="mismatch"):
        fetch_cached(receipt["url"], tmp_path, filename="file.txt")


def test_selected_km_monte_carlo_matches_analytical(expansion_model):
    result = simulate_model(expansion_model, elapsed_hours=1, start_month=6, trials=20000, estimator="kaplan_meier", horizons=(1, 3, 6))
    assert max(result["absolute_probability_error"].values()) < .015
    assert not result["raw_trajectories_included"]
