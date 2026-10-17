from __future__ import annotations

import unittest

from ml.schemas import not_applicable_result, parse_utc, unavailable_result, validate_event_context


class EventContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = {
            "site_id": "fixture-site",
            "event_id": "fixture-event",
            "event_type": "Flood",
            "event_status": "historical_replay",
            "event_start_utc": "2024-09-10T10:00:00Z",
            "as_of_utc": "2024-09-10T16:00:00Z",
            "location": {"lat": 28.0, "lon": -82.7, "spatial_match_quality": "region_only"},
            "recent_observations": [
                {"type": "rain_6h", "value": 12.0, "unit": "mm", "valid_time_utc": "2024-09-10T15:00:00Z"}
            ],
            "is_simulated": True,
        }

    def test_valid_context_normalizes_times(self) -> None:
        normalized = validate_event_context(self.context)
        self.assertEqual(normalized["as_of_utc"], "2024-09-10T16:00:00Z")

    def test_rejects_timezone_naive_as_of(self) -> None:
        context = dict(self.context, as_of_utc="2024-09-10T16:00:00")
        with self.assertRaisesRegex(ValueError, "must include a timezone"):
            validate_event_context(context)

    def test_rejects_future_observation(self) -> None:
        context = dict(self.context)
        context["recent_observations"] = [
            {"type": "rain_6h", "value": 12.0, "valid_time_utc": "2024-09-10T17:00:00Z"}
        ]
        with self.assertRaisesRegex(ValueError, "newer than as_of_utc"):
            validate_event_context(context)

    def test_rejects_start_after_as_of(self) -> None:
        context = dict(self.context, event_start_utc="2024-09-10T17:00:00Z")
        with self.assertRaisesRegex(ValueError, "later than as_of_utc"):
            validate_event_context(context)

    def test_rejects_bad_coordinates(self) -> None:
        context = dict(self.context, location={"lat": 95, "lon": 0})
        with self.assertRaisesRegex(ValueError, "lat must be between"):
            validate_event_context(context)

    def test_inactive_event_does_not_create_low_probability(self) -> None:
        result = not_applicable_result(dict(self.context, event_status="inactive"), "inactive")
        self.assertEqual(result["status"], "not_applicable_no_confirmed_event")
        self.assertEqual(result["outcomes"], {})
        self.assertTrue(result["worker_context"]["never_interpret_as_all_clear"])

    def test_unavailable_does_not_create_probabilities(self) -> None:
        result = unavailable_result(self.context, "no fitted artifact")
        self.assertEqual(result["outcomes"], {})
        self.assertTrue(result["worker_context"]["never_interpret_as_all_clear"])

    def test_parse_utc_requires_timezone(self) -> None:
        with self.assertRaises(ValueError):
            parse_utc("2024-09-10 16:00", "timestamp")


if __name__ == "__main__":
    unittest.main()
