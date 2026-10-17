"""Read-only, bounded parsers for issued NHC FST and USGS OAF products.

No retrieval at inference. Receipts and source bodies come from trusted ingestion;
neither an arbitrary URL nor a client-supplied forecast is fetched here.
"""

import base64
import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from ml.event_outlooks.schema import (
    OfficialAftershockForecast,
    OfficialEventForecast,
    SourceRecord,
    StormPoint,
)


def instant(milliseconds: float) -> str:
    if type(milliseconds) not in (int, float):
        raise ValueError("Expected numeric agency timestamp")
    return (
        datetime.fromtimestamp(milliseconds / 1000, UTC)
        .isoformat()
        .replace("+00:00", "Z")
    )


def source_record(
    body: bytes, receipt: dict, provider: str, issued: str, record_id: str
) -> SourceRecord:
    hosts = {
        "NHC": {"www.nhc.noaa.gov", "ftp.nhc.noaa.gov"},
        "USGS": {"earthquake.usgs.gov"},
    }
    url = urlparse(receipt["url"])
    if (
        url.scheme != "https"
        or url.hostname not in hosts[provider]
        or url.username
        or url.password
        or url.port not in (None, 443)
        or url.query
        or url.fragment
    ):
        raise ValueError("Unapproved official product URL")
    if len(body) > 1_000_000 or len(body) != receipt["bytes"]:
        raise ValueError("Official product size mismatch / limit")
    checksum = hashlib.sha256(body).hexdigest()
    if checksum != receipt["sha256"]:
        raise ValueError("Official product checksum mismatch")
    return SourceRecord(
        id=record_id,
        provider=provider,
        url=receipt["url"],
        sha256=checksum,
        issued_at_utc=issued,
        retrieved_at_utc=receipt["retrieved_at_utc"],
        vintage="archive_capture",
    )


def _one(pattern: str, text: str):
    matches = list(re.finditer(pattern, text, re.MULTILINE))
    if len(matches) != 1:
        raise ValueError("Missing or ambiguous NHC field")
    return matches[0]


def _coordinate(value: str) -> float:
    return float(value[:-1]) * (-1 if value[-1] in "SW" else 1)


def _day_time(token: str, issued: datetime) -> datetime:
    day, hour, minute = int(token[:2]), int(token[3:5]), int(token[5:7])
    if hour > 23 or minute > 59:
        raise ValueError("Invalid advisory time")
    for offset in range(8):
        candidate = (issued + timedelta(days=offset)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        if candidate.day == day and candidate >= issued:
            return candidate
    raise ValueError("NHC forecast date outside supported seven-day window")


def parse_nhc(body: bytes, receipt: dict) -> OfficialEventForecast:
    """Parse technical text (not public advisory prose or HURDAT post-analysis)."""
    if len(body) > 100_000:
        raise ValueError("NHC text product exceeds limit")
    text = body.decode("ascii")
    header = _one(
        r"^(HURRICANE|TROPICAL STORM|TROPICAL DEPRESSION|POST-TROPICAL CYCLONE) ([A-Z0-9 -]+) FORECAST/ADVISORY NUMBER\s+(\d+[A-Z]?)\s*$",
        text,
    )
    cyclone = _one(r"^NWS NATIONAL HURRICANE CENTER[^\n]*\s([A-Z]{2}\d{6})\s*$", text)[
        1
    ]
    stamp = _one(r"^(\d{4}) UTC [A-Z]{3} ([A-Z]{3}) (\d{1,2}) (\d{4})\s*$", text)
    # Explicit English months, independent of the operator's Windows locale.
    months = {
        m: i + 1
        for i, m in enumerate(
            [
                "JAN",
                "FEB",
                "MAR",
                "APR",
                "MAY",
                "JUN",
                "JUL",
                "AUG",
                "SEP",
                "OCT",
                "NOV",
                "DEC",
            ]
        )
    }
    issued = datetime(
        int(stamp[4]),
        months[stamp[2]],
        int(stamp[3]),
        int(stamp[1][:2]),
        int(stamp[1][2:]),
        tzinfo=UTC,
    )
    if (
        cyclone[-4:] != str(issued.year)
        or cyclone.lower() not in receipt["url"].lower()
    ):
        raise ValueError("Cyclone identity / issue year / source URL mismatch")
    initial = _one(
        r"^(?:HURRICANE|TROPICAL STORM|TROPICAL DEPRESSION|POST-TROPICAL CYCLONE) CENTER LOCATED NEAR\s+([\d.]+[NS])\s+([\d.]+[EW]) AT (\d{2}/\d{4}Z)\s*$",
        text,
    )
    initial_time = _day_time(initial[3], issued)
    if initial_time != issued:
        raise ValueError("Initial position timestamp must match advisory issuance")
    wind = _one(r"^MAX SUSTAINED WINDS\s+(\d+) KT WITH GUSTS TO\s+(\d+) KT\.\s*$", text)
    current = StormPoint(
        valid_at_utc=issued.isoformat(),
        lat=_coordinate(initial[1]),
        lon=_coordinate(initial[2]),
        max_sustained_wind_kt=float(wind[1]),
        gust_kt=float(wind[2]),
        phase=header[1],
    )
    blocks = re.findall(
        r"^(?:FORECAST|OUTLOOK) VALID (\d{2}/\d{4}Z)\s+([\d.]+[NS])\s+([\d.]+[EW])([^\n]*)\nMAX WIND\s+(\d+) KT\.\.\.GUSTS\s+(\d+) KT\.",
        text,
        re.MULTILINE,
    )
    declared = re.findall(r"^(?:FORECAST|OUTLOOK) VALID ([^\n]+)", text, re.MULTILINE)
    if len(blocks) != sum("...DISSIPATED" not in line for line in declared):
        raise ValueError(
            "Unparsed NHC forecast point; refuse a silently truncated track"
        )
    points = [
        StormPoint(
            valid_at_utc=_day_time(day, issued).isoformat(),
            lat=_coordinate(lat),
            lon=_coordinate(lon),
            max_sustained_wind_kt=float(speed),
            gust_kt=float(gust),
            phase=phase.strip(". ") or None,
        )
        for day, lat, lon, phase, speed, gust in blocks
    ]
    times = [p.valid_at_utc for p in points]
    if times != sorted(set(times)) or any(t <= current.valid_at_utc for t in times):
        raise ValueError("Forecast points must follow issuance in increasing order")
    # A newer advisory supersedes this product; do not treat it as indefinitely fresh.
    next_token = _one(r"^NEXT ADVISORY AT (\d{2}/\d{4}Z)\s*$", text)[1]
    next_time = _day_time(next_token, issued)
    if not issued < next_time <= issued + timedelta(hours=6):
        raise ValueError("Unsupported next-advisory window")
    return OfficialEventForecast(
        cyclone_id=cyclone,
        storm_name=header[2],
        provider_version=f"NHC {cyclone} FST advisory {header[3]}",
        source=source_record(
            body, receipt, "NHC", issued.isoformat(), f"nhc-{cyclone}-{header[3]}"
        ),
        next_advisory_at_utc=next_time.isoformat(),
        initial_position=current,
        forecast_points=points,
    )


def parse_oaf(
    body: bytes, receipt: dict, detail_body: bytes, detail_receipt: dict
) -> OfficialAftershockForecast:
    """Link the published forecast to its ComCat mainshock and circular region."""
    if max(len(body), len(detail_body)) > 1_000_000:
        raise ValueError("USGS product exceeds limit")
    detail, forecast = json.loads(detail_body), json.loads(body)
    if detail["type"] != "Feature" or detail["geometry"]["type"] != "Point":
        raise ValueError("Expected ComCat point event")
    event_id = detail["id"]
    products = [
        p
        for p in detail["properties"]["products"].get("oaf", [])
        if p.get("status") != "DELETE"
        and p.get("code") == event_id
        and p.get("contents", {}).get("forecast.json", {}).get("url") == receipt["url"]
    ]
    if len(products) != 1:
        raise ValueError("Aftershock forecast is not uniquely linked to the mainshock")
    product = products[0]
    published = product["updateTime"]
    checksum = product["contents"]["forecast.json"]["sha256"]
    if base64.b64decode(checksum, validate=True) != hashlib.sha256(body).digest():
        raise ValueError("ComCat product checksum mismatch")
    if not forecast["creationTime"] <= published < forecast["expireTime"]:
        raise ValueError("Invalid forecast creation / publication / expiration order")
    parameters = forecast["model"]["parameters"]
    if parameters["regionType"] != "circle":
        raise ValueError("Only explicitly described circular OAF regions are supported")
    coords = detail["geometry"]["coordinates"]
    mainshock = {
        "event_id": event_id,
        "time_utc": instant(detail["properties"]["time"]),
        "magnitude": float(detail["properties"]["mag"]),
        "lon": coords[0],
        "lat": coords[1],
    }
    if (
        detail["properties"]["time"] > forecast["creationTime"]
        or abs(mainshock["magnitude"] - parameters["magMain"]) > 0.01
    ):
        raise ValueError("Mainshock and forecast disagree")
    windows = []
    for window in forecast["forecast"]:
        if (
            not forecast["creationTime"]
            <= window["timeStart"]
            < window["timeEnd"]
            <= forecast["expireTime"]
        ):
            raise ValueError("Aftershock window contradicts product validity")
        bins = []
        for item in window["bins"]:
            low, high = item.get("p95minimum"), item.get("p95maximum")
            if low is not None and high is not None and low > high:
                raise ValueError("Reversed expected-count interval")
            bins.append(
                {
                    "magnitude_at_least": float(item["magnitude"]),
                    "probability_at_least_one": item["probability"],
                    "count_p95_minimum": low,
                    "count_p95_maximum": high,
                }
            )
        windows.append(
            {
                "label": window["label"],
                "start_utc": instant(window["timeStart"]),
                "end_utc": instant(window["timeEnd"]),
                "bins": bins,
            }
        )
    return OfficialAftershockForecast(
        mainshock=mainshock,
        provider_version=forecast["model"]["name"],
        source=source_record(
            body,
            receipt,
            "USGS",
            instant(published),
            f"usgs-oaf-{event_id}-{published}",
        ),
        mainshock_source=source_record(
            detail_body,
            detail_receipt,
            "USGS",
            instant(detail["properties"]["updated"]),
            f"usgs-mainshock-{event_id}",
        ),
        expires_at_utc=instant(forecast["expireTime"]),
        region={
            "lat": float(parameters["regionCenterLat"]),
            "lon": float(parameters["regionCenterLon"]),
            "radius_km": float(parameters["regionRadius"]),
        },
        windows=windows,
    )
