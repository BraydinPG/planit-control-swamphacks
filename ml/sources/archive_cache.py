"""Bounded serial official-source retrieval with durable checksum receipts."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ml.provision import file_sha256

OFFICIAL_HOSTS = {"www.ncei.noaa.gov", "www.nhc.noaa.gov", "ftp.nhc.noaa.gov",
                  "services3.arcgis.com", "www.arcgis.com", "www.weather.gov",
                  "waterservices.usgs.gov", "api.waterdata.usgs.gov", "firms.modaps.eosdis.nasa.gov",
                  "api.weather.gov", "api.tidesandcurrents.noaa.gov", "www.ndbc.noaa.gov",
                  "earthquake.usgs.gov", "services.swpc.noaa.gov", "www.eia.gov"}


def fetch_cached(url: str, cache_dir: Path, *, filename: str | None = None,
                 expected_sha256: str | None = None, max_bytes: int = 16 * 1024 * 1024,
                 timeout: float = 25, retries: int = 3) -> tuple[Path, dict]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in OFFICIAL_HOSTS:
        raise ValueError("Historical downloads require an allowlisted official HTTPS source")
    name = filename or hashlib.sha256(url.encode()).hexdigest() + ".cache"
    if Path(name).name != name:
        raise ValueError("cache filename must be a basename")
    cache_dir.mkdir(parents=True, exist_ok=True)
    path, receipt_path = cache_dir / name, cache_dir / (name + ".receipt.json")
    if path.exists():
        if not receipt_path.exists():
            raise ValueError("Unreceipted cached source preserved; cannot establish provenance")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt["url"] != url or file_sha256(path) != receipt["sha256"]:
            raise ValueError("Cached source checksum/URL mismatch; file preserved")
        if expected_sha256 and receipt["sha256"] != expected_sha256:
            raise ValueError("Cached source does not match pinned revision")
        return path, {**receipt, "cached": True}
    error = None
    for attempt in range(retries):
        try:
            print(f"[source] {name}: request {attempt + 1}/{retries}", flush=True)
            with urlopen(Request(url, headers={"User-Agent": "PlanIT-Control-ML/1.0 historical-research"}), timeout=timeout) as response:
                if int(response.headers.get("Content-Length", "0")) > max_bytes:
                    raise ValueError("Source exceeds bounded download size")
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise ValueError("Source exceeds bounded download size")
            checksum = hashlib.sha256(body).hexdigest()
            if expected_sha256 and checksum != expected_sha256:
                raise ValueError("Downloaded source differs from pinned SHA-256")
            with path.open("xb") as stream:
                stream.write(body)
            receipt = {"url": url, "file": name, "bytes": len(body), "sha256": checksum,
                       "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                       "historical_asof_availability_verified": False}
            receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
            return path, {**receipt, "cached": False}
        except HTTPError as failure:
            error = failure
            if failure.code not in (429, 500, 502, 503, 504):
                raise
        except (URLError, TimeoutError, OSError) as failure:
            error = failure
        if attempt + 1 < retries:
            time.sleep(min(5, .5 * 2 ** attempt))
    raise RuntimeError(f"Official historical source unavailable after {retries} attempts") from error
