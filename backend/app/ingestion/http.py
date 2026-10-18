"""Pooled synchronous HTTP, provider gates, bounded retries and safe diagnostics."""

import logging
import random
import re
import time
import weakref
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from math import isfinite
from threading import BoundedSemaphore, Lock
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from app.ingestion import runtime
from app.ingestion.base import FeedError

RETRY_STATUS = {429, 500, 502, 503, 504}
SAFE_QUERY = {
    "point",
    "zone",
    "area",
    "event",
    "active",
    "format",
    "bBox",
    "parameterCd",
    "siteStatus",
    "sites",
    "limit",
}


def safe_url(value: str) -> str:
    """Keep searchable endpoints/ordinary feed filters; never userinfo or secrets."""
    try:
        url = urlsplit(value)
        host = url.hostname or "unknown"
        if url.port:
            host += f":{url.port}"
        path = re.sub(
            r"(?i)(/(?:token|api[_-]?key|password|secret|auth)/)[^/]+", r"\1REDACTED", url.path
        )
        query = urlencode(
            [(k, v if k in SAFE_QUERY else "REDACTED") for k, v in parse_qsl(url.query)]
        )
        return urlunsplit((url.scheme, host, path, query, ""))
    except ValueError:
        return "invalid-endpoint"


class RequestFailure(FeedError):
    def __init__(self, fields: dict, *, not_covered: bool = False):
        self.fields = fields
        self.not_covered = not_covered
        super().__init__(
            f"{fields['provider']} request failed: "
            f"{fields.get('http_status') or fields['exception_type']}"
        )


@dataclass
class HttpPolicy:
    max_connections: int = 4
    min_interval_seconds: float = 0.25
    connect_seconds: float = 3.0
    read_seconds: float = 10.0
    retries: int = 1
    budget_seconds: float = 20.0
    backoff_seconds: float = 0.5
    max_response_bytes: int = 20_000_000


class _Gate:
    def __init__(self, connections: int):
        self.slots = BoundedSemaphore(connections)
        self.lock = Lock()
        self.next_request = 0.0
        self.cooldown = 0.0


_gates: dict[tuple, _Gate] = {}
_gates_lock = Lock()


def _wait(seconds: float, deadline: float):
    current = runtime.state()
    remaining = min(seconds, deadline - time.monotonic())
    if remaining < seconds or remaining < 0:
        raise FeedError("Request time budget exhausted")
    if current:
        if current.cancel.wait(remaining):
            raise FeedError("Refresh cancelled")
        current.check()
    elif remaining:
        time.sleep(remaining)


def retry_after(value: str | None, now: datetime | None = None) -> float | None:
    if not value:
        return None
    try:
        seconds = float(value)
        return max(0.0, seconds) if isfinite(seconds) else None
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
            return max(0.0, (parsed - (now or datetime.now(UTC))).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return None


class PooledHttp:
    def __init__(self, policy: HttpPolicy, transport: httpx.BaseTransport | None = None):
        _install_redaction()
        self.policy = policy
        self.client = httpx.Client(
            transport=transport,
            timeout=httpx.Timeout(policy.read_seconds, connect=policy.connect_seconds),
            limits=httpx.Limits(
                max_connections=policy.max_connections,
                max_keepalive_connections=policy.max_connections,
                keepalive_expiry=30,
            ),
            follow_redirects=False,
        )
        # The finalizer owns only the underlying client, never a bound reference to self.
        self._finalizer = weakref.finalize(self, self.client.close)

    def close(self):
        self._finalizer()

    @contextmanager
    def _slot(self, host: str, deadline: float):
        key = (host, self.policy.max_connections, self.policy.min_interval_seconds)
        with _gates_lock:
            gate = _gates.setdefault(key, _Gate(self.policy.max_connections))
        acquired = False
        try:
            while not acquired:
                current = runtime.state()
                if current:
                    current.check()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise FeedError("Request time budget exhausted")
                acquired = gate.slots.acquire(timeout=min(0.1, remaining))
            while True:
                with gate.lock:
                    wait = max(gate.next_request, gate.cooldown) - time.monotonic()
                    if wait <= 0:
                        gate.next_request = time.monotonic() + self.policy.min_interval_seconds
                        break
                _wait(wait, deadline)
            yield gate
        finally:
            if acquired:
                gate.slots.release()

    def get(self, url: str, params: dict | None, headers: dict, *, provider: str) -> httpx.Response:
        # Never memoize credentials into logs. Keyed on the exact request, not site ID.
        request = self.client.build_request("GET", url, params=params, headers=headers)
        key = ("GET", str(request.url), tuple(sorted(headers.items())))
        return runtime.once(key, lambda: self._request(request, provider))

    def _request(self, request: httpx.Request, provider: str) -> httpx.Response:
        current = runtime.state()
        deadline = min(
            time.monotonic() + self.policy.budget_seconds,
            current.deadline if current else float("inf"),
        )
        endpoint = safe_url(str(request.url))
        last = None
        for attempt in range(1, self.policy.retries + 2):
            start = time.monotonic()
            status = None
            response = None
            exception_type = None
            retryable = False
            delay = 0.0
            gate = None
            try:
                with self._slot(request.url.host, deadline) as gate, runtime.http_activity():
                    remaining = deadline - time.monotonic()
                    request.extensions["timeout"] = {
                        "connect": min(self.policy.connect_seconds, remaining),
                        "read": min(self.policy.read_seconds, remaining),
                        "write": min(self.policy.read_seconds, remaining),
                        "pool": remaining,
                    }
                    response = self.client.send(request, stream=True)
                    status = response.status_code
                    try:
                        body = bytearray()
                        for chunk in response.iter_bytes():
                            if time.monotonic() >= deadline:
                                raise FeedError("Request time budget exhausted")
                            body.extend(chunk)
                            if len(body) > self.policy.max_response_bytes:
                                raise FeedError("Feed response exceeds size limit")
                        # A detached response can be safely reused across parsing workers.
                        # iter_bytes() already decoded gzip/deflate, so drop the encoding
                        # headers; otherwise httpx decodes the body a second time and fails.
                        plain_headers = [
                            (k, v)
                            for k, v in response.headers.multi_items()
                            if k.lower() not in ("content-encoding", "content-length")
                        ]
                        detached = httpx.Response(
                            status, headers=plain_headers, content=bytes(body), request=request
                        )
                        detached.extensions["feed_attempt"] = {
                            "attempt": attempt,
                            "duration_seconds": time.monotonic() - start,
                            "retry_attempted": attempt > 1,
                        }
                    finally:
                        response.close()
                    response = detached
                    response.raise_for_status()
                    return response
            except (httpx.HTTPError, FeedError) as exc:
                exception_type = type(exc).__name__
                retryable = (
                    isinstance(exc, httpx.ConnectError | httpx.ConnectTimeout | httpx.ReadTimeout)
                    or status in RETRY_STATUS
                )
                delay = retry_after(response.headers.get("Retry-After")) if response else None
                if delay is None:
                    delay = self.policy.backoff_seconds * 2 ** (attempt - 1) + random.uniform(
                        0, self.policy.backoff_seconds
                    )
                if status in {429, 503} and gate:
                    with gate.lock:
                        gate.cooldown = max(gate.cooldown, time.monotonic() + delay)
                last = {
                    "provider": provider,
                    "method": "GET",
                    "endpoint": endpoint,
                    "http_status": status,
                    "exception_type": exception_type,
                    "attempt": attempt,
                    "duration_seconds": time.monotonic() - start,
                    "retry_attempted": attempt > 1,
                    "will_retry": retryable
                    and attempt <= self.policy.retries
                    and time.monotonic() + delay < deadline,
                }
            finally:
                runtime.event(
                    "feed_http_attempt",
                    failure=exception_type is not None,
                    feed=(runtime._labels.get() or {}).get("feed", provider),
                    provider=provider,
                    method="GET",
                    endpoint=endpoint,
                    http_status=status,
                    exception_type=exception_type,
                    attempt=attempt,
                    duration_seconds=time.monotonic() - start,
                    retry_attempted=attempt > 1,
                    will_retry=bool(exception_type and last and last.get("will_retry")),
                )
            if not last["will_retry"]:
                not_covered = False
                if status == 404 and "/points/" in request.url.path and response is not None:
                    # Generic 404 and InvalidPoint alone do not establish missing coverage.
                    try:
                        problem = response.json()
                        detail = str(problem.get("detail", "")).lower()
                        not_covered = str(problem.get("type", "")).endswith("/InvalidPoint") and (
                            "not covered" in detail
                            or ("outside" in detail and "coverage" in detail)
                        )
                    except (ValueError, AttributeError, httpx.ResponseNotRead):
                        pass
                raise RequestFailure(last, not_covered=not_covered) from None
            try:
                _wait(delay, deadline)
            except FeedError:
                raise RequestFailure({**last, "will_retry": False}) from None
        raise RequestFailure(last)  # defensive; bounded loop always returns or raises


def invalid_response(response: httpx.Response, provider: str, kind: str):
    """Parsing fails after HTTP success: retain endpoint/status without counting two requests."""
    fields = {
        "provider": provider,
        "method": "GET",
        "endpoint": safe_url(str(response.request.url)),
        "http_status": response.status_code,
        "exception_type": kind,
        "attempt": 1,
        "retry_attempted": False,
        "will_retry": False,
        **response.extensions.get("feed_attempt", {}),
    }
    runtime.event("feed_invalid_response", failure=True, **fields)
    raise RequestFailure(fields) from None


class _RedactHttpxUrls(logging.Filter):
    def filter(self, record):
        if isinstance(record.args, tuple):
            record.args = tuple(
                safe_url(str(v)) if isinstance(v, httpx.URL) else v for v in record.args
            )
        return True


def _install_redaction():
    logger = logging.getLogger("httpx")
    if not any(isinstance(f, _RedactHttpxUrls) for f in logger.filters):
        logger.addFilter(_RedactHttpxUrls())
