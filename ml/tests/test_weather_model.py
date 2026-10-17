from __future__ import annotations

import unittest

from ml.weather_features import WEATHER_FEATURE_NAMES
from ml.weather_model import conditional_weather_survival, fit_weather_model


def snapshot(index: int, duration: int, weather_value: float | None = None) -> dict[str, object]:
    features: dict[str, object] = {"event_type": "Flood", "elapsed_hours": 0.0, "start_month": index % 12 + 1}
    for feature_index, name in enumerate(WEATHER_FEATURE_NAMES):
        features[name] = None if weather_value is None else weather_value + feature_index
    return {
        "event_id": f"event-{index}",
        "episode_id": f"episode-{index}",
        "features": features,
        "labels": {"remaining_duration_hours": float(duration)},
    }


class WeatherModelTests(unittest.TestCase):
    def test_fit_and_predict_produces_monotonic_conditional_curve(self) -> None:
        durations = [2, 4, 8, 12, 20, 30, 36, 48] * 8
        snapshots = [snapshot(index, duration, float(index % 7)) for index, duration in enumerate(durations)]
        model = fit_weather_model(snapshots, minimum_snapshots=20, minimum_episodes=20)
        prediction = conditional_weather_survival(model, snapshots[0], 6)
        prediction_12h = conditional_weather_survival(model, snapshots[0], 12)
        prediction_24h = conditional_weather_survival(model, snapshots[0], 24)
        self.assertTrue(0 <= prediction_24h <= prediction_12h <= prediction <= 1)
        self.assertEqual(model.training_snapshot_count, len(snapshots))
        self.assertEqual(model.model_version, "noaa-flood-era5-retrospective-research-v2")

    def test_all_missing_weather_is_refused(self) -> None:
        snapshots = [snapshot(index, [2, 4, 8, 12][index % 4], None) for index in range(60)]
        with self.assertRaisesRegex(ValueError, "entirely missing"):
            fit_weather_model(snapshots)

    def test_small_episode_support_is_refused(self) -> None:
        snapshots = [snapshot(index % 10, [2, 4, 8, 12][index % 4], float(index)) for index in range(40)]
        for row in snapshots:
            row["episode_id"] = "one-episode"
        with self.assertRaisesRegex(ValueError, "episode groups"):
            fit_weather_model(snapshots, minimum_snapshots=20, minimum_episodes=20)


if __name__ == "__main__":
    unittest.main()
