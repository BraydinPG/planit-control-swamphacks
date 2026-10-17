from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from ml.predict import predict_active_event, predict_site
from ml.train import fit_models


def training_events() -> list[dict[str, object]]:
    durations = [2, 4, 8, 12, 20, 30, 36, 48, 72, 96] * 4
    return [
        {"event_id": f"event-{index}", "episode_id": f"episode-{index}", "event_type": "Flood",
         "start_utc": "2024-06-01T00:00:00Z",
         "end_utc": f"2024-06-{1 + duration // 24:02d}T{duration % 24:02d}:00:00Z"}
        for index, duration in enumerate(durations)
    ]


def active_context() -> dict[str, object]:
    return {
        "site_id": "fixture-site",
        "event_id": "fixture-event",
        "event_type": "Flood",
        "event_status": "historical_replay",
        "event_start_utc": "2024-06-01T00:00:00Z",
        "as_of_utc": "2024-06-01T06:00:00Z",
        "location": {"region": "example county", "spatial_match_quality": "region_only"},
        "is_simulated": True,
    }


class PredictionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.model = fit_models(training_events(), minimum_events=1, minimum_episodes=1)

    def test_active_prediction_schema_probability_order_and_json_safety(self) -> None:
        result = predict_active_event(active_context(), model=self.model)
        self.assertEqual(result["status"], "ok")
        ongoing = result["outcomes"]["recorded_event_ongoing_probability"]
        self.assertTrue(0 <= ongoing["24h"] <= ongoing["12h"] <= ongoing["6h"] <= 1)
        for horizon, probability in ongoing.items():
            self.assertAlmostEqual(
                result["outcomes"]["recorded_event_ended_probability"][horizon], 1 - probability
            )
        self.assertEqual(result["outcomes"]["trend"], "unknown")
        self.assertTrue(result["worker_context"]["never_interpret_as_all_clear"])
        json.dumps(result, allow_nan=False)

    def test_inactive_event_is_not_a_low_occurrence_probability(self) -> None:
        result = predict_active_event(dict(active_context(), event_status="inactive"), model=self.model)
        self.assertEqual(result["status"], "not_applicable_no_confirmed_event")
        self.assertEqual(result["outcomes"], {})

    def test_missing_artifact_is_unavailable_not_a_default_prediction(self) -> None:
        result = predict_active_event(active_context(), artifact_path=__import__("pathlib").Path("missing-model.joblib"))
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["outcomes"], {})

    def test_missing_event_age_or_location_is_unavailable(self) -> None:
        context = active_context()
        context["event_start_utc"] = None
        self.assertEqual(predict_active_event(context, model=self.model)["status"], "unavailable")
        context = active_context()
        context.pop("site_id")
        context.pop("location")
        self.assertEqual(predict_active_event(context, model=self.model)["status"], "unavailable")

    def test_site_compatibility_adapter_excludes_score_component(self) -> None:
        empty = predict_site({"site_id": "fixture-site"})
        self.assertEqual(empty["hazard_probabilities"], {})
        self.assertFalse(empty["data_quality"]["include_model_component_in_site_score"])
        self.assertEqual(empty["model_component_0_10"], 0.0)
        active = predict_site({"active_event_context": active_context()}, model=self.model)
        self.assertEqual(set(active["hazard_probabilities"]), {
            "active_event_persists_6", "active_event_persists_12", "active_event_persists_24"
        })
        self.assertFalse(active["data_quality"]["include_model_component_in_site_score"])

    def test_rejects_unknown_event_type(self) -> None:
        result = predict_active_event(dict(active_context(), event_type="Hail"), model=self.model)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["outcomes"], {})

    def test_stale_observations_are_explicitly_degraded(self) -> None:
        context = active_context()
        context["recent_observations"] = [{
            "type": "precipitation_6h", "value": 12.0, "valid_time_utc": "2024-06-01T05:00:00Z",
            "freshness": "stale",
        }]
        result = predict_active_event(context, model=self.model)
        self.assertEqual(result["evidence_quality"]["status"], "degraded_stale_observations")
        self.assertEqual(result["evidence_quality"]["stale_observation_count"], 1)

    def test_inference_does_not_use_network(self) -> None:
        with patch("urllib.request.urlopen", side_effect=AssertionError("inference attempted network access")):
            result = predict_active_event(active_context(), model=self.model)
        self.assertEqual(result["status"], "ok")

    def test_public_imports_work_in_fresh_process_from_repo_root(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [sys.executable, "-c", "from ml.predict import predict_active_event, predict_site"],
            cwd=repository_root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
