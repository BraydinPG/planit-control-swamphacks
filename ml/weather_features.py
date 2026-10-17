"""Deterministic episode sampling and strictly as-of weather feature extraction."""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable

WEATHER_FEATURE_NAMES = (
    "rain_6h_mm",
    "rain_24h_mm",
    "temperature_last_c",
    "temperature_mean_6h_c",
    "humidity_mean_6h_pct",
    "wind_mean_6h_m_s",
    "gust_max_6h_m_s",
    "rain_6h_change_mm",
    "wind_6h_change_m_s",
)


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def deterministic_episode_sample(events: Iterable[dict[str, Any]], *, per_year: int = 100,
                                 seed: int = 42) -> list[dict[str, Any]]:
    """Select at most one coordinate-bearing event per NOAA episode/year deterministically."""
    if per_year < 1:
        raise ValueError("per_year must be positive")
    episodes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        episode_id = str(event.get("episode_id") or event.get("event_id") or "")
        if episode_id:
            episodes[episode_id].append(event)

    representatives: list[tuple[str, dict[str, Any]]] = []
    for episode_id, rows in episodes.items():
        candidates = [row for row in rows if row.get("begin_lat") is not None and row.get("begin_lon") is not None]
        if not candidates:
            continue
        representative = dict(min(candidates, key=lambda row: (str(row.get("start_utc", "")), str(row.get("event_id", "")))))
        # Preserve full episode boundaries even when its earliest event has no
        # reported coordinates and cannot be the weather sample representative.
        representative["episode_start_utc"] = min(str(row["start_utc"]) for row in rows)
        representative["episode_end_utc"] = max(str(row.get("end_utc") or row["start_utc"]) for row in rows)
        representatives.append((episode_id, representative))

    by_year: dict[int, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for episode_id, event in representatives:
        by_year[int(event["source_year"])].append((episode_id, event))

    selected: list[dict[str, Any]] = []
    for year, rows in sorted(by_year.items()):
        ranked = sorted(rows, key=lambda item: hashlib.sha256(f"{seed}:{year}:{item[0]}".encode()).hexdigest())
        selected.extend(event for _, event in ranked[:per_year])
    return sorted(selected, key=lambda event: (int(event["source_year"]), str(event["episode_id"]), str(event["event_id"])))


def _finite_values(rows: list[dict[str, Any]], variable: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = row.get("values", {}).get(variable)
        if value is None:
            continue
        numeric = float(value)
        if math.isfinite(numeric):
            values.append(numeric)
    return values


def extract_weather_features(hourly: Iterable[dict[str, Any]], as_of_utc: str) -> dict[str, Any]:
    """Aggregate only hourly records whose valid_time is at or before the cutoff."""
    cutoff = _parse_utc(as_of_utc)
    eligible: list[tuple[datetime, dict[str, Any]]] = []
    for row in hourly:
        valid_time = _parse_utc(str(row["valid_time_utc"]))
        if valid_time <= cutoff:
            eligible.append((valid_time, row))
    eligible.sort(key=lambda item: item[0])

    def rows_in_window(start_hours_ago: int, end_hours_ago: int = 0) -> list[dict[str, Any]]:
        lower = cutoff.timestamp() - start_hours_ago * 3600
        upper = cutoff.timestamp() - end_hours_ago * 3600
        return [row for timestamp, row in eligible if lower < timestamp.timestamp() <= upper]

    recent_6h = rows_in_window(6)
    previous_6h = rows_in_window(12, 6)
    previous_24h = rows_in_window(24)
    recent_rain = _finite_values(recent_6h, "precipitation")
    previous_rain = _finite_values(previous_6h, "precipitation")
    rain_24h = _finite_values(previous_24h, "precipitation")
    temperatures = _finite_values(recent_6h, "temperature_2m")
    humidity = _finite_values(recent_6h, "relative_humidity_2m")
    winds = _finite_values(recent_6h, "wind_speed_10m")
    gusts = _finite_values(recent_6h, "wind_gusts_10m")
    previous_winds = _finite_values(previous_6h, "wind_speed_10m")

    def mean_or_none(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    last_temperature: float | None = None
    if eligible:
        last_values = eligible[-1][1].get("values", {})
        raw = last_values.get("temperature_2m")
        if raw is not None and math.isfinite(float(raw)):
            last_temperature = float(raw)

    recent_rain_total = sum(recent_rain) if len(recent_rain) >= 4 else None
    previous_rain_total = sum(previous_rain) if len(previous_rain) >= 4 else None
    rain_24h_total = sum(rain_24h) if len(rain_24h) >= 16 else None
    recent_wind_mean = mean_or_none(winds) if len(winds) >= 4 else None
    previous_wind_mean = mean_or_none(previous_winds) if len(previous_winds) >= 4 else None

    features: dict[str, Any] = {
        "rain_6h_mm": recent_rain_total,
        "rain_24h_mm": rain_24h_total,
        "temperature_last_c": last_temperature,
        "temperature_mean_6h_c": mean_or_none(temperatures) if len(temperatures) >= 4 else None,
        "humidity_mean_6h_pct": mean_or_none(humidity) if len(humidity) >= 4 else None,
        "wind_mean_6h_m_s": recent_wind_mean,
        "gust_max_6h_m_s": max(gusts) if len(gusts) >= 4 else None,
        "rain_6h_change_mm": (recent_rain_total - previous_rain_total)
        if recent_rain_total is not None and previous_rain_total is not None else None,
        "wind_6h_change_m_s": (recent_wind_mean - previous_wind_mean)
        if recent_wind_mean is not None and previous_wind_mean is not None else None,
    }
    return {
        "as_of_utc": cutoff.isoformat().replace("+00:00", "Z"),
        "features": features,
        "feature_source": "Open-Meteo ERA5 retrospective reanalysis",
        "feature_interpretation": "retrospective_as_of_reanalysis_not_archived_operational_forecast",
        "latest_valid_time_utc": eligible[-1][0].isoformat().replace("+00:00", "Z") if eligible else None,
        "valid_observation_count": len(eligible),
        "missing_features": [name for name, value in features.items() if value is None],
        "units": {
            "rain_6h_mm": "mm", "rain_24h_mm": "mm", "temperature_last_c": "degC",
            "temperature_mean_6h_c": "degC", "humidity_mean_6h_pct": "%",
            "wind_mean_6h_m_s": "m/s", "gust_max_6h_m_s": "m/s",
            "rain_6h_change_mm": "mm", "wind_6h_change_m_s": "m/s",
        },
    }
