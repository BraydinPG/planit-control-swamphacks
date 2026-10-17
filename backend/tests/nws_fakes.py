"""NWS-shaped test responses served through httpx.MockTransport. Shapes follow api.weather.gov."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.ingestion.cache import FeedCache
from app.ingestion.nws import NwsClient
from app.schemas import HazardType

BASE = "https://api.weather.gov"
NOW = datetime(2026, 10, 17, 18, 0, tzinfo=UTC)
STALE_AFTER = timedelta(minutes=60)
UNAVAILABLE_AFTER = timedelta(minutes=360)


@dataclass
class Site:
    id: str = "site-demo"
    lat: float = 25.76
    lon: float = -80.49


def iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def point() -> dict[str, Any]:
    return {
        "properties": {
            "forecastHourly": f"{BASE}/gridpoints/MFL/75,52/forecast/hourly",
            "observationStations": f"{BASE}/gridpoints/MFL/75,52/stations",
        }
    }


def stations() -> dict[str, Any]:
    return {
        "features": [
            {"id": f"{BASE}/stations/{code}", "properties": {"stationIdentifier": code}}
            for code in ("KTMB", "KMIA")
        ]
    }


def latest(
    observed_at: datetime = NOW - timedelta(minutes=20),
    heat_index: float | None = 41.7,
    temperature: float | None = 34.4,
    humidity: float | None = 61.0,
):
    return {
        "geometry": {"type": "Point", "coordinates": [-80.43, 25.65]},
        "properties": {
            "timestamp": iso(observed_at),
            "temperature": {"unitCode": "wmoUnit:degC", "value": temperature},
            "relativeHumidity": {"unitCode": "wmoUnit:percent", "value": humidity},
            "heatIndex": {"unitCode": "wmoUnit:degC", "value": heat_index},
        },
    }


def hourly(hours: int = 3) -> dict[str, Any]:
    return {
        "properties": {
            "updateTime": iso(NOW - timedelta(minutes=45)),
            "periods": [
                {
                    "startTime": iso(NOW + timedelta(hours=h)),
                    "temperature": 93 + h,
                    "temperatureUnit": "F",
                    "relativeHumidity": {"unitCode": "wmoUnit:percent", "value": 60 - h},
                    "probabilityOfPrecipitation": {"unitCode": "wmoUnit:percent", "value": 40},
                }
                for h in range(hours)
            ],
        }
    }


def alerts(*events: str) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "id": f"{BASE}/alerts/urn:oid:test.{i}",
                "properties": {
                    "id": f"urn:oid:test.{i}",
                    "event": event,
                    "headline": f"{event} issued for Miami-Dade",
                    "sent": iso(NOW - timedelta(minutes=90)),
                    "ends": iso(NOW + timedelta(hours=6)),
                },
            }
            for i, event in enumerate(events)
        ],
    }


class FakeNws:
    """Routes NWS paths to canned JSON. Set `fail=True` to simulate an outage."""

    def __init__(self, routes: dict[str, Any] | None = None) -> None:
        self.routes = {
            "/points/25.7600,-80.4900": point(),
            "/gridpoints/MFL/75,52/stations": stations(),
            "/stations/KTMB/observations/latest": latest(),
            "/gridpoints/MFL/75,52/forecast/hourly": hourly(),
            "/alerts/active": alerts("Flood Watch"),
            **(routes or {}),
        }
        self.fail = False
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail:
            return httpx.Response(503, json={"title": "Service Unavailable"})
        body = self.routes.get(request.url.path)
        if body is None:
            return httpx.Response(404, json={"title": "Not Found"})
        return httpx.Response(200, json=body)

    def client(self, user_agent: str | None = "PlanIT Control tests") -> NwsClient:
        return NwsClient(user_agent, BASE, transport=httpx.MockTransport(self.handler))


def cache(hazard_type: HazardType) -> FeedCache:
    return FeedCache("NWS", hazard_type, STALE_AFTER, UNAVAILABLE_AFTER)
