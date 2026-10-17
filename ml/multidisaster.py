"""Serial, separate, predeclared conditional-event backtests and artifact registry."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time

from threadpoolctl import threadpool_limits

from ml.backtest import _score_snapshot
from ml.config import ARTIFACT_DIR, REPORT_DIR
from ml.coverage import load_catalog
from ml.event_types import NOAA_EVENT_TYPES, event_slug
from ml.evaluate import binary_metrics, duration_metrics
from ml.features import build_active_snapshots, split_events_by_episode, split_snapshots_by_episode, validate_snapshot_features
from ml.provision import file_sha256
from ml.train import fit_models, save_models

EXPANSION_REPORT_DIR = REPORT_DIR / "multidisaster"
REGISTRY_PATH = EXPANSION_REPORT_DIR / "registry.json"
PREDECLARED_GATES = {"minimum_evaluation_episode_groups": 30, "minimum_labels_per_class": 10,
                     "maximum_expected_calibration_error": .15, "logistic_validation_improvement_fraction": .02}


def purged_expansion_split(events: list[dict], *, embargo_days: int = 7) -> dict[str, list[dict]]:
    splits = split_events_by_episode(events)
    boundaries = (datetime(2024, 1, 1, tzinfo=timezone.utc), datetime(2025, 1, 1, tzinfo=timezone.utc))
    excluded_groups = set()
    for event in events:
        start = datetime.fromisoformat(event["start_utc"].replace("Z", "+00:00"))
        end = datetime.fromisoformat((event.get("end_utc") or event["start_utc"]).replace("Z", "+00:00"))
        if any(start < cutoff + timedelta(days=embargo_days) and end > cutoff - timedelta(days=embargo_days)
               for cutoff in boundaries):
            excluded_groups.add(str(event["episode_id"]))
    for name in ("train", "validation", "test"):
        keep = []
        for event in splits[name]:
            (splits["excluded"] if str(event["episode_id"]) in excluded_groups else keep).append(event)
        splits[name] = keep
    return splits


def comparable_scores(snapshots: list[dict], model, horizons: tuple[int, ...]) -> dict:
    scored = []
    start = time.perf_counter()
    interval = max(1, len(snapshots) // 4)
    for index, snapshot in enumerate(snapshots, 1):
        validate_snapshot_features(snapshot)
        scored.append(_score_snapshot(snapshot, model, horizons))
        if index % interval == 0 or index == len(snapshots):
            elapsed = time.perf_counter() - start
            rate = index / elapsed if elapsed else 0
            print(f"[score] {index}/{len(snapshots)} snapshots {elapsed:.2f}s {rate:.0f}/s errors=0", flush=True)
    results = {"logistic": {}, "kaplan_meier": {}}
    for horizon in horizons:
        eligible = [(snapshot, row) for snapshot, row in zip(snapshots, scored)
                    if row["logistic_probabilities"][horizon] is not None and row["km_probabilities"][horizon] is not None]
        outcomes = [bool(snapshot["labels"][f"recorded_event_ongoing_{horizon}h"]) for snapshot, _ in eligible]
        groups = [row["episode_id"] for _, row in eligible]
        for name, key in (("logistic", "logistic_probabilities"), ("kaplan_meier", "km_probabilities")):
            probabilities = [row[key][horizon] for _, row in eligible]
            metrics = binary_metrics(probabilities, outcomes, groups)
            metrics["positive_labels"] = sum(outcomes)
            metrics["negative_labels"] = len(outcomes) - sum(outcomes)
            metrics["expected_calibration_error"] = (
                sum(bin_["count"] * abs(bin_["mean_predicted"] - bin_["observed_frequency"])
                    for bin_ in metrics["reliability"]) / len(probabilities) if probabilities else None)
            results[name][f"{horizon}h"] = metrics
    for name, key in (("logistic", "quantiles"), ("kaplan_meier", "km_quantiles")):
        results[name]["duration"] = duration_metrics([row["remaining_hours"] for row in scored],
                                                    [row[key] for row in scored],
                                                    [row["episode_id"] for row in scored])
    return results


def qualification(validation: dict, test: dict, selected: str, horizons: tuple[int, ...]) -> list[str]:
    failures = []
    for split_name, scores in (("validation", validation), ("test", test)):
        for horizon in horizons:
            metrics = scores[selected][f"{horizon}h"]
            if metrics["episode_count"] < PREDECLARED_GATES["minimum_evaluation_episode_groups"]:
                failures.append(f"{split_name}_{horizon}h_insufficient_episode_groups")
            if min(metrics["positive_labels"], metrics["negative_labels"]) < PREDECLARED_GATES["minimum_labels_per_class"]:
                failures.append(f"{split_name}_{horizon}h_sparse_outcome_class")
            ece = metrics["expected_calibration_error"]
            if ece is None or ece > PREDECLARED_GATES["maximum_expected_calibration_error"]:
                failures.append(f"{split_name}_{horizon}h_calibration_gate_failed")
    return failures


def run_category(events: list[dict], event_type: str, *, horizons: tuple[int, ...],
                 source_scope: str, source_version: str, definition: str,
                 offsets: tuple[int, ...] = (1, 3, 6, 12), source_receipts: list[dict] | None = None,
                 output_dir: Path = EXPANSION_REPORT_DIR, minimum_age: int = 1,
                 extra_limitations: list[str] | None = None) -> dict:
    started = time.perf_counter()
    print(f"\n[category] {event_type}: {len(events):,} candidate records; serial execution", flush=True)
    timings = {}
    stage = time.perf_counter()
    splits = purged_expansion_split(events)
    snapshots = build_active_snapshots(events, offsets, horizons)
    snapshot_splits = split_snapshots_by_episode(snapshots, splits)
    timings["split_snapshot_seconds"] = time.perf_counter() - stage
    stage = time.perf_counter()
    validation_model = fit_models(splits["train"], event_type=event_type, source_scope=source_scope)
    timings["validation_fit_seconds"] = time.perf_counter() - stage
    stage = time.perf_counter()
    validation = comparable_scores(snapshot_splits["validation"], validation_model, horizons)
    timings["validation_score_bootstrap_seconds"] = time.perf_counter() - stage
    means = {name: sum(validation[name][f"{h}h"]["brier_score"] for h in horizons) / len(horizons)
             for name in ("logistic", "kaplan_meier")}
    selected = "logistic" if means["logistic"] < .98 * means["kaplan_meier"] else "kaplan_meier"
    print(f"[category] {event_type}: validation selected {selected}; scoring fixed 2025 test once", flush=True)
    stage = time.perf_counter()
    final_model = fit_models(splits["train"] + splits["validation"], event_type=event_type, source_scope=source_scope)
    timings["final_fit_seconds"] = time.perf_counter() - stage
    stage = time.perf_counter()
    test = comparable_scores(snapshot_splits["test"], final_model, horizons)
    timings["test_score_bootstrap_seconds"] = time.perf_counter() - stage
    failed = qualification(validation, test, selected, horizons)
    artifact = ARTIFACT_DIR / "multidisaster" / (event_slug(event_type) + ".joblib")
    save_models(final_model, artifact)
    groups = {name: {row["episode_id"] for row in rows} for name, rows in splits.items()}
    if groups["train"] & groups["validation"] or groups["train"] & groups["test"] or groups["validation"] & groups["test"]:
        raise RuntimeError("Expansion episode leakage")
    example_snapshot = next((row for row in snapshot_splits["test"] if row["features"]["elapsed_hours"] >= minimum_age), None)
    example_context = None
    if example_snapshot:
        event = next(event for event in splits["test"] if event["event_id"] == example_snapshot["event_id"])
        example_context = {
            "event_id": event["event_id"], "event_type": event_type, "event_status": "historical_replay",
            "event_start_utc": event["start_utc"], "as_of_utc": example_snapshot["as_of_utc"],
            "event_definition": definition, "is_simulated": True,
            "location": {"region": event.get("region") or "historical station/region", "spatial_match_quality": "region_only"},
        }
        if event.get("station_id"):
            example_context["station_id"] = event["station_id"]
    from ml.predict import _outcomes
    reference = (_outcomes(final_model, example_snapshot["features"]["elapsed_hours"],
                           example_snapshot["features"]["start_month"], selected, horizons)
                 if example_snapshot and not failed else None)
    card = {
        "status": "evaluated_research" if not failed else "trained_not_qualified",
        "event_type": event_type, "category": NOAA_EVENT_TYPES[event_type].category if event_type in NOAA_EVENT_TYPES else "heat",
        "event_definition": definition, "target": source_scope,
        "supported_horizons_hours": list(horizons), "minimum_event_age_hours": minimum_age,
        "artifact": artifact.relative_to(ARTIFACT_DIR).as_posix(), "artifact_sha256": file_sha256(artifact),
        "artifact_model_version": final_model.model_version, "selected_estimator": selected,
        "data_version": source_version, "source_receipts": source_receipts or [],
        "training_policy": "whole_episode_purge_plus_7_day_fit_selection_embargo",
        "fit_recipe": {"offsets_hours": list(offsets), "train_end_year": 2023,
                       "validation_year": 2024, "test_year": 2025, "embargo_days": 7},
        "split": {name: {"event_records": len(rows), "episode_groups": len(groups[name]),
                          "snapshots": len(snapshot_splits[name])} for name, rows in splits.items()},
        "validation": validation, "test": test, "validation_mean_brier": means,
        "qualification_rules": PREDECLARED_GATES, "qualification_failures": failed,
        "historical_asof_availability_verified": False,
        "operational_evaluation_eligible": False, "production_eligibility": False,
        "prediction_eligible": not failed,
        "example_context": example_context,
        "example_observed_remaining_hours": example_snapshot["labels"]["remaining_duration_hours"] if example_snapshot else None,
        "reference_ongoing_probability": reference["recorded_event_ongoing_probability"] if reference else None,
        "limitations": ["Recorded/observed episode end is not worksite clearance.",
                        "2025 is a first fixed evaluation for this new target, with no test-score tuning; Flood 2025 was previously inspected.",
                        "Historical source revision/availability is not verified as of the past decision time.",
                        "Episode groups are reporting/evaluation clusters, not verified independent disasters."] + (extra_limitations or []),
        "timings_seconds": {**timings, "total": time.perf_counter() - started},
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / (event_slug(event_type) + ".json")
    report_path.write_text(json.dumps(card, indent=2, allow_nan=False), encoding="utf-8")
    print(f"[category] {event_type}: {card['status']} {card['timings_seconds']['total']:.2f}s; {failed}", flush=True)
    return card


def update_registry(cards: list[dict], path: Path = REGISTRY_PATH) -> dict:
    registry = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"contract_version": "1.1", "events": {}}
    for card in cards:
        registry["events"][card["event_type"]] = {key: card[key] for key in (
            "status", "category", "event_type", "event_definition", "target", "supported_horizons_hours",
            "minimum_event_age_hours", "artifact", "artifact_sha256", "artifact_model_version", "selected_estimator",
            "data_version", "prediction_eligible", "qualification_failures", "limitations",
            "historical_asof_availability_verified", "operational_evaluation_eligible", "production_eligibility")}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, indent=2, allow_nan=False), encoding="utf-8")
    return registry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-types", nargs="+", default=[name for name, spec in NOAA_EVENT_TYPES.items() if spec.candidate and name != "Flood"])
    args = parser.parse_args()
    coverage = json.loads((EXPANSION_REPORT_DIR / "coverage.json").read_text(encoding="utf-8"))
    events = load_catalog()
    cards = []
    with threadpool_limits(limits=1):
        for name in args.event_types:
            if name not in NOAA_EVENT_TYPES or not NOAA_EVENT_TYPES[name].candidate or name == "Flood":
                raise SystemExit("Choose an approved expansion candidate; Flood is preserved separately")
            rows = [row for row in events if row["event_type"] == name and row.get("duration_hours") and row["duration_hours"] > 0]
            cards.append(run_category(rows, name, horizons=NOAA_EVENT_TYPES[name].horizons,
                source_scope=f"NOAA regional positive-duration {name} recorded-interval persistence; not intensity or site safety",
                source_version="NOAA-2021-2025:" + coverage["archive_set_sha256"],
                definition="noaa_positive_continuous_recorded_interval", source_receipts=coverage["archives"],
                extra_limitations=[NOAA_EVENT_TYPES[name].limitation, "Zero-duration/point reports are excluded; at least one hour of independently confirmed continuing activity is required."]))
            update_registry(cards[-1:])


if __name__ == "__main__":
    main()
