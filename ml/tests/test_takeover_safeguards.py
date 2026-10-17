import copy
import hashlib
import json
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from ml.backend_adapter import ActiveEventPredictor
from ml.evaluate import binary_metrics, episode_bootstrap_brier
from ml.predict import predict_active_event
from ml.provision import ensure_archive
from ml.schemas import validate_event_context
from ml.tests.test_prediction import active_context, training_events
from ml.train import conditional_km_survival, fit_models, save_models
from ml.features import split_events_by_episode
from ml.sources.weather import fetch_historical_weather


@pytest.fixture(scope="module")
def model():
    return fit_models(training_events(), minimum_events=1, minimum_episodes=1)


def test_default_inference_is_training_only_km(model):
    result = predict_active_event(active_context(), model=model)
    assert result["estimator"] == "kaplan_meier"
    assert result["model_version"] == "noaa-flood-conditional-km-v2"
    assert result["production_eligibility"] is False
    for horizon in (6, 12, 24):
        assert result["outcomes"]["recorded_event_ongoing_probability"][f"{horizon}h"] == conditional_km_survival(model, 6, horizon)


@pytest.mark.parametrize("mutation", [
    {"event_status": []}, {"site_id": {}}, {"location": {"lat": True, "lon": 1}},
    {"location": {"lat": 1}}, {"location": {"spatial_match_quality": []}},
    {"is_simulated": "false"}, {"evidence": [{"id": "a", "source": "fixture", "available_at_utc": "2024-06-01T07:00:00Z"}]},
    {"recent_observations": [{"value": 1, "valid_time_utc": "2024-06-01T05:00:00Z", "acquired_at_utc": "2024-06-01T07:00:00Z"}]},
])
def test_invalid_or_post_asof_evidence_fails_closed(model, mutation):
    result = predict_active_event({**active_context(), **mutation}, model=model)
    assert result["status"] == "unavailable"
    assert result["outcomes"] == {}
    json.dumps(result, allow_nan=False)


def test_supplied_evidence_is_retained_without_claiming_independent_verification(model):
    context = active_context()
    context["evidence"] = [{"id": "fixture-proof", "source": "synthetic_fixture", "available_at_utc": context["as_of_utc"]}]
    quality = predict_active_event(context, model=model)["evidence_quality"]
    assert quality["evidence_ids"] == ["fixture-proof"]
    assert quality["provenance_status"] == "supplied_not_independently_verified"


def test_corrupt_artifact_has_no_probabilities_or_internal_path(tmp_path):
    path = tmp_path / "corrupt.joblib"
    path.write_bytes(b"not a pickle")
    result = predict_active_event(active_context(), artifact_path=path)
    assert result["status"] == "unavailable"
    assert result["outcomes"] == {}
    assert str(tmp_path) not in json.dumps(result)


def test_adapter_loads_once_checks_hash_and_preserves_site_and_alert_data(model, tmp_path):
    path = save_models(model, tmp_path / "model.joblib")
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    site = {"id": "fixture-site", "lat": 28, "lon": -82, "risk_score": 9, "active_alerts": 1}
    context = active_context()
    original = copy.deepcopy((site, context))
    predictor = ActiveEventPredictor(path, expected_sha256=checksum)
    with patch("ml.backend_adapter.load_models", side_effect=AssertionError("reloaded")):
        first = predictor.predict_for_site(site, context)
        second = predictor.predict_for_site(site, context)
    assert first["status"] == second["status"] == "ok"
    assert first["outcomes"] == second["outcomes"]
    assert (site, context) == original
    assert ActiveEventPredictor(path, expected_sha256="0" * 64).predict(context)["status"] == "unavailable"
    assert predictor.predict_for_site(site, {**context, "site_id": "other-site"})["outcomes"] == {}


def test_backend_working_directory_can_import_and_run_adapter(model, tmp_path):
    path = save_models(model, tmp_path / "model.joblib")
    root = Path(__file__).resolve().parents[2]
    program = "from ml.backend_adapter import ActiveEventPredictor; import json,sys; p=ActiveEventPredictor(sys.argv[1]); print(json.dumps(p.predict(json.loads(sys.argv[2])), allow_nan=False))"
    completed = subprocess.run([sys.executable, "-c", program, str(path), json.dumps(active_context())],
                               cwd=root / "backend", env={**os.environ, "PYTHONPATH": str(root)},
                               capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["status"] == "ok"


def test_aggregated_bootstrap_matches_original_seeded_flattening():
    probabilities = [0.1, 0.3, 0.7, 0.9] * 12
    outcomes = [False, True, False, True] * 12
    groups = [f"ep-{i // 3}" for i in range(len(probabilities))]
    grouped = {}
    for p, y, group in zip(probabilities, outcomes, groups):
        grouped.setdefault(group, []).append((p - int(y)) ** 2)
    rng = random.Random(42)
    estimates = []
    values = list(grouped.values())
    for _ in range(500):
        sample = [rng.choice(values) for _ in values]
        flattened = [v for group in sample for v in group]
        estimates.append(sum(flattened) / len(flattened))
    estimates.sort()
    result = episode_bootstrap_brier(probabilities, outcomes, groups)
    assert result["lower_95"] == pytest.approx(estimates[int(0.025 * 499)], abs=1e-14)
    assert result["upper_95"] == pytest.approx(estimates[int(0.975 * 499)], abs=1e-14)
    with pytest.raises(ValueError, match="identical lengths"):
        binary_metrics([0.1], [], ["a"])


def test_bad_pinned_archive_is_preserved_and_never_downloaded(tmp_path):
    name = "StormEvents_details-ftp_v1.0_d2024_c20260728.csv.gz"
    path = tmp_path / name
    path.write_bytes(b"preserve me")
    entry = {"file": name, "url": "https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/" + name,
             "bytes": 1, "sha256": "0" * 64}
    with patch("ml.provision._request_with_retries", side_effect=AssertionError("network")):
        with pytest.raises(ValueError, match="preserved"):
            ensure_archive(entry, tmp_path, download=True)
    assert path.read_bytes() == b"preserve me"


def test_episode_with_future_outcome_is_purged_even_without_cross_year_start():
    events = [{"event_id": "a", "episode_id": "crossing", "event_type": "Flood",
               "start_utc": "2023-12-31T20:00:00Z", "end_utc": "2024-01-01T02:00:00Z"},
              {"event_id": "b", "episode_id": "crossing", "event_type": "Flood",
               "start_utc": "2023-12-31T18:00:00Z", "end_utc": "2023-12-31T23:00:00Z"}]
    splits = split_events_by_episode(events)
    assert splits["train"] == []
    assert {row["event_id"] for row in splits["excluded"]} == {"a", "b"}


def test_cache_only_weather_never_uses_network(tmp_path):
    with patch("ml.sources.weather._retrieve", side_effect=AssertionError("network")):
        with pytest.raises(FileNotFoundError, match="cache-only"):
            fetch_historical_weather(28, -82, "2024-06-01", "2024-06-02", "2024-06-01T06:00:00Z",
                                     cache_dir=tmp_path, cache_only=True)
