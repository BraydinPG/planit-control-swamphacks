"""Geodesic distance and bounded GeoJSON point-in-polygon association."""

import math

from ml.worker.schema import Evidence, Point, SiteContext, SpatialMatch


def distance_km(a: Point, b: Point) -> float:
    lat1, lat2 = map(math.radians, (a.lat, b.lat))
    delta_lat, delta_lon = math.radians(b.lat - a.lat), math.radians(b.lon - a.lon)
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1.0, max(0.0, value))))


def in_ring(point: Point, ring: list[list[float]]) -> bool:
    inside = False
    x, y = point.lon, point.lat
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
        if (
            abs(cross) < 1e-10
            and min(x1, x2) - 1e-10 <= x <= max(x1, x2) + 1e-10
            and min(y1, y2) - 1e-10 <= y <= max(y1, y2) + 1e-10
        ):
            return True
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def associate(
    site: SiteContext, evidence: Evidence, *, maximum_station_km: float = 25.0
) -> SpatialMatch:
    footprint = evidence.footprint
    values = {"distance_km": None, "distance_miles": None}
    if footprint.site_id and footprint.site_id != site.id:
        return SpatialMatch(
            kind="no_supported_association",
            **values,
            limitation="Evidence is bound to a different site.",
        )
    if footprint.kind == "polygon":
        if in_ring(site, footprint.rings[0]) and not any(
            in_ring(site, hole) for hole in footprint.rings[1:]
        ):
            return SpatialMatch(
                kind="polygon_intersects",
                **values,
                limitation="Coverage intersects location; gridded guidance is not an on-site measurement.",
            )
    elif footprint.kind == "point":
        distance = distance_km(site, footprint.point)
        values = {"distance_km": distance, "distance_miles": distance / 1.609344}
        if (
            footprint.relation == "verified_gauge_basin"
            and footprint.site_id == site.id
            and footprint.relation_evidence_id
        ):
            return SpatialMatch(
                kind="verified_gauge_basin",
                **values,
                limitation="Upstream caller attests basin relation; gauge height is not site inundation depth.",
            )
        if evidence.hazard == "earthquake" and distance <= 500:
            return SpatialMatch(
                kind="epicenter_distance",
                **values,
                limitation="Epicenter context within a prototype 500km display bound, not local shaking or structural condition.",
            )
        if evidence.hazard == "earthquake":
            return SpatialMatch(
                kind="no_supported_association",
                **values,
                limitation="Epicenter lies outside the 500km contextual display bound; no local shaking inference.",
            )
        if evidence.original_type in ("NHC_track_center", "hurricane_cone"):
            return SpatialMatch(
                kind="track_center_distance",
                **values,
                limitation="A track center or cone does not specify the wind/surge footprint.",
            )
        if distance <= maximum_station_km:
            return SpatialMatch(
                kind="station_at_location" if distance < 0.1 else "nearby_station",
                **values,
                limitation="Station proximity is descriptive; local exposure is unverified.",
            )
    elif footprint.kind == "regional":
        return SpatialMatch(
            kind="county_only_context",
            **values,
            limitation="Regional attribution does not establish worksite exposure.",
        )
    elif footprint.kind == "global" and evidence.hazard == "space_weather":
        return SpatialMatch(
            kind="global_context",
            **values,
            limitation="Planetary index does not predict a site outage or equipment failure.",
        )
    return SpatialMatch(
        kind="no_supported_association",
        **values,
        limitation="No supported location association for this evidence.",
    )
