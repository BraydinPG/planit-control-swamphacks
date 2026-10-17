"""Chronological episode-grouped validation for conditional Flood persistence."""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from collections import Counter
from pathlib import Path
from typing import Any

from ml.config import MODEL_PATH, RAW_DATA_DIR, REPORT_DIR, SUPPORTED_EVENT_TYPE
from ml.events import read_noaa_detail_files
from ml.evaluate import binary_metrics, duration_metrics
from ml.features import build_active_snapshots, split_events_by_episode, split_snapshots_by_episode
from ml.predict import predict_active_event
from ml.weather_features import deterministic_episode_sample
from ml.train import (
    SurvivalModels,
    conditional_km_survival_horizons,
    conditional_km_survival_curve,
    conditional_logistic_survival_curve,
    fit_models,
    quantiles_from_survival_curve,
    save_models,
)

_WORKER_MODELS: SurvivalModels | None = None
_THREADPOOL_LIMITER: Any = None


def _initialize_score_worker(models: SurvivalModels) -> None:
    global _WORKER_MODELS, _THREADPOOL_LIMITER
    from threadpoolctl import threadpool_limits

    _WORKER_MODELS = models
    _THREADPOOL_LIMITER = threadpool_limits(limits=1)


def _score_snapshot(snapshot: dict[str, Any], models: SurvivalModels,
                    horizons_hours: tuple[int, ...] = (6, 12, 24)) -> dict[str, Any]:
    features = snapshot["features"]
    elapsed = float(features["elapsed_hours"])
    month = int(features["start_month"])
    curve = conditional_logistic_survival_curve(models, elapsed, month)
    km_horizons = conditional_km_survival_horizons(models, elapsed, horizons_hours)
    km_curve = conditional_km_survival_curve(models, elapsed)
    quantiles = (
        quantiles_from_survival_curve(curve, models.max_followup_hours - elapsed, (0.1, 0.5, 0.9))
        if curve is not None else {quantile: None for quantile in (0.1, 0.5, 0.9)}
    )
    probabilities = {
        horizon: curve[horizon - 1] if curve is not None and len(curve) >= horizon else None
        for horizon in horizons_hours
    }
    return {
        "event_id": snapshot["event_id"],
        "episode_id": str(snapshot["episode_id"]),
        "remaining_hours": float(snapshot["labels"]["remaining_duration_hours"]),
        "logistic_probabilities": probabilities,
        "km_probabilities": km_horizons,
        "quantiles": quantiles,
        "km_quantiles": (quantiles_from_survival_curve(km_curve, models.max_followup_hours - elapsed, (0.1, 0.5, 0.9))
                         if km_curve is not None else {q: None for q in (0.1, 0.5, 0.9)}),
    }


def _score_snapshot_chunk(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if _WORKER_MODELS is None:
        raise RuntimeError("score worker was not initialized with a model")
    return [_score_snapshot(snapshot, _WORKER_MODELS) for snapshot in snapshots]


def recommended_worker_count() -> int:
    # On the measured bounded workload, Windows spawn/import overhead outweighed
    # scoring work at 4/8/12 processes. Keep parallelism explicitly opt-in.
    return 1


def _show_progress(label: str, completed: int, total: int, started_at: float | None = None,
                   workers: int = 1) -> None:
    if total <= 0:
        return
    percent = min(100, int(completed * 100 / total))
    elapsed = max(0.0, time.perf_counter() - started_at) if started_at is not None else 0.0
    rate = completed / elapsed if elapsed > 0 else 0.0
    eta = (total - completed) / rate if rate > 0 else 0.0
    sys.stderr.write(
        f"\r{label}: {completed}/{total} ({percent}%) | {elapsed:.1f}s | "
        f"{rate:.1f}/s | ETA {eta:.1f}s | workers {workers}"
    )
    if completed >= total:
        sys.stderr.write("\n")
    sys.stderr.flush()


def _phase(message: str) -> None:
    sys.stderr.write(f"\n[backtest] {message}\n")
    sys.stderr.flush()


def score_snapshots(snapshots: list[dict[str, Any]], models: SurvivalModels,
                    progress_label: str | None = None, workers: int = 1) -> dict[str, Any]:
    if workers < 1:
        raise ValueError("workers must be at least 1")
    results: dict[str, Any] = {"logistic": {}, "kaplan_meier": {}, "duration": {}}
    horizons = (6, 12, 24)
    paired = {
        estimator: {horizon: ([], [], []) for horizon in horizons}
        for estimator in ("logistic", "kaplan_meier")
    }
    absolute_errors: list[float] = []
    covered: list[bool] = []
    coverage_count = 0
    example_candidates: list[dict[str, Any]] = []
    total = len(snapshots)
    update_interval = max(1, total // 20)
    started_at = time.perf_counter()
    def rows_serial() -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for index, snapshot in enumerate(snapshots, start=1):
            output.append(_score_snapshot(snapshot, models))
            if progress_label and (index % update_interval == 0 or index == total):
                _show_progress(progress_label, index, total, started_at, workers=1)
        return output

    if workers == 1 or total <= 1:
        scored_rows = rows_serial()
    else:
        chunk_size = max(1, math.ceil(total / (workers * 4)))
        chunks = [snapshots[start:start + chunk_size] for start in range(0, total, chunk_size)]
        actual_workers = min(workers, len(chunks))
        scored_rows = []
        completed = 0
        with ProcessPoolExecutor(
            max_workers=actual_workers,
            mp_context=multiprocessing.get_context("spawn"),
            initializer=_initialize_score_worker,
            initargs=(models,),
        ) as executor:
            for chunk_rows in executor.map(_score_snapshot_chunk, chunks, chunksize=1):
                scored_rows.extend(chunk_rows)
                completed += len(chunk_rows)
                if progress_label:
                    _show_progress(progress_label, completed, total, started_at, workers=actual_workers)

    # Preserve input order after process mapping, so error examples and reports are reproducible.
    for snapshot, row in zip(snapshots, scored_rows):
        remaining = row["remaining_hours"]
        quantile_values = row["quantiles"]
        median = quantile_values[0.5]
        lower = quantile_values[0.1]
        upper = quantile_values[0.9]
        if median is not None:
            absolute_errors.append(abs(median - remaining))
        if lower is not None and upper is not None:
            coverage_count += 1
            covered.append(lower <= remaining <= upper)
        for horizon in horizons:
            observed = bool(snapshot["labels"][f"recorded_event_ongoing_{horizon}h"])
            episode_id = row["episode_id"]
            logistic_probability = row["logistic_probabilities"][horizon]
            if logistic_probability is not None:
                pred, labels, groups = paired["logistic"][horizon]
                pred.append(logistic_probability)
                labels.append(observed)
                groups.append(episode_id)
            km_probability = row["km_probabilities"][horizon]
            if km_probability is not None:
                pred, labels, groups = paired["kaplan_meier"][horizon]
                pred.append(km_probability)
                labels.append(observed)
                groups.append(episode_id)
        probability = row["logistic_probabilities"][6]
        if probability is not None:
            observed = bool(snapshot["labels"]["recorded_event_ongoing_6h"])
            example_candidates.append({
                "event_id": snapshot["event_id"],
                "episode_id": row["episode_id"],
                "as_of_utc": snapshot["as_of_utc"],
                "predicted_ongoing_6h": probability,
                "observed_ongoing_6h": observed,
                "absolute_probability_error": abs(probability - int(observed)),
            })

    for estimator, output_key in (("logistic", "logistic"), ("kaplan_meier", "kaplan_meier")):
        for horizon in horizons:
            result_predictions, result_outcomes, result_groups = paired[estimator][horizon]
            results[output_key][f"{horizon}h"] = binary_metrics(
                result_predictions, result_outcomes, result_groups
            )
    example_candidates.sort(key=lambda item: (-item["absolute_probability_error"], str(item["event_id"])))
    results["duration"] = {
        "median_remaining_time_mae_hours": sum(absolute_errors) / len(absolute_errors) if absolute_errors else None,
        "median_prediction_count": len(absolute_errors),
        "p10_p90_interval_coverage": sum(covered) / len(covered) if covered else None,
        "interval_prediction_count": coverage_count,
        "unidentifiable_interval_count": len(snapshots) - coverage_count,
        "largest_6h_probability_errors": example_candidates[:5],
    }
    results["duration_by_estimator"] = {
        name: duration_metrics([row["remaining_hours"] for row in scored_rows],
                               [row[key] for row in scored_rows],
                               [row["episode_id"] for row in scored_rows])
        for name, key in (("logistic", "quantiles"), ("kaplan_meier", "km_quantiles"))
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
                 validation_year: int = 2024, test_year: int = 2025,
                 show_progress: bool = True, workers: int = 1, smoke: bool = False,
                 smoke_events_per_year: int = 20,
                 report_filename: str = "backtest_metrics.json") -> dict[str, Any]:
    if smoke and model_path == MODEL_PATH:
        model_path = MODEL_PATH.with_name("active_event_smoke.joblib")
    if smoke and report_filename == "backtest_metrics.json":
        report_filename = "backtest_smoke_metrics.json"
    timings: dict[str, float] = {}
    stage_started = time.perf_counter()
    if show_progress:
        _phase(f"reading Flood rows from {len(detail_files)} NOAA archive(s)")
    events, source_counts = read_noaa_detail_files(detail_files, event_type=SUPPORTED_EVENT_TYPE)
    timings["noaa_parse_seconds"] = time.perf_counter() - stage_started
    full_event_count = len(events)
    if smoke:
        events = deterministic_episode_sample(events, per_year=smoke_events_per_year, seed=42)
    if show_progress:
        episode_count = len({event["episode_id"] for event in events})
        scope = "smoke sample" if smoke else "full data"
        _phase(f"normalized {len(events):,} {scope} event records across {episode_count:,} episodes")
    stage_started = time.perf_counter()
    split_events = split_events_by_episode(
        events, train_end_year=train_end_year, validation_year=validation_year, test_year=test_year
    )
    all_snapshots = build_active_snapshots(events)
    split_snapshots = split_snapshots_by_episode(all_snapshots, split_events)
    timings["snapshot_generation_seconds"] = time.perf_counter() - stage_started
    if show_progress:
        _phase(f"built {len(all_snapshots):,} active snapshots; fitting validation model")
    if not split_events["train"] or not split_events["validation"] or not split_events["test"]:
        raise ValueError("chronological backtest requires non-empty train, validation, and test episode groups")

    stage_started = time.perf_counter()
    validation_model = fit_models(split_events["train"])
    timings["validation_model_fit_seconds"] = time.perf_counter() - stage_started
    if show_progress:
        _phase("scoring validation snapshots")
    stage_started = time.perf_counter()
    validation_scores = score_snapshots(
        split_snapshots["validation"], validation_model,
        progress_label="validation snapshots" if show_progress else None,
        workers=workers,
    )
    timings["validation_scoring_seconds"] = time.perf_counter() - stage_started
    final_training = split_events["train"] + split_events["validation"]
    stage_started = time.perf_counter()
    final_model = fit_models(final_training)
    timings["final_model_fit_seconds"] = time.perf_counter() - stage_started
    if show_progress:
        _phase("scoring previously inspected out-of-time test snapshots")
    stage_started = time.perf_counter()
    final_test_scores = score_snapshots(
        split_snapshots["test"], final_model,
        progress_label="test snapshots" if show_progress else None,
        workers=workers,
    )
    timings["test_scoring_seconds"] = time.perf_counter() - stage_started
    stage_started = time.perf_counter()
    save_models(final_model, model_path)
    timings["artifact_save_seconds"] = time.perf_counter() - stage_started

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
        "validation_status": "SMOKE_TEST_NOT_FINAL_VALIDATION" if smoke else "REAL_HISTORICAL_BACKTEST",
        "smoke_test": {
            "enabled": smoke,
            "sampled_event_records": len(events) if smoke else None,
            "available_full_event_records": full_event_count,
            "per_year_episode_cap": smoke_events_per_year if smoke else None,
            "seed": 42 if smoke else None,
        },
        "source": "NOAA NCEI Storm Events details CSV",
        "event_type": SUPPORTED_EVENT_TYPE,
        "target": "conditional recorded-event persistence; NOAA regional event end, not site safety",
        "source_row_counts": source_counts,
        "source_manifest": _source_manifest(),
        "split": {
            "train_years": f"<= {train_end_year}",
            "validation_year": validation_year,
            "test_year": test_year,
            "grouping": "NOAA EPISODE_ID; intact episodes assigned by earliest start, with entire episodes crossing fit/selection cutoffs purged",
            "train": _summary(split_events["train"], split_snapshots["train"]),
            "validation": _summary(split_events["validation"], split_snapshots["validation"]),
            "test": _summary(split_events["test"], split_snapshots["test"]),
            "excluded_events": len(split_events["excluded"]),
            "excluded_episode_count": len({event["episode_id"] for event in split_events["excluded"]}),
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
            "training_policy": final_model.training_policy,
            "default_estimator": "kaplan_meier",
        },
        "test_interpretation": "2025 was previously inspected; corrected rerun, not a fresh untouched holdout",
        "production_eligibility": False,
        "execution": {
            "workers_requested": workers,
            "validation_scoring_workers": min(workers, max(1, len(split_snapshots["validation"]))),
            "test_scoring_workers": min(workers, max(1, len(split_snapshots["test"]))),
            "timings_seconds": timings,
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
    if show_progress:
        _phase("writing metrics and model artifact")
    (output_dir / report_filename).write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=RAW_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--model-path", type=Path, default=MODEL_PATH)
    parser.add_argument("--train-end-year", type=int, default=2023)
    parser.add_argument("--validation-year", type=int, default=2024)
    parser.add_argument("--test-year", type=int, default=2025)
    parser.add_argument("--workers", type=int, default=None,
                        help=f"scoring processes (default: {recommended_worker_count()} from available CPUs)")
    parser.add_argument("--smoke", "--fast", action="store_true",
                        help="run a deterministic small sample; metrics are not final validation")
    parser.add_argument("--smoke-events-per-year", type=int, default=20)
    args = parser.parse_args()
    files = sorted(args.input_dir.glob("StormEvents_details-ftp_v1.0_d*.csv.gz"))
    if not files:
        raise SystemExit(f"No NOAA details archives found under {args.input_dir}; run ml.sources.noaa first.")
    workers = args.workers if args.workers is not None else recommended_worker_count()
    if workers < 1 or workers > 20:
        raise SystemExit("--workers must be between 1 and 20")
    model_path = args.model_path
    report_filename = "backtest_metrics.json"
    if args.smoke:
        if args.smoke_events_per_year < 20:
            raise SystemExit("smoke mode needs at least 20 sampled episodes per year for model support")
        if model_path == MODEL_PATH:
            model_path = MODEL_PATH.with_name("active_event_smoke.joblib")
        report_filename = "backtest_smoke_metrics.json"
    report = run_backtest(files, output_dir=args.output_dir, model_path=model_path,
                          train_end_year=args.train_end_year, validation_year=args.validation_year,
                          test_year=args.test_year, workers=workers, smoke=args.smoke,
                          smoke_events_per_year=args.smoke_events_per_year,
                          report_filename=report_filename)
    print(json.dumps({
        "status": report["validation_status"],
        "workers": workers,
        "timings_seconds": report["execution"]["timings_seconds"],
        "test_brier": {name: {h: metrics["brier_score"] for h, metrics in report["out_of_time_test_2025_train_through_2024"][name].items()}
                       for name in ("logistic", "kaplan_meier")},
        "report_filename": report_filename,
    }, indent=2))


if __name__ == "__main__":
    main()
