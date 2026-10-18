"""Hurricane feed (T045B): NHC active storms plus NWS tropical alerts.

Two sources, each with its own `FeedCache`, so an NHC outage never marks the NWS
alerts stale and the reverse:

- NHC `CurrentStorms.json`, fetched once per refresh. Each active storm whose center is
  within HURRICANE_SEARCH_RADIUS_MILES of a site becomes a `hurricane` Observation:
  `value` is the current intensity in knots, `lat`/`lon` the storm center, and
  `observed_at` the NHC advisory time. The search radius is wider than the prototype
  notice distance in spec.md and is not a rule setting.
- NWS active alerts for the site point: Hurricane Warning, Hurricane Watch, Tropical
  Storm Warning, and Tropical Storm Watch. `value` is the event name.

A successful fetch with nothing found returns one explicit "none" Observation per
source. A failed fetch reads stale, then unavailable. Never treat a failure as "no storm".
"""

from datetime import datetime
from typing import Any

from app.ingestion import runtime
from app.ingestion.base import FeedError, SiteLike
from app.ingestion.cache import FeedCache
from app.ingestion.geo import direction_from, distance_miles
from app.ingestion.json_client import JsonClient, parse_time
from app.ingestion.nws import NwsClient
from app.ingestion.settings import IngestionSettings, get_ingestion_settings
from app.schemas import DataState, HazardType, Observation

NHC_SOURCE = "NHC"
NWS_SOURCE = "NWS"
TROPICAL_EVENTS = (
    "Hurricane Warning",
    "Hurricane Watch",
    "Tropical Storm Warning",
    "Tropical Storm Watch",
)
NO_NWS_ALERTS = "No active NWS hurricane or tropical storm alerts"
CLASSIFICATIONS = {
    "HU": "Hurricane",
    "TS": "Tropical Storm",
    "TD": "Tropical Depression",
    "STS": "Subtropical Storm",
    "STD": "Subtropical Depression",
    "PTC": "Post-Tropical Cyclone",
    "PC": "Potential Tropical Cyclone",
    "TY": "Typhoon",
}


class HurricaneFeed:
    def __init__(
        self,
        http: JsonClient,
        nws: NwsClient,
        nhc_cache: FeedCache,
        nws_cache: FeedCache,
        storms_url: str = "https://www.nhc.noaa.gov/CurrentStorms.json",
        search_radius_miles: float = 300.0,
    ) -> None:
        self.http = http
        self.nws = nws
        self.nhc_cache = nhc_cache
        self.nws_cache = nws_cache
        self.storms_url = storms_url
        self.search_radius_miles = search_radius_miles

    @classmethod
    def from_settings(cls, settings: IngestionSettings) -> "HurricaneFeed":
        def cache(source: str) -> FeedCache:
            return FeedCache(
                source, HazardType.HURRICANE, settings.stale_after, settings.unavailable_after
            )

        return cls(
            JsonClient.from_settings(settings),
            NwsClient.from_settings(settings),
            cache(NHC_SOURCE),
            cache(NWS_SOURCE),
            settings.nhc_storms_url,
            settings.hurricane_search_radius_miles,
        )

    def fetch(self, sites: list[SiteLike], now: datetime) -> list[Observation]:
        """Ingestion interface. NHC is fetched once; NWS alerts once per site."""
        try:
            storms: list[dict[str, Any]] | FeedError = self._active_storms()
        except FeedError as exc:
            storms = exc

        def nhc_site(site: SiteLike, now: datetime) -> list[Observation]:
            if isinstance(storms, FeedError):
                raise storms
            return self.storms_near(site, storms, now)

        with runtime.round_scope():

            def per_site(site, at):
                return self.nhc_cache.refresh(site, at, nhc_site) + self.nws_cache.refresh(
                    site, at, self.nws_alerts
                )

            return [
                o
                for rows in runtime.ordered_map(
                    lambda site: per_site(site, now),
                    sites,
                    get_ingestion_settings().feed_site_workers,
                )
                for o in rows
            ]

    def storms_near(
        self, site: SiteLike, storms: list[dict[str, Any]], now: datetime
    ) -> list[Observation]:
        observations = [obs for storm in storms if (obs := self._storm(site, storm)) is not None]
        if observations:
            return observations
        return [
            _none(
                site,
                NHC_SOURCE,
                f"No active NHC storms within {self.search_radius_miles:g} mi",
                now,
            )
        ]

    def nws_alerts(self, site: SiteLike, now: datetime) -> list[Observation]:
        payload = self.nws.active_alerts(site, now)
        features = payload.get("features")
        if not isinstance(features, list):
            raise FeedError("NWS alerts response has no features list")
        observations = [
            obs for feature in features if (obs := _alert(site, feature, now)) is not None
        ]
        return observations or [_none(site, NWS_SOURCE, NO_NWS_ALERTS, now)]

    def _active_storms(self) -> list[dict[str, Any]]:
        storms = self.http.get_json(self.storms_url).get("activeStorms")
        if not isinstance(storms, list):
            raise FeedError("NHC response has no activeStorms list")
        return [storm for storm in storms if isinstance(storm, dict)]

    def _storm(self, site: SiteLike, storm: dict[str, Any]) -> Observation | None:
        lat, lon = _number(storm.get("latitudeNumeric")), _number(storm.get("longitudeNumeric"))
        observed_at = parse_time(storm.get("lastUpdate"))
        if lat is None or lon is None or observed_at is None:
            return None
        miles = distance_miles(site.lat, site.lon, lat, lon)
        if miles > self.search_radius_miles:
            return None
        kind = CLASSIFICATIONS.get(str(storm.get("classification")), "Storm")
        knots = _number(storm.get("intensity"))
        strength = f", {knots:g} kt" if knots is not None else ""
        where = f"{miles:.0f} mi {direction_from(site.lat, site.lon, lat, lon)} of site"
        storm_id = str(storm.get("id") or storm.get("name") or "unknown")
        return Observation(
            id=f"nhc:{site.id}:{storm_id}:{observed_at.isoformat()}",
            site_id=site.id,
            source=NHC_SOURCE,
            hazard_type=HazardType.HURRICANE,
            value=knots,
            unit="kt" if knots is not None else None,
            label=f"{kind} {storm.get('name') or storm_id}{strength}, {where}",
            source_ref=storm_id,
            lat=lat,
            lon=lon,
            observed_at=observed_at,
            data_state=DataState.OBSERVED,
        )


def _alert(site: SiteLike, feature: Any, now: datetime) -> Observation | None:
    props = feature.get("properties") if isinstance(feature, dict) else None
    if not isinstance(props, dict) or props.get("event") not in TROPICAL_EVENTS:
        return None
    alert_id = props.get("id") or feature.get("id")
    return Observation(
        id=f"nws-tropical:{site.id}:{alert_id}",
        site_id=site.id,
        source=NWS_SOURCE,
        hazard_type=HazardType.HURRICANE,
        value=props["event"],
        label=props.get("headline") or props["event"],
        source_ref=alert_id,
        lat=site.lat,
        lon=site.lon,
        observed_at=parse_time(props.get("sent") or props.get("effective")) or now,
        valid_at=parse_time(props.get("ends") or props.get("expires")),
        data_state=DataState.OBSERVED,
    )


def _none(site: SiteLike, source: str, label: str, now: datetime) -> Observation:
    return Observation(
        id=f"{source.lower()}-hurricane:{site.id}:none:{now.isoformat()}",
        site_id=site.id,
        source=source,
        hazard_type=HazardType.HURRICANE,
        value=None,
        label=label,
        lat=site.lat,
        lon=site.lon,
        observed_at=now,
        data_state=DataState.OBSERVED,
    )


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


_default_feed: HurricaneFeed | None = None


def fetch(sites: list[SiteLike], now: datetime) -> list[Observation]:
    """Module-level ingestion interface using settings from the environment."""
    global _default_feed
    if _default_feed is None:
        _default_feed = HurricaneFeed.from_settings(get_ingestion_settings())
    return _default_feed.fetch(sites, now)
