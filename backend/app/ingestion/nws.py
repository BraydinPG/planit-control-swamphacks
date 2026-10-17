"""Minimal HTTP client for the NWS API (api.weather.gov).

NWS needs no key but requires an identifying User-Agent. Every failure becomes a
`FeedError` so adapters can mark the feed unavailable instead of guessing.
"""

from threading import Lock
from typing import Any

import httpx

from app.ingestion.base import FeedError, SiteLike
from app.ingestion.settings import IngestionSettings


class NwsClient:
    def __init__(
        self,
        user_agent: str | None,
        base_url: str = "https://api.weather.gov",
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._user_agent = user_agent
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._transport = transport
        self._points: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    @classmethod
    def from_settings(cls, settings: IngestionSettings) -> "NwsClient":
        return cls(settings.nws_user_agent, settings.nws_base_url, settings.nws_timeout_seconds)

    def get_json(self, url_or_path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        if not self._user_agent:
            raise FeedError("NWS_USER_AGENT is not set")
        url = url_or_path if url_or_path.startswith("http") else self._base_url + url_or_path
        headers = {"User-Agent": self._user_agent, "Accept": "application/geo+json"}
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                response = client.get(url, params=params, headers=headers)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise FeedError(f"NWS request failed: {type(exc).__name__}") from exc
        if not isinstance(payload, dict):
            raise FeedError("NWS returned an unexpected payload")
        return payload

    def point(self, site: SiteLike) -> dict[str, Any]:
        """`/points` properties for a site. Cached per site because gridpoints rarely change."""
        with self._lock:
            cached = self._points.get(site.id)
        if cached is not None:
            return cached
        properties = self.get_json(f"/points/{site.lat:.4f},{site.lon:.4f}").get("properties")
        if not isinstance(properties, dict):
            raise FeedError("NWS point lookup returned no properties")
        with self._lock:
            self._points[site.id] = properties
        return properties
