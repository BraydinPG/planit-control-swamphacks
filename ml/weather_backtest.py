"""Opt-in retrospective NOAA-point/Open-Meteo experiment; not production inference."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from ml.config import RAW_DATA_DIR, REPORT_DIR
from ml.events import read_noaa_detail_files
from ml.evaluate import binary_metrics, duration_metrics
from ml.features import build_active_snapshots, split_events_by_episode, split_snapshots_by_episode
from ml.sources.weather import fetch_historical_weather
from ml.train import (
    conditional_km_survival_curve,
    conditional_logistic_survival_curve,
    quantiles_from_survival_curve,
    fit_models,
)
from ml.weather_features import WEATHER_FEATURE_NAMES as WEATHER_MODEL_FEATURES
from ml.weather_features import deterministic_episode_sample, extract_weather_features
from ml.weather_model import conditional_weather_survival_curve, fit_weather_model


def datetime_from_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("event start timestamp must be timezone-aware")
    return parsed


def _fetch_snapshot_weather(events: list[dict[str, Any]], *, cache_dir: Path,
                            request_limit: int, timeout: float, retries: int,
                            request_delay_seconds: float, cache_only: bool = False) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    selected = deterministic_episode_sample(events, per_year=request_limit, seed=42)
    features_by_event: dict[str, dict[str, Any]] = {}
    status_counts = Counter()
    failures: list[dict[str, str]] = []
    for index, event in enumerate(selected):
        sys.stderr.write(f"\r[weather] request {index + 1}/{len(selected)} NOAA event {event['event_id']} ...")
        sys.stderr.flush()
        start = date.fromisoformat(str(event["start_utc"])[:10])
        date_start = (start - timedelta(days=1)).isoformat()
        date_end = (start + timedelta(days=1)).isoformat()
        try:
            response = fetch_historical_weather(
                float(event["begin_lat"]), float(event["begin_lon"]), date_start, date_end,
                (datetime_from_iso(str(event["start_utc"])) + timedelta(hours=24)).isoformat(),
                cache_dir=cache_dir, timeout=timeout, retries=retries,
                cache_only=cache_only,
            )
            weather_rows = response["hourly"]
            features_by_event[str(event["event_id"])] = {
                "hourly": weather_rows,
                "weather_context": {
                    "source": response["source"],
                    "data_state": response["data_state"],
                    "spatial_match_quality": "reported_event_point_regional_proxy",
                    "as_of_interpretation": response["data_state"],
                    "source_url": response["source_url"],
                    "response_sha256": response["response_sha256"],
                    "retrieved_at_utc": response["retrieved_at_utc"],
                    "original_acquisition_time_known": response["retrieved_at_utc"] is not None,
                },
            }
            status_counts["retrieved_or_cached"] += 1
        except Exception as error:
            status_counts["request_failed"] += 1
            failures.append({"event_id": str(event["event_id"]), "error": f"{type(error).__name__}: {error}"})
        progress_interval = max(1, len(selected) // 20)
        if (index + 1) % progress_interval == 0 or index + 1 == len(selected) or failures:
            sys.stderr.write(f"\r[weather] requests complete {index + 1}/{len(selected)} ({len(failures)} failed)\n")
            sys.stderr.flush()
        if not cache_only and request_delay_seconds > 0 and index + 1 < len(selected):
            time.sleep(request_delay_seconds)
    return features_by_event, {
        "selected_event_count": len(selected),
        "status_counts": dict(status_counts),
        "failures": failures,
        "features_by_event": features_by_event,
    }


def _attach_asof_weather(snapshots: list[dict[str, Any]], weather_by_event: dict[str, dict[str, Any]],
                         progress_label: str | None = None) -> tuple[list[dict[str, Any]], dict[str, int]]:
    output: list[dict[str, Any]] = []
    count = Counter()
    update_interval = max(1, len(snapshots) // 20)
    for index, snapshot in enumerate(snapshots, start=1):
        event_weather = weather_by_event.get(str(snapshot["event_id"]))
        if event_weather is None:
            count["missing_event_weather"] += 1
        else:
            extracted = extract_weather_features(event_weather["hourly"], str(snapshot["as_of_utc"]))
            enriched = dict(snapshot)
            enriched["features"] = dict(snapshot["features"])
            enriched["features"].update(extracted["features"])
            enriched["weather_metadata"] = {
                **event_weather["weather_context"],
                "as_of_utc": extracted["as_of_utc"],
                "latest_valid_time_utc": extracted["latest_valid_time_utc"],
                "valid_observation_count": extracted["valid_observation_count"],
                "missing_features": extracted["missing_features"],
                "units": extracted["units"],
            }
            output.append(enriched)
            count["snapshots_with_weather_response"] += 1
            if extracted["valid_observation_count"]:
                count["snapshots_with_asof_observations"] += 1
        if progress_label and (index % update_interval == 0 or index == len(snapshots)):
            completed = index
            percent = int(completed * 100 / max(1, len(snapshots)))
            sys.stderr.write(f"\r[{progress_label}] {completed}/{len(snapshots)} ({percent}%)")
            if completed == len(snapshots):
                sys.stderr.write("\n")
            sys.stderr.flush()
    return output, dict(count)


def _score_comparable(weather_model: Any, baseline_model: Any,
                      snapshots: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Score all estimators on exactly the same prediction-eligible rows per horizon."""
    predictions = {
        estimator: {horizon: [] for horizon in (6, 12, 24)}
        for estimator in ("weather_model", "age_month_logistic", "conditional_km")
    }
    observed_by_horizon = {horizon: [] for horizon in (6, 12, 24)}
    groups_by_horizon = {horizon: [] for horizon in (6, 12, 24)}
    remaining, duration_groups = [], []
    duration_quantiles = {estimator: [] for estimator in predictions}
    for snapshot in snapshots:
        features = snapshot["features"]
        elapsed = float(features["elapsed_hours"])
        month = int(features["start_month"])
        curves = {
            "weather_model": conditional_weather_survival_curve(weather_model, snapshot),
            "age_month_logistic": conditional_logistic_survival_curve(baseline_model, elapsed, month),
            "conditional_km": conditional_km_survival_curve(baseline_model, elapsed),
        }
        if all(curve is not None for curve in curves.values()):
            remaining.append(float(snapshot["labels"]["remaining_duration_hours"]))
            duration_groups.append(str(snapshot["episode_id"]))
            for estimator, curve in curves.items():
                duration_quantiles[estimator].append(quantiles_from_survival_curve(
                    curve, baseline_model.max_followup_hours - elapsed, (0.1, 0.5, 0.9)))
        for horizon in (6, 12, 24):
            probabilities = {name: (curve[horizon - 1] if curve is not None and len(curve) >= horizon
                                    and elapsed + horizon <= baseline_model.max_followup_hours else None)
                             for name, curve in curves.items()}
            weather_probability, logistic_probability, km_probability = probabilities.values()
            if any(probability is None for probability in (weather_probability, logistic_probability, km_probability)):
                continue
            predictions["weather_model"][horizon].append(float(weather_probability))
            predictions["age_month_logistic"][horizon].append(float(logistic_probability))
            predictions["conditional_km"][horizon].append(float(km_probability))
            observed_by_horizon[horizon].append(
                bool(snapshot["labels"][f"recorded_event_ongoing_{horizon}h"])
            )
            groups_by_horizon[horizon].append(str(snapshot["episode_id"]))
    result = {
        estimator: {
            f"{horizon}h": binary_metrics(
                predictions[estimator][horizon], observed_by_horizon[horizon], groups_by_horizon[horizon]
            )
            for horizon in (6, 12, 24)
        }
        for estimator in predictions
    }
    for estimator in result:
        result[estimator]["duration"] = duration_metrics(remaining, duration_quantiles[estimator], duration_groups)
    common = [index for index in range(len(remaining))
              if all(all(value is not None for value in duration_quantiles[name][index].values())
                     for name in duration_quantiles)]
    for estimator in result:
        result[estimator]["duration_on_common_finite_intervals"] = duration_metrics(
            [remaining[index] for index in common], [duration_quantiles[estimator][index] for index in common],
            [duration_groups[index] for index in common])
    return result


def run_weather_backtest(detail_files: list[Path], *, output_path: Path = REPORT_DIR / "weather_backtest_metrics.json",
                         cache_dir: Path = RAW_DATA_DIR / "weather", per_year: int = 20,
                         timeout: float = 20.0, retries: int = 3, request_delay_seconds: float = 0.1,
                         cache_only: bool = False) -> dict[str, Any]:
    print(f"[weather-backtest] reading {len(detail_files)} NOAA archives", file=sys.stderr, flush=True)
    events, source_counts = read_noaa_detail_files(detail_files)
    print(f"[weather-backtest] retained {len(events):,} Flood event records", file=sys.stderr, flush=True)
    sampled = deterministic_episode_sample(events, per_year=per_year, seed=42)
    split_sample = split_events_by_episode(sampled, train_end_year=2023, validation_year=2024, test_year=2025)
    if not split_sample["train"] or not split_sample["validation"] or not split_sample["test"]:
        raise ValueError("weather experiment needs sampled episode groups from training, validation, and test years")

    weather_by_event, fetch_report = _fetch_snapshot_weather(
        sampled, cache_dir=cache_dir, request_limit=per_year, timeout=timeout, retries=retries,
        request_delay_seconds=request_delay_seconds,
        cache_only=cache_only,
    )
    sampled_snapshots = build_active_snapshots(sampled)
    split_snapshots = split_snapshots_by_episode(sampled_snapshots, split_sample)
    enriched_by_split: dict[str, list[dict[str, Any]]] = {}
    asof_counts: dict[str, dict[str, int]] = {}
    for split_name in ("train", "validation", "test"):
        enriched_by_split[split_name], asof_counts[split_name] = _attach_asof_weather(
            split_snapshots[split_name], weather_by_event, f"{split_name} feature snapshots"
        )
    if len(enriched_by_split["train"]) < 50 or len({row["episode_id"] for row in enriched_by_split["train"]}) < 20:
        raise ValueError("weather experiment has insufficient fetched training episodes; inspect fetch failures")

    training_ids = {str(row["event_id"]) for row in enriched_by_split["train"]}
    baseline_events = [event for event in split_sample["train"] if str(event["event_id"]) in training_ids]
    print("[weather-backtest] fitting age/month and weather models", file=sys.stderr, flush=True)
    baseline_logistic = fit_models(baseline_events, minimum_events=50, minimum_episodes=20)
    weather_model = fit_weather_model(enriched_by_split["train"], minimum_snapshots=50, minimum_episodes=20)

    # Keep the existing selection margin; both years have already been inspected.
    print("[weather-backtest] validation scoring / model selection", file=sys.stderr, flush=True)
    validation_scores = _score_comparable(
        weather_model, baseline_logistic, enriched_by_split["validation"]
    )
    validation_briers: dict[str, float] = {}
    for candidate in ("weather_model", "age_month_logistic", "conditional_km"):
        values = [validation_scores[candidate][h]["brier_score"] for h in ("6h", "12h", "24h")]
        if any(value is None for value in values):
            raise ValueError("matched validation support is unavailable at one or more horizons")
        validation_briers[candidate] = sum(values) / len(values)
    # Require a modest, predeclared improvement over both references. Otherwise keep the simpler model.
    selected_model = "weather_model" if (
        validation_briers["weather_model"] <= 0.98 * validation_briers["age_month_logistic"]
        and validation_briers["weather_model"] <= 0.98 * validation_briers["conditional_km"]
    ) else ("age_month_logistic" if validation_briers["age_month_logistic"] < validation_briers["conditional_km"] else "conditional_km")
    print("[weather-backtest] previously inspected 2025 test scoring", file=sys.stderr, flush=True)
    test_scores = _score_comparable(weather_model, baseline_logistic, enriched_by_split["test"])
    report = {
        "status": "RETROSPECTIVE_WEATHER_EXPERIMENT",
        "production_eligibility": False,
        "cache_only": cache_only,
        "test_interpretation": "corrected rerun of previously inspected 2025 data; not a fresh untouched holdout",
        "training_policy": baseline_logistic.training_policy,
        "source": "Open-Meteo Historical Weather API ERA5 retrospective reanalysis, joined to NOAA reported Flood points",
        "weather_is_not_archived_issued_forecast": True,
        "comparison_population_rule": "At each horizon, compare only the intersection of snapshots with defined weather, age/month logistic, and KM predictions.",
        "duration_comparison_rule": "duration_on_common_finite_intervals uses identical rows across all three estimators; duration also reports each estimator's identifiable-tail coverage separately",
        "event_site_interpretation": "NOAA report coordinates identify reported event locations, not monitored EIA site exposure",
        "feature_names": list(WEATHER_MODEL_FEATURES),
        "weather_source_manifest": [
            {"event_id": event_id, **details["weather_context"]}
            for event_id, details in sorted(weather_by_event.items())
        ],
        "source_row_counts": source_counts,
        "sampling": {
            "strategy": "deterministic SHA-256 episode sample, at most one reported event per episode per year",
            "per_year_cap": per_year,
            "seed": 42,
            "events_by_year": dict(Counter(int(event["source_year"]) for event in sampled)),
            "episodes_by_split": {name: len({event["episode_id"] for event in events}) for name, events in split_sample.items() if name != "excluded"},
            "retrieval": {key: value for key, value in fetch_report.items() if key != "features_by_event"},
            "asof_snapshot_coverage": asof_counts,
        },
        "models": {
            "weather_model": {
                "version": weather_model.model_version,
                "training_snapshot_count": weather_model.training_snapshot_count,
                "training_episode_count": weather_model.training_episode_count,
                "training_risk_row_count": weather_model.training_risk_row_count,
                "weather_feature_missing_fraction": weather_model.weather_feature_missing_fraction,
                "imputation": "median fitted on sampled training risk rows only; missingness indicators retained",
            },
            "baseline_model_version": baseline_logistic.model_version,
        },
        "validation_2024": validation_scores,
        "validation_selection_mean_brier": validation_briers,
        "selected_for_research_test_comparison": selected_model,
        "out_of_time_test_2025": test_scores,
        "limitations": [
            "ERA5 reanalysis is retrospective context and is not an archived forecast issued at the prediction time.",
            "Weather values are at NOAA reported event coordinates and do not verify site-level exposure.",
            "Only sampled episodes with weather responses are scored; sample counts and episode counts are included for each horizon.",
            "No downloaded weather feature is approved for production inference or a worker-facing API.",
            "If weather features fail to beat both references on validation by the existing 2% margin, prefer the better simple reference.",
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[weather-backtest] writing {output_path}", file=sys.stderr, flush=True)
    output_path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=RAW_DATA_DIR)
    parser.add_argument("--output", type=Path, default=REPORT_DIR / "weather_backtest_metrics.json")
    parser.add_argument("--cache-dir", type=Path, default=RAW_DATA_DIR / "weather")
    parser.add_argument("--per-year", type=int, default=20)
    parser.add_argument("--cache-only", action="store_true")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--request-delay", type=float, default=0.1)
    args = parser.parse_args()
    detail_files = sorted(args.input_dir.glob("StormEvents_details-ftp_v1.0_d*.csv.gz"))
    if not detail_files:
        raise SystemExit(f"No NOAA details archives found under {args.input_dir}; run ml.sources.noaa first.")
    report = run_weather_backtest(detail_files, output_path=args.output, cache_dir=args.cache_dir,
                                  per_year=args.per_year, timeout=args.timeout, retries=args.retries,
                                  request_delay_seconds=args.request_delay, cache_only=args.cache_only)
    print(json.dumps({
        "status": report["status"],
        "selected_for_research_test_comparison": report["selected_for_research_test_comparison"],
        "validation_selection_mean_brier": report["validation_selection_mean_brier"],
        "test_brier": {name: {horizon: metrics[horizon]["brier_score"] for horizon in ("6h", "12h", "24h")}
                       for name, metrics in report["out_of_time_test_2025"].items()},
    }, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
