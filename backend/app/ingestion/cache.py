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
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock

from app.ingestion import runtime
from app.ingestion.base import FeedError, SiteLike, unavailable_observation
from app.ingestion.settings import get_ingestion_settings
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
        self._entries: dict[tuple, _Entry] = {}
        self._lock = Lock()

    def refresh(self, site: SiteLike, now: datetime, fetch_site: FetchSite) -> list[Observation]:
        """Fetch fresh readings for one site, falling back to cached data on any failure."""
        with runtime.site_labels(site):
            return self._refresh(site, now, fetch_site)

    def _refresh(self, site, now, fetch_site):
        started = time.monotonic()
        try:
            if runtime.state():
                runtime.state().check()
            observations = fetch_site(site, now)
            if not observations or any(o.site_id != site.id for o in observations):
                raise FeedError("Feed returned missing or mismatched site evidence")
        except Exception as exc:
            outside = getattr(exc, "not_covered", False)
            rows = (
                [
                    self._unavailable(site, now).model_copy(
                        update={"label": f"{self.source}: Not covered by this provider"}
                    )
                ]
                if outside
                else self._fallback(site, now)
            )
            runtime.event(
                "feed_site_result",
                failure=True,
                source=self.source,
                hazard_type=self.hazard_type.value,
                **{
                    "exception_type": type(exc).__name__,
                    **{
                        k: v
                        for k, v in getattr(exc, "fields", {}).items()
                        if k != "duration_seconds"
                    },
                },
                final_state="not_covered" if outside else rows[0].data_state.value,
                states=sorted({r.data_state.value for r in rows}),
                duration_seconds=time.monotonic() - started,
            )
            return rows
        stamped = tuple(
            o if o.fetched_at else o.model_copy(update={"fetched_at": now}) for o in observations
        )
        with self._lock:
            self._entries[self._key(site)] = _Entry(now, stamped)
        runtime.event(
            "feed_site_result",
            source=self.source,
            hazard_type=self.hazard_type.value,
            states=sorted({r.data_state.value for r in stamped}),
            final_state="partial"
            if any(r.data_state is DataState.UNAVAILABLE for r in stamped)
            else "success",
            duration_seconds=time.monotonic() - started,
        )
        return list(stamped)

    def refresh_many(self, sites, now, fetch_site, *, workers=None):
        with runtime.round_scope():
            return [
                o
                for rows in runtime.ordered_map(
                    lambda site: self.refresh(site, now, fetch_site),
                    sites,
                    workers or get_ingestion_settings().feed_site_workers,
                )
                for o in rows
            ]

    @staticmethod
    def _key(site):
        return (site.id, site.lat, site.lon)

    def snapshot(self, site: SiteLike, now: datetime) -> list[Observation]:
        """Cached readings for one site without fetching, with freshness applied."""
        with self._lock:
            entry = self._entries.get(self._key(site))
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
            entry = self._entries.get(self._key(site))
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
