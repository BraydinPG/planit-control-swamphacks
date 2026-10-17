from __future__ import annotations

import unittest

from ml.events import event_duration_hours, normalize_noaa_row


class NOAAEventNormalizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.row = {
            "EVENT_ID": "1001",
            "EPISODE_ID": "501",
            "EVENT_TYPE": "Flood",
            "BEGIN_DATE_TIME": "10-SEP-24 10:00:00",
            "END_DATE_TIME": "10-SEP-24 16:00:00",
            "CZ_TIMEZONE": "EDT-4",
            "STATE": "FLORIDA",
            "CZ_TYPE": "C",
            "CZ_NAME": "PINELLAS",
            "BEGIN_LAT": "27.9",
            "BEGIN_LON": "-82.7",
            "MAGNITUDE": "999",
            "EVENT_NARRATIVE": "final retrospective narrative must not enter features",
        }

    def test_converts_fixed_offset_local_times_to_utc(self) -> None:
        event = normalize_noaa_row(self.row)
        self.assertEqual(event["start_utc"], "2024-09-10T14:00:00Z")
        self.assertEqual(event["end_utc"], "2024-09-10T20:00:00Z")
        self.assertEqual(event_duration_hours(event), 6.0)

    def test_unknown_end_is_censored_not_resolved(self) -> None:
        row = dict(self.row, END_DATE_TIME="")
        event = normalize_noaa_row(row)
        self.assertTrue(event["right_censored"])
        self.assertIsNone(event["duration_hours"])
        self.assertIsNone(event_duration_hours(event))

    def test_rejects_invalid_or_nonpositive_interval(self) -> None:
        row = dict(self.row, END_DATE_TIME="10-SEP-24 09:00:00")
        with self.assertRaisesRegex(ValueError, "later than"):
            normalize_noaa_row(row)

    def test_final_fields_are_not_copied_to_normalized_event(self) -> None:
        event = normalize_noaa_row(self.row)
        self.assertNotIn("MAGNITUDE", event)
        self.assertNotIn("EVENT_NARRATIVE", event)

    def test_missing_timezone_is_not_guessed(self) -> None:
        row = dict(self.row, CZ_TIMEZONE="")
        with self.assertRaisesRegex(ValueError, "no CZ_TIMEZONE"):
            normalize_noaa_row(row)


if __name__ == "__main__":
    unittest.main()
