from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from ml.weather_features import deterministic_episode_sample, extract_weather_features


class WeatherFeatureTests(unittest.TestCase):
    def test_features_exclude_future_and_use_documented_units(self) -> None:
        cutoff = datetime(2024, 6, 1, 12, tzinfo=timezone.utc)
        hourly = []
        for hours_ago in range(30, -1, -1):
            timestamp = cutoff - timedelta(hours=hours_ago)
            hourly.append({
                "valid_time_utc": timestamp.isoformat().replace("+00:00", "Z"),
                "values": {
                    "precipitation": 1.0,
                    "temperature_2m": 25.0,
                    "relative_humidity_2m": 80.0,
                    "wind_speed_10m": 4.0,
                    "wind_gusts_10m": 8.0,
                },
            })
        hourly.append({
            "valid_time_utc": (cutoff + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            "values": {"precipitation": 1000.0, "temperature_2m": 100.0},
        })
        result = extract_weather_features(hourly, cutoff.isoformat())
        features = result["features"]
        self.assertEqual(features["rain_6h_mm"], 6.0)
        self.assertEqual(features["rain_24h_mm"], 24.0)
        self.assertEqual(features["temperature_last_c"], 25.0)
        self.assertEqual(features["wind_mean_6h_m_s"], 4.0)
        self.assertEqual(features["gust_max_6h_m_s"], 8.0)
        self.assertEqual(features["rain_6h_change_mm"], 0.0)
        self.assertEqual(result["latest_valid_time_utc"], cutoff.isoformat().replace("+00:00", "Z"))
        self.assertIn("not_archived_operational_forecast", result["feature_interpretation"])

    def test_sparse_weather_is_missing_not_zero_filled(self) -> None:
        result = extract_weather_features([{
            "valid_time_utc": "2024-06-01T12:00:00Z",
            "values": {"precipitation": 0.0},
        }], "2024-06-01T12:00:00Z")
        self.assertIsNone(result["features"]["rain_6h_mm"])
        self.assertIn("rain_6h_mm", result["missing_features"])

    def test_episode_sampling_is_deterministic_and_grouped(self) -> None:
        events = [
            {"event_id": "a", "episode_id": "ep-a", "source_year": 2024, "start_utc": "2024-01-01T00:00:00Z", "begin_lat": 27.0, "begin_lon": -82.0},
            {"event_id": "b", "episode_id": "ep-a", "source_year": 2024, "start_utc": "2024-01-01T01:00:00Z", "begin_lat": 27.0, "begin_lon": -82.0},
            {"event_id": "c", "episode_id": "ep-c", "source_year": 2024, "start_utc": "2024-01-02T00:00:00Z", "begin_lat": 28.0, "begin_lon": -83.0},
            {"event_id": "d", "episode_id": "ep-d", "source_year": 2025, "start_utc": "2025-01-02T00:00:00Z", "begin_lat": 29.0, "begin_lon": -84.0},
        ]
        first = deterministic_episode_sample(events, per_year=1, seed=42)
        second = deterministic_episode_sample(events, per_year=1, seed=42)
        self.assertEqual(first, second)
        self.assertEqual(sum(row["source_year"] == 2024 for row in first), 1)
        self.assertEqual(sum(row["source_year"] == 2025 for row in first), 1)
        self.assertFalse({row["episode_id"] for row in first} & {"ep-a", "ep-c"} - {row["episode_id"] for row in first})


if __name__ == "__main__":
    unittest.main()
