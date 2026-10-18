"""Earthquake feed (T045C): USGS earthquake GeoJSON summary feed.

The summary feed (past day by default, USGS_EARTHQUAKE_URL) is fetched once per refresh.
Each event of type "earthquake" within EARTHQUAKE_SEARCH_RADIUS_MILES of a site becomes
an `earthquake` Observation: `value` is the magnitude, `unit` the USGS magnitude type
(for example "ml" or "mww"), `lat`/`lon` the epicenter, and `observed_at` the origin
time. The search radius is wider than the prototype notice distance and magnitude in
spec.md; Rudra's rule applies those.

A successful fetch with no nearby events returns one explicit "none" Observation. A
failed fetch reads stale, then unavailable. Never treat a failure as "no earthquake".
"""

from datetime import UTC, datetime
from typing import Any

from app.ingestion.base import FeedError, SiteLike
from app.ingestion.cache import FeedCache
from app.ingestion.geo import direction_from, distance_miles
from app.ingestion.json_client import JsonClient
from app.ingestion.settings import IngestionSettings, get_ingestion_settings
from app.schemas import DataState, HazardType, Observation

SOURCE = "USGS"


class EarthquakeFeed:
    def __init__(
        self,
        http: JsonClient,
        cache: FeedCache,
        feed_url: str = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson",
        search_radius_miles: float = 100.0,
    ) -> None:
        self.http = http
        self.cache = cache
        self.feed_url = feed_url
        self.search_radius_miles = search_radius_miles

    @classmethod
    def from_settings(cls, settings: IngestionSettings) -> "EarthquakeFeed":
        cache = FeedCache(
            SOURCE, HazardType.EARTHQUAKE, settings.stale_after, settings.unavailable_after
        )
        return cls(
            JsonClient.from_settings(settings),
            cache,
            settings.usgs_earthquake_url,
            settings.earthquake_search_radius_miles,
        )

    def fetch(self, sites: list[SiteLike], now: datetime) -> list[Observation]:
        """Ingestion interface. The USGS feed is fetched once for every site."""
        try:
            payload: dict[str, Any] | FeedError = self._summary()
        except FeedError as exc:
            payload = exc

        def fetch_site(site: SiteLike, now: datetime) -> list[Observation]:
            if isinstance(payload, FeedError):
                raise payload
            return self.events_near(site, payload, now)

        return [o for site in sites for o in self.cache.refresh(site, now, fetch_site)]

    def events_near(
        self, site: SiteLike, payload: dict[str, Any], now: datetime
    ) -> list[Observation]:
        observations = [
            obs for feature in payload["features"] if (obs := self._event(site, feature))
        ]
        if observations:
            return observations
        title = (payload.get("metadata") or {}).get("title") or "USGS earthquake feed"
        return [
            Observation(
                id=f"usgs-eq:{site.id}:none:{now.isoformat()}",
                site_id=site.id,
                source=SOURCE,
                hazard_type=HazardType.EARTHQUAKE,
                value=None,
                label=f"No earthquakes within {self.search_radius_miles:g} mi ({title})",
                lat=site.lat,
                lon=site.lon,
                observed_at=now,
                data_state=DataState.OBSERVED,
            )
        ]

    def _summary(self) -> dict[str, Any]:
        payload = self.http.get_json(self.feed_url)
        if not isinstance(payload.get("features"), list):
            raise FeedError("USGS earthquake response has no features list")
        return payload

    def _event(self, site: SiteLike, feature: Any) -> Observation | None:
        if not isinstance(feature, dict):
            return None
        props = feature.get("properties") or {}
        coords = (feature.get("geometry") or {}).get("coordinates")
        if props.get("type") != "earthquake" or not isinstance(coords, list) or len(coords) < 2:
            return None
        lon, lat = float(coords[0]), float(coords[1])
        millis = props.get("time")
        if not isinstance(millis, int | float):
            return None
        miles = distance_miles(site.lat, site.lon, lat, lon)
        if miles > self.search_radius_miles:
            return None
        magnitude = props.get("mag")
        magnitude = float(magnitude) if isinstance(magnitude, int | float) else None
        where = f"{miles:.0f} mi {direction_from(site.lat, site.lon, lat, lon)} of site"
        event_id = str(feature.get("id") or props.get("code") or "unknown")
        prefix = f"M{magnitude:.1f}" if magnitude is not None else "Earthquake"
        return Observation(
            id=f"usgs-eq:{site.id}:{event_id}",
            site_id=site.id,
            source=SOURCE,
            hazard_type=HazardType.EARTHQUAKE,
            value=magnitude,
            unit=props.get("magType") if magnitude is not None else None,
            label=f"{prefix} - {props.get('place') or 'location not given'}, {where}",
            source_ref=props.get("url") or event_id,
            lat=lat,
            lon=lon,
            observed_at=datetime.fromtimestamp(millis / 1000, tz=UTC),
            data_state=DataState.OBSERVED,
        )


_default_feed: EarthquakeFeed | None = None


def fetch(sites: list[SiteLike], now: datetime) -> list[Observation]:
    """Module-level ingestion interface using settings from the environment."""
    global _default_feed
    if _default_feed is None:
        _default_feed = EarthquakeFeed.from_settings(get_ingestion_settings())
    return _default_feed.fetch(sites, now)
