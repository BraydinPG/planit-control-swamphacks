"""Bounded serial source snapshot for reproducible offline worker demonstrations."""

import hashlib
from datetime import datetime, timezone
import json
import time
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

from ml.config import PACKAGE_ROOT, RAW_DATA_DIR, REPORT_DIR
from ml.sources.archive_cache import fetch_cached
from ml.sources.eia_research import acquire as acquire_sites
from ml.sources.worker_feeds import (
    coops,
    earthquake_catalog,
    ndbc_observations,
    nws_alerts,
    nws_hourly,
    nws_observation,
    swpc_kp,
)
from ml.worker.schema import Evidence, SiteContext
from ml.worker.spatial import associate

REPORT = REPORT_DIR / "worker_outlook/feed_snapshot.json"
FIXTURE = PACKAGE_ROOT / "fixtures/worker_outlook/real_evidence.json"
CACHE = RAW_DATA_DIR / "worker"


def acquire() -> dict:
    started = time.perf_counter()
    acquire_sites()
    sites = json.loads((FIXTURE.parent / "representative_sites.json").read_text(encoding="utf-8"))[
        :2
    ]
    old = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {}
    pins = {item["file"]: item for item in old.get("sources", [])}
    report = {
        "sources": [],
        "datasets": [],
        "failures": [],
        "network_policy": "serial bounded cached official snapshots; no live inference I/O",
    }
    evidence = {site["id"]: [] for site in sites}

    def request(url, name, *, text=False):
        item = pins.get(name)
        if item and item["url"] != url:
            raise ValueError("reviewed source URL changed")
        path, receipt = fetch_cached(
            url,
            CACHE,
            filename=name,
            expected_sha256=item["sha256"] if item else None,
            max_bytes=3_000_000,
            timeout=20,
            retries=2,
        )
        report["sources"].append(receipt)
        content = path.read_text(encoding="utf-8")
        return (content if text else json.loads(content)), receipt

    def record(name, payload, receipt, normalized, target=None, count=None):
        report["datasets"].append(
            {
                "name": name,
                "file": receipt["file"],
                "record_count": count,
                "normalized_evidence_count": len(normalized),
                "site_id": target,
            }
        )
        for site_id in [target] if target else evidence:
            evidence[site_id].extend(item.model_dump(mode="json") for item in normalized)

    for index, site in enumerate(sites, 1):
        print(f"[feeds] site {index}/{len(sites)} {site['id']} {site['name']}", flush=True)
        try:
            payload, receipt = request(
                f"https://api.weather.gov/points/{site['lat']:.4f},{site['lon']:.4f}",
                site["id"] + "_nws_point.json",
            )
            p = payload["properties"]
            report["datasets"].append(
                {
                    "name": "NWS_point",
                    "file": receipt["file"],
                    "record_count": 1,
                    "site_id": site["id"],
                }
            )
        except Exception as error:
            report["failures"].append(
                {"name": "NWS_point", "site_id": site["id"], "reason": type(error).__name__}
            )
            continue
        for name, url, normalizer, filename in (
            ("NWS_hourly", p["forecastHourly"], nws_hourly, site["id"] + "_hourly.json"),
            (
                "NWS_alerts",
                "https://api.weather.gov/alerts/active?"
                + urlencode({"point": f"{site['lat']:.4f},{site['lon']:.4f}"}),
                nws_alerts,
                site["id"] + "_alerts.json",
            ),
        ):
            try:
                data, item = request(url, filename)
                rows = normalizer(data, item)
                count = (
                    len(data["properties"]["periods"])
                    if name == "NWS_hourly"
                    else len(data.get("features", []))
                )
                record(name, data, item, rows, site["id"], count)
            except Exception as error:
                report["failures"].append(
                    {"name": name, "site_id": site["id"], "reason": type(error).__name__}
                )
        try:
            station_data, _ = request(p["observationStations"], site["id"] + "_stations.json")
            station = station_data["features"][0]["id"]
            data, item = request(station + "/observations/latest", site["id"] + "_observation.json")
            rows = nws_observation(data, item)
            record("NWS_observation", data, item, rows, site["id"], 1)
        except Exception as error:
            report["failures"].append(
                {"name": "NWS_observation", "site_id": site["id"], "reason": type(error).__name__}
            )
    for product in ("wind", "air_temperature", "humidity", "water_level"):
        try:
            params = {
                "station": "8726520",
                "product": product,
                "date": "recent",
                "units": "metric",
                "time_zone": "gmt",
                "format": "json",
                "application": "PlanIT_Control_research",
            }
            if product == "water_level":
                params["datum"] = "MLLW"
            data, item = request(
                "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?" + urlencode(params),
                "coops_8726520_" + product + ".json",
            )
            rows = coops(
                data, item, product=product, datum="MLLW" if product == "water_level" else None
            )
            record("COOPS_" + product, data, item, rows, count=len(data.get("data", [])))
        except Exception as error:
            report["failures"].append({"name": "COOPS_" + product, "reason": type(error).__name__})
    extras = [
        (
            "USGS_earthquakes",
            "https://earthquake.usgs.gov/fdsnws/event/1/query?"
            + urlencode(
                {
                    "format": "geojson",
                    "starttime": "2026-10-16T00:00:00",
                    "endtime": "2026-10-17T05:00:00",
                    "minmagnitude": 4,
                    "limit": 20,
                    "orderby": "time",
                }
            ),
            earthquake_catalog,
            "earthquakes_20261016.json",
        ),
        (
            "SWPC_Kp",
            "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json",
            swpc_kp,
            "swpc_kp.json",
        ),
    ]
    for name, url, normalizer, filename in extras:
        try:
            data, item = request(url, filename)
            rows = normalizer(data, item)
            count = (
                len(data.get("features", []))
                if isinstance(data, dict)
                else len(data) - (1 if data and isinstance(data[0], list) else 0)
            )
            record(name, data, item, rows, count=count)
        except Exception as error:
            report["failures"].append({"name": name, "reason": type(error).__name__})
    try:
        metadata, _ = request(
            "https://www.ndbc.noaa.gov/activestations.xml", "ndbc_stations.xml", text=True
        )
        station = next(
            item for item in ET.fromstring(metadata).iter("station") if item.get("id") == "41009"
        )
        data, item = request(
            "https://www.ndbc.noaa.gov/data/realtime2/41009.txt", "ndbc_41009.txt", text=True
        )
        rows = ndbc_observations(
            data,
            item,
            lat=float(station.get("lat")),
            lon=float(station.get("lon")),
            station_id="41009",
        )
        record("NDBC_buoy", data, item, rows, count=max(0, len(data.splitlines()) - 2))
    except Exception as error:
        report["failures"].append({"name": "NDBC_buoy", "reason": type(error).__name__})
    report["as_of_utc"] = max(
        [r["retrieved_at_utc"] for r in report["sources"]]
        + [datetime.now(timezone.utc).isoformat() if not old else old.get("as_of_utc", "")]
    )
    report["elapsed_seconds"] = time.perf_counter() - started
    # Export a small source-grounded slice, not duplicated worldwide catalog records.
    exported = {}
    for site in sites:
        readings = evidence[site["id"]]
        windows = sorted(
            {r["valid_from"] for r in readings if r["method"] == "issued_forecast"},
            key=lambda t: datetime.fromisoformat(t.replace("Z", "+00:00")),
        )
        selected_windows = {windows[i] for i in (0, 6, 12, 24) if i < len(windows)}
        latest = {}
        for row in readings:
            if row["method"] == "observed" and row["publisher"] in ("NOAA NWS", "NOAA CO-OPS"):
                match = associate(SiteContext.model_validate(site), Evidence.model_validate(row))
                if match.kind in ("station_at_location", "nearby_station"):
                    key = (row["publisher"], row["origin_url"], row["variable"])
                    if key not in latest or row["observed_at"] > latest[key]["observed_at"]:
                        latest[key] = row
        exported[site["id"]] = [
            r
            for r in readings
            if r["method"] == "official_warning"
            or (r["method"] == "issued_forecast" and r["valid_from"] in selected_windows)
        ] + list(latest.values())
    report["exported_evidence_counts"] = {key: len(value) for key, value in exported.items()}
    report["limitations"] = [
        "Real environmental readings accompany explicitly hypothetical confirmed-event demo contexts.",
        "No real disaster activation, local flood depth, worker exposure, or site probability is asserted.",
        "NWS first 25 forecast periods normalized; windows 0/6/12/24 and latest local station variables exported; unlisted hours are unknown, never interpolated.",
        "CO-OPS latest three rows normalized; one latest row/variable exported where within the 25km context bound. Regional probes are catalog evidence, not local exposure.",
        "Retrieval is a conservative known-availability time, not the original first publication timestamp.",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    bundle = {"as_of_utc": report["as_of_utc"], "evidence_by_site": exported}
    report["canonical_export_sha256"] = hashlib.sha256(
        json.dumps(bundle, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    FIXTURE.write_text(json.dumps(bundle, indent=2, allow_nan=False), encoding="utf-8")
    REPORT.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(
        f"[feeds] {len(report['sources'])} verified snapshots; {len(report['failures'])} unavailable feed/normalizer cases; {report['elapsed_seconds']:.1f}s",
        flush=True,
    )
    return report


if __name__ == "__main__":
    acquire()
