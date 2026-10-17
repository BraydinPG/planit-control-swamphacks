from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ml.train import (
    conditional_km_survival,
    fit_models,
    km_survival_at,
    load_models,
    save_models,
)


def event(event_id: str, episode_id: str, duration: int) -> dict[str, object]:
    return {
        "event_id": event_id,
        "episode_id": episode_id,
        "event_type": "Flood",
        "start_utc": "2024-06-01T00:00:00Z",
        "end_utc": f"2024-06-{1 + duration // 24:02d}T{duration % 24:02d}:00:00Z",
        "right_censored": False,
    }


class SurvivalBaselineTests(unittest.TestCase):
    def test_km_conditional_survival_is_age_conditioned(self) -> None:
        events = [event(f"e{i}", f"ep{i}", duration) for i, duration in enumerate([2, 4, 8, 12, 20, 30] * 5)]
        models = fit_models(events, minimum_events=1, minimum_episodes=1)
        young = conditional_km_survival(models, elapsed_hours=0, horizon_hours=6, min_support=1)
        aged = conditional_km_survival(models, elapsed_hours=6, horizon_hours=6, min_support=1)
        self.assertIsNotNone(young)
        self.assertIsNotNone(aged)
        self.assertAlmostEqual(young, 2 / 3)
        self.assertAlmostEqual(aged, 0.5)
        self.assertNotEqual(aged, young)

    def test_km_survival_nonincreasing_and_probability_bounds(self) -> None:
        events = [event(f"e{i}", f"ep{i}", duration) for i, duration in enumerate([2, 4, 8, 12, 20, 30] * 5)]
        models = fit_models(events, minimum_events=1, minimum_episodes=1)
        estimates = [km_survival_at(models, horizon) for horizon in (0, 6, 12, 24, 48)]
        self.assertEqual(estimates, sorted(estimates, reverse=True))
        self.assertTrue(all(0 <= probability <= 1 for probability in estimates))

    def test_unseen_event_types_are_not_in_model_training_data(self) -> None:
        events = [event(f"e{i}", f"ep{i}", duration) for i, duration in enumerate([2, 4, 8, 12, 20, 30] * 5)]
        events.append({"event_id": "hail", "episode_id": "hail", "event_type": "Hail",
                       "start_utc": "2024-06-01T00:00:00Z", "end_utc": "2024-06-01T02:00:00Z"})
        models = fit_models(events, minimum_events=1, minimum_episodes=1)
        self.assertEqual(models.event_type, "Flood")
        self.assertEqual(models.training_event_count, 30)

    def test_sparse_support_returns_none(self) -> None:
        events = [event("one", "one", 48)]
        models = fit_models(events, minimum_events=1, minimum_episodes=1)
        self.assertIsNone(conditional_km_survival(models, 0, 6, min_support=20))

    def test_artifact_round_trip_preserves_importable_state(self) -> None:
        events = [event(f"e{i}", f"ep{i}", duration) for i, duration in enumerate([2, 4, 8, 12, 20, 30] * 5)]
        models = fit_models(events, minimum_events=1, minimum_episodes=1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.joblib"
            save_models(models, path)
            loaded = load_models(path)
        self.assertEqual(loaded.model_version, models.model_version)
        self.assertEqual(loaded.training_event_count, models.training_event_count)
        self.assertEqual(km_survival_at(loaded, 12), km_survival_at(models, 12))

    def test_fit_is_reproducible_for_identical_inputs(self) -> None:
        events = [event(f"e{i}", f"ep{i}", duration) for i, duration in enumerate([2, 4, 8, 12, 20, 30] * 5)]
        first = fit_models(events, minimum_events=1, minimum_episodes=1)
        second = fit_models(events, minimum_events=1, minimum_episodes=1)
        self.assertEqual(first.classifier.coef_.tolist(), second.classifier.coef_.tolist())
        self.assertEqual(first.classifier.intercept_.tolist(), second.classifier.intercept_.tolist())


if __name__ == "__main__":
    unittest.main()
