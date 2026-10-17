from __future__ import annotations

import unittest

from ml.features import FEATURE_ALLOWLIST, build_active_snapshots, split_events_by_episode, validate_snapshot_features
from ml.labels import discrete_time_hazard_rows, duration_records


def event(event_id: str, episode_id: str, start: str, end: str | None) -> dict[str, object]:
    return {
        "event_id": event_id,
        "episode_id": episode_id,
        "event_type": "Flood",
        "start_utc": start,
        "end_utc": end,
        "duration_hours": None,
        "right_censored": end is None,
        "label_quality": "recorded_event_interval" if end else "unknown_recorded_end",
        "geometry_quality": "zone_only",
    }


class SnapshotTests(unittest.TestCase):
    def test_only_active_snapshots_with_separate_future_labels(self) -> None:
        source = event("a", "episode-a", "2024-06-01T00:00:00Z", "2024-06-01T10:00:00Z")
        source["EVENT_NARRATIVE"] = "retrospective"
        snapshots = build_active_snapshots([source])
        self.assertEqual([row["features"]["elapsed_hours"] for row in snapshots], [0.0, 6.0])
        self.assertEqual(snapshots[0]["labels"]["recorded_event_ongoing_6h"], True)
        self.assertEqual(snapshots[1]["labels"]["recorded_event_ongoing_6h"], False)
        self.assertEqual(set(snapshots[0]["features"]), set(FEATURE_ALLOWLIST))
        self.assertNotIn("EVENT_NARRATIVE", snapshots[0]["features"])
        self.assertNotIn("end_utc", snapshots[0]["features"])
        validate_snapshot_features(snapshots[0])

    def test_rejects_future_or_final_fields_in_features(self) -> None:
        snapshot = {"features": {"event_type": "Flood", "elapsed_hours": 0,
                                 "start_month": 6, "duration_hours": 10}}
        with self.assertRaisesRegex(ValueError, "forbidden predictor"):
            validate_snapshot_features(snapshot)

    def test_unknown_end_does_not_make_active_or_resolved_label(self) -> None:
        snapshots = build_active_snapshots([event("c", "episode-c", "2024-06-01T00:00:00Z", None)])
        records, counts = duration_records([event("c", "episode-c", "2024-06-01T00:00:00Z", None)])
        self.assertEqual(snapshots, [])
        self.assertEqual(records, [])
        self.assertEqual(counts["unknown_end_excluded"], 1)

    def test_grouped_year_split_keeps_cross_year_episode_together(self) -> None:
        events = [
            event("a", "shared", "2024-12-31T22:00:00Z", "2025-01-01T02:00:00Z"),
            event("b", "shared", "2025-01-01T00:00:00Z", "2025-01-01T03:00:00Z"),
            event("c", "test", "2025-02-01T00:00:00Z", "2025-02-01T04:00:00Z"),
        ]
        split = split_events_by_episode(events)
        self.assertEqual({row["event_id"] for row in split["validation"]}, {"a", "b"})
        self.assertEqual({row["event_id"] for row in split["test"]}, {"c"})
        self.assertFalse(set(row["episode_id"] for row in split["validation"]) &
                         set(row["episode_id"] for row in split["test"]))

    def test_discrete_rows_censor_at_horizon_without_fake_event(self) -> None:
        long_event = event("long", "episode-long", "2024-06-01T00:00:00Z", "2024-06-20T00:00:00Z")
        records, counts = duration_records([long_event], max_followup_hours=168)
        rows = discrete_time_hazard_rows(records)
        self.assertEqual(counts["administratively_censored"], 1)
        self.assertEqual(len(rows), 168)
        self.assertFalse(any(row["ended_in_next_hour"] for row in rows))


if __name__ == "__main__":
    unittest.main()
