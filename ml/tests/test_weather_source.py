from __future__ import annotations

import unittest

from ml.sources.weather import build_archive_url, filter_hourly_as_of


class HistoricalWeatherTests(unittest.TestCase):
    def test_filter_removes_values_after_as_of(self) -> None:
        payload = {"hourly": {
            "time": ["2024-06-01T10:00", "2024-06-01T11:00", "2024-06-01T12:00"],
            "temperature_2m": [27.0, 28.0, 29.0],
            "precipitation": [0.0, 1.0, 2.0],
        }}
        rows = filter_hourly_as_of(payload, "2024-06-01T11:00:00Z")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[-1]["valid_time_utc"], "2024-06-01T11:00:00Z")
        self.assertEqual(rows[-1]["data_state"], "retrospective_reanalysis")

    def test_bad_date_range_and_coordinates_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "on or before"):
            build_archive_url(27, -82, "2024-06-02", "2024-06-01")
        with self.assertRaisesRegex(ValueError, "valid bounds"):
            build_archive_url(95, -82, "2024-06-01", "2024-06-01")

    def test_request_window_is_bounded(self) -> None:
        with self.assertRaisesRegex(ValueError, "limited to"):
            build_archive_url(27, -82, "2024-01-01", "2024-05-01")


if __name__ == "__main__":
    unittest.main()
