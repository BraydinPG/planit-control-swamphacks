from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from ml.events import read_noaa_detail_files
from ml.sources.noaa import _read_limited, _request_with_retries, select_archive_name


class NOAAArchiveTests(unittest.TestCase):
    def test_selects_latest_archive_revision_for_year(self) -> None:
        index = """
        <a href="StormEvents_details-ftp_v1.0_d2024_c20250101.csv.gz">old</a>
        <a href="StormEvents_details-ftp_v1.0_d2024_c20260728.csv.gz">new</a>
        <a href="StormEvents_details-ftp_v1.0_d2025_c20260819.csv.gz">other</a>
        """
        self.assertEqual(
            select_archive_name(index, 2024),
            "StormEvents_details-ftp_v1.0_d2024_c20260728.csv.gz",
        )

    def test_missing_year_is_actionable(self) -> None:
        with self.assertRaisesRegex(ValueError, "was not listed"):
            select_archive_name("<a href='file.csv.gz'>file</a>", 2024)

    def test_download_stream_limit_rejects_oversize_content(self) -> None:
        class FakeHeaders(dict):
            pass

        class FakeResponse:
            headers = FakeHeaders()

            def __init__(self) -> None:
                self.chunks = [b"1234", b"5678"]

            def read(self, size: int) -> bytes:
                chunk = self.chunks.pop(0) if self.chunks else b""
                return chunk[:size]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "payload.gz"
            with self.assertRaisesRegex(ValueError, "download limit"):
                _read_limited(FakeResponse(), 5, path)

    def test_supported_noaa_year_prefix_is_stable(self) -> None:
        self.assertTrue("StormEvents_details-ftp_v1.0_d2024".startswith("StormEvents_details-ftp_v1.0_d"))

    def test_transient_network_error_retries(self) -> None:
        class FakeResponse:
            headers: dict[str, str] = {}

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback) -> None:
                _ = exc_type, exc_value, traceback

            def read(self, size: int) -> bytes:
                return b"index"[:size]

        with patch("ml.sources.noaa.urlopen", side_effect=[URLError("offline"), FakeResponse()]) as mocked:
            with patch("ml.sources.noaa.time.sleep"):
                self.assertEqual(_request_with_retries("https://example.invalid", 1, 2, limit=100), b"index")
        self.assertEqual(mocked.call_count, 2)

    def test_archive_schema_change_fails_loudly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "details_d2024_sample.csv"
            path.write_text("EVENT_ID,EVENT_TYPE\n1,Flood\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "schema changed"):
                read_noaa_detail_files([path])

    def test_duplicate_event_ids_are_counted_not_double_weighted(self) -> None:
        header = "EVENT_ID,EPISODE_ID,EVENT_TYPE,BEGIN_DATE_TIME,END_DATE_TIME,CZ_TIMEZONE,STATE,CZ_TYPE,CZ_NAME,BEGIN_LAT,BEGIN_LON\n"
        row = "1001,500,Flood,10-SEP-24 10:00:00,10-SEP-24 16:00:00,EDT-4,FLORIDA,C,PINELLAS,27.9,-82.7\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "details_d2024_sample.csv"
            path.write_text(header + row + row, encoding="utf-8")
            events, counts = read_noaa_detail_files([path])
        self.assertEqual(len(events), 1)
        self.assertEqual(counts["duplicates"], 1)


if __name__ == "__main__":
    unittest.main()
