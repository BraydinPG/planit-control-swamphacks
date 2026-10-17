"""Offline two-layer demonstration with real exported weather and explicit hypothetical events."""

import argparse
import copy
from datetime import timedelta
import json
from pathlib import Path
import statistics
import time

from ml.config import PACKAGE_ROOT, REPORT_DIR
from ml.schemas import parse_utc
from ml.worker.combined import build_worker_outlook
from ml.worker.schema import WorkerOutlook, WorkerOutlookRequest

FIXTURES = PACKAGE_ROOT / "fixtures/worker_outlook"


def scenarios() -> list[dict]:
    sites = json.loads((FIXTURES / "representative_sites.json").read_text(encoding="utf-8"))[:2]
    bundle = json.loads((FIXTURES / "real_evidence.json").read_text(encoding="utf-8"))
    as_of = parse_utc(bundle["as_of_utc"], "as_of")
    cases = []
    for name, event_type, site in (
        ("real_weather_hypothetical_flood", "Flood", sites[0]),
        ("real_weather_hypothetical_wind", "High Wind", sites[1]),
    ):
        context = {
            "event_id": "demo-hypothetical-" + name,
            "event_type": event_type,
            "event_status": "historical_replay",
            "site_id": site["id"],
            "as_of_utc": as_of.isoformat(),
            "event_start_utc": (as_of - timedelta(hours=6)).isoformat(),
            "event_definition": "noaa_positive_continuous_recorded_interval",
            "is_simulated": True,
            "location": {
                "lat": site["lat"],
                "lon": site["lon"],
                "region": "explicit hypothetical event at representative EIA location",
                "spatial_match_quality": "region_only",
            },
            "confirmation": {
                "source": "synthetic_event_context_not_actual_disaster_activation",
                "record_id": "demo-only",
                "confirmed_at": (as_of - timedelta(minutes=1)).isoformat(),
                "available_at": as_of.isoformat(),
                "is_fixture": True,
            },
        }
        cases.append(
            {
                "name": name,
                "site_context": site,
                "event_context": context,
                "evidence": bundle["evidence_by_site"][site["id"]],
            }
        )
    missing = copy.deepcopy(cases[0])
    missing["name"] = "missing_or_mismatched_site_evidence"
    missing["evidence"] = [copy.deepcopy(item) for item in missing["evidence"][:1]]
    for item in missing["evidence"]:
        item.update(
            is_fixture=True,
            availability_basis="fixture",
            source_version="synthetic-mismatch-v1",
            publisher="synthetic_fixture_spatial_mismatch",
            source_record_id="fixture-mismatch",
        )
        item["footprint"] = {
            "kind": "point",
            "point": {"lat": 0.0, "lon": 0.0},
            "precision": "deliberately mismatched demo input",
        }
    cases.append(missing)
    compound = copy.deepcopy(cases[0])
    compound["name"] = "compound_tropical_context_without_joint_probability"
    compound["event_context"]["event_type"] = "Tropical Storm"
    # Real wind/rain/heat context, but the tropical event and this warning are explicitly fixtures.
    lat, lon = compound["site_context"]["lat"], compound["site_context"]["lon"]
    compound["evidence"].append(
        {
            "evidence_id": "fixture-flood-warning",
            "publisher": "synthetic_fixture_not_an_actual_warning",
            "origin_url": "https://api.weather.gov/alerts",
            "source_record_id": "fixture-compound-warning",
            "original_type": "fixture_flood_warning",
            "hazard": "flood_context",
            "method": "official_warning",
            "variable": "warning",
            "value": "Synthetic Flood Warning for compound test only",
            "unit": "text",
            "issued_at": (as_of - timedelta(minutes=30)).isoformat(),
            "available_at": as_of.isoformat(),
            "ingested_at": as_of.isoformat(),
            "valid_from": as_of.isoformat(),
            "valid_to": (as_of + timedelta(hours=3)).isoformat(),
            "source_version": "synthetic-fixture-v1",
            "availability_basis": "fixture",
            "is_fixture": True,
            "footprint": {
                "kind": "polygon",
                "precision": "synthetic closed test polygon",
                "rings": [
                    [
                        [lon - 0.01, lat - 0.01],
                        [lon + 0.01, lat - 0.01],
                        [lon + 0.01, lat + 0.01],
                        [lon - 0.01, lat + 0.01],
                        [lon - 0.01, lat - 0.01],
                    ]
                ],
            },
        }
    )
    cases.append(compound)
    earthquake = copy.deepcopy(cases[1])
    earthquake["name"] = "fixture_earthquake_context_unknown_local_shaking"
    earthquake["event_context"]["event_type"] = "Earthquake"
    template = copy.deepcopy(compound["evidence"][-1])
    template.update(
        {
            "evidence_id": "fixture-earthquake",
            "publisher": "synthetic_fixture_not_actual_USGS_event",
            "source_record_id": "fixture-earthquake",
            "original_type": "fixture_magnitude",
            "hazard": "earthquake",
            "method": "observed",
            "variable": "earthquake_magnitude",
            "value": 5.0,
            "unit": "magnitude",
            "observed_at": as_of.isoformat(),
            "issued_at": None,
            "valid_to": as_of.isoformat(),
            "footprint": {
                "kind": "point",
                "point": {
                    "lat": earthquake["site_context"]["lat"] + 0.2,
                    "lon": earthquake["site_context"]["lon"],
                },
                "precision": "synthetic epicenter",
            },
        }
    )
    earthquake["evidence"] = [template]
    cases.append(earthquake)
    return cases


def run(
    *,
    output_dir: Path = REPORT_DIR / "worker_outlook",
    benchmark: bool = False,
    require_models: bool = False,
    export_examples: bool = False,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    records, timing = [], {}
    for index, case in enumerate(scenarios(), 1):
        before = copy.deepcopy(case)
        started = time.perf_counter()
        result = build_worker_outlook(case["event_context"], case["site_context"], case["evidence"])
        cold_ms = (time.perf_counter() - started) * 1000
        WorkerOutlook.model_validate_json(json.dumps(result, allow_nan=False))
        if before != case:
            raise RuntimeError("Outlook mutated source/site inputs")
        if (
            require_models
            and index <= 2
            and result["event_outlook"]["status"] != "supported_research"
        ):
            raise RuntimeError("Provision pinned duration models before requiring Layer A")
        if index <= 2 and not any(
            h["conditions"] for h in result["site_hazards"] if h["kind"] in ("wind", "heat", "rain")
        ):
            raise RuntimeError(
                "No accepted real site-associated environmental evidence in core demo"
            )
        records.append({"case": case["name"], "request": case, "outlook": result})
        calls = []
        if benchmark:
            for _ in range(100):
                start = time.perf_counter()
                repeated = build_worker_outlook(
                    case["event_context"], case["site_context"], case["evidence"]
                )
                calls.append((time.perf_counter() - start) * 1000)
                if (
                    repeated["event_outlook"] != result["event_outlook"]
                    or repeated["site_hazards"] != result["site_hazards"]
                ):
                    raise RuntimeError("Non-deterministic advisory output")
        timing[case["name"]] = {
            "first_ms": cold_ms,
            "warm_calls": len(calls),
            "warm_median_ms": statistics.median(calls) if calls else None,
        }
        count = sum(a["accepted"] for a in result["evidence"])
        print(
            f"[demo] {index}/5 {case['name']} LayerA={result['event_outlook']['status']} accepted_evidence={count}/{len(result['evidence'])} {cold_ms:.2f}ms",
            flush=True,
        )
    (output_dir / "demo_outputs.json").write_text(
        json.dumps(records, indent=2, allow_nan=False), encoding="utf-8"
    )
    report = {
        "status": "DEMO_SCHEMA_AND_INVARIANTS_PASSED",
        "cases": len(records),
        "runtime": timing,
        "source_mode": "real captured agency environmental evidence + labeled hypothetical event contexts; compound warning and earthquake are synthetic fixtures",
        "network_requests_during_inference": 0,
        "learned_site_models": 0,
        "operational_evaluation_eligible": False,
    }
    (output_dir / "demo_runtime.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    summary = [
        {
            "case": r["case"],
            "site_id": r["outlook"]["site"]["id"],
            "event_outlook_status": r["outlook"]["event_outlook"]["status"],
            "accepted_evidence": sum(e["accepted"] for e in r["outlook"]["evidence"]),
            "hazards": {
                h["kind"]: {
                    "status": h["status"],
                    "condition_count": len(h["conditions"]),
                    "probability": h["probability"],
                }
                for h in r["outlook"]["site_hazards"]
            },
            "unknowns": r["outlook"]["unknowns"],
            "is_demo_or_simulated": r["outlook"]["is_demo_or_simulated"],
        }
        for r in records
    ]
    (output_dir / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if export_examples:
        for name, record in zip(("flood", "wind"), records[:2]):
            (FIXTURES / (name + "_outlook.json")).write_text(
                json.dumps(record["outlook"], indent=2, allow_nan=False), encoding="utf-8"
            )
            request = {
                key: record["request"][key] for key in ("event_context", "site_context", "evidence")
            }
            (FIXTURES / (name + "_request.json")).write_text(
                json.dumps(request, indent=2, allow_nan=False), encoding="utf-8"
            )
        for name, model in (
            ("worker_outlook", WorkerOutlook),
            ("worker_request", WorkerOutlookRequest),
        ):
            (FIXTURES / (name + ".schema.json")).write_text(
                json.dumps(model.model_json_schema(), indent=2), encoding="utf-8"
            )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=REPORT_DIR / "worker_outlook")
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--require-models", action="store_true")
    parser.add_argument(
        "--export-examples",
        action="store_true",
        help="Intentionally update canonical requests/responses/schemas in fixtures.",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Default: five bounded offline cases; no downloads or full backtest.",
    )
    args = parser.parse_args()
    run(
        output_dir=args.output_dir,
        benchmark=args.benchmark,
        require_models=args.require_models,
        export_examples=args.export_examples,
    )


if __name__ == "__main__":
    main()
