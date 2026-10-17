"""Lightning strike input, replay fixture (T045), and live GOES GLM lightning (T045A).

Strike input
    `submit_strike(lat, lon, time, simulated)` normalizes one strike (coordinates
    validated and rounded to 4 decimals, time converted to UTC) and adds it to an
    in-process strike store. The replay fixture and tests submit strikes this way.
    Simulated strikes carry `source="lightning-replay"`, `simulated=True`, and
    `data_state="simulated"`.

Replay fixture
    `fixtures/lightning_replay.json` lists strikes by bearing and distance from a site.
    `replay_strike(site, step, at)` places that step relative to the site and submits
    it, so the demo can show a strike, then a second strike that resets the countdown.

Site readings
    `fetch(sites, now)` returns, per site, every stored strike within
    LIGHTNING_SEARCH_RADIUS_MILES from the last LIGHTNING_LOOKBACK_MINUTES. Each
    Observation's `value` is the distance to the site in miles, and `lat`/`lon` are the
    strike location. When there are none, it returns one explicit "no strikes"
    Observation (see below for when it is live or simulated). The search radius is not
    the 10-mile stop-work rule; Rudra's rule applies that distance.

Live lightning (T045A)
    `glm.GlmPoller` reads NOAA GOES GLM flashes from AWS Open Data and submits those near
    known sites with `simulated=False`: `source="GOES GLM"`, `data_state="observed"`.
    It starts on the first `fetch()` when LIGHTNING_LIVE_ENABLED is true and runs in a
    background thread. GLM reports total lightning, including in-cloud flashes, at
    roughly 8 km resolution, with about 20–60 seconds of delay.

    The "no strikes" reading is live only while GLM coverage is gap-free, and it states
    how many minutes were actually watched. If GLM is disabled, starting up, failing, or
    behind, the reading falls back to the replay and stays labeled simulated, so it can
    never read as a live "no lightning". Replayed strikes work either way, for the demo.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any

from app.ingestion.base import SiteLike
from app.ingestion.cache import FeedCache
from app.ingestion.geo import destination, direction_from, distance_miles
from app.ingestion.glm import GlmPoller
from app.ingestion.json_client import JsonClient
from app.ingestion.settings import IngestionSettings, get_ingestion_settings
from app.schemas import DataState, HazardType, Observation

REPLAY_SOURCE = "lightning-replay"
LIVE_SOURCE = "GOES GLM"
REPLAY_PATH = Path(__file__).with_name("fixtures") / "lightning_replay.json"
STORE_RETENTION = timedelta(hours=24)


class StrikeStore:
    """Submitted strikes, newest last. Process memory only; old strikes are pruned."""

    def __init__(self) -> None:
        self._strikes: list[Observation] = []
        self._lock = Lock()

    def submit(self, lat: float, lon: float, time: datetime, simulated: bool) -> Observation:
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("Strike coordinates are out of range")
        if time.tzinfo is None:
            raise ValueError("Strike time must include a timezone")
        at = time.astimezone(UTC)
        lat, lon = round(lat, 4), round(lon, 4)
        strike = Observation(
            id=f"ltg:{at.isoformat()}:{lat},{lon}",
            source=REPLAY_SOURCE if simulated else LIVE_SOURCE,
            hazard_type=HazardType.LIGHTNING_STRIKE,
            lat=lat,
            lon=lon,
            observed_at=at,
            data_state=DataState.SIMULATED if simulated else DataState.OBSERVED,
            simulated=simulated,
            label="Lightning strike (replay)" if simulated else "Lightning flash (GOES GLM)",
        )
        with self._lock:
            self._strikes = [s for s in self._strikes if at - s.observed_at <= STORE_RETENTION]
            self._strikes.append(strike)
        return strike

    def between(self, start: datetime, end: datetime) -> list[Observation]:
        with self._lock:
            return [s for s in self._strikes if start < s.observed_at <= end]

    def clear(self) -> None:
        with self._lock:
            self._strikes.clear()


class LightningFeed:
    def __init__(
        self,
        store: StrikeStore,
        cache: FeedCache,
        search_radius_miles: float = 30.0,
        lookback: timedelta = timedelta(minutes=60),
        live: GlmPoller | None = None,
    ) -> None:
        self.store = store
        self.cache = cache
        self.search_radius_miles = search_radius_miles
        self.lookback = lookback
        self.live = live

    @classmethod
    def from_settings(cls, settings: IngestionSettings, store: StrikeStore) -> "LightningFeed":
        cache = FeedCache(
            REPLAY_SOURCE,
            HazardType.LIGHTNING_STRIKE,
            settings.stale_after,
            settings.unavailable_after,
        )
        live = None
        if settings.lightning_live_enabled:
            live = GlmPoller(
                JsonClient.from_settings(settings),
                lambda lat, lon, time: store.submit(lat, lon, time, simulated=False),
                [name.strip() for name in settings.glm_satellites.split(",") if name.strip()],
                settings.lightning_search_radius_miles,
                timedelta(minutes=settings.glm_backfill_minutes),
                settings.glm_bucket_url,
            )
        return cls(
            store,
            cache,
            settings.lightning_search_radius_miles,
            timedelta(minutes=settings.lightning_lookback_minutes),
            live,
        )

    def fetch(self, sites: list[SiteLike], now: datetime) -> list[Observation]:
        """Ingestion interface. Strikes near each site, or an explicit "none" reading."""
        return [o for site in sites for o in self.cache.refresh(site, now, self.fetch_site)]

    def fetch_site(self, site: SiteLike, now: datetime) -> list[Observation]:
        observations = []
        for strike in self.store.between(now - self.lookback, now):
            miles = distance_miles(site.lat, site.lon, strike.lat, strike.lon)
            if miles > self.search_radius_miles:
                continue
            direction = direction_from(site.lat, site.lon, strike.lat, strike.lon)
            suffix = "replay" if strike.simulated else "GOES GLM"
            observations.append(
                strike.model_copy(
                    update={
                        "id": f"{strike.id}:{site.id}",
                        "site_id": site.id,
                        "value": round(miles, 1),
                        "unit": "mi",
                        "label": f"Strike {miles:.1f} mi {direction} ({suffix})",
                        "source_ref": strike.id,
                    }
                )
            )
        if observations:
            return observations
        return [self._none(site, now)]

    def _none(self, site: SiteLike, now: datetime) -> Observation:
        radius = f"{self.search_radius_miles:g}"
        covered_since = self.live.covered_since(now) if self.live else None
        watched = min(self.lookback, now - covered_since) if covered_since else timedelta(0)
        if watched >= timedelta(minutes=1):
            minutes = int(watched.total_seconds() // 60)
            label = f"No lightning within {radius} mi in the last {minutes} min (GOES GLM)"
            source, state, simulated = LIVE_SOURCE, DataState.OBSERVED, False
        else:
            minutes = int(self.lookback.total_seconds() // 60)
            if self.live is None:
                reason = "live lightning not enabled"
            elif covered_since is None and self.live.has_polled:
                reason = "live lightning unavailable"
            else:
                reason = "live lightning starting"
            label = f"No replayed strikes within {radius} mi in the last {minutes} min ({reason})"
            source, state, simulated = REPLAY_SOURCE, DataState.SIMULATED, True
        return Observation(
            id=f"ltg:{site.id}:none:{now.isoformat()}",
            site_id=site.id,
            source=source,
            hazard_type=HazardType.LIGHTNING_STRIKE,
            value=None,
            label=label,
            lat=site.lat,
            lon=site.lon,
            observed_at=now,
            data_state=state,
            simulated=simulated,
        )


def replay_steps(path: Path = REPLAY_PATH) -> list[dict[str, Any]]:
    """The scripted replay strikes, in order."""
    return json.loads(path.read_text())["steps"]


_store = StrikeStore()
_default_feed: LightningFeed | None = None


def submit_strike(lat: float, lon: float, time: datetime, simulated: bool = True) -> Observation:
    """Ingestion interface. Normalize one strike and add it to the strike store."""
    return _store.submit(lat, lon, time, simulated)


def replay_strike(site: SiteLike, step: int, at: datetime) -> Observation:
    """Submit replay step `step` (0-based) as a simulated strike near `site` at `at`."""
    item = replay_steps()[step]
    lat, lon = destination(site.lat, site.lon, item["bearing_deg"], item["distance_mi"])
    return submit_strike(lat, lon, at, simulated=True)


def clear_strikes() -> None:
    """Forget submitted strikes, e.g. to restart the demo replay."""
    _store.clear()


def fetch(sites: list[SiteLike], now: datetime) -> list[Observation]:
    """Module-level ingestion interface using settings from the environment."""
    global _default_feed
    if _default_feed is None:
        _default_feed = LightningFeed.from_settings(get_ingestion_settings(), _store)
    if _default_feed.live is not None:
        _default_feed.live.track(sites, get_ingestion_settings().glm_poll_seconds)
    return _default_feed.fetch(sites, now)
