"""Observed ISD-Lite records and explicit prototype heat-index episodes."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
import gzip
import json
import math
from pathlib import Path

from ml.config import PROCESSED_DATA_DIR, RAW_DATA_DIR, REPORT_DIR
from ml.sources.archive_cache import fetch_cached

STATION_IDS = ("722020-12839", "722430-12960", "722780-23183")
HEAT_EVENT_TYPE = "Heat Index Exceedance"
HEAT_DEFINITION = "observed_station_hourly_heat_index_at_or_above_90f"
HEAT_THRESHOLD_F = 90.0  # Research definition; not an employer or regulatory rule.


def relative_humidity(temperature_c: float, dewpoint_c: float) -> float:
    """NWS vapor-pressure ratio, with no fabricated saturation or missing fill."""
    if not all(math.isfinite(v) for v in (temperature_c, dewpoint_c)) or not -90 <= dewpoint_c <= temperature_c <= 60:
        raise ValueError("invalid temperature/dewpoint pair")
    return 100 * 10 ** (7.5 * dewpoint_c / (237.3 + dewpoint_c) - 7.5 * temperature_c / (237.3 + temperature_c))


def heat_index_f(temperature_f: float, humidity: float) -> float:
    """NWS simple estimate/Rothfusz regression, including published adjustments."""
    if not math.isfinite(temperature_f) or not math.isfinite(humidity) or not 0 <= humidity <= 100:
        raise ValueError("temperature/humidity must be finite and physically bounded")
    t, rh = temperature_f, humidity
    simple = (0.5 * (t + 61 + (t - 68) * 1.2 + rh * .094) + t) / 2
    if simple < 80:
        return simple
    value = (-42.379 + 2.04901523*t + 10.14333127*rh - .22475541*t*rh
             - .00683783*t*t - .05481717*rh*rh + .00122874*t*t*rh
             + .00085282*t*rh*rh - .00000199*t*t*rh*rh)
    if rh < 13 and 80 <= t <= 112:
        value -= (13-rh)/4 * math.sqrt((17-abs(t-95))/17)
    elif rh > 85 and 80 <= t <= 87:
        value += (rh-85)/10 * (87-t)/5
    return value


def parse_station(path: Path, station_id: str) -> tuple[list[dict], dict]:
    rows, counts = [], Counter()
    with gzip.open(path, "rt", encoding="ascii") as stream:
        for line in stream:
            counts["source_rows"] += 1
            try:
                values = [int(item) for item in line.split()]
                if len(values) != 12:
                    raise ValueError("ISD-Lite requires 12 fields")
                year, month, day, hour = values[:4]
                timestamp = datetime(year, month, day, hour, tzinfo=timezone.utc)
                temperature = values[4] / 10 if values[4] != -9999 else None
                dewpoint = values[5] / 10 if values[5] != -9999 else None
                wind = values[8] / 10 if values[8] != -9999 else None
                humidity, heat_index = None, None
                if temperature is not None and dewpoint is not None:
                    try:
                        humidity = relative_humidity(temperature, dewpoint)
                        heat_index = heat_index_f(temperature * 1.8 + 32, humidity)
                    except ValueError:
                        counts["invalid_thermodynamic_pair"] += 1
                if heat_index is None:
                    counts["missing_heat_measurement"] += 1
                rows.append({"station_id": station_id, "valid_time_utc": timestamp.isoformat().replace("+00:00", "Z"),
                             "temperature_c": temperature, "dewpoint_c": dewpoint, "relative_humidity_pct": humidity,
                             "heat_index_f": heat_index, "wind_speed_m_s": wind})
            except (ValueError, IndexError):
                counts["invalid_rows"] += 1
    return rows, dict(counts)


def threshold_episodes(rows: list[dict], metadata: dict, threshold_f: float = HEAT_THRESHOLD_F) -> tuple[list[dict], dict]:
    """Unknown starts/ends and measurement gaps never become resolved labels."""
    rows = sorted(rows, key=lambda row: row["valid_time_utc"])
    events, counts = [], Counter()
    active, known_start, previous, previous_low = None, False, None, False

    def finish(end: datetime | None) -> None:
        nonlocal active
        if active is None:
            return
        if not known_start:
            counts["left_censored_episodes_excluded"] += 1
        elif end is None:
            counts["right_censored_episodes_excluded"] += 1
        else:
            start = datetime.fromisoformat(active["valid_time_utc"].replace("Z", "+00:00"))
            year, week, _ = start.isocalendar()
            station_id = active["station_id"]
            events.append({"event_id": f"heat:{station_id}:{active['valid_time_utc']}",
                           "episode_id": f"heat:{station_id}:week:{year}-{week}",
                           "event_type": HEAT_EVENT_TYPE, "original_event_type": "observed_heat_index_threshold",
                           "start_utc": active["valid_time_utc"], "end_utc": end.isoformat().replace("+00:00", "Z"),
                           "source_year": start.year, "station_id": station_id,
                           "duration_hours": (end-start).total_seconds()/3600,
                           "begin_lat": metadata["lat"], "begin_lon": metadata["lon"],
                           "region": metadata["name"], "geometry_quality": "station_measurement_not_worksite",
                           "label_quality": "hourly_observed_threshold_interval;_crossing_time_quantized_to_1h",
                           "source": "NOAA_ISD_Lite_observations", "threshold_f": threshold_f})
            counts["complete_threshold_episodes"] += 1
        active = None

    seen = set()
    for row in rows:
        now = datetime.fromisoformat(row["valid_time_utc"].replace("Z", "+00:00"))
        if now in seen:
            counts["duplicate_hours_excluded"] += 1
            continue
        seen.add(now)
        value = row["heat_index_f"]
        if previous is not None and now-previous != timedelta(hours=1):
            finish(None)
            previous_low = False
            counts["observation_gaps"] += 1
        if value is None:
            finish(None)
            previous_low = False
        elif value >= threshold_f:
            if active is None:
                active, known_start = row, previous_low
            previous_low = False
        else:
            finish(now)
            previous_low = True
        previous = now
    finish(None)
    return events, dict(counts)


def acquire(years: tuple[int, ...] = (2021, 2022, 2023, 2024, 2025)) -> dict:
    cache = RAW_DATA_DIR / "stations"
    history, receipt = fetch_cached("https://www.ncei.noaa.gov/pub/data/noaa/isd-history.csv", cache,
                                    filename="isd-history.csv", max_bytes=8_000_000)
    metadata = {}
    with history.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            station_id = row["USAF"] + "-" + row["WBAN"]
            if station_id in STATION_IDS:
                metadata[station_id] = {"station_id": station_id, "name": row["STATION NAME"], "state": row["STATE"],
                                        "lat": float(row["LAT"]), "lon": float(row["LON"]),
                                        "archive_end_metadata": row["END"]}
    all_events, sources, summary = [], [receipt], {}
    for station_id in STATION_IDS:
        rows, counts = [], Counter()
        for year in years:
            name = f"{station_id}-{year}.gz"
            path, source = fetch_cached(f"https://www.ncei.noaa.gov/pub/data/noaa/isd-lite/{year}/{name}", cache, filename=name, max_bytes=2_000_000)
            part, quality = parse_station(path, station_id)
            rows.extend(part)
            counts.update(quality)
            sources.append(source)
        events, labels = threshold_episodes(rows, metadata[station_id])
        all_events.extend(events)
        summary[station_id] = {**metadata[station_id], **dict(counts), **labels,
                               "first_valid_time": rows[0]["valid_time_utc"], "last_valid_time": rows[-1]["valid_time_utc"],
                               "threshold_episode_count": len(events),
                               "evaluation_week_groups": len({event["episode_id"] for event in events})}
    report = {"source": "NOAA observed ISD-Lite, not ERA5 or issued forecasts", "sources": sources,
              "stations": summary, "threshold_f": HEAT_THRESHOLD_F, "event_definition": HEAT_DEFINITION,
              "event_records": len(all_events), "historical_asof_availability_verified": False,
              "limitations": ["Three airport stations in FL/TX/AZ, not a nationwide site-exposure model.",
                              "2025 legacy station archives end in August; no complete-year claim.",
                              "Hourly rounded archived observations; individual QC flags and original issue/acquisition times are unavailable in ISD-Lite.",
                              "Threshold 90F is a configurable research definition, not work/rest or employer policy.",
                              "Heat index is derived from observed temperature/dewpoint; it is not a directly measured WBGT.",
                              "Station/week clusters reduce repeated-cycle dependence but are not independent regional heatwaves."]}
    output = PROCESSED_DATA_DIR / "multidisaster/station_heat_events.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(all_events, allow_nan=False), encoding="utf-8")
    report_path = REPORT_DIR / "multidisaster/station_coverage.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(f"[stations] {len(all_events)} complete threshold episodes; coverage report written", flush=True)
    return report


if __name__ == "__main__":
    acquire()
