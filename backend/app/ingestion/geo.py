"""Great-circle helpers for matching feed events to sites."""

from math import asin, atan2, cos, degrees, radians, sin, sqrt

EARTH_RADIUS_MILES = 3958.8
_COMPASS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def distance_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance between two points."""
    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi, d_lambda = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * asin(min(1.0, sqrt(a)))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing from the first point to the second, 0–360 clockwise from north."""
    phi1, phi2 = radians(lat1), radians(lat2)
    d_lambda = radians(lon2 - lon1)
    x = sin(d_lambda) * cos(phi2)
    y = cos(phi1) * sin(phi2) - sin(phi1) * cos(phi2) * cos(d_lambda)
    return (degrees(atan2(x, y)) + 360) % 360


def compass(bearing: float) -> str:
    """Eight-point compass direction, e.g. "NW"."""
    return _COMPASS[round(bearing / 45) % 8]


def direction_from(site_lat: float, site_lon: float, lat: float, lon: float) -> str:
    """Where a point lies as seen from the site, e.g. "NW"."""
    return compass(bearing_deg(site_lat, site_lon, lat, lon))


def destination(lat: float, lon: float, bearing: float, miles: float) -> tuple[float, float]:
    """Point reached by travelling `miles` from (lat, lon) on the given bearing."""
    phi1, lambda1, theta = radians(lat), radians(lon), radians(bearing)
    delta = miles / EARTH_RADIUS_MILES
    phi2 = asin(sin(phi1) * cos(delta) + cos(phi1) * sin(delta) * cos(theta))
    lambda2 = lambda1 + atan2(
        sin(theta) * sin(delta) * cos(phi1), cos(delta) - sin(phi1) * sin(phi2)
    )
    return degrees(phi2), (degrees(lambda2) + 540) % 360 - 180
