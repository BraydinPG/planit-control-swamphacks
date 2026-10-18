"""NWS severe-storm feed (T049C).

Active Tornado Warning, Tornado Watch, Severe Thunderstorm Warning and Severe
Thunderstorm Watch alerts for each site point, as `severe_storm` Observations whose
`value` is the event name. Only warnings qualify for the prototype stop-work rules in
`app.rules.stop_work`; watches are shown as readings only.

Follows `nws_alerts`: a successful fetch with no active alerts returns one
`NO_ACTIVE_ALERTS` Observation, so "no alerts" is never confused with "fetch failed"
(which is unavailable). Like the flood and tropical feeds, it makes its own NWS active-
alert lookup per site each refresh round.
"""

from datetime import datetime
from typing import Any

from app.ingestion.base import FeedError, SiteLike
from app.ingestion.cache import FeedCache
from app.ingestion.json_client import parse_time
from app.ingestion.nws import NwsClient
from app.ingestion.settings import IngestionSettings, get_ingestion_settings
from app.schemas import DataState, HazardType, Observation

SOURCE = "NWS"
STORM_EVENTS = frozenset(
    {
        "Tornado Warning",
        "Tornado Watch",
        "Severe Thunderstorm Warning",
        "Severe Thunderstorm Watch",
    }
)
NO_ACTIVE_ALERTS = "No active NWS tornado or severe thunderstorm alerts"


class NwsSevereStormFeed:
    def __init__(self, client: NwsClient, cache: FeedCache) -> None:
        self.client = client
        self.cache = cache

    @classmethod
    def from_settings(cls, settings: IngestionSettings) -> "NwsSevereStormFeed":
        cache = FeedCache(
            SOURCE, HazardType.SEVERE_STORM, settings.stale_after, settings.unavailable_after
        )
        return cls(NwsClient.from_settings(settings), cache)

    def fetch(self, sites: list[SiteLike], now: datetime) -> list[Observation]:
        """Ingestion interface. Failures fall back to stale or unavailable per site."""
        return self.cache.refresh_many(sites, now, self.fetch_site)

    def fetch_site(self, site: SiteLike, now: datetime) -> list[Observation]:
        payload = self.client.active_alerts(site, now)
        features = payload.get("features")
        if not isinstance(features, list):
            raise FeedError("NWS alerts response has no features list")
        observations = [
            obs for feature in features if (obs := _to_observation(site, feature, now)) is not None
        ]
        if observations:
            return observations
        return [
            Observation(
                id=f"nws-storm:{site.id}:none:{now.isoformat()}",
                site_id=site.id,
                source=SOURCE,
                hazard_type=HazardType.SEVERE_STORM,
                value=None,
                label=NO_ACTIVE_ALERTS,
                lat=site.lat,
                lon=site.lon,
                observed_at=now,
                data_state=DataState.OBSERVED,
            )
        ]


def _to_observation(site: SiteLike, feature: Any, now: datetime) -> Observation | None:
    props = feature.get("properties") if isinstance(feature, dict) else None
    if not isinstance(props, dict) or props.get("event") not in STORM_EVENTS:
        return None
    alert_id = props.get("id") or feature.get("id")
    return Observation(
        id=f"nws-storm:{site.id}:{alert_id}",
        site_id=site.id,
        source=SOURCE,
        hazard_type=HazardType.SEVERE_STORM,
        value=props["event"],
        label=props.get("headline") or props["event"],
        source_ref=alert_id,
        lat=site.lat,
        lon=site.lon,
        observed_at=parse_time(props.get("sent") or props.get("effective")) or now,
        valid_at=parse_time(props.get("ends") or props.get("expires")),
        data_state=DataState.OBSERVED,
    )


_default_feed: NwsSevereStormFeed | None = None


def fetch(sites: list[SiteLike], now: datetime) -> list[Observation]:
    """Module-level ingestion interface using settings from the environment."""
    global _default_feed
    if _default_feed is None:
        _default_feed = NwsSevereStormFeed.from_settings(get_ingestion_settings())
    return _default_feed.fetch(sites, now)
