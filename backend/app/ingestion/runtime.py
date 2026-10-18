"""Internal refresh context, bounded I/O workers and credential-free diagnostics.

No ORM objects or sessions belong in worker threads. API Observation/DataState
contracts do not change; these metrics describe retrieval, not hazard severity.
"""

import json
import logging
import re
import time
from collections import Counter, defaultdict, deque
from collections.abc import Callable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from dataclasses import dataclass, field
from math import isfinite
from threading import Event, Lock
from typing import Any, TypeVar

from app.ingestion.base import FeedError, SiteLike

log = logging.getLogger(__name__)
T = TypeVar("T")
R = TypeVar("R")


@dataclass(frozen=True)
class SiteSnapshot:
    id: str
    lat: float
    lon: float
    region: str | None = None


def valid_site(site: SiteLike) -> bool:
    return (
        isinstance(site.id, str)
        and bool(site.id.strip())
        and isinstance(site.lat, int | float)
        and not isinstance(site.lat, bool)
        and isinstance(site.lon, int | float)
        and not isinstance(site.lon, bool)
        and isfinite(site.lat)
        and isfinite(site.lon)
        and -90 <= site.lat <= 90
        and -180 <= site.lon <= 180
    )


def region_of(site: SiteLike) -> str:
    match = re.match(r"eia860m-([A-Z]{2})-", site.id if isinstance(site.id, str) else "")
    return match[1] if match else (getattr(site, "region", None) or "unknown")


@dataclass
class RoundState:
    deadline: float
    cancel: Event = field(default_factory=Event)
    requests: list[dict] = field(default_factory=list)
    outcomes: list[dict] = field(default_factory=list)
    invalid_responses: list[dict] = field(default_factory=list)
    phases: Counter = field(default_factory=Counter)
    memo: dict[Any, Future] = field(default_factory=dict)
    lock: Lock = field(default_factory=Lock)
    active_requests: int = 0
    peak_requests: int = 0

    def check(self):
        if self.cancel.is_set():
            raise FeedError("Refresh cancelled")
        if time.monotonic() >= self.deadline:
            raise FeedError("Refresh network budget exhausted")

    def report(self) -> dict:
        requests = defaultdict(list)
        for row in self.requests:
            requests[row["feed"]].append(row)
        return {
            "peak_http_concurrency": self.peak_requests,
            "phase_seconds": dict(self.phases),
            "requests": {
                name: {
                    "attempts": len(rows),
                    "average_seconds": sum(r["duration_seconds"] for r in rows) / len(rows),
                    "maximum_seconds": max(r["duration_seconds"] for r in rows),
                    "http_status": dict(Counter(str(r["http_status"]) for r in rows)),
                    "failures_by_exception": dict(
                        Counter(r["exception_type"] for r in rows if r["exception_type"])
                    ),
                    "failures_by_region": dict(
                        Counter(r.get("region", "shared") for r in rows if r["exception_type"])
                    ),
                }
                for name, rows in requests.items()
            },
            "site_feed_outcomes": self.outcomes,
            "invalid_responses": self.invalid_responses,
        }


_round: ContextVar[RoundState | None] = ContextVar("feed_round", default=None)
_labels: ContextVar[dict | None] = ContextVar("feed_labels", default=None)


def state() -> RoundState | None:
    return _round.get()


@contextmanager
def round_scope(budget_seconds: float = 480, cancel: Event | None = None):
    existing = state()
    if existing is not None:
        yield existing
        return
    value = RoundState(time.monotonic() + budget_seconds, cancel or Event())
    token = _round.set(value)
    try:
        yield value
    finally:
        _round.reset(token)


@contextmanager
def labels(**values):
    token = _labels.set({**(_labels.get() or {}), **values})
    try:
        yield
    finally:
        _labels.reset(token)


def site_labels(site: SiteLike):
    return labels(site_id=site.id, region=region_of(site), affected_group="site")


@contextmanager
def http_activity():
    current = state()
    if current:
        with current.lock:
            current.active_requests += 1
            current.peak_requests = max(current.peak_requests, current.active_requests)
    try:
        yield
    finally:
        if current:
            with current.lock:
                current.active_requests -= 1


def event(name: str, *, failure=False, **values):
    row = {"event": name, **(_labels.get() or {}), **values}
    # Values must be normalized by the caller: never pass raw exceptions, headers,
    # response bodies, connection strings or arbitrary external diagnostic text.
    (log.warning if failure else log.info)(json.dumps(row, sort_keys=True, default=str))
    current = state()
    if current:
        with current.lock:
            if name == "feed_http_attempt":
                current.requests.append(row)
            elif name == "feed_site_result":
                current.outcomes.append(row)
            elif name == "feed_invalid_response":
                current.invalid_responses.append(row)


def once(key: Any, operation: Callable[[], R]) -> R:
    """Single-flight successful or failed resource, only within this refresh round."""
    current = state()
    if current is None:
        return operation()
    current.check()
    with current.lock:
        future = current.memo.get(key)
        owner = future is None
        if owner:
            future = current.memo[key] = Future()
    if owner:
        try:
            future.set_result(operation())
        except BaseException as exc:
            future.set_exception(exc)
            raise
    # Deadline/cancellation checks while another worker owns the request.
    while not future.done():
        current.check()
        try:
            return future.result(timeout=0.1)
        except TimeoutError:
            continue
    return future.result()


def ordered_map(function: Callable[[T], R], items: list[T], workers: int) -> Iterator[R]:
    """At most `workers` submitted operations, stable output order and context propagation."""
    if workers == 1 or len(items) < 2:
        for item in items:
            yield function(item)
        return
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="feed-io") as pool:
        pending = deque()
        iterator = iter(items)

        def submit(item):
            return pool.submit(copy_context().run, function, item)

        for _ in range(min(workers, len(items))):
            pending.append(submit(next(iterator)))
        try:
            while pending:
                yield pending.popleft().result()
                item = next(iterator, None)
                if item is not None:
                    pending.append(submit(item))
        finally:
            for future in pending:
                future.cancel()
