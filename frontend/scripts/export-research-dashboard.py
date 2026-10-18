"""Export static public research data. No training, provider calls or artifact writes.

Run with the approved ML environment and --with-model-samples to reproduce draws.
Without that flag, reuse the verified committed draw export; no model is required.
"""

import argparse
import csv
import hashlib
import io
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "frontend/public/research"
FLOOD_SHA = "2d33812b2d238bfa0ad18665f0b447c5d0d6925c1398c763814d4e5889067598"
TARGETS = {
    "Flood": None,
    "Flash Flood": "flash_flood",
    "High Wind": "high_wind",
    "Heavy Rain": "heavy_rain",
    "Winter Storm": "winter_storm",
    "Heat Index Exceedance": "heat_index_exceedance",
}


def sha(path):
    return hashlib.sha256(
        (ROOT / path).read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def samples():
    sys.path.insert(0, str(ROOT))
    from scipy.stats import binomtest

    from ml.monte_carlo import _draw_duration, simulate_hazards
    from ml.train import conditional_logistic_survival_curve, load_models

    model = load_models(
        ROOT / "ml/artifacts/provisioned_v2/active_event.joblib",
        expected_sha256=FLOOD_SHA,
    )
    curve = conditional_logistic_survival_curve(model, 6, 9)
    assert curve is not None and len(curve) == 162
    previous = 1.0
    hazards = []
    for probability in curve:
        hazards.append(
            max(0.0, min(1.0, 1 - probability / previous)) if previous else 0.0
        )
        previous = probability
    summary = simulate_hazards(hazards, trials=5000, seed=42)
    original = read("ml/reports/purged_v2/monte_carlo_summary.json")
    for field in (
        "analytical_ongoing_probability",
        "simulated_ongoing_proportion",
        "remaining_duration_hours",
    ):
        assert summary[field] == original[field], (
            f"Seeded replay no longer matches {field}"
        )
    rng = random.Random(42)
    durations = [_draw_duration(hazards, rng) for _ in range(5000)]
    resolved = [d for d in durations if d is not None]
    assert len(durations) - len(resolved) == 172
    for horizon in (6, 12, 24):
        assert (
            sum(d is None or d > horizon for d in durations) / 5000
            == original["simulated_ongoing_proportion"][f"{horizon}h"]
        )
    convergence = []
    for count in (100, 500, 1000, 2500, 5000):
        for horizon in (6, 12, 24):
            successes = sum(d is None or d > horizon for d in durations[:count])
            interval = binomtest(successes, count).proportion_ci(0.95, method="wilson")
            convergence.append(
                {
                    "draws": count,
                    "horizon_hours": horizon,
                    "simulated": successes / count,
                    "analytical": curve[horizon - 1],
                    "lower_95": interval.low,
                    "upper_95": interval.high,
                }
            )
    return {
        "kind": "seeded_model_implied_draws_not_physical_storm_paths",
        "model_version": model.model_version,
        "estimator": "logistic",
        "artifact_sha256": FLOOD_SHA,
        "fixture": "ml/fixtures/active_flood.json",
        "elapsed_hours": 6,
        "start_month": 9,
        "seed": 42,
        "trials": 5000,
        "modeled_remaining_horizon_hours": len(curve),
        "model_total_age_limit_hours": model.max_followup_hours,
        "summary": original,
        "minimum_resolved_hours": min(resolved),
        "maximum_resolved_within_horizon_hours": max(resolved),
        "unresolved": 172,
        "durations_hours": durations,
        "curve": [{"hour": 0, "analytical": 1.0, "simulated": 1.0}]
        + [
            {
                "hour": h,
                "analytical": probability,
                "simulated": sum(d is None or d > h for d in durations) / 5000,
            }
            for h, probability in enumerate(curve, 1)
        ],
        "convergence": convergence,
        "interval_method": "95% Wilson binomial intervals for i.i.d. Monte Carlo indicators; sample prefixes are nested and dependent across N. Not model-parameter uncertainty or predictive validation.",
    }


def heldout(archive_dir):
    code_paths = ("ml/features.py", "ml/events.py", "ml/backtest.py")
    if archive_dir is None:
        cached = read("frontend/public/research/flood-holdout.json")
        assert cached["artifact_sha256"] == FLOOD_SHA
        assert all(sha(p) == cached["code_hashes"][p] for p in code_paths)
        return cached
    sys.path.insert(0, str(ROOT))
    from ml.backtest import _score_snapshot
    from ml.events import read_noaa_detail_files
    from ml.features import (
        build_active_snapshots,
        split_events_by_episode,
        split_snapshots_by_episode,
    )
    from ml.train import load_models

    manifest = read("ml/reports/source_manifest.json")
    paths = []
    receipts = []
    for item in manifest["archives"]:
        assert Path(item["file"]).name == item["file"]
        path = archive_dir / item["file"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"], item[
            "file"
        ]
        paths.append(path)
        receipts.append({"file": item["file"], "sha256": item["sha256"]})
    model = load_models(
        ROOT / "ml/artifacts/provisioned_v2/active_event.joblib",
        expected_sha256=FLOOD_SHA,
    )
    events, _counts = read_noaa_detail_files(paths)
    splits = split_events_by_episode(
        events, train_end_year=2023, validation_year=2024, test_year=2025
    )
    snapshots = split_snapshots_by_episode(build_active_snapshots(events), splits)[
        "test"
    ]
    assert len(snapshots) == 3539 and len({s["episode_id"] for s in snapshots}) == 567
    rows = []
    for snapshot in snapshots:
        scored = _score_snapshot(snapshot, model)
        row = {
            "event_id": scored["event_id"],
            "episode_id": scored["episode_id"],
            "as_of_utc": snapshot["as_of_utc"],
            "elapsed_hours": snapshot["features"]["elapsed_hours"],
            "observed_remaining_hours": scored["remaining_hours"],
        }
        for method, qkey, pkey in (
            ("logistic", "quantiles", "logistic_probabilities"),
            ("kaplan_meier", "km_quantiles", "km_probabilities"),
        ):
            q = scored[qkey]
            row[method] = {
                "p10": q[0.1],
                "median": q[0.5],
                "p90": q[0.9],
                "ongoing": {f"{h}h": scored[pkey][h] for h in (6, 12, 24)},
            }
        rows.append(row)
    report = read("ml/reports/purged_v2/backtest_metrics.json")
    metrics = report["out_of_time_test_2025_train_through_2024"]
    verified = {}
    for method in ("logistic", "kaplan_meier"):
        for h in (6, 12, 24):
            brier = sum(
                (r[method]["ongoing"][f"{h}h"] - (r["observed_remaining_hours"] > h))
                ** 2
                for r in rows
            ) / len(rows)
            assert math.isclose(
                brier, metrics[method][f"{h}h"]["brier_score"], abs_tol=1e-12
            )
        mae = sum(
            abs(r[method]["median"] - r["observed_remaining_hours"]) for r in rows
        ) / len(rows)
        expected = metrics["duration_by_estimator"][method][
            "median_remaining_time_mae_hours"
        ]
        assert math.isclose(mae, expected, abs_tol=1e-9)
        verified[method] = {
            "mean_absolute_error_hours": mae,
            "prediction_min_hours": min(r[method]["median"] for r in rows),
            "prediction_max_hours": max(r[method]["median"] for r in rows),
            "unidentified_intervals": sum(
                r[method]["p10"] is None or r[method]["p90"] is None for r in rows
            ),
        }
    return {
        "scope": "previously_inspected_2025_flood_evaluation_not_fresh_holdout",
        "artifact_sha256": FLOOD_SHA,
        "model_version": model.model_version,
        "training_through_year": 2024,
        "snapshot_count": len(rows),
        "episode_count": 567,
        "source_report": "ml/reports/purged_v2/backtest_metrics.json",
        "archive_receipts": receipts,
        "code_hashes": {p: sha(p) for p in code_paths},
        "observed_min_hours": min(r["observed_remaining_hours"] for r in rows),
        "observed_max_hours": max(r["observed_remaining_hours"] for r in rows),
        "verified_metrics": verified,
        "rows": rows,
    }


def export(with_samples, archive_dir):
    source_paths = [
        "ml/reports/purged_v2/backtest_metrics.json",
        "ml/reports/purged_v2/monte_carlo_summary.json",
        "ml/reports/purged_v2/benchmark.json",
        "ml/reports/multidisaster/registry.json",
        "ml/reports/multidisaster/examples.json",
        "ml/reports/multidisaster/runtime_checks.json",
        "ml/fixtures/active_flood.json",
        "ml/train.py",
        "ml/monte_carlo.py",
    ]
    source_paths += [
        f"ml/reports/multidisaster/{stem}.json" for stem in TARGETS.values() if stem
    ]
    source_paths += [
        "ml/features.py",
        "ml/events.py",
        "ml/backtest.py",
        "ml/reports/source_manifest.json",
        "ml/model_reference.json",
    ]
    source_paths += [
        f"ml/reports/multidisaster/{stem}.json"
        for stem in ("strong_wind", "ice_storm", "heavy_snow", "hurricane_trend")
    ]
    flood = read(source_paths[0])
    categories = {}
    replays = []
    for name, stem in TARGETS.items():
        if stem is None:
            train = flood["split"]["train"]
            categories[name] = {
                "name": name,
                "horizons": [6, 12, 24],
                "selected_estimator": "kaplan_meier",
                "model_version": flood["model"]["model_version"],
                "report": source_paths[0],
                "training": {
                    "records": train["event_record_count"],
                    "groups": train["episode_count"],
                    "snapshots": train["snapshot_count"],
                },
                "validation": flood["validation_2024_train_through_2023"],
                "test": flood["out_of_time_test_2025_train_through_2024"],
                "research_status": "retrospective_research_only",
                "group_basis": "NOAA reporting episode",
                "limits": flood["limitations"],
            }
            replay = flood["held_out_replay"]
            prediction = replay["prediction_at_as_of"]
            actual = replay["observed_remaining_hours"]
        else:
            report = read(f"ml/reports/multidisaster/{stem}.json")
            assert (
                report["prediction_eligible"] and not report["production_eligibility"]
            )
            train = report["split"]["train"]
            categories[name] = {
                "name": name,
                "horizons": report["supported_horizons_hours"],
                "selected_estimator": report["selected_estimator"],
                "model_version": report["artifact_model_version"],
                "report": f"ml/reports/multidisaster/{stem}.json",
                "training": {
                    "records": train["event_records"],
                    "groups": train["episode_groups"],
                    "snapshots": train["snapshots"],
                },
                "validation": report["validation"],
                "test": report["test"],
                "research_status": report["status"],
                "group_basis": "station week"
                if stem == "heat_index_exceedance"
                else "NOAA reporting episode",
                "limits": report["limitations"],
            }
            prediction = read("ml/reports/multidisaster/examples.json")[name][
                "prediction"
            ]
            actual = report["example_observed_remaining_hours"]
        replays.append(
            {
                "event_type": name,
                "event_id": prediction["event_id"],
                "as_of_utc": prediction["as_of_utc"],
                "estimator": prediction.get("estimator", "kaplan_meier"),
                "model_version": prediction["model_version"],
                "prediction": prediction["outcomes"]["remaining_duration_hours"],
                "observed_remaining_hours": actual,
                "source_report": categories[name]["report"],
                "interpretation": "One historical recorded-event replay, not a representative error distribution or worksite reopening.",
            }
        )
    if with_samples:
        monte_carlo = samples()
    else:
        cached = read("frontend/public/research/dashboard.json")
        monte_carlo = cached["monte_carlo_lab"]
        assert monte_carlo["artifact_sha256"] == FLOOD_SHA
        for item in cached["sources"]:
            if item["path"] in (
                "ml/train.py",
                "ml/monte_carlo.py",
                "ml/fixtures/active_flood.json",
            ):
                assert sha(item["path"]) == item["sha256"], (
                    "Sampling inputs changed; rerun --with-model-samples"
                )
    assert monte_carlo["summary"] == read(
        "ml/reports/purged_v2/monte_carlo_summary.json"
    )
    disabled = [
        {
            "name": name,
            "reasons": read(f"ml/reports/multidisaster/{stem}.json")[
                "qualification_failures"
            ],
        }
        for name, stem in (
            ("Strong Wind", "strong_wind"),
            ("Ice Storm", "ice_storm"),
            ("Heavy Snow", "heavy_snow"),
        )
    ]
    for category in categories.values():
        for period in ("validation", "test"):
            for method in ("kaplan_meier", "logistic"):
                for horizon in category["horizons"]:
                    metric = category[period][method][f"{horizon}h"]
                    assert metric["snapshot_count"] == sum(
                        b["count"] for b in metric["reliability"]
                    )
                    metric.setdefault(
                        "expected_calibration_error",
                        sum(
                            abs(b["mean_predicted"] - b["observed_frequency"])
                            * b["count"]
                            for b in metric["reliability"]
                        )
                        / metric["snapshot_count"],
                    )
    return {
        "schema_version": "research-dashboard-1",
        "scope": "archived_research_only_no_operational_decisions",
        "source_hash_normalization": "UTF-8 LF",
        "sources": [{"path": p, "sha256": sha(p)} for p in source_paths],
        "categories": categories,
        "replays": replays,
        "disabled_targets": disabled,
        "monte_carlo_lab": monte_carlo,
        "flood_cohort": {"counts": flood["source_row_counts"], "split": flood["split"]},
        "benchmark": read("ml/reports/purged_v2/benchmark.json"),
        "runtime": read("ml/reports/multidisaster/runtime_checks.json")["inference"],
        "hurricane_experiment": read("ml/reports/multidisaster/hurricane_trend.json"),
        "flood_holdout": heldout(archive_dir),
    }


def csv_exports(data):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(
        [
            "draw",
            "resolved_at_remaining_hour",
            "unresolved_at_horizon",
            "modeled_remaining_horizon_hours",
            "seed",
        ]
    )
    for index, value in enumerate(data["monte_carlo_lab"]["durations_hours"], 1):
        writer.writerow([index, "" if value is None else value, value is None, 162, 42])
    samples_csv = stream.getvalue().encode()
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(
        [
            "target",
            "period",
            "estimator",
            "horizon_hours",
            "snapshots",
            "reporting_groups",
            "brier",
            "brier_lower_95",
            "brier_upper_95",
            "ece",
            "source_report",
        ]
    )
    for category in data["categories"].values():
        for period in ("validation", "test"):
            for method in ("kaplan_meier", "logistic"):
                for horizon in category["horizons"]:
                    m = category[period][method][f"{horizon}h"]
                    ci = m["episode_bootstrap_brier_95"]
                    writer.writerow(
                        [
                            category["name"],
                            period,
                            method,
                            horizon,
                            m["snapshot_count"],
                            m["episode_count"],
                            m["brier_score"],
                            ci["lower_95"],
                            ci["upper_95"],
                            m["expected_calibration_error"],
                            category["report"],
                        ]
                    )
    return {
        "monte-carlo-draws.csv": samples_csv,
        "backtest-comparison.csv": stream.getvalue().encode(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-model-samples", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--archive-dir",
        type=Path,
        help="Read-only approved archive directory; scoring only, no refit",
    )
    args = parser.parse_args()
    data = export(args.with_model_samples, args.archive_dir)
    heldout_data = data.pop("flood_holdout")
    data["flood_holdout_summary"] = {
        k: v for k, v in heldout_data.items() if k != "rows"
    }
    files = {
        "dashboard.json": (
            json.dumps(data, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
            + "\n"
        ).encode(),
        **csv_exports(data),
        "flood-holdout.json": (
            json.dumps(heldout_data, separators=(",", ":"), allow_nan=False) + "\n"
        ).encode(),
    }
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(
        [
            "event_id",
            "episode_id",
            "as_of_utc",
            "elapsed_hours",
            "observed_remaining_hours",
            "estimator",
            "predicted_p10_hours",
            "predicted_median_hours",
            "predicted_p90_hours",
        ]
    )
    for row in heldout_data["rows"]:
        for method in ("kaplan_meier", "logistic"):
            writer.writerow(
                [
                    row["event_id"],
                    row["episode_id"],
                    row["as_of_utc"],
                    row["elapsed_hours"],
                    row["observed_remaining_hours"],
                    method,
                    row[method]["p10"],
                    row[method]["median"],
                    row[method]["p90"],
                ]
            )
    files["flood-holdout.csv"] = stream.getvalue().encode()
    for name, content in files.items():
        path = OUT / name
        if args.check:
            if not path.exists() or path.read_bytes() != content:
                raise SystemExit(f"Export mismatch: {name}")
        else:
            path.write_bytes(content)
    print(
        json.dumps(
            {
                "checked": args.check,
                "targets": len(data["categories"]),
                "draws": 5000,
                "summary_exactly_reproduced": True,
                "raw_draw_maximum_resolved": data["monte_carlo_lab"][
                    "maximum_resolved_within_horizon_hours"
                ],
                "artifacts_changed": False,
                "network_calls": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
