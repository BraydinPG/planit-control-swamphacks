"""Bounded profiling and worker-count benchmark; never runs a full historical backtest."""

from __future__ import annotations

import argparse
import cProfile
from collections import Counter
import hashlib
import io
import json
import os
import pstats
import sys
import threading
import time
from datetime import timedelta
from pathlib import Path
from typing import Any

import psutil

from ml.backtest import _score_snapshot, score_snapshots
from ml.config import MODEL_PATH, RAW_DATA_DIR, REPORT_DIR
from ml.evaluate import episode_bootstrap_brier
from ml.events import read_noaa_detail_files
from ml.features import build_active_snapshots, split_events_by_episode
from ml.monte_carlo import simulate_model
from ml.sources.weather import build_archive_url, filter_hourly_as_of
from ml.train import (conditional_km_survival, conditional_logistic_survival,
                      conditional_logistic_survival_curve,
                      conditional_logistic_survival_horizons, fit_models, load_models,
                      quantiles_from_survival_curve)
from ml.weather_features import deterministic_episode_sample, extract_weather_features


class ProcessTreeRssSampler:
    def __init__(self, sample_interval_seconds: float = 0.05) -> None:
        self.sample_interval_seconds = sample_interval_seconds
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.peak_bytes = 0
        self.process = psutil.Process()

    def _sample_tree(self) -> None:
        total = 0
        try:
            processes = [self.process, *self.process.children(recursive=True)]
            for process in processes:
                try:
                    total += process.memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            self.peak_bytes = max(self.peak_bytes, total)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    def _sample(self) -> None:
        while not self.stop_event.is_set():
            self._sample_tree()
            self.stop_event.wait(self.sample_interval_seconds)

    def __enter__(self) -> "ProcessTreeRssSampler":
        self._sample_tree()
        self.thread = threading.Thread(target=self._sample, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)


def _same_scores(left: dict[str, Any], right: dict[str, Any], tolerance: float = 1e-12) -> bool:
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(_same_scores(left[key], right[key], tolerance) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(_same_scores(first, second, tolerance) for first, second in zip(left, right))
    if isinstance(left, float) and isinstance(right, float):
        return abs(left - right) <= tolerance
    return left == right


def _profile_weather_cache(events: list[dict[str, Any]], cache_dir: Path) -> dict[str, Any]:
    started = time.perf_counter()
    cache_hits = 0
    extracted_feature_count = 0
    for event in events:
        start_text = str(event["start_utc"])
        start = __import__("datetime").datetime.fromisoformat(start_text.replace("Z", "+00:00"))
        date_start = (start.date() - timedelta(days=1)).isoformat()
        date_end = (start.date() + timedelta(days=1)).isoformat()
        url = build_archive_url(float(event["begin_lat"]), float(event["begin_lon"]), date_start, date_end)
        cache_key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        cache_path = cache_dir / f"open_meteo_{cache_key}.json"
        if not cache_path.exists():
            continue
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        cutoff = (start + timedelta(hours=24)).isoformat()
        hourly = filter_hourly_as_of(payload, cutoff)
        features = extract_weather_features(hourly, cutoff)["features"]
        extracted_feature_count += sum(value is not None for value in features.values())
        cache_hits += 1
    return {
        "cached_events_processed": cache_hits,
        "nonmissing_weather_features_extracted": extracted_feature_count,
        "elapsed_seconds": time.perf_counter() - started,
        "network_requests": 0,
    }


def _profile_bootstrap(model: Any, snapshots: list[dict[str, Any]], replicates: int = 200) -> dict[str, Any]:
    probabilities: list[float] = []
    outcomes: list[bool] = []
    episodes: list[str] = []
    for snapshot in snapshots:
        features = snapshot["features"]
        horizon_predictions = conditional_logistic_survival_horizons(
            model, float(features["elapsed_hours"]), int(features["start_month"]), (6,)
        )
        probability = horizon_predictions[6]
        if probability is not None:
            probabilities.append(probability)
            outcomes.append(bool(snapshot["labels"]["recorded_event_ongoing_6h"]))
            episodes.append(str(snapshot["episode_id"]))
    start = time.perf_counter()
    interval = episode_bootstrap_brier(probabilities, outcomes, episodes, replicates=replicates, seed=42)
    return {
        "replicates": replicates,
        "snapshot_count": len(probabilities),
        "episode_count": len(set(episodes)),
        "elapsed_seconds": time.perf_counter() - start,
        "interval": interval,
    }


def _active_backtest_processes() -> list[dict[str, Any]]:
    active: list[dict[str, Any]] = []
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            command = process.info.get("cmdline") or []
            if (process.info.get("pid") != os.getpid()
                    and any(command[index:index + 2] in (["-m", "ml.backtest"], ["-m", "ml.weather_backtest"])
                            for index in range(len(command) - 1))):
                scope = ("smoke" if "--smoke" in command or "--fast" in command else
                         "retrospective_weather" if "ml.weather_backtest" in command else "full_historical_backtest")
                active.append({"pid": process.info["pid"], "name": process.info.get("name"), "scope": scope})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return active


def _legacy_score_snapshot(snapshot: dict[str, Any], models: Any) -> dict[str, Any]:
    """Reference call pattern from 9281c1f:ml/backtest.py and ml/train.py.

    Four scalar horizons (including the repeated 6h error example) and three
    independently computed duration curves. Only prediction timing is compared;
    this is not a reproduction of the running process or full-backtest runtime.
    """
    age = float(snapshot["features"]["elapsed_hours"])
    month = int(snapshot["features"]["start_month"])
    probabilities = {h: conditional_logistic_survival(models, age, month, h) for h in (6, 12, 24)}
    conditional_logistic_survival(models, age, month, 6)
    quantiles: dict[float, float | None] = {}
    for q in (0.1, 0.5, 0.9):
        curve = conditional_logistic_survival_curve(models, age, month)
        quantiles[q] = (quantiles_from_survival_curve(curve, models.max_followup_hours - age, (q,))[q]
                        if curve is not None else None)
    result = {
        "event_id": snapshot["event_id"], "episode_id": str(snapshot["episode_id"]),
        "remaining_hours": float(snapshot["labels"]["remaining_duration_hours"]),
        "logistic_probabilities": probabilities,
        "km_probabilities": {h: conditional_km_survival(models, age, h) for h in (6, 12, 24)},
        "quantiles": quantiles,
    }
    # KM duration metrics were added after the reference revision. Compute the
    # same addition in both paths so the legacy-vs-reuse comparison stays paired.
    from ml.train import conditional_quantiles
    result["km_quantiles"] = conditional_quantiles(models, age, month, (0.1, 0.5, 0.9), estimator="km")
    return result


def benchmark_curve_reuse(snapshots: list[dict[str, Any]], model: Any, repeats: int = 5) -> dict[str, Any]:
    """Time equivalent predictions separately from metrics/bootstrap overhead."""
    sample = snapshots[:24]
    # Warm both paths; alternate order to reduce first-call bias.
    for scorer in (_legacy_score_snapshot, _score_snapshot):
        for snapshot in sample:
            scorer(snapshot, model)
    timings = {"legacy": [], "reused_curve": []}
    outputs: dict[str, Any] = {}
    for repeat in range(repeats):
        order = ("legacy", "reused_curve") if repeat % 2 == 0 else ("reused_curve", "legacy")
        for name in order:
            scorer = _legacy_score_snapshot if name == "legacy" else _score_snapshot
            started = time.perf_counter()
            outputs[name] = [scorer(snapshot, model) for snapshot in sample]
            timings[name].append(time.perf_counter() - started)
    import statistics
    legacy = statistics.median(timings["legacy"])
    reused = statistics.median(timings["reused_curve"])
    if not _same_scores(outputs["legacy"], outputs["reused_curve"]):
        raise RuntimeError("optimized predictions differ from the preserved reference")
    return {"reference_revision": "9281c1f", "snapshot_count": len(sample), "repeats": repeats,
            "elapsed_seconds_by_repeat": timings, "legacy_median_seconds": legacy,
            "reused_curve_median_seconds": reused, "measured_prediction_speedup": legacy / reused,
            "predictions_match_tolerance_1e_12": True, "full_backtest_speedup_measured": False}


def run_benchmark(*, input_dir: Path = RAW_DATA_DIR, artifact_path: Path = MODEL_PATH,
                  cache_dir: Path = RAW_DATA_DIR / "weather", events_per_year: int = 20,
                  worker_counts: tuple[int, ...] = (1, 4, 8, 12),
                  bootstrap_replicates: int = 200,
                  output_path: Path = REPORT_DIR / "worker_benchmark.json") -> dict[str, Any]:
    worker_counts = tuple(dict.fromkeys((1, *worker_counts)))
    if events_per_year < 20 or any(count < 1 or count > 20 for count in worker_counts):
        raise ValueError("use at least 20 events per year and worker counts between 1 and 20")
    active_jobs = _active_backtest_processes()
    started = time.perf_counter()
    archive_paths = sorted(input_dir.glob("StormEvents_details-ftp_v1.0_d*.csv.gz"))
    if not archive_paths:
        raise ValueError(f"No NOAA detail archives found under {input_dir}")

    print(f"[benchmark] parsing {len(archive_paths)} NOAA archive(s)", file=sys.stderr, flush=True)
    phase_start = time.perf_counter()
    events, source_counts = read_noaa_detail_files(archive_paths)
    parse_seconds = time.perf_counter() - phase_start

    print(f"[benchmark] parsed {len(events):,} supported events", file=sys.stderr, flush=True)
    phase_start = time.perf_counter()
    sampled = deterministic_episode_sample(events, per_year=events_per_year, seed=42)
    event_splits = split_events_by_episode(sampled)
    snapshots = build_active_snapshots(sampled)
    snapshot_seconds = time.perf_counter() - phase_start

    print(f"[benchmark] smoke data: {len(sampled)} events, {len(snapshots)} snapshots", file=sys.stderr, flush=True)
    phase_start = time.perf_counter()
    model = load_models(artifact_path)
    artifact_load_seconds = time.perf_counter() - phase_start
    print("[benchmark] comparing preserved repeated-curve scoring with curve reuse", file=sys.stderr, flush=True)
    curve_reuse = benchmark_curve_reuse(snapshots, model)
    phase_start = time.perf_counter()
    curves = [conditional_logistic_survival_curve(model, float(s["features"]["elapsed_hours"]),
                                                 int(s["features"]["start_month"])) for s in snapshots]
    curve_seconds = time.perf_counter() - phase_start
    phase_start = time.perf_counter()
    for snapshot, curve in zip(snapshots, curves):
        if curve is not None:
            quantiles_from_survival_curve(curve, model.max_followup_hours - float(snapshot["features"]["elapsed_hours"]),
                                          (0.1, 0.5, 0.9))
    quantile_seconds = time.perf_counter() - phase_start

    smoke_training = event_splits["train"]
    print(f"[benchmark] fitting one smoke model on {len(smoke_training)} training events", file=sys.stderr, flush=True)
    phase_start = time.perf_counter()
    smoke_model = fit_models(smoke_training, minimum_events=50, minimum_episodes=20)
    smoke_fit_seconds = time.perf_counter() - phase_start

    print("[benchmark] aggregating cached weather only (no network)", file=sys.stderr, flush=True)
    weather_cache_profile = _profile_weather_cache(sampled, cache_dir)
    print("[benchmark] timing smoke Monte Carlo", file=sys.stderr, flush=True)
    monte_carlo_start = time.perf_counter()
    monte_carlo_summary = simulate_model(smoke_model, elapsed_hours=0, start_month=6, trials=500, seed=42)
    monte_carlo_seconds = time.perf_counter() - monte_carlo_start

    scoring_snapshots = snapshots
    if not scoring_snapshots:
        raise ValueError("smoke sample created no active snapshots to score")
    results: list[dict[str, Any]] = []
    reference_metrics: dict[str, Any] | None = None
    base_rss_mb = psutil.Process().memory_info().rss / (1024 * 1024)
    memory_budget_mb = psutil.virtual_memory().available / (1024 * 1024) * 0.55
    for workers in worker_counts:
        if workers < 1 or workers > 20:
            raise ValueError("benchmark worker counts must be between 1 and 20")
        estimated_worker_memory = base_rss_mb * workers
        if workers > 1 and estimated_worker_memory > memory_budget_mb:
            results.append({"workers": workers, "skipped": "estimated worker RSS exceeds 55% of currently available memory"})
            continue
        phase_start = time.perf_counter()
        print(f"[benchmark] scoring {len(scoring_snapshots)} snapshots with {workers} worker(s)", file=sys.stderr, flush=True)
        with ProcessTreeRssSampler() as memory_sampler:
            metrics = score_snapshots(scoring_snapshots, model, workers=workers)
        elapsed = time.perf_counter() - phase_start
        speedup_equivalent = reference_metrics is not None and _same_scores(reference_metrics, metrics)
        if workers == 1 and reference_metrics is None:
            reference_metrics = metrics
        results.append({
            "workers": workers,
            "elapsed_seconds": elapsed,
            "snapshots_per_second": len(scoring_snapshots) / elapsed if elapsed else None,
            "process_tree_peak_rss_mb": memory_sampler.peak_bytes / (1024 * 1024),
            "speedup_vs_1_worker": None,
            "metrics_match_serial": True if speedup_equivalent or workers == 1 else False,
            "metrics": metrics,
        })
        print(f"[benchmark] workers={workers} elapsed={elapsed:.3f}s rss_peak={memory_sampler.peak_bytes / (1024 * 1024):.1f}MiB", file=sys.stderr, flush=True)
    serial_time = next((item["elapsed_seconds"] for item in results if item.get("workers") == 1), None)
    for item in results:
        if serial_time and "elapsed_seconds" in item:
            item["speedup_vs_1_worker"] = serial_time / item["elapsed_seconds"]

    print("[benchmark] profiling a 24-snapshot serial slice", file=sys.stderr, flush=True)
    profiler = cProfile.Profile()
    profiler.enable()
    profile_snapshots = scoring_snapshots[:min(24, len(scoring_snapshots))]
    score_snapshots(profile_snapshots, model, workers=1)
    profiler.disable()
    profile_output = io.StringIO()
    pstats.Stats(profiler, stream=profile_output).strip_dirs().sort_stats("cumtime").print_stats(15)

    print("[benchmark] collecting grouped bootstrap stage timing", file=sys.stderr, flush=True)
    bootstrap_timing = _profile_bootstrap(smoke_model, scoring_snapshots, replicates=bootstrap_replicates)
    report = {
        "status": "BOUNDED_WORKER_BENCHMARK_NOT_FULL_BACKTEST",
        "machine": {
            "logical_cpu_count": os.cpu_count(),
            "process_cpu_count": getattr(os, "process_cpu_count", lambda: None)(),
            "physical_cpu_count": psutil.cpu_count(logical=False),
            "available_memory_mb_at_start": memory_budget_mb / 0.55,
        },
        "active_full_backtest_processes_at_benchmark_start": [job for job in active_jobs if job["scope"] == "full_historical_backtest"],
        "other_active_backtest_processes_at_benchmark_start": [job for job in active_jobs if job["scope"] != "full_historical_backtest"],
        "benchmark_interference_note": "Timings are hardware observations from a bounded repeated scoring smoke sample, not full-backtest wall time. Active background jobs can affect timings.",
        "data": {
            "archives": [path.name for path in archive_paths],
            "source_rows": source_counts["rows_total"],
            "sampled_events_by_year": dict(Counter(int(event["source_year"]) for event in sampled)),
            "episode_groups_by_split": {name: len({event["episode_id"] for event in rows}) for name, rows in event_splits.items() if name != "excluded"},
            "snapshot_count": len(scoring_snapshots),
        },
        "stage_timings_seconds": {
            "noaa_parse_and_normalization": parse_seconds,
            "grouping_and_snapshot_generation": snapshot_seconds,
            "artifact_load": artifact_load_seconds,
            "survival_prediction_only": curve_seconds,
            "quantile_extraction_only": quantile_seconds,
            "smoke_model_fit_once": smoke_fit_seconds,
            "cached_weather_feature_attachment": weather_cache_profile,
            "monte_carlo_500_trials": monte_carlo_seconds,
            "full_historical_backtest": "NOT_RUN",
            "external_weather_fetch": "NOT_RUN; cache-only feature timing",
            "bootstrap": bootstrap_timing,
        },
        "monte_carlo_smoke_summary": monte_carlo_summary,
        "curve_reuse_comparison": curve_reuse,
        "worker_benchmarks": results,
        "cprofile_top_calls": profile_output.getvalue(),
        "reproducibility": {"seed": 42, "episode_sampling_cap_per_year": events_per_year},
        "production_eligibility": False,
    }
    report["stage_timings_seconds"]["benchmark_total_before_report_write"] = time.perf_counter() - started
    phase_start = time.perf_counter()
    json.dumps(report, indent=2, allow_nan=False)
    report["stage_timings_seconds"]["serialization"] = time.perf_counter() - phase_start
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=RAW_DATA_DIR)
    parser.add_argument("--artifact", type=Path, default=MODEL_PATH)
    parser.add_argument("--cache-dir", type=Path, default=RAW_DATA_DIR / "weather")
    parser.add_argument("--events-per-year", type=int, default=20)
    parser.add_argument("--worker-counts", type=int, nargs="+", default=[1, 4, 8, 12])
    parser.add_argument("--bootstrap-replicates", type=int, default=200)
    parser.add_argument("--output", type=Path, default=REPORT_DIR / "worker_benchmark.json")
    args = parser.parse_args()
    report = run_benchmark(input_dir=args.input_dir, artifact_path=args.artifact,
                           cache_dir=args.cache_dir, events_per_year=args.events_per_year,
                           worker_counts=tuple(args.worker_counts),
                           bootstrap_replicates=args.bootstrap_replicates, output_path=args.output)
    print(json.dumps({
        "status": report["status"],
        "snapshot_count": report["data"]["snapshot_count"],
        "worker_benchmarks": [
            {key: row.get(key) for key in ("workers", "elapsed_seconds", "snapshots_per_second", "process_tree_peak_rss_mb", "speedup_vs_1_worker", "metrics_match_serial", "skipped")}
            for row in report["worker_benchmarks"]
        ],
        "active_full_backtest_processes": report["active_full_backtest_processes_at_benchmark_start"],
    }, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
