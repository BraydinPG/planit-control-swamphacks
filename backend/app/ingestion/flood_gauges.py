"""USGS flood gauge feed (T045D): Water Services instantaneous values.

Sites share bounded regional requests to USGS_WATER_URL; each site then selects
the nearest FLOOD_GAUGE_MAX_GAUGES gauges within
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
from math import ceil, cos, floor, isfinite, radians
from typing import Any

from app.ingestion import runtime
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
        *,
        batch_degrees: float = 0.5,
        batch_sites: int = 32,
    ) -> None:
        self.http = http
        self.cache = cache
        self.water_url = water_url
        self.search_radius_miles = search_radius_miles
        self.max_gauges = max_gauges
        self.batch_degrees = batch_degrees
        self.batch_sites = batch_sites

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
            batch_degrees=settings.flood_gauge_batch_degrees,
            batch_sites=settings.flood_gauge_batch_sites,
        )

    def fetch(self, sites: list[SiteLike], now: datetime) -> list[Observation]:
        """Ingestion interface. Failures fall back to stale or unavailable per site."""
        settings = get_ingestion_settings()
        groups = {}
        for site in sites:
            if not runtime.valid_site(site):
                raise FeedError("Invalid site coordinates")
            key = (
                runtime.region_of(site),
                floor(site.lat / self.batch_degrees),
                floor(site.lon / self.batch_degrees),
            )
            groups.setdefault(key, []).append(site)
        batches = [
            rows[i : i + self.batch_sites]
            for rows in groups.values()
            for i in range(0, len(rows), self.batch_sites)
        ]

        def batch(rows):
            boxes = [
                list(map(float, _bounding_box(s, self.search_radius_miles).split(",")))
                for s in rows
            ]
            bounds = (
                min(b[0] for b in boxes),
                min(b[1] for b in boxes),
                max(b[2] for b in boxes),
                max(b[3] for b in boxes),
            )
            box = ",".join(
                f"{(floor(v * 10000) if i < 2 else ceil(v * 10000)) / 10000:.4f}"
                for i, v in enumerate(bounds)
            )
            try:
                if (bounds[2] - bounds[0]) * (bounds[3] - bounds[1]) > 25:
                    raise FeedError("USGS bounding box exceeds supported query area")
                with runtime.labels(
                    site_ids=[s.id for s in rows],
                    region=runtime.region_of(rows[0]),
                    affected_group="gauge_batch",
                ):
                    payload = self._payload(box)
            except FeedError as exc:

                def failed(site, at, error=exc):
                    raise error

                return [o for s in rows for o in self.cache.refresh(s, now, failed)]
            return [
                o
                for s in rows
                for o in self.cache.refresh(
                    s, now, lambda site, at: self._observations(site, payload, at)
                )
            ]

        with runtime.round_scope(settings.feed_round_budget_seconds):
            observations = [
                o
                for rows in runtime.ordered_map(batch, batches, settings.feed_site_workers)
                for o in rows
            ]
        # Return site order, independent of geographical batch completion order.
        order = {s.id: i for i, s in enumerate(sites)}
        return sorted(observations, key=lambda o: order[o.site_id])

    def fetch_site(self, site: SiteLike, now: datetime) -> list[Observation]:
        if not runtime.valid_site(site):
            raise FeedError("Invalid site coordinates")
        payload = self._payload(_bounding_box(site, self.search_radius_miles))
        return self._observations(site, payload, now)

    def _payload(self, box):
        payload = self.http.get_json(
            self.water_url,
            params={
                "format": "json",
                "bBox": box,
                "parameterCd": ",".join(PARAMETERS),
                "siteStatus": "active",
            },
        )
        series = (payload.get("value") or {}).get("timeSeries")
        if not isinstance(series, list):
            raise FeedError("USGS water response has no timeSeries list")
        return payload

    def _observations(self, site, payload, now):
        series = payload["value"]["timeSeries"]
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
                    f"No usable USGS gauge measurements within {self.search_radius_miles:g} mi; "
                    "flood conditions unknown. NWS flood alerts are the flood source"
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
        try:
            no_data = float(variable.get("noDataValue"))
        except (TypeError, ValueError):
            no_data = None
        if (
            observed_at is None
            or observed_at > now
            or not all(isfinite(v) for v in (lat, lon, value))
            or not -90 <= lat <= 90
            or not -180 <= lon <= 180
            or value == no_data
            or (variable.get("unit") or {}).get("unitCode") != metric[1]
        ):
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
    return ",".join(
        f"{(floor(v * 10000) if i < 2 else ceil(v * 10000)) / 10000:.4f}"
        for i, v in enumerate((west, south, east, north))
    )


_default_feed: FloodGaugeFeed | None = None


def fetch(sites: list[SiteLike], now: datetime) -> list[Observation]:
    """Module-level ingestion interface using settings from the environment."""
    global _default_feed
    if _default_feed is None:
        _default_feed = FloodGaugeFeed.from_settings(get_ingestion_settings())
    return _default_feed.fetch(sites, now)
