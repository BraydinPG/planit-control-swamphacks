"""Offline, synthetic 256-site refresh benchmark. No sockets, secrets or shared DB.

Run the identical script on the recorded baseline ref and optimized ref. Sixteen
synthetic clusters deliberately share provider resources; this is not a live SLA.
"""

import argparse
import hashlib
import json
import logging
import os
import platform
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from threading import Lock
from unittest.mock import patch

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import models as db
from app.ingestion.earthquakes import EarthquakeFeed
from app.ingestion.flood_gauges import FloodGaugeFeed
from app.ingestion.hurricanes import HurricaneFeed
from app.ingestion.json_client import JsonClient
from app.ingestion.nws import NwsClient
from app.ingestion.nws_alerts import NwsFloodAlertFeed
from app.ingestion.nws_weather import NwsWeatherFeed
from app.ingestion.settings import get_ingestion_settings
from app.schemas import HazardType
from app.services import refresh
from tests.feed_fakes import NHC_URL, QUAKE_URL, WATER_URL, cache, gauge_series, quakes, storms
from tests.nws_fakes import NOW, Site, alerts, hourly, latest


def run(latency: float = 0.01, paced: bool = False, workers: int = 6) -> dict:
    with patch.dict(
        os.environ,
        {
            "FEED_SITE_WORKERS": str(workers),
            "FEED_ROUND_BUDGET_SECONDS": "480",
            "FEED_REFRESH_ENABLED": "false",
            "BRIEFING_SCHEDULE_ENABLED": "false",
        },
    ):
        get_ingestion_settings.cache_clear()
        try:
            return _run(latency, paced, workers)
        finally:
            get_ingestion_settings.cache_clear()


def _run(latency, paced, workers):
    backend = Path(__file__).resolve().parents[1]
    source_hashes = {
        str(path.relative_to(backend)).replace("\\", "/"): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted((backend / "app/ingestion").glob("*.py"))
        + [backend / "app/services/refresh.py", Path(__file__).resolve()]
    }
    lock = Lock()
    requests = Counter()
    durations = defaultdict(list)
    active = peak = 0
    centers = [(25.65 + (i // 4) * 0.5, -80.49 - (i % 4) * 0.5) for i in range(16)]
    sites = [
        Site(f"benchmark-{i:03d}", centers[i // 16][0] + (i % 16) * 0.0001, centers[i // 16][1])
        for i in range(256)
    ]
    gauges = []
    for i, (lat, lon) in enumerate(centers):
        row = gauge_series(f"0000{i:04d}", 0)
        row["sourceInfo"]["geoLocation"]["geogLocation"] = {"latitude": lat, "longitude": lon}
        gauges.append(row)

    def handler(request):
        nonlocal active, peak
        key = (
            "NWS"
            if request.url.host == "api.weather.gov"
            else (
                "USGS-gauges"
                if request.url.path == "/nwis/iv/"
                else "NHC"
                if request.url.host == "www.nhc.noaa.gov"
                else "USGS-earthquakes"
            )
        )
        start = time.perf_counter()
        with lock:
            requests[key] += 1
            active += 1
            peak = max(peak, active)
        try:
            time.sleep(latency)  # Explicit synthetic provider latency, never a real request.
            path = request.url.path
            if path.startswith("/points/"):
                lat, lon = map(float, path.rsplit("/", 1)[1].split(","))
                group = min(
                    range(16), key=lambda i: abs(lat - centers[i][0]) + abs(lon - centers[i][1])
                )
                payload = {
                    "properties": {
                        "forecastHourly": f"https://api.weather.gov/gridpoints/TEST/{group},0/forecast/hourly",
                        "observationStations": f"https://api.weather.gov/gridpoints/TEST/{group},0/stations",
                    }
                }
            elif path.endswith("/stations"):
                group = int(path.split("/")[3].split(",")[0])
                payload = {
                    "features": [
                        {
                            "id": f"https://api.weather.gov/stations/TEST{group}",
                            "properties": {"stationIdentifier": f"TEST{group}"},
                        }
                    ]
                }
            elif path.endswith("/observations/latest"):
                group = int(path.split("/")[2].replace("TEST", ""))
                payload = latest()
                payload["geometry"]["coordinates"] = [centers[group][1], centers[group][0]]
            elif path.endswith("/forecast/hourly"):
                payload = hourly()
            elif path == "/alerts/active":
                payload = alerts()
            elif request.url.host == "www.nhc.noaa.gov":
                payload = storms()
            elif path == "/nwis/iv/":
                west, south, east, north = map(float, request.url.params["bBox"].split(","))
                series = [
                    g
                    for g in gauges
                    if west <= g["sourceInfo"]["geoLocation"]["geogLocation"]["longitude"] <= east
                    and south <= g["sourceInfo"]["geoLocation"]["geogLocation"]["latitude"] <= north
                ]
                payload = {"value": {"timeSeries": series}}
            else:
                payload = quakes()
            return httpx.Response(200, json=payload)
        finally:
            with lock:
                active -= 1
                durations[key].append(time.perf_counter() - start)

    transport = httpx.MockTransport(handler)
    nws = NwsClient("PlanIT offline benchmark", transport=transport)
    http = JsonClient(transport=transport)
    # Optimized clients expose policy options. Disable pacing only in this explicit
    # synthetic benchmark; production defaults and tests exercise real rate controls.
    for client, interval in ((nws, 0.25), (http, 0.5)):
        if hasattr(client, "policy"):
            client.policy.min_interval_seconds = interval if paced else 0
    feed_objects = [
        ("weather", HazardType.WEATHER, NwsWeatherFeed(nws, cache("NWS", HazardType.WEATHER), 3)),
        (
            "flood-alert",
            HazardType.FLOOD_ALERT,
            NwsFloodAlertFeed(nws, cache("NWS", HazardType.FLOOD_ALERT)),
        ),
        (
            "hurricane",
            HazardType.HURRICANE,
            HurricaneFeed(
                http,
                nws,
                cache("NHC", HazardType.HURRICANE),
                cache("NWS", HazardType.HURRICANE),
                NHC_URL,
            ),
        ),
        (
            "earthquake",
            HazardType.EARTHQUAKE,
            EarthquakeFeed(http, cache("USGS", HazardType.EARTHQUAKE), QUAKE_URL),
        ),
        (
            "gauges",
            HazardType.FLOOD_GAUGE,
            FloodGaugeFeed(http, cache("USGS", HazardType.FLOOD_GAUGE), WATER_URL),
        ),
    ]
    fetch_seconds = {}
    coverage = {}
    signatures = {}

    def wrap(name, fetch):
        def measured(items, now):
            start = time.perf_counter()
            rows = fetch(items, now)
            fetch_seconds[name] = time.perf_counter() - start
            by_site = defaultdict(set)
            for row in rows:
                by_site[row.site_id].add(row.data_state.value)
            coverage[name] = dict(Counter(state for states in by_site.values() for state in states))
            signatures[name] = hashlib.sha256(
                json.dumps(
                    sorted((r.model_dump(mode="json") for r in rows), key=lambda r: r["id"]),
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            return rows

        return measured

    feeds = [refresh.Feed(name, kind, wrap(name, obj.fetch)) for name, kind, obj in feed_objects]
    phase = Counter()

    def timed(name, original):
        def call(*args, **kwargs):
            start = time.perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                phase[name] += time.perf_counter() - start

        return call

    engine = create_engine("sqlite://")  # Test database only; never application configuration.
    db.Base.metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False) as session:
            session.add_all(
                [
                    db.Site(
                        id=s.id,
                        name=s.id,
                        lat=s.lat,
                        lon=s.lon,
                        source="SYNTHETIC BENCHMARK",
                        location_type="power_plant",
                    )
                    for s in sites
                ]
            )
            session.add(
                db.Site(
                    id="benchmark-demo-excluded",
                    name="Excluded demo",
                    lat=25,
                    lon=-80,
                    source="SYNTHETIC",
                    location_type="demo_site",
                )
            )
            session.commit()
            with (
                patch.object(
                    refresh, "store_observations", timed("persistence", refresh.store_observations)
                ),
                patch.object(refresh, "score_site", timed("scoring", refresh.score_site)),
            ):
                start = time.perf_counter()
                result = refresh.refresh_all(session, NOW, feeds)
                elapsed = time.perf_counter() - start
            score_signature = hashlib.sha256(
                json.dumps(
                    sorted(
                        (s.site_id, s.risk_score, s.factor_contributions)
                        for s in session.scalars(select(db.HazardScore))
                    ),
                    sort_keys=True,
                ).encode()
            ).hexdigest()
    finally:
        engine.dispose()
        for client in (nws, http):
            if hasattr(client, "close"):
                client.close()
    result_report = asdict(result)
    # Full per-site diagnostic logs remain available to operators, but this benchmark
    # commits aggregate metrics and content hashes rather than 1,536 repetitive rows.
    result_report.get("metrics", {}).pop("site_feed_outcomes", None)
    return {
        "scope": (
            "OFFLINE SYNTHETIC: 256 sites in 16 shared-resource clusters; in-memory SQLite, "
            "mocked HTTP only; not a live-provider speed or coverage claim"
        ),
        "python_version": platform.python_version(),
        "source_sha256": source_hashes,
        "mock_request_latency_seconds": latency,
        "sites_processed": result.sites,
        "total_seconds": elapsed,
        "fetch_seconds": fetch_seconds,
        "database_and_processing_seconds": elapsed - sum(fetch_seconds.values()),
        "phase_seconds": dict(phase),
        "http_requests": dict(requests),
        "request_seconds": {
            k: {"average": sum(v) / len(v), "maximum": max(v)} for k, v in durations.items()
        },
        "peak_http_concurrency": peak,
        "coverage_site_states": coverage,
        "failed_sites": result.failed_sites,
        "failed_feeds": result.failed_feeds,
        "observation_sha256_by_feed": signatures,
        "site_score_sha256": score_signature,
        "timeout_count": 0,  # This workload injects latency only, not outages.
        "pacing": "Conservative production defaults"
        if paced
        else "Disabled for synthetic comparison",
        "configured_site_workers": workers,
        "lightning_scope": (
            "No lightning network adapter; alert rule runs unchanged on missing evidence"
        ),
        "result": result_report,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--latency", type=float, default=0.01)
    parser.add_argument(
        "--paced", action="store_true", help="Use default provider pacing (still mocks)"
    )
    parser.add_argument("--workers", type=int, choices=range(1, 17), default=6)
    args = parser.parse_args()
    logging.basicConfig(level=logging.ERROR)
    result = run(args.latency, args.paced, args.workers)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "sites_processed",
                    "total_seconds",
                    "http_requests",
                    "peak_http_concurrency",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
