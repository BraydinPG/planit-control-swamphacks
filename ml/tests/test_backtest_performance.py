from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from ml.backtest import score_snapshots
from ml.features import build_active_snapshots
from ml.train import fit_models


class BacktestScoringPerformanceTests(unittest.TestCase):
    def test_one_classifier_prediction_per_snapshot_and_paired_baselines(self) -> None:
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        durations = [8, 12, 18, 24, 36, 48, 72, 96] * 6
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
            })
        model = fit_models(events, minimum_events=1, minimum_episodes=1)
        snapshots = build_active_snapshots(events)

        with patch.object(model.classifier, "predict_proba", wraps=model.classifier.predict_proba) as predict:
            result = score_snapshots(snapshots, model)

        self.assertEqual(predict.call_count, len(snapshots))
        for horizon in ("6h", "12h", "24h"):
            logistic = result["logistic"][horizon]
            km = result["kaplan_meier"][horizon]
            self.assertEqual(logistic["snapshot_count"], len(snapshots))
            self.assertEqual(km["snapshot_count"], len(snapshots))
            self.assertEqual(logistic["episode_count"], len(events))
            self.assertEqual(km["episode_count"], len(events))
        self.assertIsNotNone(result["duration"]["median_remaining_time_mae_hours"])

    def test_spawn_parallel_scoring_matches_serial(self) -> None:
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        durations = [8, 12, 18, 24, 36, 48, 72, 96] * 4
        events = []
        for index, duration in enumerate(durations):
            event_start = start + timedelta(days=index)
            event_end = event_start + timedelta(hours=duration)
            events.append({
                "event_id": f"parallel-event-{index}",
                "episode_id": f"parallel-episode-{index}",
                "event_type": "Flood",
                "start_utc": event_start.isoformat().replace("+00:00", "Z"),
                "end_utc": event_end.isoformat().replace("+00:00", "Z"),
            })
        model = fit_models(events, minimum_events=1, minimum_episodes=1)
        snapshots = build_active_snapshots(events)
        serial = score_snapshots(snapshots, model, workers=1)
        parallel = score_snapshots(snapshots, model, workers=2)
        self.assertEqual(serial, parallel)


if __name__ == "__main__":
    unittest.main()
