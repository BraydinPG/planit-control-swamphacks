"""Per-feed cache of the last successful readings, with stale and unavailable states.

One `FeedCache` per feed, so a failing feed never marks another feed stale. Rules:

- A successful refresh stores readings with their fetch time.
- A failed refresh never returns current data: it returns the last readings marked
  stale, or an unavailable placeholder when nothing usable is cached.
- Readings older than `stale_after` are stale. Older than `unavailable_after`, they are
  dropped and the feed reads as unavailable.

The cache lives in process memory. Persisting Observations is the caller's job.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock

from app.ingestion.base import SiteLike, unavailable_observation
from app.schemas import DataState, HazardType, Observation

logger = logging.getLogger(__name__)

FetchSite = Callable[[SiteLike, datetime], list[Observation]]


@dataclass(frozen=True)
class _Entry:
    fetched_at: datetime
    observations: tuple[Observation, ...]


class FeedCache:
    def __init__(
        self,
        source: str,
        hazard_type: HazardType,
        stale_after: timedelta,
        unavailable_after: timedelta,
    ) -> None:
        if unavailable_after < stale_after:
            raise ValueError("unavailable_after must be at least stale_after")
        self.source = source
        self.hazard_type = hazard_type
        self.stale_after = stale_after
        self.unavailable_after = unavailable_after
        self._entries: dict[str, _Entry] = {}
        self._lock = Lock()

    def refresh(self, site: SiteLike, now: datetime, fetch_site: FetchSite) -> list[Observation]:
        """Fetch fresh readings for one site, falling back to cached data on any failure."""
        try:
            observations = fetch_site(site, now)
        except Exception as exc:
            # A failed fetch is never silent: it falls back to stale or unavailable readings.
            logger.warning(
                "%s %s fetch failed for %s; using cached readings: %s: %s",
                self.source,
                self.hazard_type.value,
                site.id,
                type(exc).__name__,
                str(exc)[:200],
            )
            return self._fallback(site, now)
        stamped = tuple(
            o if o.fetched_at else o.model_copy(update={"fetched_at": now}) for o in observations
        )
        with self._lock:
            self._entries[site.id] = _Entry(now, stamped)
        return list(stamped)

    def snapshot(self, site: SiteLike, now: datetime) -> list[Observation]:
        """Cached readings for one site without fetching, with freshness applied."""
        with self._lock:
            entry = self._entries.get(site.id)
        if entry is None:
            return [self._unavailable(site, now)]
        age = now - entry.fetched_at
        if age > self.unavailable_after:
            return [self._unavailable(site, now)]
        if age > self.stale_after:
            return [_as_stale(o) for o in entry.observations]
        return list(entry.observations)

    def _fallback(self, site: SiteLike, now: datetime) -> list[Observation]:
        with self._lock:
            entry = self._entries.get(site.id)
        if entry is None or now - entry.fetched_at > self.unavailable_after:
            return [self._unavailable(site, now)]
        return [_as_stale(o) for o in entry.observations]

    def _unavailable(self, site: SiteLike, now: datetime) -> Observation:
        return unavailable_observation(
            site,
            self.source,
            self.hazard_type,
            f"{self.source} {self.hazard_type} unavailable",
            now,
        )


def _as_stale(observation: Observation) -> Observation:
    if observation.data_state is DataState.UNAVAILABLE:
        return observation
    return observation.model_copy(update={"data_state": DataState.STALE})
