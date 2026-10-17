"""T045A: live NOAA GOES GLM lightning, read from GLM-shaped HDF5 files built in memory."""

import io
from datetime import datetime, timedelta

import h5py
import httpx
import numpy as np
import pytest

from app.ingestion import glm, lightning
from app.ingestion.glm import J2000, GlmPoller, file_start, parse_flashes
from app.ingestion.json_client import JsonClient
from app.ingestion.lightning import LightningFeed, StrikeStore
from app.schemas import DataState, HazardType
from tests.feed_fakes import cache, near
from tests.nws_fakes import NOW, Site

SCALE, OFFSET = 0.00038148, -5.0
BUCKET = "https://noaa-{satellite}.s3.amazonaws.com"


def glm_file(start: datetime, flashes: list[tuple[float, float, float]]) -> bytes:
    """A GLM-L2-LCFA-shaped file: packed unsigned int16 times, as in the real product."""
    lats = [lat for lat, _, _ in flashes]
    lons = [lon for _, lon, _ in flashes]
    packed = [round((seconds - OFFSET) / SCALE) for _, _, seconds in flashes]
    buffer = io.BytesIO()
    with h5py.File(buffer, "w") as f:
        f["flash_lat"] = np.array(lats, dtype="float32")
        f["flash_lon"] = np.array(lons, dtype="float32")
        times = f.create_dataset(
            "flash_time_offset_of_first_event", data=np.array(packed, "uint16").view("int16")
        )
        times.attrs["scale_factor"] = np.array([SCALE], dtype="float32")
        times.attrs["add_offset"] = np.array([OFFSET], dtype="float32")
        times.attrs["_Unsigned"] = "true"
        quality = f.create_dataset("flash_quality_flag", data=np.zeros(len(flashes), "int16"))
        quality.attrs["_Unsigned"] = "true"
        f["product_time"] = (start - J2000).total_seconds()
    return buffer.getvalue()


def key(satellite: str, start: datetime) -> str:
    tag = "G19" if satellite == "goes19" else "G18"
    stamp = f"{start:%Y%j%H%M%S}{start.microsecond // 100_000}"
    return f"GLM-L2-LCFA/{start:%Y/%j/%H}/OR_GLM-L2-LCFA_{tag}_s{stamp}_e{stamp}_c{stamp}.nc"


class FakeBucket:
    """S3 ListObjectsV2 (prefix, start-after) and GET for the GLM buckets."""

    def __init__(self) -> None:
        self.files: dict[str, dict[str, bytes]] = {"goes19": {}, "goes18": {}}
        self.fail: set[str] = set()

    def add(self, satellite: str, start: datetime, flashes=()) -> str:
        name = key(satellite, start)
        self.files[satellite][name] = glm_file(start, list(flashes))
        return name

    def handler(self, request: httpx.Request) -> httpx.Response:
        satellite = request.url.host.split(".")[0].removeprefix("noaa-")
        if satellite in self.fail:
            return httpx.Response(503)
        files = self.files[satellite]
        path = request.url.path.lstrip("/")
        if path:
            return (
                httpx.Response(200, content=files[path]) if path in files else httpx.Response(404)
            )
        prefix = request.url.params.get("prefix", "")
        after = request.url.params.get("start-after", "")
        keys = sorted(k for k in files if k.startswith(prefix) and k > after)
        contents = "".join(f"<Contents><Key>{k}</Key></Contents>" for k in keys)
        xml = (
            '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
            f"{contents}</ListBucketResult>"
        )
        return httpx.Response(200, content=xml.encode())

    def poller(self, store: StrikeStore, satellites=("goes19",)) -> GlmPoller:
        client = JsonClient("PlanIT Control tests", transport=httpx.MockTransport(self.handler))
        return GlmPoller(
            client,
            lambda lat, lon, time: store.submit(lat, lon, time, simulated=False),
            satellites,
            search_radius_miles=30,
            backfill=timedelta(minutes=5),
            bucket_url=BUCKET,
        )


def feed(store: StrikeStore, live: GlmPoller | None) -> LightningFeed:
    return LightningFeed(
        store,
        cache(lightning.REPLAY_SOURCE, HazardType.LIGHTNING_STRIKE),
        30,
        timedelta(minutes=60),
        live,
    )


def test_parses_flash_positions_and_unpacked_times() -> None:
    start = NOW - timedelta(seconds=40)
    [early, late] = parse_flashes(glm_file(start, [(25.7, -80.5, -1.1), (26.0, -81.0, 18.25)]))
    assert early.lat == pytest.approx(25.7, abs=1e-4)
    assert early.time == pytest.approx(
        start - timedelta(seconds=1.1), abs=timedelta(milliseconds=1)
    )
    assert late.time == pytest.approx(
        start + timedelta(seconds=18.25), abs=timedelta(milliseconds=1)
    )


def test_unreadable_file_raises_value_error() -> None:
    with pytest.raises(ValueError):
        parse_flashes(b"not an hdf5 file")


def test_file_start_reads_the_scan_time_from_the_name() -> None:
    name = "GLM-L2-LCFA/2026/290/07/OR_GLM-L2-LCFA_G19_s20262900700200_e2026_c2026.nc"
    assert file_start(name) == datetime.fromisoformat("2026-10-17T07:00:20+00:00")


def test_live_flash_near_a_site_arrives_as_an_observed_strike() -> None:
    bucket, store = FakeBucket(), StrikeStore()
    flash_lat, flash_lon = near(45, 5.0)
    bucket.add("goes19", NOW - timedelta(seconds=40), [(flash_lat, flash_lon, 3.0)])
    bucket.add("goes19", NOW - timedelta(seconds=20), [(*near(0, 200), 1.0)])  # far away
    poller = bucket.poller(store)

    assert poller.poll_once([Site()], NOW) == 1
    [reading] = feed(store, poller).fetch([Site()], NOW)
    assert reading.source == "GOES GLM"
    assert reading.simulated is False
    assert reading.data_state is DataState.OBSERVED
    assert reading.value == pytest.approx(5.0, abs=0.1)
    assert reading.label == "Strike 5.0 mi NE (GOES GLM)"


def test_quiet_live_coverage_reports_only_the_minutes_watched() -> None:
    bucket, store = FakeBucket(), StrikeStore()
    for seconds in range(180, 0, -20):
        bucket.add("goes19", NOW - timedelta(seconds=seconds))
    poller = bucket.poller(store)
    poller.poll_once([Site()], NOW)

    [reading] = feed(store, poller).fetch([Site()], NOW)
    assert reading.label == "No lightning within 30 mi in the last 3 min (GOES GLM)"
    assert reading.data_state is DataState.OBSERVED
    assert reading.simulated is False


def test_failing_glm_falls_back_to_the_labeled_replay() -> None:
    bucket, store = FakeBucket(), StrikeStore()
    bucket.add("goes19", NOW - timedelta(seconds=60))
    bucket.fail.add("goes19")
    poller = bucket.poller(store)
    poller.poll_once([Site()], NOW)

    [reading] = feed(store, poller).fetch([Site()], NOW)
    assert reading.simulated is True
    assert reading.data_state is DataState.SIMULATED
    assert reading.label.endswith("(live lightning unavailable)")


def test_before_the_first_poll_the_fallback_says_starting() -> None:
    poller = FakeBucket().poller(StrikeStore())
    [reading] = feed(StrikeStore(), poller).fetch([Site()], NOW)
    assert reading.label.endswith("(live lightning starting)")
    assert reading.simulated is True


def test_coverage_requires_every_satellite() -> None:
    bucket, store = FakeBucket(), StrikeStore()
    for seconds in (180, 160, 140):
        bucket.add("goes19", NOW - timedelta(seconds=seconds))
        bucket.add("goes18", NOW - timedelta(seconds=seconds))
    bucket.fail.add("goes18")
    poller = bucket.poller(store, ("goes19", "goes18"))
    poller.poll_once([Site()], NOW)
    assert poller.covered_since(NOW) is None


def test_missing_files_restart_coverage() -> None:
    bucket, store = FakeBucket(), StrikeStore()
    bucket.add("goes19", NOW - timedelta(seconds=240))
    bucket.add("goes19", NOW - timedelta(seconds=60))  # 160 s of files missing before this
    bucket.add("goes19", NOW - timedelta(seconds=40))
    poller = bucket.poller(store)
    poller.poll_once([Site()], NOW)
    assert poller.covered_since(NOW) == NOW - timedelta(seconds=60)


def test_new_files_are_read_once_across_polls() -> None:
    bucket, store = FakeBucket(), StrikeStore()
    bucket.add("goes19", NOW - timedelta(seconds=60), [(*near(90, 3.0), 2.0)])
    poller = bucket.poller(store)
    assert poller.poll_once([Site()], NOW) == 1
    assert poller.poll_once([Site()], NOW) == 0
    bucket.add("goes19", NOW - timedelta(seconds=40), [(*near(90, 4.0), 2.0)])
    assert poller.poll_once([Site()], NOW + timedelta(seconds=20)) == 1


def test_a_flash_seen_by_both_satellites_is_submitted_once() -> None:
    bucket, store = FakeBucket(), StrikeStore()
    lat, lon = near(90, 3.0)
    bucket.add("goes19", NOW - timedelta(seconds=60), [(lat, lon, 5.0)])
    bucket.add("goes18", NOW - timedelta(seconds=60), [(lat + 0.01, lon, 5.2)])
    poller = bucket.poller(store, ("goes19", "goes18"))
    assert poller.poll_once([Site()], NOW) == 1


def test_files_older_than_backfill_are_skipped_on_cold_start() -> None:
    bucket, store = FakeBucket(), StrikeStore()
    bucket.add("goes19", NOW - timedelta(minutes=30), [(*near(90, 3.0), 2.0)])
    bucket.add("goes19", NOW - timedelta(seconds=60))
    poller = bucket.poller(store)
    assert poller.poll_once([Site()], NOW) == 0
    assert poller.covered_since(NOW) == NOW - timedelta(seconds=60)


def test_settings_build_a_live_feed_by_default() -> None:
    from app.ingestion.settings import IngestionSettings

    live = LightningFeed.from_settings(IngestionSettings(_env_file=None), StrikeStore()).live
    assert isinstance(live, glm.GlmPoller)
    off = IngestionSettings(_env_file=None, lightning_live_enabled=False)
    assert LightningFeed.from_settings(off, StrikeStore()).live is None
