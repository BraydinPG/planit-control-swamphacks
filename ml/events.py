"""Normalize NOAA event rows without carrying retrospective fields into features."""

from __future__ import annotations

import csv
import gzip
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from ml.config import SUPPORTED_EVENT_TYPE

_REQUIRED_COLUMNS = {
    "EVENT_ID", "EPISODE_ID", "EVENT_TYPE", "BEGIN_DATE_TIME", "END_DATE_TIME",
    "CZ_TIMEZONE", "STATE", "CZ_TYPE", "CZ_NAME",
}
_DATE_FORMATS = (
    "%d-%b-%y %H:%M:%S",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%y %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
)
_OFFSET_PATTERN = re.compile(r"(?P<offset>[+-]\d{1,2}(?::\d{2})?)$")


def _parse_local_datetime(value: str) -> datetime:
    stripped = value.strip()
    for date_format in _DATE_FORMATS:
        try:
            return datetime.strptime(stripped, date_format)
        except ValueError:
            pass
    raise ValueError(f"unsupported NOAA local timestamp: {value!r}")


def _fixed_offset(timezone_label: str) -> timezone:
    label = timezone_label.strip().upper()
    if label in {"UTC", "GMT", "Z"}:
        return timezone.utc
    match = _OFFSET_PATTERN.search(label)
    if not match:
        raise ValueError(f"NOAA timezone has no numeric offset: {timezone_label!r}")
    offset_text = match.group("offset")
    sign = -1 if offset_text.startswith("-") else 1
    magnitude = offset_text[1:]
    if ":" in magnitude:
        hours_text, minutes_text = magnitude.split(":", 1)
    else:
        hours_text, minutes_text = magnitude, "0"
    hours = int(hours_text)
    minutes = int(minutes_text)
    if hours > 14 or minutes >= 60:
        raise ValueError(f"invalid NOAA timezone offset: {timezone_label!r}")
    return timezone(sign * timedelta(hours=hours, minutes=minutes))


def _utc_timestamp(local_value: str, timezone_label: str) -> datetime:
    local_time = _parse_local_datetime(local_value)
    return local_time.replace(tzinfo=_fixed_offset(timezone_label)).astimezone(timezone.utc)


def _coordinate(value: str | None, minimum: float, maximum: float) -> float | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    if not math.isfinite(parsed) or not minimum <= parsed <= maximum:
        return None
    return parsed


def normalize_noaa_row(row: dict[str, str], source_year: int | None = None) -> dict[str, object]:
    """Return an allowlisted event record; never include narratives or final magnitude."""
    missing = _REQUIRED_COLUMNS.difference(row)
    if missing:
        raise ValueError(f"NOAA detail schema missing columns: {', '.join(sorted(missing))}")
    event_id = (row.get("EVENT_ID") or "").strip()
    event_type = (row.get("EVENT_TYPE") or "").strip()
    begin_value = (row.get("BEGIN_DATE_TIME") or "").strip()
    timezone_label = (row.get("CZ_TIMEZONE") or "").strip()
    if not event_id:
        raise ValueError("NOAA event row has no EVENT_ID")
    if not begin_value:
        raise ValueError("NOAA event row has no BEGIN_DATE_TIME")
    if not timezone_label:
        raise ValueError("NOAA event row has no CZ_TIMEZONE")

    start = _utc_timestamp(begin_value, timezone_label)
    end_value = (row.get("END_DATE_TIME") or "").strip()
    end = _utc_timestamp(end_value, timezone_label) if end_value else None
    if end and end <= start:
        raise ValueError("NOAA recorded end must be later than its recorded start")

    latitude = _coordinate(row.get("BEGIN_LAT"), -90, 90)
    longitude = _coordinate(row.get("BEGIN_LON"), -180, 180)
    if latitude == 0 and longitude == 0:
        latitude = longitude = None
    if latitude is None or longitude is None:
        geometry_quality = "zone_only"
    else:
        geometry_quality = "point_reported_not_site_verified"

    duration_hours = (end - start).total_seconds() / 3600 if end else None
    episode_id = (row.get("EPISODE_ID") or "").strip() or event_id
    state = (row.get("STATE") or "").strip()
    county_zone = (row.get("CZ_NAME") or "").strip()
    county_zone_type = (row.get("CZ_TYPE") or "").strip()
    region = ", ".join(value for value in (county_zone, state) if value) or None
    return {
        "event_id": event_id,
        "episode_id": episode_id,
        "event_type": event_type,
        "start_utc": start.isoformat().replace("+00:00", "Z"),
        "end_utc": end.isoformat().replace("+00:00", "Z") if end else None,
        "duration_hours": duration_hours,
        "right_censored": end is None,
        "state": state or None,
        "region": region,
        "county_zone_type": county_zone_type or None,
        "geometry_quality": geometry_quality,
        "label_quality": "recorded_event_interval" if end else "unknown_recorded_end",
        "duration_quality": "fixed_offset_local_source_time" if end else "right_censored_unknown_end",
        "source": "NOAA_NCEI_StormEvents",
        "source_year": source_year or start.year,
        "source_timezone": timezone_label,
        "begin_lat": latitude,
        "begin_lon": longitude,
    }


def read_noaa_detail_files(paths: Iterable[Path], event_type: str = SUPPORTED_EVENT_TYPE
                           ) -> tuple[list[dict[str, object]], dict[str, int]]:
    """Read supported event rows and return explicit quality/exclusion counts."""
    normalized: list[dict[str, object]] = []
    counts = {"rows_total": 0, "unsupported_type": 0, "malformed": 0, "duplicates": 0,
              "complete_end": 0, "right_censored": 0}
    seen_ids: set[str] = set()
    for path in paths:
        year_match = re.search(r"_d(\d{4})_", path.name)
        source_year = int(year_match.group(1)) if year_match else None
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames is None:
                raise ValueError(f"NOAA detail file has no header: {path}")
            missing = _REQUIRED_COLUMNS.difference(reader.fieldnames)
            if missing:
                raise ValueError(f"NOAA detail schema changed in {path.name}; missing {sorted(missing)}")
            for row in reader:
                counts["rows_total"] += 1
                if (row.get("EVENT_TYPE") or "").strip().casefold() != event_type.casefold():
                    counts["unsupported_type"] += 1
                    continue
                event_id = (row.get("EVENT_ID") or "").strip()
                if event_id in seen_ids:
                    counts["duplicates"] += 1
                    continue
                seen_ids.add(event_id)
                try:
                    event = normalize_noaa_row(row, source_year)
                except ValueError:
                    counts["malformed"] += 1
                    continue
                normalized.append(event)
                counts["right_censored" if event["right_censored"] else "complete_end"] += 1
    return normalized, counts


def _iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def event_duration_hours(event: dict[str, object]) -> float | None:
    """Compute duration from normalized labels; missing end remains censored."""
    start_value = event.get("start_utc")
    end_value = event.get("end_utc")
    if not start_value or not end_value:
        return None
    start = _iso_datetime(str(start_value))
    end = _iso_datetime(str(end_value))
    if end <= start:
        return None
    return (end - start).total_seconds() / 3600
