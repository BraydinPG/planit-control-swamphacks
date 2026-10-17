"""USGS flood gauge feed (T045D): Water Services instantaneous values.

Per site, one request to USGS_WATER_URL for active gauges in a bounding box around
the site, then the nearest FLOOD_GAUGE_MAX_GAUGES gauges within
FLOOD_GAUGE_SEARCH_RADIUS_MILES. Each gauge's latest gage height (parameter 00065, ft)
and streamflow (00060, ft3/s) become `flood_gauge` Observations. `label` starts with
`GAGE_HEIGHT` or `STREAMFLOW`, then names the gauge; `source_ref` is the USGS site
number. Readings older than FEED_STALE_AFTER_MINUTES are marked stale. USGS no-data
values are skipped, never written as zero.

Water Services gives readings, not flood stages, so this feed does not say whether a
gauge is flooding. NWS flood alerts (`nws_alerts.py`) stay the flood source: when no
gauge is near a site the "none" label says so, and a failed gauge fetch marks only this
feed unavailable.
"""

from datetime import datetime
from math import cos, radians
from typing import Any

from app.ingestion.base import FeedError, SiteLike
from app.ingestion.cache import FeedCache
from app.ingestion.geo import direction_from, distance_miles
from app.ingestion.json_client import JsonClient, parse_time
from app.ingestion.settings import IngestionSettings, get_ingestion_settings
from app.schemas import DataState, HazardType, Observation

SOURCE = "USGS"
GAGE_HEIGHT = "Gage height"
STREAMFLOW = "Streamflow"
PARAMETERS = {"00065": (GAGE_HEIGHT, "ft"), "00060": (STREAMFLOW, "ft3/s")}
MILES_PER_DEGREE = 69.0


class FloodGaugeFeed:
    def __init__(
        self,
        http: JsonClient,
        cache: FeedCache,
        water_url: str = "https://waterservices.usgs.gov/nwis/iv/",
        search_radius_miles: float = 10.0,
        max_gauges: int = 3,
    ) -> None:
        self.http = http
        self.cache = cache
        self.water_url = water_url
        self.search_radius_miles = search_radius_miles
        self.max_gauges = max_gauges

    @classmethod
    def from_settings(cls, settings: IngestionSettings) -> "FloodGaugeFeed":
        cache = FeedCache(
            SOURCE, HazardType.FLOOD_GAUGE, settings.stale_after, settings.unavailable_after
        )
        return cls(
            JsonClient.from_settings(settings),
            cache,
            settings.usgs_water_url,
            settings.flood_gauge_search_radius_miles,
            settings.flood_gauge_max_gauges,
        )

    def fetch(self, sites: list[SiteLike], now: datetime) -> list[Observation]:
        """Ingestion interface. Failures fall back to stale or unavailable per site."""
        return [o for site in sites for o in self.cache.refresh(site, now, self.fetch_site)]

    def fetch_site(self, site: SiteLike, now: datetime) -> list[Observation]:
        payload = self.http.get_json(
            self.water_url,
            params={
                "format": "json",
                "bBox": _bounding_box(site, self.search_radius_miles),
                "parameterCd": ",".join(PARAMETERS),
                "siteStatus": "active",
            },
        )
        series = (payload.get("value") or {}).get("timeSeries")
        if not isinstance(series, list):
            raise FeedError("USGS water response has no timeSeries list")
        readings = [r for item in series if (r := self._reading(site, item, now)) is not None]
        readings.sort(key=lambda reading: reading[0])
        nearest = list(dict.fromkeys(o.source_ref for _, o in readings))[: self.max_gauges]
        observations = [o for _, o in readings if o.source_ref in nearest]
        if observations:
            return observations
        return [
            Observation(
                id=f"usgs-gauge:{site.id}:none:{now.isoformat()}",
                site_id=site.id,
                source=SOURCE,
                hazard_type=HazardType.FLOOD_GAUGE,
                value=None,
                label=(
                    f"No active USGS gauges within {self.search_radius_miles:g} mi; "
                    "NWS flood alerts are the flood source"
                ),
                lat=site.lat,
                lon=site.lon,
                observed_at=now,
                data_state=DataState.OBSERVED,
            )
        ]

    def _reading(
        self, site: SiteLike, item: Any, now: datetime
    ) -> tuple[float, Observation] | None:
        if not isinstance(item, dict):
            return None
        info = item.get("sourceInfo") or {}
        variable = item.get("variable") or {}
        codes = variable.get("variableCode") or [{}]
        metric = PARAMETERS.get(codes[0].get("value"))
        location = (info.get("geoLocation") or {}).get("geogLocation") or {}
        site_codes = info.get("siteCode") or [{}]
        gauge_id = site_codes[0].get("value")
        if metric is None or not gauge_id:
            return None
        try:
            lat, lon = float(location["latitude"]), float(location["longitude"])
            latest = item["values"][0]["value"][-1]
            value = float(latest["value"])
        except (KeyError, IndexError, TypeError, ValueError):
            return None
        observed_at = parse_time(latest.get("dateTime"))
        if observed_at is None or value == variable.get("noDataValue"):
            return None
        miles = distance_miles(site.lat, site.lon, lat, lon)
        if miles > self.search_radius_miles:
            return None
        label, unit = metric
        stale = now - observed_at > self.cache.stale_after
        where = f"{miles:.1f} mi {direction_from(site.lat, site.lon, lat, lon)}"
        name = info.get("siteName") or f"USGS {gauge_id}"
        return miles, Observation(
            id=f"usgs-gauge:{site.id}:{gauge_id}:{codes[0]['value']}:{observed_at.isoformat()}",
            site_id=site.id,
            source=SOURCE,
            hazard_type=HazardType.FLOOD_GAUGE,
            value=value,
            unit=unit,
            label=f"{label}, {name} ({where})",
            source_ref=f"USGS-{gauge_id}",
            lat=lat,
            lon=lon,
            observed_at=observed_at,
            data_state=DataState.STALE if stale else DataState.OBSERVED,
        )


def _bounding_box(site: SiteLike, miles: float) -> str:
    """west,south,east,north in degrees, enclosing a circle of `miles` around the site."""
    d_lat = miles / MILES_PER_DEGREE
    d_lon = miles / (MILES_PER_DEGREE * max(cos(radians(site.lat)), 0.01))
    west, east = max(site.lon - d_lon, -180.0), min(site.lon + d_lon, 180.0)
    south, north = max(site.lat - d_lat, -90.0), min(site.lat + d_lat, 90.0)
    return ",".join(f"{v:.4f}" for v in (west, south, east, north))


_default_feed: FloodGaugeFeed | None = None


def fetch(sites: list[SiteLike], now: datetime) -> list[Observation]:
    """Module-level ingestion interface using settings from the environment."""
    global _default_feed
    if _default_feed is None:
        _default_feed = FloodGaugeFeed.from_settings(get_ingestion_settings())
    return _default_feed.fetch(sites, now)
