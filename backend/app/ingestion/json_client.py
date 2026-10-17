"""Minimal JSON-over-HTTP client for the NHC and USGS feeds.

NWS requests go through `nws.NwsClient`. Every failure here becomes a `FeedError`, so
`FeedCache` marks the feed stale or unavailable instead of guessing.
"""

from datetime import datetime
from typing import Any

import httpx

from app.ingestion.http import HttpPolicy, PooledHttp, invalid_response
from app.ingestion.settings import IngestionSettings

DEFAULT_USER_AGENT = "PlanIT Control (SwampHacks prototype)"


class JsonClient:
    def __init__(
        self,
        user_agent: str | None = None,
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
        *,
        policy: HttpPolicy | None = None,
    ) -> None:
        self._user_agent = user_agent or DEFAULT_USER_AGENT
        self._timeout = timeout_seconds
        self._transport = transport
        self.policy = policy or HttpPolicy(
            read_seconds=timeout_seconds,
            min_interval_seconds=0 if transport else 0.5,
            max_connections=2,
        )
        self._http = PooledHttp(self.policy, transport)

    @classmethod
    def from_settings(cls, settings: IngestionSettings) -> "JsonClient":
        return cls(
            settings.nws_user_agent,
            settings.feed_timeout_seconds,
            policy=HttpPolicy(
                max_connections=settings.usgs_http_connections,
                min_interval_seconds=settings.usgs_min_interval_seconds,
                connect_seconds=settings.feed_http_connect_seconds,
                read_seconds=settings.feed_timeout_seconds,
                retries=settings.feed_http_max_retries,
                budget_seconds=settings.feed_http_budget_seconds,
                backoff_seconds=settings.feed_http_backoff_seconds,
            ),
        )

    def get_json(self, url: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        response = self._get(url, params, "application/json")
        provider = httpx.URL(url).host or "JSON feed"
        try:
            payload = response.json()
        except ValueError:
            invalid_response(response, provider, "InvalidJSON")
        if not isinstance(payload, dict):
            invalid_response(response, provider, "InvalidPayload")
        return payload

    def get_bytes(self, url: str, params: dict[str, str] | None = None) -> bytes:
        """Raw response body, e.g. an S3 listing or a GLM netCDF file."""
        return self._get(url, params, "*/*").content

    def _get(self, url: str, params: dict[str, str] | None, accept: str) -> httpx.Response:
        headers = {"User-Agent": self._user_agent, "Accept": accept}
        return self._http.get(url, params, headers, provider=httpx.URL(url).host or "JSON feed")

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def parse_time(value: Any) -> datetime | None:
    """Timezone-aware ISO-8601 time, or None. Naive times are rejected, not guessed."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None
