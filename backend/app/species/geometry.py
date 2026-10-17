"""Small geometry helpers: the square footprint around a site, and clipping map polygons.

Clipping keeps the critical habitat overlay small. A statewide boundary can be a
megabyte of GeoJSON even after the map service simplifies it; only the part inside the
map window is drawn.
"""

from math import cos, radians
from typing import Any

KM_PER_DEGREE_LAT = 111.32

Box = tuple[float, float, float, float]  # west, south, east, north


def square(lat: float, lon: float, half_km: float) -> Box:
    """A lon/lat box with sides of 2 * half_km, centered on the point."""
    dlat = half_km / KM_PER_DEGREE_LAT
    dlon = half_km / (KM_PER_DEGREE_LAT * max(cos(radians(lat)), 0.01))
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def box_polygon(box: Box) -> dict[str, Any]:
    west, south, east, north = box
    ring = [[west, south], [east, south], [east, north], [west, north], [west, south]]
    return {"type": "Polygon", "coordinates": [[[round(x, 6), round(y, 6)] for x, y in ring]]}


def clip_to_box(geometry: dict[str, Any] | None, box: Box) -> dict[str, Any] | None:
    """Clip a GeoJSON Polygon or MultiPolygon to the box. None when nothing is left.

    Sutherland-Hodgman per ring. Good enough for display; the result may carry zero-width
    edges along the box border where a concave shape leaves and re-enters it.
    """
    if not geometry:
        return None
    kind = geometry.get("type")
    coords = geometry.get("coordinates")
    if kind == "Polygon":
        polygons = [coords]
    elif kind == "MultiPolygon":
        polygons = coords
    else:
        return None
    kept = []
    for polygon in polygons or []:
        rings = [_clip_ring(ring, box) for ring in polygon or []]
        if not rings or rings[0] is None:  # the outer ring is outside the box
            continue
        kept.append([r for r in rings if r is not None])
    if not kept:
        return None
    return {"type": "MultiPolygon", "coordinates": kept}


def _clip_ring(ring: list[list[float]], box: Box) -> list[list[float]] | None:
    west, south, east, north = box
    points = [(float(p[0]), float(p[1])) for p in ring]
    edges = (
        (lambda p: p[0] >= west, lambda a, b: _at_x(a, b, west)),
        (lambda p: p[0] <= east, lambda a, b: _at_x(a, b, east)),
        (lambda p: p[1] >= south, lambda a, b: _at_y(a, b, south)),
        (lambda p: p[1] <= north, lambda a, b: _at_y(a, b, north)),
    )
    for inside, cross in edges:
        if not points:
            return None
        out = []
        previous = points[-1]
        for point in points:
            if inside(point):
                if not inside(previous):
                    out.append(cross(previous, point))
                out.append(point)
            elif inside(previous):
                out.append(cross(previous, point))
            previous = point
        points = out
    # Drop the duplicate closing point the clip may have kept, then close the ring.
    deduped = [p for i, p in enumerate(points) if i == 0 or p != points[i - 1]]
    if len(deduped) > 1 and deduped[0] == deduped[-1]:
        deduped.pop()
    if len(deduped) < 3:
        return None
    return [[round(x, 5), round(y, 5)] for x, y in [*deduped, deduped[0]]]


def _at_x(a: tuple[float, float], b: tuple[float, float], x: float) -> tuple[float, float]:
    t = (x - a[0]) / (b[0] - a[0])
    return (x, a[1] + t * (b[1] - a[1]))


def _at_y(a: tuple[float, float], b: tuple[float, float], y: float) -> tuple[float, float]:
    t = (y - a[1]) / (b[1] - a[1])
    return (a[0] + t * (b[0] - a[0]), y)
