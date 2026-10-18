"""Conservative CAP matching. Uncertain geometry requires the point endpoint."""

from math import isfinite

from app.ingestion.base import FeedError
from app.ingestion.json_client import parse_time

EVENTS = {
    "Flood Warning",
    "Flash Flood Warning",
    "Flood Watch",
    "Hurricane Warning",
    "Hurricane Watch",
    "Tropical Storm Warning",
    "Tropical Storm Watch",
    "Tornado Warning",
    "Tornado Watch",
    "Severe Thunderstorm Warning",
    "Severe Thunderstorm Watch",
}


def active(feature, now):
    if not isinstance(feature, dict) or not isinstance(feature.get("properties"), dict):
        raise FeedError("Invalid NWS alert feature")
    props = feature["properties"]
    if props.get("event") not in EVENTS:
        return False
    if props.get("status", "Actual") != "Actual" or props.get("messageType") == "Cancel":
        return False
    if not isinstance(props.get("id") or feature.get("id"), str):
        raise FeedError("NWS alert has no source identity")
    for key in ("ends", "expires"):
        if props.get(key) is not None:
            stamp = parse_time(props[key])
            if stamp is None:
                raise FeedError("NWS alert has invalid expiration")
            if stamp <= now:
                return False
    sent = parse_time(props.get("sent") or props.get("effective"))
    if sent is None or sent > now:
        raise FeedError("NWS alert issue time is missing, invalid or in the future")
    return True


def _cross(a, b, p):
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def _on_segment(a, b, p):
    return (
        abs(_cross(a, b, p)) < 1e-10
        and min(a[0], b[0]) - 1e-10 <= p[0] <= max(a[0], b[0]) + 1e-10
        and min(a[1], b[1]) - 1e-10 <= p[1] <= max(a[1], b[1]) + 1e-10
    )


def _ring(ring, point):
    if not isinstance(ring, list) or not 4 <= len(ring) <= 1000 or ring[0] != ring[-1]:
        raise ValueError("Invalid or overly complex ring")
    for p in ring:
        if (
            not isinstance(p, list)
            or len(p) < 2
            or any(
                isinstance(x, bool) or not isinstance(x, int | float) or not isfinite(x)
                for x in p[:2]
            )
            or not -180 <= p[0] <= 180
            or not -90 <= p[1] <= 90
        ):
            raise ValueError("Invalid position")
    edges = list(zip(ring[:-1], ring[1:], strict=True))
    for i, (a, b) in enumerate(edges):
        if abs(a[0] - b[0]) > 180:
            raise ValueError("Antimeridian needs authoritative matching")
        for j in range(i + 2, len(edges)):
            if i == 0 and j == len(edges) - 1:
                continue
            c, d = edges[j]
            if (
                (_cross(a, b, c) * _cross(a, b, d) < 0 and _cross(c, d, a) * _cross(c, d, b) < 0)
                or _on_segment(a, b, c)
                or _on_segment(a, b, d)
            ):
                raise ValueError("Self-intersecting ring")
    x, y = point
    inside = False
    for a, b in edges:
        if _on_segment(a, b, point):
            return True
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
            inside = not inside
    return inside


def _intersects(a, b, c, d):
    return (
        (_cross(a, b, c) * _cross(a, b, d) < 0 and _cross(c, d, a) * _cross(c, d, b) < 0)
        or _on_segment(a, b, c)
        or _on_segment(a, b, d)
        or _on_segment(c, d, a)
        or _on_segment(c, d, b)
    )


def _valid_holes(rings):
    for i, hole in enumerate(rings[1:], 1):
        if not all(_ring(rings[0], p) for p in hole[:-1]):
            return False
        for other in rings[:i]:
            if any(
                _intersects(a, b, c, d)
                for a, b in zip(hole[:-1], hole[1:], strict=True)
                for c, d in zip(other[:-1], other[1:], strict=True)
            ):
                return False
            if other is not rings[0] and (_ring(other, hole[0]) or _ring(hole, other[0])):
                return False
    return True


def matches(feature, site, zones):
    geometry = feature.get("geometry")
    if geometry is not None:
        try:
            polygons = (
                [geometry["coordinates"]]
                if geometry["type"] == "Polygon"
                else geometry["coordinates"]
                if geometry["type"] == "MultiPolygon"
                else None
            )
            if not isinstance(polygons, list) or not polygons:
                return None
            if sum(len(r) for polygon in polygons for r in polygon) > 1000:
                return None
            hits = []
            for rings in polygons:
                if not isinstance(rings, list) or not rings:
                    return None
                checks = [_ring(r, (site.lon, site.lat)) for r in rings]
                if not _valid_holes(rings):
                    return None
                hits.append(checks[0] and not any(checks[1:]))
            return any(hits)
        except (ValueError, KeyError, TypeError, IndexError):
            return None
    affected = feature["properties"].get("affectedZones")
    if isinstance(affected, list) and affected and all(isinstance(z, str) for z in affected):
        return bool(set(affected) & zones)
    return None
