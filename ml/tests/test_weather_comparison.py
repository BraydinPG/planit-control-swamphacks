from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from ml.backtest import _summary
from ml.features import build_active_snapshots
from ml.train import fit_models
from ml.weather_backtest import _score_comparable
from ml.weather_features import WEATHER_FEATURE_NAMES
from ml.weather_model import fit_weather_model


class WeatherComparisonTests(unittest.TestCase):
    def test_models_share_identical_eligible_snapshots_at_every_horizon(self) -> None:
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        durations = [8, 12, 18, 24, 36, 48, 72, 96] * 8
        events = []
        for index, duration in enumerate(durations):
            event_start = start + timedelta(days=index)
            event_end = event_start + timedelta(hours=duration)
            events.append({
                "event_id": f"event-{index}",
                "episode_id": f"episode-{index}",
                "event_type": "Flood",
                "start_utc": event_start.isoformat().replace("+00:00", "Z"),
                "end_utc": event_end.isoformat().replace("+00:00", "Z"),
                "duration_hours": float(duration),
                "event_observed": True,
            })
        snapshots = build_active_snapshots(events)
        for index, snapshot in enumerate(snapshots):
            for feature_index, name in enumerate(WEATHER_FEATURE_NAMES):
                snapshot["features"][name] = float((index + feature_index) % 11)

        baseline = fit_models(events, minimum_events=20, minimum_episodes=20)
        weather_model = fit_weather_model(snapshots, minimum_snapshots=20, minimum_episodes=20)
        scores = _score_comparable(weather_model, baseline, snapshots)

        for horizon in ("6h", "12h", "24h"):
            sample_counts = {scores[name][horizon]["snapshot_count"] for name in scores}
            episode_counts = {scores[name][horizon]["episode_count"] for name in scores}
            self.assertEqual(len(sample_counts), 1)
            self.assertEqual(len(episode_counts), 1)
            self.assertGreaterEqual(sample_counts.pop(), episode_counts.pop())


if __name__ == "__main__":
    unittest.main()
