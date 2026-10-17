"""All-record NOAA census plus explicitly staged official-source research catalog."""

from collections import Counter, defaultdict
import csv
import gzip
import json
import time

from ml.config import PACKAGE_ROOT, RAW_DATA_DIR, REPORT_DIR
from ml.events import normalize_noaa_row
from ml.provision import ensure_archive
from ml.worker.schema import Contract

REPORT = REPORT_DIR / "worker_outlook/noaa_census.json"
CATALOG = PACKAGE_ROOT / "source_catalog.json"


class SourceEntry(Contract):
    canonical_name: str
    family: str
    raw_event_types: list[str]
    official_source_url: str
    access: str
    licensing: str
    maturity: list[str]
    downloaded: bool
    adapter_fixture_tested: bool
    temporal_coverage: str
    geographic_coverage: str
    record_count: int | None
    episode_count: int | None
    independent_event_count: int | None = None
    group_definition: str
    spatial_resolution: str
    temporal_resolution: str
    availability: str
    outcome_label_validity: str
    gaps: list[str]
    supported_targets: list[str]
    evidence_feed_status: str
    model_availability: str
    validation_gate_outcome: str
    integration_status: str
    limitations: list[str]
    source_version: str | None
    receipts: list[dict]


def family_for(name: str) -> str:
    if "Volcanic" in name:
        return "volcanic"
    if name in ("Flood", "Flash Flood", "Heavy Rain"):
        return "inland_water_rain"
    if any(
        word in name
        for word in (
            "Tide",
            "Coastal",
            "Lakeshore",
            "Surf",
            "Rip Current",
            "Seiche",
            "Tsunami",
            "Sneakerwave",
        )
    ):
        return "coastal_ocean"
    if any(word in name for word in ("Hurricane", "Tropical")):
        return "tropical_cyclone"
    if any(word in name for word in ("Heat",)):
        return "heat"
    if any(
        word in name
        for word in ("Snow", "Winter", "Ice", "Sleet", "Frost", "Cold", "Blizzard", "Freeze")
    ):
        return "winter_cold_ice"
    if "Marine" in name:
        return "marine_weather"
    if any(
        word in name for word in ("Wind", "Tornado", "Funnel", "Lightning", "Hail", "Waterspout")
    ):
        return "wind_convective"
    if any(word in name for word in ("Fog", "Dust", "Smoke")):
        return "visibility_air_quality"
    if name == "Wildfire":
        return "wildfire"
    if name in ("Debris Flow", "Avalanche"):
        return "terrain_ground"
    if name == "Drought":
        return "drought_soil"
    return "other_recorded_weather"


def census() -> dict:
    started = time.perf_counter()
    manifest = json.loads((REPORT_DIR / "source_manifest.json").read_text())
    stats = defaultdict(
        lambda: {
            "records": 0,
            "episodes": set(),
            "event_ids": set(),
            "missing_episode_ids": 0,
            "invalid_rows": 0,
            "missing_coordinates": 0,
            "zero_duration_rows": 0,
            "years": Counter(),
            "states": Counter(),
        }
    )
    for index, item in enumerate(manifest["archives"], 1):
        path = ensure_archive(item, RAW_DATA_DIR)
        print(f"[census] archive {index}/{len(manifest['archives'])} {item['file']}", flush=True)
        with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                name = row["EVENT_TYPE"].strip()
                data = stats[name]
                data["records"] += 1
                data["event_ids"].add(row.get("EVENT_ID"))
                if row.get("EPISODE_ID"):
                    data["episodes"].add(row["EPISODE_ID"])
                else:
                    data["missing_episode_ids"] += 1
                data["years"][str(item["year"])] += 1
                data["states"][row.get("STATE") or "UNKNOWN"] += 1
                try:
                    event = normalize_noaa_row(row, item["year"], allow_zero_duration=True)
                    data["missing_coordinates"] += event["geometry_quality"] == "zone_only"
                    data["zero_duration_rows"] += event["duration_hours"] == 0
                except ValueError:
                    data["invalid_rows"] += 1
    families = {}
    for name, data in stats.items():
        family = family_for(name)
        group = families.setdefault(family, {"records": 0, "episodes": set(), "raw_types": []})
        group["records"] += data["records"]
        group["episodes"].update(data["episodes"])
        group["raw_types"].append(name)
    report = {
        "status": "ALL_CACHED_NOAA_TYPES_INVENTORIED_NOT_NEW_MODEL_VALIDATION",
        "period": "2021-2025",
        "total_records": sum(s["records"] for s in stats.values()),
        "distinct_raw_event_types": len(stats),
        "categories": {
            name: {
                **{k: v for k, v in s.items() if k not in ("event_ids", "episodes")},
                "episode_groups": len(s["episodes"]),
                "distinct_event_ids": len(s["event_ids"]),
                "family": family_for(name),
            }
            for name, s in sorted(stats.items())
        },
        "receipts": manifest["archives"],
        "elapsed_seconds": time.perf_counter() - started,
        "families": {
            name: {
                "records": data["records"],
                "reporting_episode_groups": len(data["episodes"]),
                "raw_types": sorted(data["raw_types"]),
            }
            for name, data in sorted(families.items())
        },
        "group_limit": "Reporting episode IDs are not verified independent meteorological disasters; no new fits are made.",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        f"[census] {report['total_records']} records / {len(stats)} verbatim types in {report['elapsed_seconds']:.2f}s",
        flush=True,
    )
    return report


def build_catalog() -> dict:
    coverage = json.loads(REPORT.read_text()) if REPORT.exists() else census()
    registry = json.loads((REPORT_DIR / "multidisaster/registry.json").read_text())["events"]
    validation_path = REPORT_DIR / "worker_outlook/validation.json"
    tested_adapters = (
        set(json.loads(validation_path.read_text()).get("adapter_checks", []))
        if validation_path.exists()
        else set()
    )
    tested = "NOAA" in tested_adapters
    entries = []
    for name, row in coverage["categories"].items():
        model = registry.get(name, {})
        eligible = model.get("prediction_eligible", False)
        trained = "artifact" in model or name == "Flood"
        stages = ["source_discovered", "real_data_retrieved"]
        if tested:
            stages.append("adapter_fixture_tested")
        if trained:
            stages += ["valid_recorded_interval_target", "trained", "chronologically_backtested"]
        if eligible:
            stages.append("research_eligible")
        entries.append(
            SourceEntry(
                canonical_name=name,
                family=row["family"],
                raw_event_types=[name],
                official_source_url="https://www.ncei.noaa.gov/access/storm-events-database/",
                access="Public cached bulk archives; no key",
                licensing="NOAA public federal records; preserve attribution and source quality limitations.",
                maturity=stages,
                downloaded=True,
                adapter_fixture_tested=tested,
                temporal_coverage="2021-2025",
                geographic_coverage=", ".join(sorted(row["states"])),
                record_count=row["records"],
                episode_count=row["episode_groups"],
                group_definition="NOAA EPISODE_ID reporting clusters, not verified independent disasters",
                spatial_resolution="County/zone or reported event point; source-dependent",
                temporal_resolution="Administrative recorded intervals; some instantaneous reports",
                availability="retrospective_final_records",
                outcome_label_validity="Recorded interval only; intensity/site impact not labeled",
                gaps=[
                    f"{row['invalid_rows']} invalid rows",
                    f"{row['missing_coordinates']} normalized rows without point geometry",
                    f"{row['missing_episode_ids']} missing raw episode IDs",
                ],
                supported_targets=[model.get("target", "recorded Flood interval persistence")]
                if eligible
                else [],
                evidence_feed_status="historical_inventory_only",
                model_availability=model.get("status", "ingestion_only"),
                validation_gate_outcome="passed_research_screen"
                if eligible
                else ";".join(model.get("qualification_failures", []))
                or "not_evaluated_for_prediction",
                integration_status="Layer A callable" if eligible else "no predictive dispatch",
                limitations=model.get(
                    "limitations",
                    ["No validated continuous duration, severity or site-consequence target."],
                ),
                source_version="pinned NOAA archive set 2021-2025",
                receipts=coverage["receipts"],
            ).model_dump()
        )
    # Specialized datasets and identified sources stay separate from raw NOAA labels.
    specs = [
        (
            "NHC Atlantic tracks/advisories",
            "tropical_cyclone",
            "https://www.nhc.noaa.gov/data/",
            "hurdat_coverage.json",
            "2000-2025",
            "North Atlantic",
            "Public archives; no key",
            "Post-analysis tracks; issued advisories are a small probe, not an operational training cohort.",
        ),
        (
            "Observed station heat/wind",
            "heat",
            "https://www.ncei.noaa.gov/products/land-based-station/integrated-surface-database",
            "station_coverage.json",
            "2021-August 2025",
            "Three FL/TX/AZ airport stations",
            "Public archives; no key",
            "Rounded station observations; original availability/QC vintages absent.",
        ),
        (
            "NIFC historical perimeters",
            "wildfire",
            "https://data-nifc.opendata.arcgis.com/",
            "wildfire_sources.json",
            "2021-2024 in requested sample",
            "Legacy layer subset, not complete national incidents",
            "Public ArcGIS layer; honor per-layer use terms",
            "191 perimeter attribute records (geometry not retrieved) do not reconstruct containment or as-of progression.",
        ),
        (
            "USGS gauge feasibility",
            "inland_water_rain",
            "https://api.waterdata.usgs.gov/docs/ogcapi/",
            "gauge_sources.json",
            "2024-10-08/09",
            "USGS-02303000",
            "Public bounded API; higher-rate keys optional",
            "Gauge datum/basin/site transfer not validated.",
        ),
    ]
    for name, family, url, filename, period, geo, access, limit in specs:
        r = json.loads((REPORT_DIR / "multidisaster" / filename).read_text())
        count = r.get(
            "selected_track_points",
            r.get(
                "event_records",
                r.get("requested_2021_2025_perimeter_record_count", r.get("records")),
            ),
        )
        groups = r.get(
            "selected_storms", r.get("requested_period_sample", {}).get("distinct_incident_ids")
        )
        if filename == "station_coverage.json":
            count = sum(s["source_rows"] for s in r["stations"].values())
            groups = sum(s["evaluation_week_groups"] for s in r["stations"].values())
        receipts = r.get("sources", [r.get("source_receipt", {})])
        entry = _special(
            name,
            family,
            url,
            access,
            period,
            geo,
            count,
            groups,
            limit,
            receipts,
            (
                "NHC"
                if filename == "hurdat_coverage.json"
                else "ISD"
                if filename == "station_coverage.json"
                else "none"
            )
            in tested_adapters,
        )
        if filename in ("hurdat_coverage.json", "station_coverage.json"):
            entry["maturity"] += ["trained", "chronologically_backtested"]
            entry["model_availability"] = (
                "offline_retrospective_wind_change"
                if filename == "hurdat_coverage.json"
                else "research_eligible_three_station_threshold_replay"
            )
            entry["validation_gate_outcome"] = (
                "existing_retrospective_experiment_only"
                if filename == "hurdat_coverage.json"
                else "passed_existing_research_screen; no operational eligibility"
            )
            entry["supported_targets"] = (
                ["24h cyclone maximum-wind change, post-analysis only"]
                if filename == "hurdat_coverage.json"
                else ["90F observed station heat-index threshold episode persistence"]
            )
        entries.append(entry)
    snapshot = json.loads((REPORT_DIR / "worker_outlook/feed_snapshot.json").read_text())
    for prefix, family, url, geographic_scope in (
        (
            "NWS_",
            "wind_convective",
            "https://www.weather.gov/documentation/services-web-API",
            "Two Tampa/Phoenix-area station and forecast-grid footprints",
        ),
        (
            "COOPS_",
            "coastal_ocean",
            "https://api.tidesandcurrents.noaa.gov/api/prod/",
            "Station 8726520, St. Petersburg, Florida",
        ),
        (
            "USGS_earthquakes",
            "earthquake",
            "https://earthquake.usgs.gov/fdsnws/event/1/",
            "Global catalog query, minimum magnitude 4",
        ),
        (
            "SWPC_",
            "space_weather",
            "https://www.swpc.noaa.gov/products/planetary-k-index",
            "Planetary Kp context, not site exposure",
        ),
        (
            "NDBC_",
            "coastal_ocean",
            "https://www.ndbc.noaa.gov/measdes.shtml",
            "Atlantic marine buoy 41009; no automatic onshore association",
        ),
    ):
        data = [d for d in snapshot["datasets"] if d["name"].startswith(prefix)]
        files = {d["file"] for d in data}
        receipts = [r for r in snapshot["sources"] if r["file"] in files]
        entries.append(
            _special(
                prefix.rstrip("_") + " captured environmental evidence",
                family,
                url,
                "Public serial snapshot; no key",
                "Snapshot at "
                + snapshot["as_of_utc"]
                + "; per-evidence valid windows; full raw span not profiled",
                geographic_scope,
                sum(d["record_count"] or 0 for d in data),
                None,
                "Descriptive evidence only; no learned site probability or original historical vintage reconstructed.",
                receipts,
                prefix.rstrip("_") in tested_adapters,
            )
        )
    eia = json.loads((REPORT_DIR / "worker_outlook/eia_coverage.json").read_text())
    entries.append(
        _special(
            "EIA-860M representative location metadata",
            "site_locations",
            "https://www.eia.gov/electricity/data/eia860m/",
            "Public workbook, no key; attribution required",
            "August 2026",
            "US representative power plants",
            eia["generator_rows"],
            eia["validated_unique_plant_locations"],
            "50 validated locations exported for the research harness; no backend database import or active-worksite verification.",
            [eia["source_receipt"]],
            "EIA" in tested_adapters,
        )
    )
    identified = [
        (
            "NASA FIRMS",
            "wildfire",
            "https://firms.modaps.eosdis.nasa.gov/",
            "Earthdata archive login / some API products require map key; no credentials supplied",
            "Thermal anomalies are not containment or a complete fire perimeter.",
        ),
        (
            "EPA AirNow reporting-area API",
            "visibility_air_quality",
            "https://docs.airnowapi.org/",
            "AirNow account/API key; no credentials supplied",
            "Fixture-tested parser only; preliminary reporting-area data do not establish on-site exposure.",
        ),
        (
            "EPA AQS regulatory archive",
            "visibility_air_quality",
            "https://www.epa.gov/aqs",
            "Distinct regulatory archive; API account/key not supplied",
            "Identified only: no AQS records retrieved or adapter tested; regulatory observations do not establish site exposure.",
        ),
        (
            "NWPS river forecasts",
            "inland_water_rain",
            "https://water.noaa.gov/",
            "Public forecast/API; historical issued-vintage cohort not acquired",
            "Flood stage is gauge/datum specific; no automatic site inundation mapping.",
        ),
        (
            "USGS landslide inventories",
            "terrain_ground",
            "https://www.usgs.gov/programs/landslide-hazards",
            "Public catalog discovery; no inventory downloaded",
            "Susceptibility/occurrence inventories lack validated local future labels in this package.",
        ),
        (
            "NOAA tsunami history/warnings",
            "coastal_ocean",
            "https://www.ncei.noaa.gov/products/natural-hazards/tsunamis-earthquakes-volcanoes/tsunamis",
            "Historical database / official warnings identified; not retrieved",
            "Historical occurrence is not an issued site warning or evacuation forecast.",
        ),
        (
            "USGS volcano alerts",
            "volcanic",
            "https://volcanoes.usgs.gov/vsc/api/",
            "Public observatory alert API identified; not retrieved",
            "No volcanic unrest or ash exposure model.",
        ),
        (
            "Drought / soil moisture / flood terrain context",
            "drought_soil",
            "https://www.drought.gov/",
            "NOAA/USDA/NASA/FEMA products identified; attribution/product-specific access; no raster acquisition",
            "No parcel ground stability, saturated soil, flood depth or FEMA map forecast inferred.",
        ),
        (
            "Confirmed crew infrastructure reports",
            "infrastructure",
            "https://github.com/BraydinPG/planit-control-swamphacks",
            "Authorized backend human-confirmed reports only; no real personal data collected",
            "Weather cannot identify energized water, broken poles, wildlife, chemicals or access condition.",
        ),
    ]
    for name, family, url, access, limit in identified:
        entries.append(
            _special(
                name,
                family,
                url,
                access,
                "not acquired",
                "source-dependent",
                None,
                None,
                limit,
                [],
                (
                    "FIRMS"
                    if name == "NASA FIRMS"
                    else "AirNow"
                    if name == "EPA AirNow reporting-area API"
                    else "none"
                )
                in tested_adapters,
            )
        )
    catalog = {
        "schema_version": "1.0.0",
        "taxonomy_version": "raw-NOAA-2021-2025-v1",
        "operational_evaluation_eligible": False,
        "noaa_type_count": coverage["distinct_raw_event_types"],
        "entries": entries,
        "stage_note": "Maturity is per dataset/target. Descriptive evidence normalization is not model validation. No operationally evaluated source/model is claimed.",
    }
    CATALOG.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    return catalog


def _special(name, family, url, access, period, geo, count, groups, limit, receipts, tested):
    downloaded = bool(receipts)
    return SourceEntry(
        canonical_name=name,
        family=family,
        raw_event_types=[],
        official_source_url=url,
        access=access,
        licensing="Retain agency attribution and product-specific use terms; no key or credentials committed.",
        maturity=["source_discovered"]
        + (["adapter_fixture_tested"] if tested else [])
        + (["real_data_retrieved"] if downloaded else []),
        downloaded=downloaded,
        adapter_fixture_tested=tested,
        temporal_coverage=period,
        geographic_coverage=geo,
        record_count=count,
        episode_count=groups,
        group_definition="Distinct source IDs/clusters where reported; independence not established",
        spatial_resolution="Station / forecast polygon / regional / global, explicitly per evidence",
        temporal_resolution="Provider-specific; see receipts and evidence windows",
        availability="mixed_observed_issued_or_retrospective; per-evidence gate authoritative",
        outcome_label_validity="No new learned local target validated",
        gaps=[limit],
        supported_targets=[],
        evidence_feed_status="captured_or_investigated" if downloaded else "not_retrieved",
        model_availability="see existing per-target model registry; no new learned model",
        validation_gate_outcome="not_a_new_predictive_validation",
        integration_status="independent ML harness only",
        limitations=[limit],
        source_version=receipts[0].get("sha256") if receipts else None,
        receipts=receipts,
    ).model_dump()


def write_coverage(catalog: dict) -> None:
    census_report = json.loads(REPORT.read_text())
    registry = json.loads((REPORT_DIR / "multidisaster/registry.json").read_text())["events"]
    lines = [
        "# Disaster evidence coverage",
        "",
        "Verified from the five pinned 2021–2025 NOAA archives and bounded official-source snapshots. All source versions, receipt URLs/hashes/times, access requirements and readiness stages are in [source_catalog.json](source_catalog.json). Taxonomy version: `raw-NOAA-2021-2025-v1`.",
        "",
        "The cached archives contain **349,030 records / 54 verbatim event types**. The often cited 48-type expectation is not imposed on these actual archives; marine/newer labels are retained. Missing types such as Freezing Rain are not fabricated. This census is not training or model validation.",
        "",
        "## NOAA families",
        "",
        "| Inventory family | Real rows | Distinct reporting episode IDs within family |",
        "|---|---:|---:|",
    ]
    for name, row in census_report["families"].items():
        lines.append(f"| {name} | {row['records']:,} | {row['reporting_episode_groups']:,} |")
    lines += [
        "",
        "Episode IDs are reporting groups, not verified independent meteorological disasters. IDs can occur across families; do not sum groups across rows or providers. Statistical independence remains unknown. Per-type missing episode IDs, coordinate gaps, invalid rows, state/year coverage and instantaneous reports are in [noaa_census.json](reports/worker_outlook/noaa_census.json).",
        "",
        "## Original event types and model maturity",
        "",
        "| Verbatim NOAA type | Real rows | Reporting groups | Model state |",
        "|---|---:|---:|---|",
    ]
    for name, row in census_report["categories"].items():
        lines.append(
            f"| {name} | {row['records']:,} | {row['episode_groups']:,} | {registry.get(name, {}).get('status', 'inventory_only')} |"
        )
    lines += [
        "",
        "Only existing Flood, Flash Flood, High Wind, Heavy Rain and Winter Storm duration research is dispatched. Station Heat Index Exceedance is a different observed target, not an alias for NOAA Heat/Excessive Heat. Strong Wind, Ice Storm and Heavy Snow remain disabled after their previous gates failed. Hurricane wind-change is offline post-analysis research, with no live dispatch. None is operationally eligible.",
        "",
        "## Specialized sources",
        "",
        "Counts below describe downloaded records, not a complete national inventory. `unknown` means not acquired/not established, not zero events. Only two site weather snapshots are associated with the demo; other probes do not establish site exposure.",
        "",
        "| Source | Retrieved records | Source groups (independence unproven) | Stage | Access / main gap |",
        "|---|---:|---:|---|---|",
    ]
    for entry in catalog["entries"]:
        if entry["raw_event_types"]:
            continue
        records = "unknown" if entry["record_count"] is None else f"{entry['record_count']:,}"
        groups = "unknown" if entry["episode_count"] is None else f"{entry['episode_count']:,}"
        stage = (
            "real data retrieved"
            if entry["downloaded"]
            else "fixture tested, not retrieved"
            if entry["adapter_fixture_tested"]
            else "identified only"
        )
        lines.append(
            f"| [{entry['canonical_name']}]({entry['official_source_url']}) | {records} | {groups} | {stage} | {entry['limitations'][0]} |"
        )
    lines += [
        "",
        "NWS counts include two point metadata records, two station observation records and 312 hourly forecast periods. First 25 periods/site were normalized; four explicit windows and latest local station variables were exported. NDBC includes 6,390 table rows; only its latest three rows were normalized. CO-OPS humidity was unavailable; its error response is receipted but is not a valid measurement. The preliminary coastal water reading has a quality flag and is rejected for site assessment.",
        "",
        "The EIA workbook has 28,379 generator rows, 14,700 validated unique plant locations and two invalid/missing location rows; 50 public representative locations are exported. This is a Cache research fixture set, not a completed backend/database import or verified jobsite inventory.",
        "",
        "## Availability and scientific limits",
        "",
        "- Captured NWS forecasts retain generated/update time, future valid windows, actual retrieval/known-availability time and forecast polygon. They are actual issued products, not newly trained predictions.",
        "- NWS/CO-OPS/USGS/NDBC/SWPC snapshots prove availability at capture, not an earlier historical issue time. Revised catalog values cannot be backdated to event occurrence.",
        "- HURDAT2/NOAA final records and legacy ISD archives remain retrospective; no operational-vintage cohort was created.",
        "- Real environmental demo evidence is paired with explicitly hypothetical confirmed-event contexts. No actual ongoing flood/high-wind event at either plant is asserted. The compound warning and earthquake example are synthetic and labeled.",
        "- Layer B is descriptive evidence only. No learned site target, Brier/PR-AUC, injury likelihood, joint hazard probability, flood depth, containment, ground stability or work clearance is claimed.",
        "- AirNow and FIRMS adapters are fixture-tested, with no authenticated archive collection. NWPS, landslide, soil/terrain, tsunami warning and volcano products remain identified-only dependencies.",
        "",
        "Run `python -m ml.disaster_catalog` to intentionally rebuild the census/catalog from verified cached archives. It makes no training/model-selection changes. Run `python -m ml.collect_worker_evidence` only to intentionally reconstruct the pinned snapshot from cache; changed dynamic URLs fail checksum verification rather than silently becoming the same vintage. Offline demos use committed normalized extracts, not live requests.",
        "",
    ]
    (PACKAGE_ROOT / "DISASTER_COVERAGE.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    census()
    write_coverage(build_catalog())
