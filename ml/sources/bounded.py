"""Opt-in serial snapshots. No network access is used by inference or replay."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

HOSTS = frozenset(
    {
        "api.weather.gov",
        "api.waterdata.usgs.gov",
        "earthquake.usgs.gov",
        "services.swpc.noaa.gov",
        "www.tsunami.gov",
        "services3.arcgis.com",
        "droughtmonitor.unl.edu",
        "usdmdataservices.unl.edu",
        "hazards.fema.gov",
    }
)


def validate_url(url: str) -> str:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in HOSTS
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or parsed.fragment
        or any(ord(c) < 32 for c in url)
    ):
        raise ValueError("Snapshot destination is not an approved public HTTPS URL")
    if any(
        re.search(r"key|token|secret|password|email", key, re.I)
        for key, _ in parse_qsl(parsed.query)
    ):
        raise ValueError("Credential-bearing requests are not supported by public snapshots")
    return url


class RestrictedRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_LAST_REQUEST: dict[str, float] = {}


def snapshot(
    url: str,
    directory: Path,
    name: str,
    *,
    max_bytes: int = 8_000_000,
    timeout: float = 15,
    retries: int = 2,
) -> tuple[bytes, dict]:
    """Immutable capture with bounded retries; cached content must match its receipt."""
    validate_url(url)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}", name) or ".." in name:
        raise ValueError("Invalid snapshot basename")
    if not 1 <= max_bytes <= 16_000_000 or not 0 < timeout <= 30 or not 1 <= retries <= 3:
        raise ValueError("Snapshot bounds exceeded")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path, sidecar = directory / name, directory / (name + ".receipt.json")
    if path.exists():
        if path.stat().st_size > max_bytes or not sidecar.exists():
            raise ValueError("Oversized or unreceipted cache preserved")
        body = path.read_bytes()
        receipt = json.loads(sidecar.read_text(encoding="utf-8"))
        if receipt["url"] != url or hashlib.sha256(body).hexdigest() != receipt["sha256"]:
            raise ValueError("Snapshot identity mismatch; cache preserved")
        return body, {**receipt, "cached": True}
    host, opener = urlparse(url).hostname, build_opener(RestrictedRedirect())
    for attempt in range(retries):
        delay = max(0, 1.0 - (time.monotonic() - _LAST_REQUEST.get(host, 0)))
        if delay:
            time.sleep(delay)
        _LAST_REQUEST[host] = time.monotonic()
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": "PlanIT-Control-Research/2.1 (https://github.com/BraydinPG/planit-control-swamphacks)",
                    "Accept": "application/geo+json, application/json, application/xml;q=0.8",
                    "Accept-Encoding": "identity",
                },
            )
            with opener.open(request, timeout=timeout) as response:
                validate_url(response.geturl())
                if int(response.headers.get("Content-Length", "0")) > max_bytes:
                    raise ValueError("Response exceeds snapshot byte limit")
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise ValueError("Response exceeds snapshot byte limit")
                content_type = response.headers.get("Content-Type", "unknown")
            receipt = {
                "url": url,
                "file": name,
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "retrieved_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "content_type": content_type,
                "historical_availability_verified": False,
                "collection_policy": "serial; <=1 request/s/host; 15s timeout; 2 attempts; <=8MB default",
                "provider_rate_limit": "Provider limits apply; this local cap is not a provider quota guarantee",
                "use": "Agency attribution and product-specific terms; public research snapshot, no secrets",
            }
            path.write_bytes(body)
            sidecar.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
            return body, {**receipt, "cached": False}
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt + 1 == retries:
                raise RuntimeError(f"Official source HTTP {error.code}") from None
        except (URLError, TimeoutError, OSError):
            if attempt + 1 == retries:
                raise RuntimeError("Official source unavailable after bounded attempts") from None
        time.sleep(min(2, 0.5 * 2**attempt))
    raise RuntimeError("Snapshot unavailable")
