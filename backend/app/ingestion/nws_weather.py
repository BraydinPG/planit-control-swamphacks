"""NWS weather and forecast feed (T043).

Per site: `/points` lookup, latest station observation, and the hourly forecast. Each
Observation carries one metric named by `label` (see `METRIC_LABELS`). Temperatures are
converted to °F. Missing NWS values are skipped, never reported as zero.
"""

from datetime import datetime
from typing import Any

from app.ingestion.base import FeedError, SiteLike, unavailable_observation
from app.ingestion.cache import FeedCache
from app.ingestion.nws import NwsClient
from app.ingestion.settings import IngestionSettings, get_ingestion_settings
from app.schemas import DataState, HazardType, Observation

SOURCE = "NWS"
TEMPERATURE = "Temperature"
RELATIVE_HUMIDITY = "Relative humidity"
HEAT_INDEX = "Heat index"
PRECIPITATION_PROBABILITY = "Precipitation probability"
METRIC_LABELS = (TEMPERATURE, RELATIVE_HUMIDITY, HEAT_INDEX, PRECIPITATION_PROBABILITY)
MAX_STATIONS = 3


class NwsWeatherFeed:
    def __init__(self, client: NwsClient, cache: FeedCache, forecast_hours: int = 12) -> None:
        self.client = client
        self.cache = cache
        self.forecast_hours = forecast_hours

    @classmethod
    def from_settings(cls, settings: IngestionSettings) -> "NwsWeatherFeed":
        cache = FeedCache(
            SOURCE, HazardType.WEATHER, settings.stale_after, settings.unavailable_after
        )
        return cls(NwsClient.from_settings(settings), cache, settings.nws_forecast_hours)

    def fetch(self, sites: list[SiteLike], now: datetime) -> list[Observation]:
        """Ingestion interface. Failures fall back to stale or unavailable per site."""
        return [o for site in sites for o in self.cache.refresh(site, now, self.fetch_site)]

    def fetch_site(self, site: SiteLike, now: datetime) -> list[Observation]:
        """Fresh readings for one site. Raises `FeedError` if NWS gives nothing usable."""
        point = self.client.point(site)
        observations = self._latest_observation(site, point, now)
        observations += self._hourly_forecast(site, point)
        if not observations:
            raise FeedError("NWS returned no usable readings")
        return observations

    def _latest_observation(
        self, site: SiteLike, point: dict[str, Any], now: datetime
    ) -> list[Observation]:
        stations = self.client.get_json(_require(point, "observationStations")).get("features")
        if not stations:
            raise FeedError("NWS point has no observation stations")
        # Nearby stations often report null values, so try the closest few in order.
        for station in stations[:MAX_STATIONS]:
            try:
                observations = self._station_reading(site, station, now)
            except FeedError:
                continue
            if observations:
                return observations
        return [
            unavailable_observation(
                site, SOURCE, HazardType.WEATHER, "No nearby NWS station reported values", now
            )
        ]

    def _station_reading(
        self, site: SiteLike, station: dict[str, Any], now: datetime
    ) -> list[Observation]:
        station_id = station.get("properties", {}).get("stationIdentifier", "unknown")
        latest = self.client.get_json(f"{_require(station, 'id')}/observations/latest")
        props = latest.get("properties") or {}
        observed_at = _parse_time(props.get("timestamp"))
        if observed_at is None:
            return []
        lon, lat = _coordinates(latest, site)
        state = (
            DataState.STALE if now - observed_at > self.cache.stale_after else DataState.OBSERVED
        )
        readings = [
            (TEMPERATURE, _to_fahrenheit(props.get("temperature")), "°F"),
            (RELATIVE_HUMIDITY, _value(props.get("relativeHumidity")), "%"),
            (HEAT_INDEX, _to_fahrenheit(props.get("heatIndex")), "°F"),
        ]
        return [
            Observation(
                id=f"nws-obs:{site.id}:{label}:{observed_at.isoformat()}",
                site_id=site.id,
                source=SOURCE,
                hazard_type=HazardType.WEATHER,
                value=value,
                unit=unit,
                label=label,
                source_ref=f"station:{station_id}",
                lat=lat,
                lon=lon,
                observed_at=observed_at,
                data_state=state,
            )
            for label, value, unit in readings
            if value is not None
        ]

    def _hourly_forecast(self, site: SiteLike, point: dict[str, Any]) -> list[Observation]:
        forecast = self.client.get_json(_require(point, "forecastHourly"))
        props = forecast.get("properties") or {}
        issued_at = _parse_time(props.get("updateTime") or props.get("generatedAt"))
        observations: list[Observation] = []
        for period in (props.get("periods") or [])[: self.forecast_hours]:
            valid_at = _parse_time(period.get("startTime"))
            if valid_at is None:
                continue
            temperature = period.get("temperature")
            if isinstance(temperature, int | float) and period.get("temperatureUnit") == "C":
                temperature = temperature * 9 / 5 + 32
            readings = [
                (TEMPERATURE, temperature if isinstance(temperature, int | float) else None, "°F"),
                (RELATIVE_HUMIDITY, _value(period.get("relativeHumidity")), "%"),
                (PRECIPITATION_PROBABILITY, _value(period.get("probabilityOfPrecipitation")), "%"),
            ]
            observations += [
                Observation(
                    id=f"nws-fc:{site.id}:{label}:{valid_at.isoformat()}",
                    site_id=site.id,
                    source=SOURCE,
                    hazard_type=HazardType.FORECAST,
                    value=float(value),
                    unit=unit,
                    label=label,
                    source_ref="forecastHourly",
                    lat=site.lat,
                    lon=site.lon,
                    observed_at=issued_at or valid_at,
                    valid_at=valid_at,
                    data_state=DataState.FORECAST,
                )
                for label, value, unit in readings
                if value is not None
            ]
        return observations


_default_feed: NwsWeatherFeed | None = None


def fetch(sites: list[SiteLike], now: datetime) -> list[Observation]:
    """Module-level ingestion interface using settings from the environment."""
    global _default_feed
    if _default_feed is None:
        _default_feed = NwsWeatherFeed.from_settings(get_ingestion_settings())
    return _default_feed.fetch(sites, now)


def _require(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise FeedError(f"NWS response is missing {key}")
    return value


def _value(quantity: Any) -> float | None:
    if isinstance(quantity, dict) and isinstance(quantity.get("value"), int | float):
        return float(quantity["value"])
    return None


def _to_fahrenheit(quantity: Any) -> float | None:
    value = _value(quantity)
    if value is None:
        return None
    if str(quantity.get("unitCode", "")).endswith("degF"):
        return round(value, 1)
    return round(value * 9 / 5 + 32, 1)


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None


def _coordinates(feature: dict[str, Any], site: SiteLike) -> tuple[float, float]:
    coords = (feature.get("geometry") or {}).get("coordinates")
    if isinstance(coords, list) and len(coords) >= 2:
        return float(coords[0]), float(coords[1])
    return site.lon, site.lat
