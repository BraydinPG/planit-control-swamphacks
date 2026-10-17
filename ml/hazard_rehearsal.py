"""Disconnected CLI rehearsal of an upstream-authorized library call; never a server."""

import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import socket
import statistics
import time
import tracemalloc
from unittest.mock import patch

from pydantic import ValidationError

from ml.collect_hazard_sources import FIXTURES
from ml.config import REPORT_DIR
from ml.hazard_scenarios import activation, scenarios
from ml.worker.comprehensive import build_comprehensive_outlook, _covers
from ml.worker.comprehensive_schema import (
    ComprehensiveOutlook,
    ComprehensiveRequest,
    OfficialAlert,
    TrustPolicy,
    to_legacy,
)
from ml.worker.identity import reconcile_site

REPORTS = REPORT_DIR / "hazard_coverage"
DEMO_POLICY = TrustPolicy(
    allowed_report_issuers=frozenset({"fixture-authorized-report-service"}),
    allow_fixture_reports=True,
)


def verify_fixtures():
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    if manifest["schema_version"] != "1.0.0":
        raise ValueError("Unknown fixture manifest version")
    if manifest.get("hash_basis") != "UTF-8 text with CRLF normalized to LF":
        raise ValueError("Unknown normalized fixture hash basis")
    for name, expected in manifest["files"].items():
        if Path(name).name != name:
            raise ValueError("Unsafe fixture manifest path")
        file = FIXTURES / name
        content = file.read_bytes().replace(b"\r\n", b"\n")
        if (
            len(content) != expected["bytes"]
            or hashlib.sha256(content).hexdigest() != expected["sha256"]
        ):
            raise ValueError("Normalized fixture checksum mismatch: " + name)


def check_rehearsal_scope(role: str, allowed_site_ids: frozenset[str], request: dict):
    """Fixture-only permission rehearsal, not Auth0 validation or a production dependency."""
    if request["event_context"]["event_status"] != "historical_replay":
        raise PermissionError("Rehearsal is restricted to explicitly labeled replay activation")
    if role not in ("crew", "supervisor") or request["site_context"]["id"] not in allowed_site_ids:
        raise PermissionError("Fixture principal has no assigned-site/organization scope")


def _assert_safety(outlook):
    checked = ComprehensiveOutlook.model_validate(outlook)
    assert (
        checked.research_only and checked.not_work_clearance and not checked.production_eligibility
    )
    assert not checked.operational_evaluation_eligible
    assert all(
        h.probability is None and h.severity is None and h.needs_field_verification
        for h in checked.worksite_hazards
    )
    assert not {
        "risk_score",
        "active_alerts",
        "all_clear_at",
        "stop_work",
        "timer",
        "trajectories",
    }.intersection(outlook)
    for hid in ("energized_floodwater", "structural_collapse", "downed_lines"):
        hazard = next(h for h in checked.worksite_hazards if h.hazard_id == hid)
        if not any(r.accepted and r.report.hazard_id == hid for r in checked.reviewed_reports):
            assert hazard.status == "unknown" and not hazard.source_ids
    to_legacy(outlook)
    return checked


def run(
    output: Path = REPORTS, *, require_models=False, benchmark=False, export=False, predictor=None
):
    verify_fixtures()
    output.mkdir(parents=True, exist_ok=True)
    snapshot = json.loads((FIXTURES / "source_snapshot.json").read_text())
    exported_sites = json.loads((FIXTURES / "backend_sites.json").read_text())
    index = {r["id"]: r for r in exported_sites["records"]}
    cases, summary, samples, runtimes = scenarios(), [], [], {}
    fixture_scope = frozenset(exported_sites["batch_site_ids"]) | frozenset(
        c["request"]["site_context"]["id"] for c in cases
    )
    tested_hazards = set()
    cold_artifact_ms = None
    if benchmark and predictor is None:
        from ml.worker.combined import _predictor

        if _predictor.cache_info().currsize == 0:
            tick = time.perf_counter()
            _predictor()
            cold_artifact_ms = (time.perf_counter() - tick) * 1000
    # A true network attempt fails the acceptance run, including third-party socket calls.
    with (
        patch.object(
            socket.socket,
            "connect",
            side_effect=AssertionError("Offline rehearsal attempted network access"),
        ),
        patch.object(
            socket,
            "create_connection",
            side_effect=AssertionError("Offline rehearsal attempted network access"),
        ),
    ):
        for case in cases:
            request, before = case["request"], copy.deepcopy(case["request"])
            check_rehearsal_scope("supervisor", fixture_scope, request)
            start = time.perf_counter()
            try:
                validated = ComprehensiveRequest.model_validate(request)
                outlook = build_comprehensive_outlook(
                    **validated.model_dump(mode="json"),
                    trust_policy=DEMO_POLICY,
                    predictor=predictor,
                )
                checked = _assert_safety(outlook)
                tested_hazards.update(h.hazard_id for h in checked.worksite_hazards)
            except (ValidationError, ValueError):
                if case.get("expected_error") != "invalid_request_422_upstream":
                    raise
                summary.append(
                    {
                        "case": case["name"],
                        "result": "expected_validation_error_422",
                        "is_actual_incident": False,
                    }
                )
                continue
            assert not case.get("expected_error")
            assert request == before
            elapsed = (time.perf_counter() - start) * 1000
            runtimes[case["name"]] = {"first_ms": elapsed}
            if require_models and case["name"] in {
                "real_local_rain_and_gauge_without_basin_or_datum",
                "real_wind_and_forecast_backend_identity",
            }:
                assert checked.event_outlook.status == "supported_research", (
                    "Provision the pinned duration artifacts first"
                )
            if benchmark and len(samples) < 2:
                timings = []
                for _ in range(30):
                    tick = time.perf_counter()
                    build_comprehensive_outlook(
                        **validated.model_dump(mode="json"),
                        trust_policy=DEMO_POLICY,
                        predictor=predictor,
                    )
                    timings.append((time.perf_counter() - tick) * 1000)
                runtimes[case["name"]].update(
                    warm_calls=30, warm_median_ms=statistics.median(timings)
                )
            item = {
                "case": case["name"],
                "result": "passed",
                "is_actual_incident": False,
                "event_status": checked.event_outlook.status,
                "accepted_environmental_evidence": sum(a.accepted for a in checked.evidence),
                "accepted_notices": sum(a.accepted for a in checked.official_notices),
                "accepted_reports": sum(a.accepted for a in checked.reviewed_reports),
                "worksite_unknowns": sum(h.status == "unknown" for h in checked.worksite_hazards),
                "local_probabilities_validated": 0,
            }
            summary.append(item)
            if len(samples) < 2 or case["name"] == "real_native_nws_notice_hypothetical_activation":
                samples.append({"case": case["name"], "request": request, "response": outlook})
        # Native national notices are NOT blindly asserted at every location.
        alerts = [OfficialAlert.model_validate(a) for a in snapshot["alerts"]]
        batch, coverage, known_hazards = [], Counter(), set()
        started = time.perf_counter()
        for ordinal, sid in enumerate(exported_sites["batch_site_ids"]):
            site = reconcile_site(index[sid]["site"], index, snapshot["as_of_utc"])
            matching = (
                [
                    OfficialAlert.model_validate(a)
                    for a in snapshot.get("site_alerts", {}).get(sid, [])
                ]
                if sid in snapshot.get("site_alerts", {})
                else [a for a in alerts if a.polygons and _covers(site, a.polygons)]
            )
            regional = [
                a
                for a in alerts
                if not a.polygons
                and any(z.rsplit("/", 1)[-1].startswith(index[sid]["state"]) for z in a.zone_ids)
            ]
            request = {
                "event_context": activation(
                    site.model_dump(mode="json"),
                    snapshot["as_of_utc"],
                    "Flood" if ordinal % 2 == 0 else "High Wind",
                ),
                "site_context": site,
                "evidence": snapshot["evidence"],
                "alerts": matching,
                "context_signals": snapshot["context_signals"],
                "source_states": [snapshot["site_alert_states"][sid]]
                if sid in snapshot.get("site_alert_states", {})
                else [],
            }
            check_rehearsal_scope(
                "supervisor",
                fixture_scope,
                {**request, "site_context": site.model_dump(mode="json")},
            )
            outlook = build_comprehensive_outlook(**request, predictor=predictor)
            checked = _assert_safety(outlook)
            provider_counts = Counter(
                a.evidence.publisher
                for a in checked.evidence
                if a.accepted and not a.evidence.is_fixture
            )
            for provider in provider_counts:
                coverage[provider] += 1
            if any(a.accepted for a in checked.official_notices):
                coverage["NWS site-qualified notices"] += 1
            accepted_ids = {
                a.evidence.evidence_id
                for a in checked.evidence
                if a.accepted and not a.evidence.is_fixture
            }
            accepted_ids.update(
                a.alert.id
                for a in checked.official_notices
                if a.accepted and not a.alert.is_fixture
            )
            for h in checked.worksite_hazards:
                if accepted_ids.intersection(h.source_ids):
                    known_hazards.add(h.hazard_id)
            batch.append(
                {
                    "site_id": sid,
                    "state": index[sid]["state"],
                    "identity_reconciled": True,
                    "source_counts": dict(provider_counts),
                    "accepted_environmental_evidence": sum(provider_counts.values()),
                    "accepted_site_notices": sum(a.accepted for a in checked.official_notices),
                    "point_notice_query_state": snapshot.get("site_alert_states", {})
                    .get(sid, {})
                    .get("state", "not_queried"),
                    "zone_only_notices_not_site_qualified": len(regional),
                    "worksite_unknowns": sum(
                        h.status == "unknown" for h in checked.worksite_hazards
                    ),
                    "local_shaking_supported": any(
                        c.accepted and c.signal.hazard_id == "shaking"
                        for c in checked.context_evidence
                    ),
                    "is_actual_incident": False,
                }
            )
        batch_ms = (time.perf_counter() - started) * 1000
        assert len(batch) >= 50 and len({b["site_id"] for b in batch}) == len(batch)
        tracemalloc.start()
        build_comprehensive_outlook(
            **samples[0]["request"], trust_policy=DEMO_POLICY, predictor=predictor
        )
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        tick = time.perf_counter()
        for _ in range(30):
            ComprehensiveOutlook.model_validate(samples[0]["response"])
        validation_ms = (time.perf_counter() - tick) * 1000 / 30
    report = {
        "status": "PASSED_OFFLINE_RESEARCH_ACCEPTANCE",
        "contract_version": "2.1.0",
        "scenarios": len(summary),
        "scenarios_passed": len(summary),
        "sites": len(batch),
        "identity_reconciled_sites": len(batch),
        "is_actual_incident": False,
        "no_network_enforced": True,
        "new_site_probability_models": 0,
        "operationally_validated": False,
        "source_counts": snapshot["counts"],
        "site_coverage_by_provider": dict(coverage),
        "verified_site_hazard_ids": sorted(known_hazards),
        "offline_tested_hazard_ids": sorted(tested_hazards),
        "sites_without_qualified_environmental_evidence": sum(
            not b["source_counts"] for b in batch
        ),
        "sites_without_qualified_gauge_transfer": len(batch),
        "sites_without_local_shakemap": sum(not b["local_shaking_supported"] for b in batch),
        "sites_without_trusted_live_crew_or_asset_feed": len(batch),
        "performance": {
            "cold_flood_artifact_initialization_ms": cold_artifact_ms,
            "workers": 1,
            "batch_ms": batch_ms,
            "batch_ms_per_site": batch_ms / len(batch),
            "warm_response_validation_mean_ms_30_calls": validation_ms,
            "peak_traced_python_allocations_one_call_bytes": peak,
            "traced_memory_is_not_process_RSS": True,
            "scenario_calls": runtimes,
        },
        "limits": [
            "50-site source evidence coverage is sparse, not a nationwide ingestion system",
            "Batch activations are hypothetical replays",
            "Zone-only alerts are not confirmed local warnings",
            "State association uses EIA workbook; independent state-boundary polygons not acquired",
            "No deployed DB/authorization/route integration verified",
            "No new historical predictive evaluation or artifact refit",
        ],
    }
    (output / "acceptance.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (output / "scenario_results.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output / "site_batch.json").write_text(json.dumps(batch, indent=2), encoding="utf-8")
    if export:
        for name, model in (
            ("comprehensive_request.schema.json", ComprehensiveRequest),
            ("comprehensive_outlook.schema.json", ComprehensiveOutlook),
        ):
            (FIXTURES / name).write_text(
                json.dumps(model.model_json_schema(), indent=2), encoding="utf-8"
            )
        for ordinal, sample in enumerate(samples, 1):
            for field in ("request", "response"):
                (FIXTURES / f"example_{ordinal}_{field}.json").write_text(
                    json.dumps(sample[field], indent=2), encoding="utf-8"
                )
        scenario_manifest = [
            {
                "name": case["name"],
                "is_actual_incident": False,
                "expected_error": case.get("expected_error"),
                "source_mode": case["source_mode"],
                "request_factory": "ml.hazard_scenarios.scenarios()",
                "canonical_request_sha256": hashlib.sha256(
                    json.dumps(case["request"], sort_keys=True).encode()
                ).hexdigest(),
                "input_counts": {
                    key: len(case["request"].get(key, []))
                    for key in (
                        "evidence",
                        "alerts",
                        "reports",
                        "context_signals",
                        "lightning_replay",
                        "source_states",
                    )
                },
            }
            for case in cases
        ]
        (FIXTURES / "scenarios.json").write_text(
            json.dumps(scenario_manifest, indent=2), encoding="utf-8"
        )
        from ml.collect_hazard_sources import fixture_manifest

        fixture_manifest()
    print(
        f"PASS: {len(summary)} scenarios; {len(batch)} reconciled EIA sites; {report['sites_without_qualified_environmental_evidence']} sites lack qualified local environmental evidence; no network; research only",
        flush=True,
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-models", action="store_true")
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument(
        "--export", action="store_true", help="Intentionally update canonical schemas/examples"
    )
    parser.add_argument("--output", type=Path, default=REPORTS)
    options = parser.parse_args()
    run(
        options.output,
        require_models=options.require_models,
        benchmark=options.benchmark,
        export=options.export,
    )
