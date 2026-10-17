"""NHC- and USGS-shaped test responses served through httpx.MockTransport.

Shapes follow the live CurrentStorms.json, USGS earthquake summary GeoJSON, and USGS
Water Services instantaneous-values JSON. Sites and times come from `nws_fakes`.
"""

from datetime import datetime, timedelta
from typing import Any

import httpx

from app.ingestion.cache import FeedCache
from app.ingestion.geo import destination
from app.ingestion.json_client import JsonClient
from app.schemas import HazardType
from tests.nws_fakes import NOW, STALE_AFTER, UNAVAILABLE_AFTER, Site, iso

NHC_URL = "https://www.nhc.noaa.gov/CurrentStorms.json"
QUAKE_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
WATER_URL = "https://waterservices.usgs.gov/nwis/iv/"


def near(bearing: float, miles: float, site: Site | None = None) -> tuple[float, float]:
    site = site or Site()
    return destination(site.lat, site.lon, bearing, miles)


def storm(
    name: str, miles: float, bearing: float = 135, classification: str = "HU", knots="80"
) -> dict[str, Any]:
    lat, lon = near(bearing, miles)
    return {
        "id": f"al99{name.lower()}",
        "name": name,
        "classification": classification,
        "intensity": knots,
        "pressure": "979",
        "latitudeNumeric": lat,
        "longitudeNumeric": lon,
        "lastUpdate": "2026-10-17T15:00:00.000Z",
    }


def storms(*items: dict[str, Any]) -> dict[str, Any]:
    return {"activeStorms": list(items)}


def quake(
    event_id: str,
    miles: float,
    mag: float | None = 4.6,
    kind: str = "earthquake",
    at: datetime = NOW - timedelta(minutes=30),
) -> dict[str, Any]:
    lat, lon = near(200, miles)
    return {
        "type": "Feature",
        "id": event_id,
        "properties": {
            "mag": mag,
            "magType": "mww",
            "place": "12 km SW of Example, FL",
            "time": int(at.timestamp() * 1000),
            "url": f"https://earthquake.usgs.gov/earthquakes/eventpage/{event_id}",
            "type": kind,
        },
        "geometry": {"type": "Point", "coordinates": [lon, lat, 10.0]},
    }


def quakes(*features: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "metadata": {"title": "USGS All Earthquakes, Past Day"},
        "features": list(features),
    }


def gauge_series(
    gauge_id: str,
    miles: float,
    parameter: str = "00065",
    value: str = "6.42",
    at: datetime = NOW - timedelta(minutes=15),
) -> dict[str, Any]:
    lat, lon = near(90, miles)
    unit = "ft" if parameter == "00065" else "ft3/s"
    return {
        "sourceInfo": {
            "siteName": f"EXAMPLE CANAL {gauge_id}",
            "siteCode": [{"value": gauge_id, "agencyCode": "USGS"}],
            "geoLocation": {"geogLocation": {"latitude": lat, "longitude": lon}},
        },
        "variable": {
            "variableCode": [{"value": parameter}],
            "unit": {"unitCode": unit},
            "noDataValue": -999999.0,
        },
        "values": [{"value": [{"value": value, "qualifiers": ["P"], "dateTime": iso(at)}]}],
        "name": f"USGS:{gauge_id}:{parameter}:00000",
    }


def water(*series: dict[str, Any]) -> dict[str, Any]:
    return {"value": {"timeSeries": list(series)}}


class FakeFeeds:
    """Routes full URLs (without query) to canned JSON. Set `fail=True` for an outage."""

    def __init__(self, routes: dict[str, Any] | None = None) -> None:
        self.routes = dict(routes or {})
        self.fail = False
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail:
            return httpx.Response(503, json={"error": "Service Unavailable"})
        body = self.routes.get(str(request.url.copy_with(query=None)))
        if body is None:
            return httpx.Response(404, json={"error": "Not Found"})
        return httpx.Response(200, json=body)

    def client(self) -> JsonClient:
        return JsonClient("PlanIT Control tests", transport=httpx.MockTransport(self.handler))


def cache(source: str, hazard_type: HazardType) -> FeedCache:
    return FeedCache(source, hazard_type, STALE_AFTER, UNAVAILABLE_AFTER)
