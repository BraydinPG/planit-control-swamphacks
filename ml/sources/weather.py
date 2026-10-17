"""Bounded Open-Meteo historical reanalysis adapter for offline retrospective context."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ml.config import RAW_DATA_DIR
from ml.schemas import parse_utc

ARCHIVE_API_URL = "https://archive-api.open-meteo.com/v1/archive"
HOURLY_VARIABLES = (
    "temperature_2m", "relative_humidity_2m", "precipitation", "wind_speed_10m", "wind_gusts_10m"
)
MAX_RESPONSE_BYTES = 10 * 1024 * 1024
MAX_REQUEST_DAYS = 92


def build_archive_url(latitude: float, longitude: float, start_date: str, end_date: str) -> str:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if start > end:
        raise ValueError("start_date must be on or before end_date")
    if (end - start).days >= MAX_REQUEST_DAYS:
        raise ValueError(f"weather requests are limited to {MAX_REQUEST_DAYS} calendar days")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("latitude/longitude are outside valid bounds")
    params = {
        "latitude": f"{latitude:.5f}",
        "longitude": f"{longitude:.5f}",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "hourly": ",".join(HOURLY_VARIABLES),
        "timezone": "UTC",
    }
    return f"{ARCHIVE_API_URL}?{urlencode(params)}"


def _retrieve(url: str, *, timeout: float = 20.0, retries: int = 3) -> bytes:
    request = Request(url, headers={"User-Agent": "PlanIT-Control-ML/0.1 historical-weather-context"})
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=timeout) as response:
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > MAX_RESPONSE_BYTES:
                    raise ValueError("Open-Meteo response exceeds the 10 MiB limit")
                data = response.read(MAX_RESPONSE_BYTES + 1)
                if len(data) > MAX_RESPONSE_BYTES:
                    raise ValueError("Open-Meteo response exceeds the 10 MiB limit")
                return data
        except ValueError:
            raise
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            last_error = error
            if attempt + 1 < retries:
                time.sleep(0.5 * (2 ** attempt))
    raise RuntimeError(f"Open-Meteo request failed after {retries} attempts: {last_error}") from last_error


def filter_hourly_as_of(payload: dict[str, Any], as_of_utc: str) -> list[dict[str, Any]]:
    """Normalize hourly data and exclude every observation after the decision time."""
    cutoff = parse_utc(as_of_utc, "as_of_utc")
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict) or not isinstance(hourly.get("time"), list):
        raise ValueError("Open-Meteo response is missing hourly.time")
    times = hourly["time"]
    result: list[dict[str, Any]] = []
    for index, timestamp in enumerate(times):
        raw_timestamp = str(timestamp)
        try:
            parsed_time = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError(f"invalid Open-Meteo hourly timestamp: {raw_timestamp!r}") from error
        if parsed_time.tzinfo is None:
            parsed_time = parsed_time.replace(tzinfo=timezone.utc)
        valid_time = parsed_time.astimezone(timezone.utc)
        if valid_time > cutoff:
            continue
        values: dict[str, float | None] = {}
        for variable in HOURLY_VARIABLES:
            series = hourly.get(variable)
            value = series[index] if isinstance(series, list) and index < len(series) else None
            values[variable] = float(value) if value is not None else None
        result.append({
            "valid_time_utc": valid_time.isoformat().replace("+00:00", "Z"),
            "values": values,
            "source": "Open-Meteo Historical Weather API",
            "data_state": "retrospective_reanalysis",
        })
    return result


def fetch_historical_weather(latitude: float, longitude: float, start_date: str, end_date: str,
                            as_of_utc: str, *, cache_dir: Path = RAW_DATA_DIR / "weather",
                            timeout: float = 20.0, retries: int = 3) -> dict[str, Any]:
    url = build_archive_url(latitude, longitude, start_date, end_date)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    cache_path = cache_dir / f"open_meteo_{cache_key}.json"
    cache_hit = cache_path.exists()
    if cache_hit:
        body = cache_path.read_bytes()
    else:
        body = _retrieve(url, timeout=timeout, retries=retries)
        cache_path.write_bytes(body)
    payload = json.loads(body)
    hourly = filter_hourly_as_of(payload, as_of_utc)
    return {
        "source": "Open-Meteo Historical Weather API",
        "source_url": url,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "spatial_match_quality": "caller_supplied_location_not_verified_site_measurement",
        "data_state": "retrospective_reanalysis",
        "operational_forecast_skill": False,
        "hourly": hourly,
        "cached_response": cache_hit,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latitude", type=float, required=True)
    parser.add_argument("--longitude", type=float, required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--as-of-utc", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = fetch_historical_weather(args.latitude, args.longitude, args.start, args.end, args.as_of_utc)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"records": len(result["hourly"]), "data_state": result["data_state"],
                      "source": result["source"]}, indent=2))


if __name__ == "__main__":
    main()
