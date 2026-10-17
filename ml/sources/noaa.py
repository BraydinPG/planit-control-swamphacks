"""Bounded acquisition of official NOAA NCEI Storm Events detail archives."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html.parser
import json
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ml.config import NOAA_INDEX_URL, NOAA_MAX_ARCHIVE_BYTES, RAW_DATA_DIR, REPORT_DIR

_ARCHIVE_PATTERN = re.compile(r"StormEvents_details-ftp_v1\.0_d(?P<year>\d{4})_c(?P<created>\d{8})\.csv\.gz$")
_USER_AGENT = "PlanIT-Control-ML/0.1 (historical event research; bounded download)"


class _LinkParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            for name, value in attrs:
                if name.lower() == "href" and value:
                    self.hrefs.append(value)


def select_archive_name(index_html: str, year: int) -> str:
    parser = _LinkParser()
    parser.feed(index_html)
    candidates: list[tuple[str, str]] = []
    for href in parser.hrefs:
        name = href.rsplit("/", 1)[-1]
        match = _ARCHIVE_PATTERN.fullmatch(name)
        if match and int(match.group("year")) == year:
            candidates.append((match.group("created"), name))
    if not candidates:
        raise ValueError(f"NOAA detail archive for {year} was not listed in the official index")
    return max(candidates)[1]


def _read_limited(response, limit: int, destination: Path) -> tuple[int, str]:
    content_length = response.headers.get("Content-Length")
    if content_length and int(content_length) > limit:
        raise ValueError(f"NOAA archive exceeds the {limit}-byte download limit")
    digest = hashlib.sha256()
    size = 0
    with destination.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                raise ValueError(f"NOAA archive exceeds the {limit}-byte download limit")
            digest.update(chunk)
            output.write(chunk)
    return size, digest.hexdigest()


def _request_bytes(url: str, timeout: float, limit: int | None = None) -> bytes:
    request = Request(url, headers={"User-Agent": _USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        if limit is not None:
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > limit:
                raise ValueError(f"Response exceeds the {limit}-byte limit")
            content = response.read(limit + 1)
            if len(content) > limit:
                raise ValueError(f"Response exceeds the {limit}-byte limit")
            return content
        return response.read()


def _request_with_retries(url: str, timeout: float, retries: int, limit: int | None = None) -> bytes:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            return _request_bytes(url, timeout, limit)
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            last_error = error
            if attempt + 1 < retries:
                time.sleep(0.5 * (2**attempt))
    raise RuntimeError(f"Unable to retrieve {url} after {retries} attempts: {last_error}") from last_error


def _validate_gzip(path: Path) -> None:
    try:
        with gzip.open(path, "rb") as archive:
            # Read through the trailer so truncated streams and CRC failures
            # cannot pass an artifact-provisioning check.
            while archive.read(1024 * 1024):
                pass
    except (OSError, EOFError) as error:
        raise ValueError(f"Downloaded NOAA archive is not a valid gzip stream: {path.name}") from error


def download_year(year: int, output_dir: Path = RAW_DATA_DIR, timeout: float = 30.0,
                  retries: int = 3, max_bytes: int = NOAA_MAX_ARCHIVE_BYTES) -> dict[str, object]:
    if not 1950 <= year <= datetime.now(timezone.utc).year:
        raise ValueError("year must be between 1950 and the current UTC year")
    if retries < 1:
        raise ValueError("retries must be at least 1")
    output_dir.mkdir(parents=True, exist_ok=True)
    index = _request_with_retries(NOAA_INDEX_URL, timeout, retries, limit=2_000_000).decode("utf-8", "replace")
    archive_name = select_archive_name(index, year)
    archive_url = NOAA_INDEX_URL + archive_name
    final_path = output_dir / archive_name
    if final_path.exists():
        size = final_path.stat().st_size
        if size > max_bytes:
            raise ValueError(f"Cached NOAA archive exceeds the {max_bytes}-byte limit")
        _validate_gzip(final_path)
        digest = hashlib.sha256(final_path.read_bytes()).hexdigest()
        return {"year": year, "url": archive_url, "path": final_path.name, "bytes": size,
                "sha256": digest, "retrieved_at_utc": None, "cached": True}

    temporary_path: Path | None = None
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(archive_url, headers={"User-Agent": _USER_AGENT})
            with urlopen(request, timeout=timeout) as response:
                fd, temp_name = tempfile.mkstemp(prefix=f"{year}-", suffix=".part", dir=output_dir)
                os.close(fd)
                temporary_path = Path(temp_name)
                size, digest = _read_limited(response, max_bytes, temporary_path)
            _validate_gzip(temporary_path)
            os.replace(temporary_path, final_path)
            temporary_path = None
            return {"year": year, "url": archive_url, "path": final_path.name, "bytes": size,
                    "sha256": digest, "retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "cached": False}
        except ValueError:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
                temporary_path = None
            raise
        except (HTTPError, URLError, TimeoutError, OSError, EOFError) as error:
            last_error = error
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
                temporary_path = None
            if attempt + 1 < retries:
                time.sleep(0.5 * (2**attempt))
    raise RuntimeError(f"Unable to download {archive_url} after {retries} attempts: {last_error}") from last_error


def download_years(years: Iterable[int], output_dir: Path = RAW_DATA_DIR, **kwargs) -> list[dict[str, object]]:
    results = [download_year(year, output_dir=output_dir, **kwargs) for year in years]
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "source": "NOAA NCEI Storm Events CSV bulk archive",
        "index_url": NOAA_INDEX_URL,
        "retrieval_manifest_created_at_utc": datetime.now(timezone.utc).isoformat(),
        "archives": results,
        "notes": [
            "Event detail records are regional reports; coordinates and county/zone fields do not prove site-level exposure.",
            "NOAA event end is a recorded reporting interval end, not a worksite safety or return-to-work signal.",
            "Archive rows and narratives may be revised after the historical event; only allowlisted pre-as-of fields are predictors.",
        ],
    }
    manifest_path = output_dir / "source_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "source_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", type=int, nargs="+", required=True)
    parser.add_argument("--output", type=Path, default=RAW_DATA_DIR)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--max-mb", type=int, default=25)
    args = parser.parse_args()
    results = download_years(args.years, args.output, timeout=args.timeout, retries=args.retries,
                             max_bytes=args.max_mb * 1024 * 1024)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
