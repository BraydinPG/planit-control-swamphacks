"""Bounded planar GeoJSON validation; dateline polygons require upstream splitting."""

from ml.worker.schema import Footprint
from ml.worker.spatial import in_ring


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _intersects(a, b, c, d):
    if max(a[0], b[0]) < min(c[0], d[0]) or max(c[0], d[0]) < min(a[0], b[0]):
        return False
    if max(a[1], b[1]) < min(c[1], d[1]) or max(c[1], d[1]) < min(a[1], b[1]):
        return False
    return _cross(a, b, c) * _cross(a, b, d) <= 0 and _cross(c, d, a) * _cross(c, d, b) <= 0


def checked_polygon(rings: list) -> Footprint:
    if not 1 <= len(rings) <= 20 or sum(map(len, rings)) > 600:
        raise ValueError("Polygon exceeds replay geometry bounds")
    footprint = Footprint(kind="polygon", rings=rings, precision="Official source polygon")
    for ring in footprint.rings:
        if len({tuple(p) for p in ring[:-1]}) != len(ring) - 1:
            raise ValueError("Repeated polygon vertices")
        area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:]))
        if abs(area) < 1e-12:
            raise ValueError("Degenerate polygon")
        edges = list(zip(ring, ring[1:]))
        for i, (a, b) in enumerate(edges):
            for j, (c, d) in enumerate(edges[i + 1 :], start=i + 1):
                if j == i + 1 or (i == 0 and j == len(edges) - 1):
                    continue
                if _intersects(a, b, c, d):
                    raise ValueError("Self-intersecting polygon")
    from ml.worker.schema import Point

    for i, hole in enumerate(footprint.rings[1:], start=1):
        if not in_ring(Point(lon=hole[0][0], lat=hole[0][1]), footprint.rings[0]):
            raise ValueError("Polygon hole lies outside shell")
        for other in footprint.rings[:i]:
            if any(
                _intersects(a, b, c, d)
                for a, b in zip(hole, hole[1:])
                for c, d in zip(other, other[1:])
            ):
                raise ValueError("Polygon rings intersect")
            if other is not footprint.rings[0] and (
                in_ring(Point(lon=hole[0][0], lat=hole[0][1]), other)
                or in_ring(Point(lon=other[0][0], lat=other[0][1]), hole)
            ):
                raise ValueError("Nested/overlapping polygon holes")
    return footprint


def geojson_polygons(geometry: dict | None) -> list[Footprint]:
    geometry = geometry or {}
    if geometry.get("type") == "Polygon":
        return [checked_polygon(geometry["coordinates"])]
    if geometry.get("type") == "MultiPolygon":
        coordinates = geometry["coordinates"]
        if not 1 <= len(coordinates) <= 30:
            raise ValueError("Too many polygon components")
        return [checked_polygon(rings) for rings in coordinates]
    if geometry.get("type") not in (None, "GeometryCollection"):
        raise ValueError("Unsupported areal geometry")
    return []
