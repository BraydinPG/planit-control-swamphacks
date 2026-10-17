"""Live lightning from NOAA GOES GLM on AWS Open Data (T045A).

Source: GLM Level 2 flashes (GLM-L2-LCFA) in the public buckets noaa-goes19 (GOES-East)
and noaa-goes18 (GOES-West). Each satellite writes one netCDF4/HDF5 file every 20
seconds. `GlmPoller` lists new files, reads each flash centroid and first-event time
with h5py, and submits flashes within the lightning search radius of a known site
through `lightning.submit_strike(..., simulated=False)`.

Limits to keep in mind:

- GLM detects total lightning, including in-cloud flashes, not only ground strikes.
  Flash positions are centroids with roughly 8 km resolution.
- Files arrive about 20 seconds after their window ends, so live strikes lag by
  roughly 20–60 seconds.
- Where both satellites see a flash, it is submitted once (same time and place).

Coverage: `covered_since(now)` is the time since which every configured satellite has
been read without a gap, or None when any satellite is failing or behind. The lightning
feed uses it so a "no lightning" reading never claims more time than was watched. On a
cold start or after a long gap, only the last GLM_BACKFILL_MINUTES are read.
"""

import io
import re
import threading
import xml.etree.ElementTree as ElementTree
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.ingestion.base import FeedError, SiteLike
from app.ingestion.geo import distance_miles
from app.ingestion.json_client import JsonClient

PRODUCT = "GLM-L2-LCFA"
FILE_SECONDS = 20
J2000 = datetime(2000, 1, 1, 12, tzinfo=UTC)
MAX_LATENCY = timedelta(minutes=3)
DUPLICATE_SECONDS = 2.0
DUPLICATE_MILES = 6.0
_S3 = "{http://s3.amazonaws.com/doc/2006-03-01/}"
_START = re.compile(r"_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{2})(\d)_")

SubmitStrike = Callable[[float, float, datetime], Any]


@dataclass(frozen=True)
class Flash:
    lat: float
    lon: float
    time: datetime


@dataclass
class _Satellite:
    name: str
    last_key: str | None = None
    covered_since: datetime | None = None
    covered_until: datetime | None = None
    healthy: bool = False


def file_start(key: str) -> datetime | None:
    """Scan start time from a GLM file name, e.g. ..._s20262900700000_... is 07:00:00.0."""
    match = _START.search(key)
    if match is None:
        return None
    year, day, hour, minute, second, tenth = (int(part) for part in match.groups())
    return datetime(year, 1, 1, hour, minute, second, tenth * 100_000, tzinfo=UTC) + timedelta(
        days=day - 1
    )


def parse_flashes(data: bytes) -> list[Flash]:
    """Flash centroids and first-event times from one GLM-L2-LCFA file."""
    import h5py

    try:
        with h5py.File(io.BytesIO(data), "r") as glm:
            lats = glm["flash_lat"][()].tolist()
            lons = glm["flash_lon"][()].tolist()
            offsets = _unpacked(glm["flash_time_offset_of_first_event"])
            quality = _unpacked(glm["flash_quality_flag"], scaled=False)
            base = J2000 + timedelta(seconds=float(glm["product_time"][()]))
    except (OSError, KeyError, ValueError, TypeError) as exc:
        raise ValueError(f"Unreadable GLM file: {exc}") from exc
    flashes = []
    for lat, lon, offset, flag in zip(lats, lons, offsets, quality, strict=True):
        if flag == 0xFFFF or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        flashes.append(Flash(float(lat), float(lon), base + timedelta(seconds=offset)))
    return flashes


class GlmPoller:
    def __init__(
        self,
        http: JsonClient,
        submit: SubmitStrike,
        satellites: Sequence[str] = ("goes19", "goes18"),
        search_radius_miles: float = 30.0,
        backfill: timedelta = timedelta(minutes=5),
        bucket_url: str = "https://noaa-{satellite}.s3.amazonaws.com",
    ) -> None:
        self.http = http
        self.submit = submit
        self.search_radius_miles = search_radius_miles
        self.backfill = backfill
        self.bucket_url = bucket_url
        self._satellites = [_Satellite(name) for name in satellites]
        self._recent: list[Flash] = []
        self._sites: list[SiteLike] = []
        self._lock = threading.Lock()
        self._poll_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.has_polled = False

    def poll_once(self, sites: Sequence[SiteLike], now: datetime) -> int:
        """Read new files from every satellite. Returns the number of strikes submitted."""
        submitted = 0
        with self._poll_lock:
            for satellite in self._satellites:
                try:
                    submitted += self._poll(satellite, sites, now)
                    satellite.healthy = True
                except FeedError:
                    satellite.healthy = False
            self.has_polled = True
        return submitted

    def covered_since(self, now: datetime) -> datetime | None:
        """Start of gap-free coverage across all satellites, or None if any is not live."""
        with self._poll_lock:
            starts = []
            for satellite in self._satellites:
                if not satellite.healthy or satellite.covered_since is None:
                    return None
                if satellite.covered_until is None or now - satellite.covered_until > MAX_LATENCY:
                    return None
                starts.append(satellite.covered_since)
        return max(starts) if starts else None

    def track(self, sites: Sequence[SiteLike], interval_seconds: float = FILE_SECONDS) -> None:
        """Remember the sites to watch and start the background poller once."""
        with self._lock:
            self._sites = list(sites)
            if self._thread is not None:
                return
            self._thread = threading.Thread(
                target=self._run, args=(interval_seconds,), name="glm-poller", daemon=True
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self, interval_seconds: float) -> None:
        while not self._stop.is_set():
            with self._lock:
                sites = list(self._sites)
            try:
                self.poll_once(sites, datetime.now(UTC))
            except Exception:  # never let one bad poll kill the thread
                for satellite in self._satellites:
                    satellite.healthy = False
            self._stop.wait(interval_seconds)

    def _poll(self, satellite: _Satellite, sites: Sequence[SiteLike], now: datetime) -> int:
        earliest = now - self.backfill
        last_start = file_start(satellite.last_key) if satellite.last_key else None
        resume = last_start is not None and last_start >= earliest
        keys = self._new_keys(satellite, last_start if resume else earliest, now)
        keys = [key for key in keys if (file_start(key) or earliest) >= earliest]
        if not keys:
            return 0
        if not resume:
            satellite.covered_since = file_start(keys[0])
        window = timedelta(seconds=FILE_SECONDS)
        submitted = 0
        for key in keys:
            start = file_start(key) or now
            data = self.http.get_bytes(f"{self._bucket(satellite)}/{key}")
            satellite.last_key = key
            if satellite.covered_until and start - satellite.covered_until > timedelta(seconds=1):
                satellite.covered_since = start  # files were missing: coverage restarts here
            try:
                flashes = parse_flashes(data)
            except ValueError:
                satellite.covered_since = start + window  # unreadable window is a gap
                continue
            satellite.covered_until = start + window
            submitted += self._submit_near(flashes, sites)
        return submitted

    def _new_keys(self, satellite: _Satellite, since: datetime, now: datetime) -> list[str]:
        keys: list[str] = []
        hour = since.replace(minute=0, second=0, microsecond=0)
        while hour <= now:
            params = {"list-type": "2", "prefix": f"{PRODUCT}/{hour:%Y/%j/%H}/"}
            if satellite.last_key:
                params["start-after"] = satellite.last_key
            keys += _listed_keys(self.http.get_bytes(self._bucket(satellite), params))
            hour += timedelta(hours=1)
        return sorted(key for key in keys if key.endswith(".nc"))

    def _submit_near(self, flashes: list[Flash], sites: Sequence[SiteLike]) -> int:
        radius = self.search_radius_miles
        degrees = radius / 69.0
        submitted = 0
        for flash in flashes:
            near = any(
                abs(site.lat - flash.lat) <= degrees
                and distance_miles(site.lat, site.lon, flash.lat, flash.lon) <= radius
                for site in sites
            )
            if not near or self._is_duplicate(flash):
                continue
            self.submit(flash.lat, flash.lon, flash.time)
            submitted += 1
        return submitted

    def _is_duplicate(self, flash: Flash) -> bool:
        """Both satellites can report one flash; keep the first copy."""
        cutoff = flash.time - timedelta(minutes=5)
        self._recent = [f for f in self._recent if f.time >= cutoff]
        for seen in self._recent:
            close_in_time = abs((seen.time - flash.time).total_seconds()) <= DUPLICATE_SECONDS
            if close_in_time and (
                distance_miles(seen.lat, seen.lon, flash.lat, flash.lon) <= DUPLICATE_MILES
            ):
                return True
        self._recent.append(flash)
        return False

    def _bucket(self, satellite: _Satellite) -> str:
        return self.bucket_url.format(satellite=satellite.name)


def _listed_keys(body: bytes) -> list[str]:
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as exc:
        raise FeedError("GLM bucket listing is not valid XML") from exc
    return [node.text for node in root.iter(f"{_S3}Key") if node.text]


def _unpacked(variable: Any, scaled: bool = True) -> list[float]:
    """Apply netCDF `_Unsigned`, `scale_factor`, and `add_offset`, which h5py leaves packed."""
    raw = variable[()].tolist()
    unsigned = _attr(variable, "_Unsigned") == "true"
    values = [v & 0xFFFF if unsigned and v < 0 else v for v in raw]
    if not scaled:
        return values
    scale = float(_attr(variable, "scale_factor", 1.0))
    offset = float(_attr(variable, "add_offset", 0.0))
    return [v * scale + offset for v in values]


def _attr(variable: Any, name: str, default: Any = None) -> Any:
    value = variable.attrs.get(name, default)
    if isinstance(value, bytes):
        return value.decode()
    if hasattr(value, "tolist"):
        value = value.tolist()
        return value[0] if isinstance(value, list) else value
    return value
