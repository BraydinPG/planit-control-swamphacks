"""Official feed normalizers for Cache's independent harness, not Braydin's ingestion service."""

from datetime import datetime, timedelta, timezone
import hashlib
import re
from urllib.parse import urlparse

from ml.schemas import parse_utc
from ml.worker.schema import Evidence


def _base(
    receipt: dict,
    *,
    publisher: str,
    record_id: str,
    hazard: str,
    method: str,
    variable: str,
    value,
    unit: str,
    valid_from: str,
    valid_to: str,
    footprint: dict,
    observed_at=None,
    issued_at=None,
    original_type=None,
    **extra,
) -> Evidence:
    # Retrieval proves availability no earlier than actual ingestion, never backdates a source.
    acquired = receipt["retrieved_at_utc"]
    identity = f"{receipt['sha256']}:{record_id}:{variable}"
    parsed = urlparse(receipt["url"])
    origin = parsed._replace(query="", fragment="").geturl()
    return Evidence(
        evidence_id=hashlib.sha256(identity.encode()).hexdigest()[:24],
        publisher=publisher,
        origin_url=origin,
        source_record_id=record_id,
        original_type=original_type or variable,
        hazard=hazard,
        method=method,
        variable=variable,
        value=value,
        unit=unit,
        observed_at=observed_at,
        issued_at=issued_at,
        available_at=acquired,
        ingested_at=acquired,
        valid_from=valid_from,
        valid_to=valid_to,
        source_version=receipt["sha256"],
        availability_basis="retrieved_by_pipeline",
        footprint=footprint,
        **extra,
    )


def _nws_unit(unit: str) -> str:
    return {
        "wmoUnit:degC": "C",
        "wmoUnit:degF": "F",
        "wmoUnit:percent": "%",
        "wmoUnit:km_h-1": "km/h",
        "wmoUnit:m_s-1": "m/s",
        "wmoUnit:mm": "mm",
        "wmoUnit:m": "m",
    }.get(unit, unit)


def nws_observation(payload: dict, receipt: dict) -> list[Evidence]:
    properties = payload["properties"]
    lon, lat = payload["geometry"]["coordinates"][:2]
    footprint = {
        "kind": "point",
        "point": {"lat": lat, "lon": lon},
        "precision": "NWS weather station; not an on-site sensor",
    }
    timestamp = properties["timestamp"]
    result = []
    for key, variable, hazard in (
        ("temperature", "temperature", "heat"),
        ("relativeHumidity", "relative_humidity", "heat"),
        ("heatIndex", "heat_index", "heat"),
        ("windSpeed", "wind_speed", "wind"),
        ("windGust", "wind_gust", "wind"),
        ("precipitationLastHour", "rainfall", "rain"),
        ("visibility", "visibility", "visibility"),
    ):
        reading = properties.get(key) or {}
        if reading.get("value") is None:
            continue
        control = reading.get("qualityControl")
        flags = [] if control in (None, "V", "S") else ["NWS_QC:" + str(control)]
        start = (
            parse_utc(timestamp, "timestamp") - timedelta(hours=1)
            if key == "precipitationLastHour"
            else parse_utc(timestamp, "timestamp")
        )
        result.append(
            _base(
                receipt,
                publisher="NOAA NWS",
                record_id=payload.get("id", properties.get("station", "station")) + ":" + timestamp,
                hazard=hazard,
                method="observed",
                variable=variable,
                value=reading["value"],
                unit=_nws_unit(reading["unitCode"]),
                valid_from=start.isoformat(),
                valid_to=timestamp,
                observed_at=timestamp,
                footprint=footprint,
                quality_flags=flags,
            )
        )
    return result


def nws_hourly(payload: dict, receipt: dict) -> list[Evidence]:
    properties = payload["properties"]
    issued = max(
        (properties[k] for k in ("generatedAt", "updateTime") if properties.get(k)),
        key=lambda t: parse_utc(t, "issue"),
    )
    geometry = payload.get("geometry") or {}
    footprint = (
        {
            "kind": "polygon",
            "rings": geometry["coordinates"],
            "precision": "NWS hourly forecast grid footprint",
        }
        if geometry.get("type") == "Polygon"
        else {"kind": "unknown", "precision": "missing forecast polygon"}
    )
    result = []
    for period in properties["periods"][:25]:
        source_id = "hourly:" + period["startTime"]
        common = dict(
            receipt=receipt,
            publisher="NOAA NWS",
            record_id=source_id,
            method="issued_forecast",
            valid_from=period["startTime"],
            valid_to=period["endTime"],
            issued_at=issued,
            footprint=footprint,
        )
        result.append(
            _base(
                **common,
                hazard="heat",
                variable="temperature",
                value=period["temperature"],
                unit=period["temperatureUnit"],
            )
        )
        for key, variable, hazard in (
            ("relativeHumidity", "relative_humidity", "heat"),
            ("probabilityOfPrecipitation", "rain_probability", "rain"),
        ):
            reading = period.get(key) or {}
            if reading.get("value") is not None:
                result.append(
                    _base(
                        **common,
                        hazard=hazard,
                        variable=variable,
                        value=reading["value"],
                        unit=_nws_unit(reading["unitCode"]),
                    )
                )
        wind = period.get("windSpeed")
        if isinstance(wind, str):
            match = re.fullmatch(r"(\d+(?:\.\d+)?)(?: to (\d+(?:\.\d+)?))? (mph|km/h|kn|m/s)", wind)
            if match:
                for variable, value in (
                    ("wind_speed_min", float(match[1])),
                    ("wind_speed_max", float(match[2] or match[1])),
                ):
                    result.append(
                        _base(
                            **common,
                            hazard="wind",
                            variable=variable,
                            value=value,
                            unit=match[3],
                            original_type="NWS_hourly_wind_range",
                        )
                    )
    return result


def nws_alerts(payload: dict, receipt: dict) -> list[Evidence]:
    result = []
    for feature in payload.get("features", [])[:20]:
        p, geometry = feature["properties"], feature.get("geometry") or {}
        # Cancellation/expired messages cannot be treated as an active authoritative warning.
        if p.get("messageType") == "Cancel" or p.get("status") not in ("Actual", None):
            continue
        footprint = (
            {
                "kind": "polygon",
                "rings": geometry["coordinates"],
                "precision": "NWS alert coverage polygon",
            }
            if geometry.get("type") == "Polygon"
            else {"kind": "regional", "precision": "alert zones only; no site geometry"}
        )
        name = p.get("event", "Unknown warning")
        hazard = (
            "flood_context"
            if "Flood" in name
            else "wind"
            if any(w in name for w in ("Wind", "Tropical", "Hurricane"))
            else "heat"
            if "Heat" in name
            else "winter"
            if any(w in name for w in ("Snow", "Winter", "Ice"))
            else "visibility"
        )
        result.append(
            _base(
                receipt,
                publisher="NOAA NWS",
                record_id=feature.get("id", p.get("id", "alert")),
                hazard=hazard,
                method="official_warning",
                variable="warning",
                value=name,
                unit="text",
                issued_at=p["sent"],
                valid_from=p.get("onset") or p["effective"],
                valid_to=p.get("ends") or p["expires"],
                footprint=footprint,
            )
        )
    return result


def coops(
    payload: dict, receipt: dict, *, product: str, datum: str | None = None
) -> list[Evidence]:
    if "error" in payload:
        raise ValueError("CO-OPS unavailable")
    metadata = payload["metadata"]
    footprint = {
        "kind": "point",
        "point": {"lat": float(metadata["lat"]), "lon": float(metadata["lon"])},
        "precision": "CO-OPS station",
    }
    variables = {
        "water_level": (("v", "coastal_water_level", "coastal_water", "m"),),
        "wind": (("s", "wind_speed", "wind", "m/s"), ("g", "wind_gust", "wind", "m/s")),
        "air_temperature": (("v", "temperature", "heat", "C"),),
        "humidity": (("v", "relative_humidity", "heat", "%"),),
    }
    result = []
    for row in payload.get("data", [])[-3:]:
        timestamp = row["t"].replace(" ", "T") + ":00Z"
        for field, variable, hazard, unit in variables[product]:
            if row.get(field) in (None, ""):
                continue
            flags = (
                []
                if all(f.strip() in ("0", "") for f in row.get("f", "").split(","))
                else ["COOPS_quality_flag"]
            )
            result.append(
                _base(
                    receipt,
                    publisher="NOAA CO-OPS",
                    record_id=metadata["id"] + ":" + row["t"],
                    hazard=hazard,
                    method="observed",
                    variable=variable,
                    value=float(row[field]),
                    unit=unit,
                    observed_at=timestamp,
                    valid_from=timestamp,
                    valid_to=timestamp,
                    footprint=footprint,
                    datum=datum,
                    quality_flags=flags,
                )
            )
    return result


def earthquake_catalog(payload: dict, receipt: dict) -> list[Evidence]:
    result = []
    for row in payload.get("features", []):
        p = row["properties"]
        if p.get("mag") is None:
            continue
        occurred = datetime.fromtimestamp(p["time"] / 1000, timezone.utc).isoformat()
        updated = datetime.fromtimestamp(p["updated"] / 1000, timezone.utc).isoformat()
        lon, lat = row["geometry"]["coordinates"][:2]
        result.append(
            _base(
                receipt,
                publisher="USGS",
                record_id=row["id"],
                hazard="earthquake",
                method="observed",
                variable="earthquake_magnitude",
                value=p["mag"],
                unit="magnitude",
                observed_at=occurred,
                issued_at=updated,
                valid_from=occurred,
                valid_to=occurred,
                footprint={
                    "kind": "point",
                    "point": {"lat": lat, "lon": lon},
                    "precision": "USGS hypocentral epicenter, not a shaking footprint",
                },
                original_type=p.get("magType") or "magnitude",
            )
        )
    return result


def swpc_kp(payload: list, receipt: dict) -> list[Evidence]:
    # NOAA changed from header/row arrays to objects in 2026; support both explicitly.
    rows = (
        [dict(zip(payload[0], row)) for row in payload[1:]]
        if payload and isinstance(payload[0], list)
        else payload
    )
    result = []
    for row in rows[-3:]:
        timestamp = str(row["time_tag"]).replace(" ", "T")
        if not timestamp.endswith("Z") and "+" not in timestamp:
            timestamp += "Z"
        result.append(
            _base(
                receipt,
                publisher="NOAA SWPC",
                record_id=timestamp,
                hazard="space_weather",
                method="observed",
                variable="geomagnetic_kp",
                value=float(row.get("Kp", row.get("kp"))),
                unit="Kp",
                observed_at=timestamp,
                valid_from=timestamp,
                valid_to=timestamp,
                footprint={"kind": "global", "precision": "Planetary three-hour index"},
            )
        )
    return result


def airnow_reporting_area(rows: list[dict], receipt: dict) -> list[Evidence]:
    """Public reporting-area response schema; never treated as an on-site AQ sensor."""
    offsets = {
        "EST": -5,
        "EDT": -4,
        "CST": -6,
        "CDT": -5,
        "MST": -7,
        "MDT": -6,
        "PST": -8,
        "PDT": -7,
    }
    result = []
    for row in rows:
        if row["LocalTimeZone"] not in offsets:
            raise ValueError("AirNow local timezone is ambiguous")
        local = datetime.strptime(row["DateObserved"], "%Y-%m-%d").replace(
            hour=int(row["HourObserved"]),
            tzinfo=timezone(timedelta(hours=offsets[row["LocalTimeZone"]])),
        )
        timestamp = local.astimezone(timezone.utc).isoformat()
        result.append(
            _base(
                receipt,
                publisher="EPA AirNow",
                record_id=row["ReportingArea"] + ":" + row["ParameterName"] + ":" + timestamp,
                hazard="air_quality",
                method="observed",
                variable="air_quality_index",
                value=float(row["AQI"]),
                unit="AQI",
                observed_at=timestamp,
                valid_from=timestamp,
                valid_to=timestamp,
                footprint={
                    "kind": "regional",
                    "precision": "AirNow reporting area; not a worksite measurement",
                },
            )
        )
    return result


def ndbc_observations(
    text: str, receipt: dict, *, lat: float, lon: float, station_id: str
) -> list[Evidence]:
    lines = text.splitlines()
    if len(lines) < 3 or not lines[0].startswith("#YY"):
        raise ValueError("NDBC station table header missing")
    header = lines[0].lstrip("#").split()
    result = []
    for line in lines[2:5]:
        row = dict(zip(header, line.split(), strict=True))
        timestamp = datetime(
            int(row["YY"]),
            int(row["MM"]),
            int(row["DD"]),
            int(row["hh"]),
            int(row["mm"]),
            tzinfo=timezone.utc,
        ).isoformat()
        for field, variable, hazard, unit in (
            ("WSPD", "wind_speed", "wind", "m/s"),
            ("GST", "wind_gust", "wind", "m/s"),
            ("WVHT", "wave_height", "waves", "m"),
            ("VIS", "visibility", "visibility", "nmi"),
        ):
            if row.get(field) in (None, "MM"):
                continue
            value = float(row[field])
            if unit == "nmi":
                value *= 1852
                unit = "m"
            result.append(
                _base(
                    receipt,
                    publisher="NOAA NDBC",
                    record_id=station_id + ":" + timestamp,
                    hazard=hazard,
                    method="observed",
                    variable=variable,
                    value=value,
                    unit=unit,
                    observed_at=timestamp,
                    valid_from=timestamp,
                    valid_to=timestamp,
                    footprint={
                        "kind": "point",
                        "point": {"lat": lat, "lon": lon},
                        "precision": "Marine buoy; no onshore exposure footprint inferred",
                    },
                )
            )
    return result
