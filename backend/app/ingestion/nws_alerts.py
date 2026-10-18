"""NWS flood-alert feed (T043A).

Active Flood Warning, Flash Flood Warning, and Flood Watch alerts for each site point.
A successful fetch with no active alerts returns one `NO_ACTIVE_ALERTS` Observation, so
"no alerts" is never confused with "fetch failed" (which is unavailable).
"""

from datetime import datetime
from typing import Any

from app.ingestion.base import FeedError, SiteLike
from app.ingestion.cache import FeedCache
from app.ingestion.nws import NwsClient
from app.ingestion.settings import IngestionSettings, get_ingestion_settings
from app.schemas import DataState, HazardType, Observation

SOURCE = "NWS"
FLOOD_EVENTS = frozenset({"Flood Warning", "Flash Flood Warning", "Flood Watch"})
NO_ACTIVE_ALERTS = "No active NWS flood alerts"


class NwsFloodAlertFeed:
    def __init__(self, client: NwsClient, cache: FeedCache) -> None:
        self.client = client
        self.cache = cache

    @classmethod
    def from_settings(cls, settings: IngestionSettings) -> "NwsFloodAlertFeed":
        cache = FeedCache(
            SOURCE, HazardType.FLOOD_ALERT, settings.stale_after, settings.unavailable_after
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
                id=f"nws-flood:{site.id}:none:{now.isoformat()}",
                site_id=site.id,
                source=SOURCE,
                hazard_type=HazardType.FLOOD_ALERT,
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
    if not isinstance(props, dict) or props.get("event") not in FLOOD_EVENTS:
        return None
    alert_id = props.get("id") or feature.get("id")
    return Observation(
        id=f"nws-flood:{site.id}:{alert_id}",
        site_id=site.id,
        source=SOURCE,
        hazard_type=HazardType.FLOOD_ALERT,
        value=props["event"],
        label=props.get("headline") or props["event"],
        source_ref=alert_id,
        lat=site.lat,
        lon=site.lon,
        observed_at=_parse_time(props.get("sent") or props.get("effective")) or now,
        valid_at=_parse_time(props.get("ends") or props.get("expires")),
        data_state=DataState.OBSERVED,
    )


_default_feed: NwsFloodAlertFeed | None = None


def fetch(sites: list[SiteLike], now: datetime) -> list[Observation]:
    """Module-level ingestion interface using settings from the environment."""
    global _default_feed
    if _default_feed is None:
        _default_feed = NwsFloodAlertFeed.from_settings(get_ingestion_settings())
    return _default_feed.fetch(sites, now)


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None
