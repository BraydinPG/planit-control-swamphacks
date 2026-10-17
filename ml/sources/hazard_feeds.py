"""Native CAP, modern water, ShakeMap and SWPC normalizers for offline evidence."""

import hashlib
import re
import xml.etree.ElementTree as ET

from ml.schemas import parse_utc
from ml.sources.worker_feeds import _base
from ml.worker.comprehensive_schema import OfficialAlert, ContextSignal
from ml.worker.geometry import geojson_polygons
from ml.worker.schema import SiteContext
from ml.worker.spatial import in_ring


def parse_alerts(
    payload: dict, receipt: dict, *, query_site: SiteContext | None = None
) -> tuple[list[OfficialAlert], list[str]]:
    features = payload.get("features")
    if payload.get("type") != "FeatureCollection" or not isinstance(features, list):
        raise ValueError("NWS response is not an alert collection")
    if len(features) > 600:
        raise ValueError("Alert collection exceeds bounded snapshot size")
    result, errors = [], []
    proof = {}
    if query_site is not None:
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(receipt["url"])
        coordinates = parse_qs(parsed.query).get("point", [""])[0].split(",")
        if (
            parsed.hostname != "api.weather.gov"
            or parsed.path != "/alerts/active"
            or len(coordinates) != 2
        ):
            raise ValueError("Point-match provenance missing from source receipt")
        lat, lon = map(float, coordinates)
        if abs(lat - query_site.lat) > 0.0001 or abs(lon - query_site.lon) > 0.0001:
            raise ValueError("Point query targets a different site")
        proof = {
            "query_site_id": query_site.id,
            "query_point": {"lat": lat, "lon": lon},
            "query_url": receipt["url"],
        }
    for index, feature in enumerate(features):
        try:
            p = feature["properties"]
            result.append(
                OfficialAlert(
                    id=p.get("id") or feature["id"],
                    event=p["event"],
                    status=p["status"],
                    message_type=p["messageType"],
                    sent=p["sent"],
                    updated=p.get("updated") or p["sent"],
                    effective=p["effective"],
                    onset=p.get("onset"),
                    expires=p["expires"],
                    ends=p.get("ends"),
                    available_at=receipt["retrieved_at_utc"],
                    ingested_at=receipt["retrieved_at_utc"],
                    source_version=receipt["sha256"],
                    polygons=geojson_polygons(feature.get("geometry")),
                    zone_ids=p.get("affectedZones") or [],
                    references=[
                        r.get("identifier") or r.get("@id")
                        for r in p.get("references", [])
                        if isinstance(r, dict) and (r.get("identifier") or r.get("@id"))
                    ],
                    severity=p.get("severity", "Unknown"),
                    certainty=p.get("certainty", "Unknown"),
                    urgency=p.get("urgency", "Unknown"),
                    **proof,
                )
            )
        except (KeyError, TypeError, ValueError):
            errors.append(f"invalid_native_alert_{index}")
    return result, errors


def alert_hazards(name: str) -> list[str]:
    name = name.lower()
    if "flash flood" in name:
        return ["flash_flood", "flood"]
    if "coastal flood" in name:
        return ["coastal_flood"]
    if "flood" in name:
        return ["flood"]
    if "tsunami" in name:
        return ["tsunami"]
    if "tornado" in name:
        return ["tornado"]
    if "thunderstorm" in name:
        return ["thunderstorm", "thunderstorm_wind"]
    if "red flag" in name or "fire weather" in name:
        return ["red_flag", "fire_weather"]
    if "air quality" in name:
        return ["air_quality"]
    if "heat" in name:
        return ["extreme_heat"]
    if "freeze" in name or "frost" in name:
        return ["frost_freeze", "extreme_cold"]
    if any(word in name for word in ("winter", "snow", "ice", "blizzard", "freezing")):
        return ["winter_storm"]
    if any(word in name for word in ("hurricane", "typhoon", "tropical")):
        return ["tropical_cyclone", "high_wind"]
    if any(word in name for word in ("gale", "marine", "seas", "craft", "storm warning")):
        return ["marine_wind_waves"]
    if "rip current" in name:
        return ["rip_current"]
    if "surf" in name or "beach" in name:
        return ["surf"]
    if "wind" in name:
        return ["high_wind"]
    if "dust" in name:
        return ["dust"]
    if "fog" in name:
        return ["fog"]
    return []  # Unknown official terminology stays a notice, never relabeled as heat/wind.


def modern_water(payload: dict, receipt: dict) -> list:
    features = payload.get("features")
    if not isinstance(features, list) or len(features) > 1000:
        raise ValueError("Invalid bounded USGS continuous collection")
    result = []
    for feature in features:
        p = feature["properties"]
        if p.get("parameter_code") not in ("00065", "63160"):
            continue
        lon, lat = feature["geometry"]["coordinates"][:2]
        flags = (
            []
            if p.get("approval_status") == "Approved" and not p.get("qualifier")
            else ["USGS_provisional_or_qualified"]
        )
        if p.get("last_modified") and parse_utc(p["last_modified"], "revision") > parse_utc(
            receipt["retrieved_at_utc"], "capture"
        ):
            flags.append("revision_after_capture")
        result.append(
            _base(
                receipt,
                publisher="USGS modern water API",
                record_id=str(feature["id"]),
                original_type="USGS_modern_continuous:" + p["monitoring_location_id"],
                hazard="flood_context",
                method="observed",
                variable="gauge_height",
                value=float(p["value"]) if p.get("value") is not None else None,
                unit=p["unit_of_measure"],
                observed_at=p["time"],
                valid_from=p["time"],
                valid_to=p["time"],
                footprint={
                    "kind": "point",
                    "point": {"lat": float(lat), "lon": float(lon)},
                    "precision": "USGS gauge; basin relation unverified",
                },
                datum=None,
                quality_flags=flags,
            )
        )
    return result


def swpc_messages(payload: list, receipt: dict) -> list[ContextSignal]:
    if not isinstance(payload, list) or len(payload) > 1000:
        raise ValueError("Invalid SWPC message collection")
    result = []
    for row in payload:
        if not re.fullmatch(r"K0[4-9][AW]", row["product_id"]):
            continue  # Radio, particle and summary products are not geomagnetic K messages.
        # The provider's documented UTC issue_datetime lacks an explicit suffix.
        issued = row["issue_datetime"].replace(" ", "T")
        if not issued.endswith("Z") and "+" not in issued:
            issued += "Z"
        identity = row["product_id"] + ":" + issued
        result.append(
            ContextSignal(
                id="swpc:" + hashlib.sha256(identity.encode()).hexdigest()[:20],
                hazard_id="geomagnetic_storm",
                method="official_message",
                source="NOAA SWPC",
                origin_url="https://services.swpc.noaa.gov/products/alerts.json",
                source_version=receipt["sha256"],
                issued_at=issued,
                available_at=receipt["retrieved_at_utc"],
                footprint={
                    "kind": "global",
                    "precision": "Planetary/regional communications and grid context",
                },
                value=None,
                unit="context",
                valid_to=None,
                description="Captured SWPC message; no structured expiration established. Not an active site warning or outage estimate.",
                source_metadata={
                    "product_id": row["product_id"],
                    "message_sha256": hashlib.sha256(row["message"].encode()).hexdigest(),
                },
            )
        )
    return result


def shakemap_at_site(xml: bytes, receipt: dict, site: SiteContext) -> ContextSignal | None:
    if len(xml) > 16_000_000 or b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
        raise ValueError("Unsafe or oversized ShakeMap XML")
    root = ET.fromstring(xml)
    ns = {"s": root.tag.split("}")[0].lstrip("{")} if "}" in root.tag else {}
    prefix = "s:" if ns else ""
    spec = root.find(prefix + "grid_specification", ns)
    if spec is None:
        raise ValueError("ShakeMap grid specification missing")
    attrs = spec.attrib
    lon0, lon1 = float(attrs["lon_min"]), float(attrs["lon_max"])
    lat0, lat1 = float(attrs["lat_min"]), float(attrs["lat_max"])
    if not (-180 <= lon0 < lon1 <= 180 and -90 <= lat0 < lat1 <= 90):
        raise ValueError("Invalid or unsplit ShakeMap bounds")
    if not lon0 <= site.lon <= lon1 or not lat0 <= site.lat <= lat1:
        return None
    fields = {
        e.attrib["name"].upper(): int(e.attrib["index"]) - 1
        for e in root.findall(prefix + "grid_field", ns)
    }
    if not {"LON", "LAT", "MMI"} <= fields.keys():
        raise ValueError("ShakeMap MMI columns missing")
    mmi_field = next(
        e for e in root.findall(prefix + "grid_field", ns) if e.attrib["name"].upper() == "MMI"
    )
    if mmi_field.attrib.get("units", "").lower() not in ("intensity", "mmi"):
        raise ValueError("Unexpected ShakeMap intensity units")
    text = root.findtext(prefix + "grid_data", "", ns)
    best, best_distance = None, float("inf")
    rows = text.strip().splitlines()
    if len(rows) > 200_000:
        raise ValueError("ShakeMap grid exceeds bounded row count")
    for line in rows:
        values = line.split()
        lon, lat, mmi = (float(values[fields[k]]) for k in ("LON", "LAT", "MMI"))
        if not lon0 <= lon <= lon1 or not lat0 <= lat <= lat1 or not 1 <= mmi <= 12:
            raise ValueError("Invalid ShakeMap grid node")
        distance = (lon - site.lon) ** 2 + (lat - site.lat) ** 2
        if distance < best_distance:
            best, best_distance = (lon, lat, mmi), distance
    if best is None:
        raise ValueError("Empty ShakeMap grid")
    dx, dy = float(attrs["nominal_lon_spacing"]), float(attrs["nominal_lat_spacing"])
    if (
        not 0 < dx <= 1
        or not 0 < dy <= 1
        or abs(best[0] - site.lon) > dx / 2 + 1e-6
        or abs(best[1] - site.lat) > dy / 2 + 1e-6
    ):
        raise ValueError("Site lacks a nearby valid model grid node")
    x0, x1, y0, y1 = (
        max(lon0, best[0] - dx / 2),
        min(lon1, best[0] + dx / 2),
        max(lat0, best[1] - dy / 2),
        min(lat1, best[1] + dy / 2),
    )
    rings = [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]
    from ml.worker.geometry import checked_polygon

    footprint = checked_polygon(rings)
    if not in_ring(site, footprint.rings[0]):
        return None
    return ContextSignal(
        id="shakemap:" + root.attrib.get("event_id", "unknown") + ":" + site.id,
        hazard_id="shaking",
        method="issued_model_estimate",
        source="USGS ShakeMap",
        origin_url=receipt["url"],
        source_version=receipt["sha256"],
        issued_at=root.attrib["process_timestamp"]
        + (
            "Z"
            if not root.attrib["process_timestamp"].endswith("Z")
            and "+" not in root.attrib["process_timestamp"]
            else ""
        ),
        available_at=receipt["retrieved_at_utc"],
        footprint=footprint,
        value=best[2],
        unit="MMI",
        valid_to=None,
        description="Nearest source ShakeMap grid node within half-cell spacing; modeled shaking estimate, not a sensor reading or equipment/structural damage estimate.",
        source_metadata={
            "node_lon": best[0],
            "node_lat": best[1],
            "lon_spacing": dx,
            "lat_spacing": dy,
            "event_id": root.attrib.get("event_id", "unknown"),
            "map_version": root.attrib.get("shakemap_version", "unknown"),
        },
    )
