"""Minimal JSON-over-HTTP client for the NHC and USGS feeds.

NWS requests go through `nws.NwsClient`. Every failure here becomes a `FeedError`, so
`FeedCache` marks the feed stale or unavailable instead of guessing.
"""

from datetime import datetime
from typing import Any

import httpx

from app.ingestion.base import FeedError
from app.ingestion.settings import IngestionSettings

DEFAULT_USER_AGENT = "PlanIT Control (SwampHacks prototype)"


class JsonClient:
    def __init__(
        self,
        user_agent: str | None = None,
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._user_agent = user_agent or DEFAULT_USER_AGENT
        self._timeout = timeout_seconds
        self._transport = transport

    @classmethod
    def from_settings(cls, settings: IngestionSettings) -> "JsonClient":
        return cls(settings.nws_user_agent, settings.feed_timeout_seconds)

    def get_json(self, url: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        try:
            payload = self._get(url, params, "application/json").json()
        except ValueError as exc:
            raise FeedError(f"{httpx.URL(url).host} returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise FeedError("Feed returned an unexpected payload")
        return payload

    def get_bytes(self, url: str, params: dict[str, str] | None = None) -> bytes:
        """Raw response body, e.g. an S3 listing or a GLM netCDF file."""
        return self._get(url, params, "*/*").content

    def _get(self, url: str, params: dict[str, str] | None, accept: str) -> httpx.Response:
        headers = {"User-Agent": self._user_agent, "Accept": accept}
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                response = client.get(url, params=params, headers=headers)
                response.raise_for_status()
                response.read()
        except httpx.HTTPError as exc:
            host = httpx.URL(url).host
            raise FeedError(f"{host} request failed: {type(exc).__name__}") from exc
        return response


def parse_time(value: Any) -> datetime | None:
    """Timezone-aware ISO-8601 time, or None. Naive times are rejected, not guessed."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None
