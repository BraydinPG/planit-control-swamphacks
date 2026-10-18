"""Minimal HTTP client for the NWS API (api.weather.gov).

NWS needs no key but requires an identifying User-Agent. Every failure becomes a
`FeedError` so adapters can mark the feed unavailable instead of guessing.
"""

from collections import OrderedDict
from concurrent.futures import Future
from copy import deepcopy
from threading import Lock
from time import monotonic
from typing import Any

import httpx

from app.ingestion import runtime
from app.ingestion.base import FeedError, SiteLike
from app.ingestion.http import HttpPolicy, PooledHttp, RequestFailure, invalid_response
from app.ingestion.settings import IngestionSettings


class NwsClient:
    def __init__(
        self,
        user_agent: str | None,
        base_url: str = "https://api.weather.gov",
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
        *,
        policy: HttpPolicy | None = None,
        point_cache_seconds: float = 86400,
        not_covered_cache_seconds: float = 3600,
        station_cache_seconds: float = 3600,
    ) -> None:
        self._user_agent = user_agent
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._transport = transport
        self.policy = policy or HttpPolicy(
            read_seconds=timeout_seconds, min_interval_seconds=0 if transport else 0.25
        )
        self._http = PooledHttp(self.policy, transport)
        self.point_cache_seconds = point_cache_seconds
        self.not_covered_cache_seconds = not_covered_cache_seconds
        self.station_cache_seconds = station_cache_seconds
        self._points = OrderedDict()
        self._lock = Lock()

    @classmethod
    def from_settings(cls, settings: IngestionSettings) -> "NwsClient":
        return cls(
            settings.nws_user_agent,
            settings.nws_base_url,
            settings.nws_timeout_seconds,
            policy=HttpPolicy(
                max_connections=settings.nws_http_connections,
                min_interval_seconds=settings.nws_min_interval_seconds,
                connect_seconds=settings.feed_http_connect_seconds,
                read_seconds=settings.nws_timeout_seconds,
                retries=settings.feed_http_max_retries,
                budget_seconds=settings.feed_http_budget_seconds,
                backoff_seconds=settings.feed_http_backoff_seconds,
            ),
            point_cache_seconds=settings.nws_point_cache_seconds,
            not_covered_cache_seconds=settings.nws_not_covered_cache_seconds,
            station_cache_seconds=settings.nws_station_cache_seconds,
        )

    def get_json(self, url_or_path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        if not self._user_agent:
            raise FeedError("NWS_USER_AGENT is not set")
        url = url_or_path if url_or_path.startswith("http") else self._base_url + url_or_path
        target, base = httpx.URL(url), httpx.URL(self._base_url)
        if (
            (target.scheme, target.host, target.port) != (base.scheme, base.host, base.port)
            or target.username
            or target.password
        ):
            raise FeedError("NWS metadata endpoint has an untrusted origin")
        headers = {"User-Agent": self._user_agent, "Accept": "application/geo+json"}
        response = self._http.get(url, params, headers, provider="NWS")
        try:
            payload = response.json()
        except ValueError:
            invalid_response(response, "NWS", "InvalidJSON")
        if not isinstance(payload, dict):
            invalid_response(response, "NWS", "InvalidPayload")
        return deepcopy(payload)

    def point(self, site: SiteLike) -> dict[str, Any]:
        """Coordinate-keyed, expiring single-flight mapping; never permanent negative cache."""
        if not runtime.valid_site(site):
            raise FeedError("Invalid site coordinates")

        def lookup():
            properties = self.get_json(f"/points/{site.lat:.4f},{site.lon:.4f}").get("properties")
            if not isinstance(properties, dict):
                raise FeedError("NWS point lookup returned no properties")
            return properties

        return self._metadata(("point", site.lat, site.lon), self.point_cache_seconds, lookup)

    def stations(self, url: str) -> dict:
        return self._metadata(
            ("stations", url), self.station_cache_seconds, lambda: self.get_json(url)
        )

    def _collection(self, params: dict) -> dict:
        url = "/alerts/active"
        features = []
        seen = set()
        for _ in range(30):
            payload = self.get_json(url, params=params)
            rows = payload.get("features")
            if not isinstance(rows, list):
                raise FeedError("NWS alerts response has no features list")
            features.extend(rows)
            next_url = (payload.get("pagination") or {}).get("next")
            if not next_url:
                return {"features": features}
            if (
                not isinstance(next_url, str)
                or httpx.URL(next_url).host != httpx.URL(self._base_url).host
                or next_url in seen
            ):
                raise FeedError("Invalid NWS alert pagination")
            seen.add(next_url)
            url, params = next_url, None
        raise FeedError("NWS alert pagination limit reached")

    def active_alerts(self, site: SiteLike, now) -> dict:
        from app.ingestion.alert_matching import active, matches

        def point_query():
            payload = self._collection({"point": f"{site.lat:.4f},{site.lon:.4f}"})
            rows = []
            for feature in payload["features"]:
                if not active(feature, now):
                    continue
                hit = matches(feature, site, set())
                if feature.get("geometry") is not None and hit is None:
                    raise FeedError("NWS alert geometry cannot be verified")
                if feature.get("geometry") is None or hit:
                    rows.append(feature)
            return {"features": rows}

        if not runtime.valid_site(site):
            raise FeedError("Invalid site coordinates")
        try:
            point = self.point(site)
        except FeedError:
            # Weather-grid coverage and alert coverage are different capabilities.
            return point_query()
        zones = {
            point[k]
            for k in ("forecastZone", "county", "fireWeatherZone")
            if isinstance(point.get(k), str) and point[k].startswith(self._base_url + "/zones/")
        }
        if not zones:
            return point_query()
        rows = {}
        for zone in sorted(zones):
            for feature in self._collection({"zone": zone.rsplit("/", 1)[-1]})["features"]:
                if not active(feature, now):
                    continue
                hit = matches(feature, site, zones)
                if hit is None:
                    return point_query()
                if hit:
                    props = feature["properties"]
                    rows[props.get("id") or feature["id"]] = feature
        return {"features": list(rows.values())}

    def _metadata(self, key, ttl, fetch):
        with self._lock:
            entry = self._points.get(key)
            if entry is not None and entry[0] <= monotonic() and entry[1].done():
                del self._points[key]
                entry = None
            owner = entry is None
            if owner:
                future = Future()
                self._points[key] = (monotonic() + ttl, future)
            else:
                future = entry[1]
            # Keep in-flight lookups; evict only completed entries.
            while len(self._points) > 4096:
                oldest = next((k for k, v in self._points.items() if v[1].done()), None)
                if oldest is None:
                    break
                del self._points[oldest]
        if owner:
            try:
                future.set_result(fetch())
            except BaseException as exc:
                future.set_exception(exc)
                with self._lock:
                    if isinstance(exc, RequestFailure) and exc.not_covered:
                        self._points[key] = (monotonic() + self.not_covered_cache_seconds, future)
                    else:
                        self._points.pop(key, None)
                raise
        while not future.done():
            if runtime.state():
                runtime.state().check()
            try:
                return deepcopy(future.result(timeout=0.1))
            except TimeoutError:
                continue
        return deepcopy(future.result())

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
