"""Chronological episode-grouped validation for conditional Flood persistence."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from ml.config import MODEL_PATH, RAW_DATA_DIR, REPORT_DIR, SUPPORTED_EVENT_TYPE
from ml.events import read_noaa_detail_files
from ml.evaluate import binary_metrics
from ml.features import build_active_snapshots, split_events_by_episode, split_snapshots_by_episode
from ml.predict import predict_active_event
from ml.train import (
    SurvivalModels,
    conditional_km_survival,
    conditional_logistic_survival,
    conditional_quantile,
    fit_models,
    save_models,
)


def _survival_probability(models: SurvivalModels, snapshot: dict[str, Any], horizon: int,
                          estimator: str) -> float | None:
    features = snapshot["features"]
    if estimator == "logistic":
        return conditional_logistic_survival(
            models, float(features["elapsed_hours"]), int(features["start_month"]), float(horizon)
        )
    return conditional_km_survival(models, float(features["elapsed_hours"]), float(horizon))


def score_snapshots(snapshots: list[dict[str, Any]], models: SurvivalModels) -> dict[str, Any]:
    results: dict[str, Any] = {"logistic": {}, "kaplan_meier": {}, "duration": {}}
    for estimator, output_key in (("logistic", "logistic"), ("km", "kaplan_meier")):
        for horizon in (6, 12, 24):
            probabilities: list[float] = []
            outcomes: list[bool] = []
            groups: list[str] = []
            for snapshot in snapshots:
                prediction = _survival_probability(models, snapshot, horizon, estimator)
                if prediction is None:
                    continue
                probabilities.append(prediction)
                outcomes.append(bool(snapshot["labels"][f"recorded_event_ongoing_{horizon}h"]))
                groups.append(str(snapshot["episode_id"]))
            results[output_key][f"{horizon}h"] = binary_metrics(probabilities, outcomes, groups)

    absolute_errors: list[float] = []
    covered: list[bool] = []
    coverage_count = 0
    example_candidates: list[dict[str, Any]] = []
    for snapshot in snapshots:
        features = snapshot["features"]
        elapsed = float(features["elapsed_hours"])
        month = int(features["start_month"])
        remaining = float(snapshot["labels"]["remaining_duration_hours"])
        median = conditional_quantile(models, elapsed, month, 0.5)
        lower = conditional_quantile(models, elapsed, month, 0.1)
        upper = conditional_quantile(models, elapsed, month, 0.9)
        if median is not None:
            absolute_errors.append(abs(median - remaining))
        if lower is not None and upper is not None:
            coverage_count += 1
            covered.append(lower <= remaining <= upper)
        probability = conditional_logistic_survival(models, elapsed, month, 6)
        if probability is not None:
            observed = bool(snapshot["labels"]["recorded_event_ongoing_6h"])
            example_candidates.append({
                "event_id": snapshot["event_id"],
                "episode_id": snapshot["episode_id"],
                "as_of_utc": snapshot["as_of_utc"],
                "predicted_ongoing_6h": probability,
                "observed_ongoing_6h": observed,
                "absolute_probability_error": abs(probability - int(observed)),
            })
    example_candidates.sort(key=lambda item: item["absolute_probability_error"], reverse=True)
    results["duration"] = {
        "median_remaining_time_mae_hours": sum(absolute_errors) / len(absolute_errors) if absolute_errors else None,
        "median_prediction_count": len(absolute_errors),
        "p10_p90_interval_coverage": sum(covered) / len(covered) if covered else None,
        "interval_prediction_count": coverage_count,
        "unidentifiable_interval_count": len(snapshots) - coverage_count,
        "largest_6h_probability_errors": example_candidates[:5],
    }
    return results


def _summary(events: list[dict[str, Any]], snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "event_record_count": len(events),
        "episode_count": len({str(event["episode_id"]) for event in events}),
        "snapshot_count": len(snapshots),
        "event_year_counts": dict(sorted(Counter(int(event["source_year"]) for event in events).items())),
    }


def _source_manifest() -> dict[str, Any] | None:
    manifest_path = RAW_DATA_DIR / "source_manifest.json"
    if not manifest_path.exists():
        return None
    source = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        "source": source.get("source"),
        "index_url": source.get("index_url"),
        "retrieval_manifest_created_at_utc": source.get("retrieval_manifest_created_at_utc"),
        "archives": [
            {
                "year": archive.get("year"),
                "file": Path(str(archive.get("path", ""))).name,
                "url": archive.get("url"),
                "bytes": archive.get("bytes"),
                "sha256": archive.get("sha256"),
                "retrieved_at_utc": archive.get("retrieved_at_utc"),
                "cached": archive.get("cached"),
            }
            for archive in source.get("archives", [])
        ],
    }


def run_backtest(detail_files: list[Path], *, output_dir: Path = REPORT_DIR,
                 model_path: Path = MODEL_PATH, train_end_year: int = 2023,
                 validation_year: int = 2024, test_year: int = 2025) -> dict[str, Any]:
    events, source_counts = read_noaa_detail_files(detail_files, event_type=SUPPORTED_EVENT_TYPE)
    split_events = split_events_by_episode(
        events, train_end_year=train_end_year, validation_year=validation_year, test_year=test_year
    )
    all_snapshots = build_active_snapshots(events)
    split_snapshots = split_snapshots_by_episode(all_snapshots, split_events)
    if not split_events["train"] or not split_events["validation"] or not split_events["test"]:
        raise ValueError("chronological backtest requires non-empty train, validation, and test episode groups")

    validation_model = fit_models(split_events["train"])
    validation_scores = score_snapshots(split_snapshots["validation"], validation_model)
    final_training = split_events["train"] + split_events["validation"]
    final_model = fit_models(final_training)
    final_test_scores = score_snapshots(split_snapshots["test"], final_model)
    save_models(final_model, model_path)

    replay_snapshot = next((snapshot for snapshot in split_snapshots["test"]
                            if snapshot["features"]["elapsed_hours"] == 6.0), None)
    if replay_snapshot is None and split_snapshots["test"]:
        replay_snapshot = split_snapshots["test"][0]
    replay_result: dict[str, Any] | None = None
    if replay_snapshot:
        event = next(event for event in split_events["test"] if event["event_id"] == replay_snapshot["event_id"])
        context = {
            "site_id": None,
            "event_id": replay_snapshot["event_id"],
            "event_type": event["event_type"],
            "event_status": "historical_replay",
            "event_start_utc": event["start_utc"],
            "as_of_utc": replay_snapshot["as_of_utc"],
            "location": {"region": event.get("region"), "spatial_match_quality": "region_only"},
            "is_simulated": True,
        }
        replay_result = {
            "prediction_at_as_of": predict_active_event(context, model=final_model),
            "observed_recorded_end_utc": event["end_utc"],
            "observed_remaining_hours": replay_snapshot["labels"]["remaining_duration_hours"],
            "warning": "Historical recorded event end is not worksite clearance.",
        }

    report = {
        "validation_status": "REAL_HISTORICAL_BACKTEST",
        "source": "NOAA NCEI Storm Events details CSV",
        "event_type": SUPPORTED_EVENT_TYPE,
        "target": "conditional recorded-event persistence; NOAA regional event end, not site safety",
        "source_row_counts": source_counts,
            "source_row_counts": source_counts,
            "source_manifest": _source_manifest(),
        "split": {
            "train_years": f"<= {train_end_year}",
            "validation_year": validation_year,
            "test_year": test_year,
            "grouping": "NOAA EPISODE_ID; every event/snapshot in an episode is assigned together by earliest episode start year",
            "train": _summary(split_events["train"], split_snapshots["train"]),
            "validation": _summary(split_events["validation"], split_snapshots["validation"]),
            "test": _summary(split_events["test"], split_snapshots["test"]),
            "excluded_events": len(split_events["excluded"]),
        },
        "validation_2024_train_through_2023": validation_scores,
        "out_of_time_test_2025_train_through_2024": final_test_scores,
        "model": {
            "model_version": final_model.model_version,
            "event_type": final_model.event_type,
            "training_event_count": final_model.training_event_count,
            "training_episode_count": final_model.training_episode_count,
            "features": list(final_model.feature_names),
            "max_supported_age_hours": final_model.max_supported_age_hours,
            "weather_features_used": False,
        },
        "held_out_replay": replay_result,
        "limitations": [
            "NOAA rows are county/zone or reported-point event intervals, not verified EIA site exposure.",
            "NOAA local timestamps are converted using the archive's fixed numeric CZ_TIMEZONE offset; daylight-saving transition ambiguity remains.",
            "The fitted model uses event type, elapsed age, and event-start month only; it does not use weather or current site measurements.",
            "NOAA historical reanalysis availability and source revisions are not equivalent to forecasts actually issued at the historical as-of time.",
            "Episode bootstrap intervals are descriptive; geographic and reporting dependence can remain across NOAA episodes.",
            "Recorded event end is not evidence that infrastructure, access, ground, or electrical hazards are safe.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "backtest_metrics.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=RAW_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--model-path", type=Path, default=MODEL_PATH)
    parser.add_argument("--train-end-year", type=int, default=2023)
    parser.add_argument("--validation-year", type=int, default=2024)
    parser.add_argument("--test-year", type=int, default=2025)
    args = parser.parse_args()
    files = sorted(args.input_dir.glob("StormEvents_details-ftp_v1.0_d*.csv.gz"))
    if not files:
        raise SystemExit(f"No NOAA details archives found under {args.input_dir}; run ml.sources.noaa first.")
    report = run_backtest(files, output_dir=args.output_dir, model_path=args.model_path,
                          train_end_year=args.train_end_year, validation_year=args.validation_year,
                          test_year=args.test_year)
    print(json.dumps({"status": report["validation_status"], "test": report["out_of_time_test_2025_train_through_2024"]}, indent=2))


if __name__ == "__main__":
    main()
