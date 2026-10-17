"""Rebuild a truthful source-diff report from committed receipts; no network or training."""

from collections import Counter
import json

from ml.config import PACKAGE_ROOT


def build():
    root = PACKAGE_ROOT
    snapshot = json.loads((root / "fixtures/hazard_coverage/source_snapshot.json").read_text())
    entries = [
        {
            "provider": "NOAA NCEI / existing duration sources",
            "state": "existing_historical_verified",
            "records": 349030,
            "note": "54 raw labels, prior fitted/gated models unchanged; no archive download or refit",
        },
        {
            "provider": "NWS native CAP/API notices",
            "state": "new_real_retrieval_verified",
            "records": len(snapshot["alerts"]),
            "point_query_records": snapshot["counts"].get("point_alert_notice_records", 0),
            "point_queries_succeeded": snapshot["counts"].get("point_alert_sites_retrieved", 0),
            "note": "National and point records overlap; never sum as independent events. Native status/message lifecycle and actual polygon or provider point-filter provenance are retained.",
        },
        {
            "provider": "NWS local observations/issued hourly forecast",
            "state": "new_real_retrieval_verified",
            "normalized_records": sum(e["publisher"] == "NOAA NWS" for e in snapshot["evidence"]),
            "sites": 2,
            "note": "Actual backend-selected coordinates; four explicit forecast windows plus latest available station readings, not universal 50-site weather coverage",
        },
        {
            "provider": "USGS modern water v1",
            "state": "new_real_retrieval_verified",
            "records": snapshot["counts"]["modern_gauge_readings"],
            "note": "Parameter 63160 historical/provisional stage sample, not latest-live guarantee. Datum and basin/site transfer absent; rejected as site water evidence. Legacy WaterServices retirement is February 22, 2027 per official notice; new acquisition uses api.waterdata.usgs.gov/ogcapi/v1.",
        },
        {
            "provider": "USGS earthquake/ShakeMap",
            "state": "new_real_retrieval_verified",
            "catalog_events": snapshot["counts"]["earthquake_catalog_events"],
            "grid_products": 1,
            "note": "Real automatic Pakistan grid, real model estimate at hypothetical source location; zero US EIA-site coverage. Uncertainty product and damage labels absent.",
        },
        {
            "provider": "NOAA SWPC issued messages",
            "state": "new_real_retrieval_verified",
            "records": snapshot["counts"]["swpc_all_messages"],
            "normalized_geomagnetic": snapshot["counts"]["swpc_geomagnetic_messages"],
            "note": "Only K-index message families mapped to geomagnetic context. No structured expiry inferred from prose; no current site warning or outage estimate.",
        },
        {
            "provider": "EIA-860M backend identity export",
            "state": "existing_source_new_verified_export",
            "backend_selected_locations": 260,
            "acceptance_sites": 50,
            "note": "Actual read-only backend selector export, source hash/state/plant/coordinates checked; no deployed DB contents or active work orders verified.",
        },
        {
            "provider": "NHC / CO-OPS / NDBC / ISD / NIFC",
            "state": "existing_probes_preserved",
            "note": "Prior receipts/limitations retained. NIFC sample is attributes only; no new perimeter geometry, containment, historical issued cohort or basin transfer.",
        },
        {
            "provider": "NASA FIRMS",
            "state": "fixture_only_blocked_credentials",
            "note": "MAP_KEY/archive access not supplied. Existing detector parser and synthetic hotspot/perimeter scenario are not authenticated collection.",
        },
        {
            "provider": "EPA AirNow",
            "state": "fixture_only_blocked_credentials",
            "note": "Account/API key not supplied. Concentration units and explicit averaging windows remain distinct from AQI.",
        },
        {
            "provider": "EPA AQS",
            "state": "source_discovered_not_retrieved",
            "note": "Separate historical regulatory archive; no AQS adapter/records claimed and not used as live AirNow.",
        },
        {
            "provider": "FEMA NRI/NFHL; USDM/NRCS; terrain; volcano/tsunami",
            "state": "context_sources_discovered_or_fixture_only",
            "note": "No new mapped background raster/soil/coastal issuance histories. NRI is long-term background, not a current event. Synthetic drought/tsunami contexts do not establish collection.",
        },
        {
            "provider": "DOT/511 / evacuation / local emergency notices",
            "state": "needs_jurisdiction_feed",
            "note": "No universal or authenticated regional API acquired. Reviewed-notice contracts and fixtures only; no scraping/auth bypass.",
        },
        {
            "provider": "Human reports / utility telemetry",
            "state": "needs_teammate_feed_fixture_contract_tested",
            "note": "Server-owned issuer/role/time/site review gates; no actual reports, sensor measurements, identities or production writes collected.",
        },
    ]
    report = {
        "as_of_utc": snapshot["as_of_utc"],
        "sources": entries,
        "receipts": snapshot["receipts"],
        "capture_failures": snapshot["failures"],
        "native_parse_errors": snapshot["alert_parse_errors"],
        "site_query_states": dict(
            Counter(r["state"] for r in snapshot.get("site_alert_states", {}).values())
        ),
        "collection": "Opt-in immutable public snapshots; <=1 request/s/host, 15-second timeout, two attempts, 8MB default/16MB ShakeMap cap; provider quotas/terms still apply",
        "replay": "Offline normalized fixtures are hash-pinned; cached old data are not silently refreshed or relabeled current",
        "authentication": "No credentials supplied/read/stored; authenticated providers stay unavailable or fixture-only",
    }
    output = root / "reports/hazard_coverage/source_inventory.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [
        "# Source inventory diff from merged PR #9",
        "",
        f"Snapshot as-of: **{report['as_of_utc']}**. All activations remain hypothetical; records are not independent disasters or worker incidents.",
        "",
        "| Provider | Actual state | Count / limits |",
        "|---|---|---|",
    ]
    for entry in entries:
        numbers = ", ".join(f"{k}={v}" for k, v in entry.items() if isinstance(v, int))
        lines.append(f"| {entry['provider']} | {entry['state']} | {numbers}; {entry['note']} |")
    lines += [
        "",
        "## Availability, access and attribution",
        "",
        "- NWS/USGS/SWPC products were publicly accessible without credentials. Public availability is not operational validation. Retain agency attribution and source/product terms; no separate redistribution clearance is claimed.",
        "- The local collection cap is one request per second per host, 15-second timeout and two attempts. This is our ceiling, not a claim about a provider's quota. Cache receipts preserve request URL, byte count, SHA-256 and capture time; no inference network request is allowed.",
        "- [NWS API documentation](https://www.weather.gov/documentation/services-web-api) supplies CAP/API semantics. No-polygon alerts need a checked original point-filter request tied to this site, or remain unmatched. An excluding polygon/hole takes precedence. Captures older than one hour are marked stale by a research freshness policy, not an employer safety threshold.",
        "- [USGS migration notice](https://waterdata.usgs.gov/blog/api-waterservices-decom/) and [modern API documentation](https://api.waterdata.usgs.gov/docs/ogcapi/) were checked. New code uses v1; no request fallback to retiring WaterServices is added. Existing cached historical probes remain provenance-preserved. Source retrieval, revision and original observation times are distinct.",
        "- [AirNow rate/access guidance](https://docs.airnowapi.org/faq) and [FIRMS access](https://firms.modaps.eosdis.nasa.gov/api/) require provider credentials/limits for the relevant APIs. No credentials were requested or extracted from the workspace. [AQS](https://www.epa.gov/aqs) is a separate archive.",
        "- [USGS ShakeMap format](https://ghsc.code-pages.usgs.gov/esi/shakemap/docs2020/manual4_0/ug_products.html): UTC grid generation, version, original grid-node coordinates/spacing and nearest-cell method are retained. The acquired grid is an automatic model product, not local equipment inspection or a measured injury outcome. No uncertainty grid was acquired.",
        "- [FEMA NRI](https://www.fema.gov/sites/default/files/documents/fema_national-risk-index_technical-documentation.pdf), [NFHL](https://www.fema.gov/flood-maps/national-flood-hazard-layer), [USDM](https://droughtmonitor.unl.edu/Data.aspx) and [NRCS](https://www.nrcs.usda.gov/resources/data-and-reports/web-soil-survey) remain context/discovery pointers, not newly collected site forecasts.",
        "",
        "Exact receipts and failure states: [source_inventory.json](reports/hazard_coverage/source_inventory.json). Normalized fixture hashes: [manifest.json](fixtures/hazard_coverage/manifest.json). Full hazard sign-off: [HAZARD_COVERAGE_AUDIT.md](HAZARD_COVERAGE_AUDIT.md).",
        "",
    ]
    (root / "SOURCE_INVENTORY_DIFF.md").write_text("\n".join(lines), encoding="utf-8")
    print(
        f"Source inventory: {len(snapshot['receipts'])} receipts; {len(snapshot['failures'])} acquisition failures; no network"
    )
    return report


if __name__ == "__main__":
    build()
