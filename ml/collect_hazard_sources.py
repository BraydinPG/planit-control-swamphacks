"""Explicit opt-in bounded capture/export. Offline acceptance never acquires remote data."""

import argparse
import hashlib
import json
import sys

from ml.config import PACKAGE_ROOT, PROJECT_ROOT, RAW_DATA_DIR
from ml.provision import file_sha256
from ml.sources.bounded import snapshot
from ml.sources.hazard_feeds import modern_water, parse_alerts, shakemap_at_site, swpc_messages
from ml.sources.worker_feeds import nws_hourly, nws_observation
from ml.worker.schema import SiteContext
from ml.worker.spatial import distance_km

FIXTURES = PACKAGE_ROOT / "fixtures/hazard_coverage"
CACHE = RAW_DATA_DIR / "hazard_push"


def build_sites():
    # Import read-only backend functions; never call import_workbook(), sessions or routes.
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))
    from app.ingestion.eia860m import load_plants, select_worksites

    source = RAW_DATA_DIR / "worker/august_generator2026.xlsx"
    receipt = json.loads(source.with_name(source.name + ".receipt.json").read_text())
    if file_sha256(source) != receipt["sha256"]:
        raise ValueError("Pinned EIA source checksum mismatch")
    plants = select_worksites(load_plants(str(source)))
    records = []
    for p in sorted(plants, key=lambda p: p.site_id):
        site = SiteContext(
            id=p.site_id,
            name=p.name,
            lat=p.lat,
            lon=p.lon,
            site_type="representative_monitored_site",
            source="EIA-860M August 2026; backend selection export",
            source_version=receipt["sha256"],
            is_fixture=False,
        )
        records.append(
            {
                "id": p.site_id,
                "plant_id": p.plant_id,
                "state": p.state,
                "source_period_start": "2026-08-01",
                "source_available_at": receipt["retrieved_at_utc"],
                "site": site.model_dump(mode="json"),
            }
        )
    selected = []
    for target in (
        SiteContext(
            id="target",
            name="Tampa reference",
            lat=27.9756,
            lon=-82.5333,
            site_type="fixture_site",
            source="reference coordinates",
            source_version="v1",
        ),
        SiteContext(
            id="target",
            name="Phoenix reference",
            lat=33.4342,
            lon=-112.0116,
            site_type="fixture_site",
            source="reference coordinates",
            source_version="v1",
        ),
    ):
        selected.append(
            min(records, key=lambda r: distance_km(target, SiteContext.model_validate(r["site"])))
        )
    for state in sorted({r["state"] for r in records}):
        choices = [
            r for r in records if r["state"] == state and r["id"] not in {x["id"] for x in selected}
        ]
        if choices and len(selected) < 50:
            selected.append(choices[0])
    for record in records:
        if len(selected) >= 50:
            break
        if record["id"] not in {r["id"] for r in selected}:
            selected.append(record)
    output = {
        "source_receipt": receipt,
        "backend_selector_sha256": file_sha256(PROJECT_ROOT / "backend/app/ingestion/eia860m.py"),
        "selection": "Actual backend load_plants/select_worksites, then two nearest reference stations and state diversity for 50-site research batch",
        "database_state_verified": False,
        "state_association": "EIA sheet state column verified; independent state-boundary GIS not acquired",
        "records": records,
        "batch_site_ids": [r["id"] for r in selected],
    }
    FIXTURES.mkdir(parents=True, exist_ok=True)
    (FIXTURES / "backend_sites.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    return output


def collect():
    FIXTURES.mkdir(parents=True, exist_ok=True)
    site_file = FIXTURES / "backend_sites.json"
    sites = json.loads(site_file.read_text()) if site_file.exists() else build_sites()
    receipts, failures = [], []

    def get(name, url, **options):
        try:
            raw, receipt = snapshot(url, CACHE, name, **options)
            receipts.append(receipt)
            return raw, receipt
        except (ValueError, RuntimeError) as error:
            failures.append(
                {"file": name, "url": url, "state": "unavailable", "reason": str(error)}
            )
            return None, None

    raw, receipt = get("nws_alerts.json", "https://api.weather.gov/alerts/active?status=actual")
    alerts, alert_errors = (
        parse_alerts(json.loads(raw), receipt) if raw else ([], ["NWS unavailable"])
    )
    evidence, context = [], []
    raw, receipt = get(
        "water_v1.json",
        "https://api.waterdata.usgs.gov/ogcapi/v1/collections/continuous/items?f=json&limit=5&monitoring_location_id=USGS-02303000&datetime=2026-10-16T00:00:00Z/2026-10-17T07:30:00Z",
    )
    if raw:
        evidence += modern_water(json.loads(raw), receipt)
    raw, receipt = get("swpc_alerts.json", "https://services.swpc.noaa.gov/products/alerts.json")
    swpc_count = len(json.loads(raw)) if raw else 0
    if raw:
        context += swpc_messages(json.loads(raw), receipt)
    raw, receipt = get(
        "earthquakes.json",
        "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=2026-10-01&minmagnitude=5&limit=3&orderby=time",
    )
    quake_count = len(json.loads(raw)["features"]) if raw else 0
    for feature in json.loads(raw)["features"] if raw else []:
        detail, detail_receipt = get(
            feature["id"] + "_detail.json", feature["properties"]["detail"]
        )
        if not detail:
            continue
        products = json.loads(detail)["properties"].get("products", {}).get("shakemap", [])
        if not products:
            continue
        product = max(products, key=lambda p: p["updateTime"])
        urls = [v["url"] for k, v in product["contents"].items() if k.endswith("/grid.xml")]
        if not urls:
            continue
        grid, grid_receipt = get("shakemap_grid.xml", urls[0], max_bytes=16_000_000)
        if grid:
            lon, lat = feature["geometry"]["coordinates"][:2]
            probe = SiteContext(
                id="fixture-shakemap-location",
                name="Hypothetical location at actual source epicenter; not an EIA site",
                lat=float(lat),
                lon=float(lon),
                site_type="fixture_site",
                source="USGS event coordinates; hypothetical worksite",
                source_version=grid_receipt["sha256"],
                is_fixture=True,
            )
            signal = shakemap_at_site(grid, grid_receipt, probe)
            (FIXTURES / "real_shakemap_probe.json").write_text(
                json.dumps(
                    {
                        "site": probe.model_dump(mode="json"),
                        "signal": signal.model_dump(mode="json") if signal else None,
                        "is_actual_worksite": False,
                        "notes": "Real USGS product at a hypothetical Pakistan location; outside all US EIA batch sites",
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            break
    index = {r["id"]: r for r in sites["records"]}
    local_ids = sites["batch_site_ids"][:2]
    for sid in local_ids:
        site = index[sid]["site"]
        raw, receipt = get(
            sid + "_point.json",
            f"https://api.weather.gov/points/{site['lat']:.4f},{site['lon']:.4f}",
        )
        if not raw:
            continue
        properties = json.loads(raw)["properties"]
        forecast, forecast_receipt = get(sid + "_hourly.json", properties["forecastHourly"])
        if forecast:
            values = nws_hourly(json.loads(forecast), forecast_receipt)
            windows = sorted({e.valid_from for e in values})
            keep = {windows[i] for i in (0, 6, 12, 24) if i < len(windows)}
            evidence += [e for e in values if e.valid_from in keep]
        stations, station_receipt = get(sid + "_stations.json", properties["observationStations"])
        if stations:
            station = json.loads(stations)["features"][0]["properties"]["stationIdentifier"]
            observed, observed_receipt = get(
                sid + "_observed.json",
                f"https://api.weather.gov/stations/{station}/observations/latest",
            )
            if observed:
                evidence += nws_observation(json.loads(observed), observed_receipt)
    output = {
        "as_of_utc": max(r["retrieved_at_utc"] for r in receipts),
        "alerts": [a.model_dump(mode="json") for a in alerts],
        "alert_parse_errors": alert_errors,
        "evidence": [e.model_dump(mode="json") for e in evidence],
        "context_signals": [s.model_dump(mode="json") for s in context],
        "receipts": receipts,
        "failures": failures,
        "counts": {
            "nws_alerts": len(alerts),
            "polygon_notices": sum(bool(a.polygons) for a in alerts),
            "modern_gauge_readings": sum(e.variable == "gauge_height" for e in evidence),
            "swpc_all_messages": swpc_count,
            "swpc_geomagnetic_messages": len(context),
            "earthquake_catalog_events": quake_count,
            "local_weather_sites_requested": len(local_ids),
        },
        "limits": [
            "Not universal warning/site coverage",
            "Source availability at retrieval only",
            "No verified basin/datum transfer",
            "Provisional gauge readings retained but rejected",
            "Native zone-only notices are regional, not site warnings",
            "No operational/injury/clearance claim",
        ],
    }
    (FIXTURES / "source_snapshot.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output["counts"]), flush=True)
    return output


def fixture_manifest():
    files = {}
    for path in sorted(FIXTURES.glob("*.json")):
        if path.name == "manifest.json":
            continue
        content = path.read_bytes().replace(b"\r\n", b"\n")
        files[path.name] = {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
    (FIXTURES / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "hash_basis": "UTF-8 text with CRLF normalized to LF",
                "files": files,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def collect_site_alerts():
    """At most 50 serial point requests, reusable immutable receipts; empty is not clearance."""
    sites = json.loads((FIXTURES / "backend_sites.json").read_text())
    data = json.loads((FIXTURES / "source_snapshot.json").read_text())
    index = {r["id"]: r["site"] for r in sites["records"]}
    by_site, states, receipts = {}, {}, []
    for ordinal, sid in enumerate(sites["batch_site_ids"]):
        site = SiteContext.model_validate(index[sid])
        url = f"https://api.weather.gov/alerts/active?point={site.lat:.4f},{site.lon:.4f}&status=actual"
        try:
            raw, receipt = snapshot(url, CACHE, sid + "_point_alerts.json")
            alerts, errors = parse_alerts(json.loads(raw), receipt, query_site=site)
            receipts.append(receipt)
            by_site[sid] = [a.model_dump(mode="json") for a in alerts]
            states[sid] = {
                "provider": "NOAA NWS point alerts",
                "state": "current" if not errors else "unavailable",
                "attempted": True,
                "last_success_at": receipt["retrieved_at_utc"],
                "reason": f"{len(alerts)} notices; {len(errors)} parse errors; no absence/safety inference",
            }
        except (ValueError, RuntimeError) as error:
            by_site[sid] = []
            states[sid] = {
                "provider": "NOAA NWS point alerts",
                "state": "unavailable",
                "attempted": True,
                "reason": str(error),
            }
        if (ordinal + 1) % 10 == 0:
            print(
                f"[NWS point alerts] {ordinal + 1}/50 captured or explicitly unavailable",
                flush=True,
            )
    data["site_alerts"], data["site_alert_states"] = by_site, states
    existing = {r["file"]: r for r in data["receipts"]}
    existing.update({r["file"]: r for r in receipts})
    data["receipts"] = list(existing.values())
    data["as_of_utc"] = max(r["retrieved_at_utc"] for r in data["receipts"])
    data["counts"].update(
        point_alert_sites_requested=len(states),
        point_alert_sites_retrieved=len(receipts),
        point_alert_notice_records=sum(map(len, by_site.values())),
    )
    (FIXTURES / "source_snapshot.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    fixture_manifest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--collect", action="store_true", help="Explicit public network/cache acquisition"
    )
    parser.add_argument(
        "--manifest", action="store_true", help="Intentionally refresh normalized fixture hashes"
    )
    parser.add_argument(
        "--site-alerts",
        action="store_true",
        help="Explicit bounded NWS queries for the 50 reconciled sites",
    )
    args = parser.parse_args()
    if args.collect:
        collect()
    if args.manifest:
        fixture_manifest()
    if args.site_alerts:
        collect_site_alerts()
    if not (args.collect or args.manifest or args.site_alerts):
        parser.error("Choose --collect or --manifest; offline replay is ml.hazard_rehearsal")
