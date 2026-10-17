"""Retrospective NHC intensity-trend experiment; never an operational predictor.

Fixed before its first evaluation: 2000-2019 train, 2020-2022 validation,
2023-2025 test; whole storm identities. Label: 24h cyclone-maximum wind
change >=10 kt / <=-10 kt / between. No test-dependent retuning.
"""

from collections import Counter
from datetime import datetime, timedelta
import json
from pathlib import Path
import time

import joblib
import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from ml.config import ARTIFACT_DIR, PROCESSED_DATA_DIR, REPORT_DIR
from ml.evaluate import binary_metrics
from ml.sources.hurdat import TROPICAL_STATES

FEATURES = ("current_wind_kt", "previous_6h_wind_change_kt", "current_pressure_hpa", "lat", "lon", "month")
CLASSES = ("improving", "stable", "worsening")


def track_snapshots(storms: list[dict]) -> tuple[list[dict], dict]:
    rows, excluded = [], Counter()
    for storm in storms:
        points = {datetime.fromisoformat(p["valid_time_utc"].replace("Z", "+00:00")): p for p in storm["points"]}
        for now, point in sorted(points.items()):
            if now.hour not in (0, 6, 12, 18) or now.minute or point["status"] not in TROPICAL_STATES:
                continue
            previous, future = points.get(now-timedelta(hours=6)), points.get(now+timedelta(hours=24))
            if not previous or not future or any(p.get("max_wind_kt") is None for p in (previous, point, future)):
                excluded["missing_exact_past_or_future_measurement"] += 1
                continue
            delta = future["max_wind_kt"] - point["max_wind_kt"]
            label = "worsening" if delta >= 10 else "improving" if delta <= -10 else "stable"
            rows.append({"storm_id": storm["storm_id"], "year": storm["year"], "as_of_utc": point["valid_time_utc"],
                         "features": dict(zip(FEATURES, (point["max_wind_kt"], point["max_wind_kt"]-previous["max_wind_kt"],
                             point["min_pressure_hpa"], point["lat"], point["lon"], now.month))),
                         "label": label, "future_24h_wind_change_kt": delta})
    return rows, dict(excluded)


def matrix(rows: list[dict]) -> np.ndarray:
    return np.asarray([[np.nan if row["features"][key] is None else row["features"][key] for key in FEATURES] for row in rows], dtype=float)


def fit(rows: list[dict]):
    model = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                          LogisticRegression(C=.1, max_iter=500, random_state=42))
    # Normalize storm weights: long tracks do not dominate the training loss.
    counts = Counter(row["storm_id"] for row in rows)
    model.fit(matrix(rows), [row["label"] for row in rows],
              logisticregression__sample_weight=np.asarray([1/counts[row["storm_id"]] for row in rows]))
    return model


def score(rows: list[dict], model, train: list[dict]) -> dict:
    probabilities = model.predict_proba(matrix(rows))
    groups = [row["storm_id"] for row in rows]
    train_groups = Counter(row["storm_id"] for row in train)
    class_weights = {label: sum(1/train_groups[row["storm_id"]] for row in train if row["label"] == label) / len(train_groups) for label in CLASSES}
    result = {"logistic": {}, "train_frequency_baseline": {}}
    for label in CLASSES:
        outcomes = [row["label"] == label for row in rows]
        for name, values in (("logistic", probabilities[:, list(model.classes_).index(label)].tolist()),
                             ("train_frequency_baseline", [class_weights[label]] * len(rows))):
            metrics = binary_metrics(values, outcomes, groups)
            metrics["positive_labels"] = sum(outcomes)
            metrics["negative_labels"] = len(outcomes) - sum(outcomes)
            metrics["expected_calibration_error"] = sum(b["count"] * abs(b["mean_predicted"]-b["observed_frequency"]) for b in metrics["reliability"]) / len(rows)
            result[name][label] = metrics
    for name in result:
        result[name]["multiclass_brier_score"] = sum(result[name][label]["brier_score"] for label in CLASSES)
    return result


def predict_replay(features: dict, model, *, data_state: str, event_status: str) -> dict:
    """Executable offline boundary; source vintage prohibits live dispatch."""
    if data_state != "retrospective_best_track" or event_status != "historical_replay":
        raise ValueError("HURDAT model requires an explicitly retrospective historical replay")
    if set(features) != set(FEATURES):
        raise ValueError("hurricane predictors must match the past/current feature allowlist")
    probabilities = model.predict_proba(matrix([{"features": features}]))[0]
    return {"trend_probability": dict(zip(model.classes_, map(float, probabilities))),
            "trend_basis": "24h_change_in_cyclone_maximum_wind;_not_worksite_severity",
            "research_only": True, "operational_evaluation_eligible": False,
            "historical_asof_availability_verified": False}


def evaluate() -> dict:
    start = time.perf_counter()
    storms = json.loads((PROCESSED_DATA_DIR / "multidisaster/hurdat_storms.json").read_text(encoding="utf-8"))
    rows, excluded = track_snapshots(storms)
    # Storm IDs own splits, but a track spanning a fit boundary must be purged.
    crossing = {storm["storm_id"] for storm in storms if any(
        storm["points"][0]["valid_time_utc"] < cutoff < storm["points"][-1]["valid_time_utc"]
        for cutoff in ("2020-01-01T00:00:00Z", "2023-01-01T00:00:00Z"))}
    rows = [row for row in rows if row["storm_id"] not in crossing]
    excluded["boundary_crossing_storms_purged"] = len(crossing)
    splits = {name: [row for row in rows if low <= row["year"] <= high] for name, low, high in
              (("train", 2000, 2019), ("validation", 2020, 2022), ("test", 2023, 2025))}
    with threadpool_limits(limits=1):
        preliminary = fit(splits["train"])
        validation = score(splits["validation"], preliminary, splits["train"])
        means = {name: validation[name]["multiclass_brier_score"] for name in validation}
        selected = "logistic" if means["logistic"] < .98*means["train_frequency_baseline"] else "train_frequency_baseline"
        final_train = splits["train"] + splits["validation"]
        final = fit(final_train)
        test = score(splits["test"], final, final_train)
    failures = []
    for split_name, metrics in (("validation", validation), ("test", test)):
        for label in CLASSES:
            value = metrics[selected][label]
            if value["episode_count"] < 30 or min(value["positive_labels"], value["negative_labels"]) < 10 or value["expected_calibration_error"] > .15:
                failures.append(split_name + "_" + label + "_support_or_calibration_gate_failed")
    artifact = ARTIFACT_DIR / "multidisaster/hurricane_trend.joblib"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": final, "feature_names": FEATURES, "model_version": "nhc-retrospective-wind-trend-v1",
                 "selected_estimator": selected, "replay_only": True}, artifact)
    report = {"status": "evaluated_retrospective_experiment" if not failures else "trained_not_qualified",
              "live_dispatch_status": "unavailable_no_historical_operational_vintage_validation",
              "event_type": "North Atlantic Tropical Cyclone", "target": "24h_cyclone_max_wind_change_10kt_classes",
              "split_policy": "whole_storm_2000_2019_train;_2020_2022_validation;_2023_2025_test",
              "split": {name: {"snapshots": len(part), "storm_count": len({row["storm_id"] for row in part}),
                               "labels": dict(Counter(row["label"] for row in part))} for name, part in splits.items()},
              "exclusions": excluded, "feature_names": FEATURES, "selected_estimator": selected,
              "validation": validation, "test": test, "qualification_failures": failures,
              "production_eligibility": False, "operational_evaluation_eligible": False,
              "historical_asof_availability_verified": False,
              "limitations": ["Post-analysis HURDAT features were not necessarily known at the historical decision time.",
                              "Exact past 6h and future 24h wind measurements required; missing future tracks are excluded, not declared improving.",
                              "Trend means cyclone-maximum wind change, not geographic development or local worker danger.",
                              "All hurricane/typhoon live interface calls remain unavailable; no Pacific extrapolation.",
                              "Duration and interval coverage are inapplicable to this categorical wind-change target."],
              "elapsed_seconds": time.perf_counter()-start,
              "example": predict_replay(splits["test"][0]["features"], final, data_state="retrospective_best_track", event_status="historical_replay") if selected == "logistic" else None}
    report["reference_features"] = splits["test"][0]["features"]
    report["reference_storm_id"] = splits["test"][0]["storm_id"]
    report["reference_as_of_utc"] = splits["test"][0]["as_of_utc"]
    from ml.provision import file_sha256
    report["artifact_sha256"] = file_sha256(artifact)
    coverage = json.loads((REPORT_DIR / "multidisaster/hurdat_coverage.json").read_text(encoding="utf-8"))
    report["data_version"] = coverage["source_receipt"]["sha256"]
    path = REPORT_DIR / "multidisaster/hurricane_trend.json"
    path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(f"[hurricane] {report['split']} selected={selected} failures={failures} {report['elapsed_seconds']:.2f}s", flush=True)
    return report


if __name__ == "__main__":
    evaluate()
