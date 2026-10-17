"""Conditional survival baseline and interpretable discrete-time hazard model."""

from __future__ import annotations

import math
import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression

from ml.config import MAX_FOLLOWUP_HOURS, MODEL_PATH, RANDOM_SEED, SUPPORTED_EVENT_TYPE
from ml.labels import discrete_time_hazard_rows, duration_records

MODEL_VERSION = "noaa-flood-pooled-logistic-v1"
MINIMUM_AT_RISK_SUPPORT = 20


@dataclass
class SurvivalModels:
    classifier: LogisticRegression
    durations_hours: tuple[float, ...]
    end_observed: tuple[bool, ...]
    support_by_hour: tuple[int, ...]
    km_event_times: tuple[float, ...]
    km_survival_values: tuple[float, ...]
    training_event_count: int
    training_episode_count: int
    max_followup_hours: int
    max_supported_age_hours: int
    model_version: str = MODEL_VERSION
    event_type: str = SUPPORTED_EVENT_TYPE
    source_scope: str = "NOAA regional recorded Flood intervals"
    feature_names: tuple[str, ...] = ("log1p_elapsed_hours", "start_month_sin", "start_month_cos")


def _vector(elapsed_hours: float, start_month: int) -> list[float]:
    angle = 2 * math.pi * (start_month - 1) / 12
    return [math.log1p(elapsed_hours), math.sin(angle), math.cos(angle)]


def _survival_feature_matrix(risk_rows: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    features = np.asarray([
        _vector(float(row["features"]["elapsed_hours"]), int(row["features"]["start_month"]))
        for row in risk_rows
    ], dtype=float)
    labels = np.asarray([int(row["ended_in_next_hour"]) for row in risk_rows], dtype=int)
    weights = np.asarray([float(row["sample_weight"]) for row in risk_rows], dtype=float)
    return features, labels, weights


def fit_models(events: Iterable[dict[str, Any]], *, max_followup_hours: int = MAX_FOLLOWUP_HOURS,
               minimum_events: int = 50, minimum_episodes: int = 20) -> SurvivalModels:
    """Fit pooled logistic hazards and retain same-sample KM baseline data."""
    event_list = [event for event in events if event.get("event_type") == SUPPORTED_EVENT_TYPE]
    records, _ = duration_records(event_list, max_followup_hours=max_followup_hours)
    episodes = {str(record["episode_id"]) for record in records}
    if len(records) < minimum_events:
        raise ValueError(f"training requires at least {minimum_events} complete Flood intervals; found {len(records)}")
    if len(episodes) < minimum_episodes:
        raise ValueError(f"training requires at least {minimum_episodes} independent NOAA episodes; found {len(episodes)}")

    risk_rows = discrete_time_hazard_rows(records)
    features, labels, weights = _survival_feature_matrix(risk_rows)
    if len(set(labels.tolist())) < 2:
        raise ValueError("training intervals contain only one hazard-label class")
    classifier = LogisticRegression(C=0.1, max_iter=500, random_state=RANDOM_SEED, solver="lbfgs")
    classifier.fit(features, labels, sample_weight=weights)

    durations = tuple(float(record["duration_hours"]) for record in records)
    observed = tuple(bool(record["event_observed"]) for record in records)
    support = tuple(sum(duration > hour for duration in durations) for hour in range(max_followup_hours + 1))
    km_event_times: list[float] = []
    km_survival_values: list[float] = []
    survival = 1.0
    for event_time in sorted({duration for duration, observed_end in zip(durations, observed) if observed_end}):
        at_risk = sum(duration >= event_time for duration in durations)
        failures = sum(duration == event_time and observed_end
                       for duration, observed_end in zip(durations, observed))
        if at_risk:
            survival *= 1.0 - failures / at_risk
        km_event_times.append(event_time)
        km_survival_values.append(survival)

    supported_ages = [hour for hour, count in enumerate(support) if count >= MINIMUM_AT_RISK_SUPPORT]
    max_supported_age = max(supported_ages, default=0)
    return SurvivalModels(
        classifier=classifier,
        durations_hours=durations,
        end_observed=observed,
        support_by_hour=support,
        km_event_times=tuple(km_event_times),
        km_survival_values=tuple(km_survival_values),
        training_event_count=len(records),
        training_episode_count=len(episodes),
        max_followup_hours=max_followup_hours,
        max_supported_age_hours=max_supported_age,
    )


def save_models(models: SurvivalModels, path: Path = MODEL_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "artifact_schema_version": 1,
        "classifier": models.classifier,
        "durations_hours": models.durations_hours,
        "end_observed": models.end_observed,
        "support_by_hour": models.support_by_hour,
        "km_event_times": models.km_event_times,
        "km_survival_values": models.km_survival_values,
        "training_event_count": models.training_event_count,
        "training_episode_count": models.training_episode_count,
        "max_followup_hours": models.max_followup_hours,
        "max_supported_age_hours": models.max_supported_age_hours,
        "model_version": models.model_version,
        "event_type": models.event_type,
        "source_scope": models.source_scope,
        "feature_names": models.feature_names,
    }
    joblib.dump(payload, path)
    return path


def load_models(path: Path = MODEL_PATH) -> SurvivalModels:
    """Load a locally trained artifact; callers must only load trusted project files."""
    payload = joblib.load(path)
    if isinstance(payload, SurvivalModels):
        models = payload
    elif isinstance(payload, dict) and payload.get("artifact_schema_version") == 1:
        models = SurvivalModels(**{key: value for key, value in payload.items()
                                   if key != "artifact_schema_version"})
    else:
        raise ValueError("model artifact has an unsupported schema")
    if models.event_type != SUPPORTED_EVENT_TYPE or models.model_version != MODEL_VERSION:
        raise ValueError("model artifact version or event type is unsupported")
    return models


def km_survival_at(models: SurvivalModels, time_hours: float) -> float:
    """Evaluate a right-censor-aware Kaplan-Meier survival estimate."""
    if time_hours < 0:
        raise ValueError("time_hours must be non-negative")
    from bisect import bisect_right

    index = bisect_right(models.km_event_times, time_hours) - 1
    survival = models.km_survival_values[index] if index >= 0 else 1.0
    return min(1.0, max(0.0, survival))


def km_support_at(models: SurvivalModels, elapsed_hours: float) -> int:
    return sum(duration > elapsed_hours for duration in models.durations_hours)


def conditional_km_survival(models: SurvivalModels, elapsed_hours: float, horizon_hours: float,
                            min_support: int = MINIMUM_AT_RISK_SUPPORT) -> float | None:
    """Return P(recorded event persists through horizon | active at elapsed age)."""
    if elapsed_hours < 0 or horizon_hours < 0:
        raise ValueError("elapsed and horizon hours must be non-negative")
    if elapsed_hours + horizon_hours > models.max_followup_hours:
        return None
    if km_support_at(models, elapsed_hours) < min_support:
        return None
    denominator = km_survival_at(models, elapsed_hours)
    if denominator <= 0:
        return None
    return min(1.0, max(0.0, km_survival_at(models, elapsed_hours + horizon_hours) / denominator))


def logistic_hourly_hazard(models: SurvivalModels, elapsed_hours: float, start_month: int) -> float:
    if not 1 <= start_month <= 12:
        raise ValueError("start_month must be in [1, 12]")
    features = np.asarray([_vector(elapsed_hours, start_month)], dtype=float)
    probability = float(models.classifier.predict_proba(features)[0, 1])
    return min(1.0, max(0.0, probability))


def conditional_logistic_survival(models: SurvivalModels, elapsed_hours: float, start_month: int,
                                  horizon_hours: float) -> float | None:
    """Integrate discrete hazards fractionally from current age to a horizon."""
    if elapsed_hours < 0 or horizon_hours < 0:
        raise ValueError("elapsed and horizon hours must be non-negative")
    if elapsed_hours > models.max_supported_age_hours:
        return None
    if elapsed_hours + horizon_hours > models.max_followup_hours:
        return None
    start = elapsed_hours
    end = elapsed_hours + horizon_hours
    intervals = list(range(math.floor(start), math.ceil(end)))
    if not intervals:
        return 1.0
    features = np.asarray([_vector(float(interval), start_month) for interval in intervals], dtype=float)
    hazards = models.classifier.predict_proba(features)[:, 1]
    survival = 1.0
    for interval, hazard in zip(intervals, hazards):
        overlap = max(0.0, min(end, interval + 1.0) - max(start, float(interval)))
        if overlap:
            survival *= (1.0 - float(hazard)) ** overlap
    return min(1.0, max(0.0, survival))


def conditional_logistic_survival_curve(models: SurvivalModels, elapsed_hours: float,
                                        start_month: int) -> tuple[float, ...] | None:
    """Evaluate every integer remaining-hour survival point with one classifier call."""
    if elapsed_hours < 0:
        raise ValueError("elapsed_hours must be non-negative")
    if not 1 <= start_month <= 12:
        raise ValueError("start_month must be in [1, 12]")
    if elapsed_hours > models.max_supported_age_hours:
        return None
    max_remaining = models.max_followup_hours - elapsed_hours
    if max_remaining <= 0:
        return None
    final_time = elapsed_hours + max_remaining
    intervals = list(range(math.floor(elapsed_hours), math.ceil(final_time)))
    features = np.asarray([_vector(float(interval), start_month) for interval in intervals], dtype=float)
    predicted_hazards = models.classifier.predict_proba(features)[:, 1]
    hazard_by_hour = dict(zip(intervals, predicted_hazards))

    survival = 1.0
    current_time = elapsed_hours
    curve: list[float] = []
    for step in range(1, math.ceil(max_remaining) + 1):
        target_time = min(elapsed_hours + step, final_time)
        while current_time < target_time:
            interval = math.floor(current_time + 1e-12)
            next_time = min(target_time, interval + 1.0)
            overlap = next_time - current_time
            hazard = float(hazard_by_hour[interval])
            survival *= (1.0 - hazard) ** overlap
            current_time = next_time
        curve.append(min(1.0, max(0.0, survival)))
    return tuple(curve)


def conditional_quantile(models: SurvivalModels, elapsed_hours: float, start_month: int,
                         quantile: float, *, estimator: str = "logistic") -> float | None:
    """Find a remaining-time quantile; return None when tail support is insufficient."""
    if not 0 < quantile < 1:
        raise ValueError("quantile must be between 0 and 1")
    max_remaining = models.max_followup_hours - elapsed_hours
    if max_remaining <= 0:
        return None
    if estimator not in {"logistic", "km"}:
        raise ValueError("estimator must be logistic or km")
    if estimator == "km" and km_support_at(models, elapsed_hours) < MINIMUM_AT_RISK_SUPPORT:
        return None
    steps = math.ceil(max_remaining)
    if estimator == "logistic":
        curve = conditional_logistic_survival_curve(models, elapsed_hours, start_month)
        if curve is None:
            return None
    else:
        denominator = km_survival_at(models, elapsed_hours)
        if denominator <= 0:
            return None
        curve = tuple(km_survival_at(models, elapsed_hours + step) / denominator
                      for step in range(1, steps + 1))
    for step, survival in enumerate(curve[:steps], start=1):
        if 1.0 - survival >= quantile:
            return min(float(step), max_remaining)
    return None


def main() -> None:
    from ml.config import RAW_DATA_DIR
    from ml.events import read_noaa_detail_files

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=RAW_DATA_DIR)
    parser.add_argument("--output", type=Path, default=MODEL_PATH)
    parser.add_argument("--through-year", type=int, default=2024)
    args = parser.parse_args()
    files = sorted(args.input_dir.glob("StormEvents_details-ftp_v1.0_d*.csv.gz"))
    if not files:
        raise SystemExit(f"No NOAA detail archives found under {args.input_dir}; run ml.sources.noaa first.")
    events, source_counts = read_noaa_detail_files(files)
    training_events = [event for event in events if int(event["source_year"]) <= args.through_year]
    models = fit_models(training_events)
    save_models(models, args.output)
    print(json.dumps({
        "model_version": models.model_version,
        "event_type": models.event_type,
        "training_event_count": models.training_event_count,
        "training_episode_count": models.training_episode_count,
        "through_year": args.through_year,
        "source_row_counts": source_counts,
        "artifact": str(args.output),
    }, indent=2))


if __name__ == "__main__":
    main()
