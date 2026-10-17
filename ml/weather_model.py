"""Research-only survival model using weather available by an as-of timestamp."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.config import MAX_FOLLOWUP_HOURS, RANDOM_SEED
from ml.weather_features import WEATHER_FEATURE_NAMES

BASE_FEATURE_NAMES = ("log1p_elapsed_hours", "start_month_sin", "start_month_cos")
WEATHER_MODEL_VERSION = "noaa-flood-era5-retrospective-research-v2"


def _angle_features(elapsed_hours: float, start_month: int) -> list[float]:
    angle = 2 * math.pi * (start_month - 1) / 12
    return [math.log1p(elapsed_hours), math.sin(angle), math.cos(angle)]


def _feature_vector(features: dict[str, Any], elapsed_hours: float | None = None) -> list[float]:
    age = float(features["elapsed_hours"] if elapsed_hours is None else elapsed_hours)
    vector = _angle_features(age, int(features["start_month"]))
    for name in WEATHER_FEATURE_NAMES:
        value = features.get(name)
        vector.append(float(value) if value is not None and math.isfinite(float(value)) else np.nan)
    return vector


@dataclass
class WeatherSurvivalModel:
    pipeline: Pipeline
    training_snapshot_count: int
    training_episode_count: int
    training_risk_row_count: int
    weather_feature_missing_fraction: dict[str, float]
    feature_names: tuple[str, ...] = BASE_FEATURE_NAMES + WEATHER_FEATURE_NAMES
    model_version: str = WEATHER_MODEL_VERSION
    interpretation: str = "retrospective_as_of_reanalysis_not_operational_forecast_skill"


def build_weather_risk_rows(snapshots: Iterable[dict[str, Any]], *, max_followup_hours: int = MAX_FOLLOWUP_HOURS
                            ) -> list[dict[str, Any]]:
    """Expand active snapshots into hourly risks with as-of weather held fixed."""
    snapshot_list = list(snapshots)
    snapshots_by_episode: dict[str, int] = {}
    for snapshot in snapshot_list:
        episode_id = str(snapshot["episode_id"])
        snapshots_by_episode[episode_id] = snapshots_by_episode.get(episode_id, 0) + 1

    rows: list[dict[str, Any]] = []
    for snapshot in snapshot_list:
        features = dict(snapshot["features"])
        elapsed = float(features["elapsed_hours"])
        remaining = float(snapshot["labels"]["remaining_duration_hours"])
        episode_weight = 1.0 / snapshots_by_episode[str(snapshot["episode_id"])]
        intervals = min(math.ceil(remaining), max(0, math.ceil(max_followup_hours - elapsed)))
        for lead_hour in range(intervals):
            ended = remaining <= lead_hour + 1
            rows.append({
                "event_id": snapshot["event_id"],
                "episode_id": snapshot["episode_id"],
                "x": _feature_vector(features, elapsed + lead_hour),
                "ended_in_next_hour": ended,
                "sample_weight": episode_weight,
            })
            if ended:
                break
    return rows


def fit_weather_model(snapshots: Iterable[dict[str, Any]], *, minimum_snapshots: int = 50,
                      minimum_episodes: int = 20) -> WeatherSurvivalModel:
    snapshot_list = list(snapshots)
    episodes = {str(snapshot["episode_id"]) for snapshot in snapshot_list}
    if len(snapshot_list) < minimum_snapshots:
        raise ValueError(f"weather model requires {minimum_snapshots} training snapshots; found {len(snapshot_list)}")
    if len(episodes) < minimum_episodes:
        raise ValueError(f"weather model requires {minimum_episodes} episode groups; found {len(episodes)}")
    risk_rows = build_weather_risk_rows(snapshot_list)
    x = np.asarray([row["x"] for row in risk_rows], dtype=float)
    y = np.asarray([int(row["ended_in_next_hour"]) for row in risk_rows], dtype=int)
    weights = np.asarray([float(row["sample_weight"]) for row in risk_rows], dtype=float)
    if len(set(y.tolist())) < 2:
        raise ValueError("weather training rows contain only one event-end label class")
    if np.all(np.isnan(x[:, len(BASE_FEATURE_NAMES):])):
        raise ValueError("weather features are entirely missing in the training sample")
    missing_fraction = {
        name: float(np.isnan(x[:, len(BASE_FEATURE_NAMES) + index]).mean())
        for index, name in enumerate(WEATHER_FEATURE_NAMES)
    }

    pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
        ("scaler", StandardScaler()),
        ("hazard", LogisticRegression(C=0.1, max_iter=500, random_state=RANDOM_SEED, solver="lbfgs")),
    ])
    pipeline.fit(x, y, hazard__sample_weight=weights)
    return WeatherSurvivalModel(
        pipeline=pipeline,
        training_snapshot_count=len(snapshot_list),
        training_episode_count=len(episodes),
        training_risk_row_count=len(risk_rows),
        weather_feature_missing_fraction=missing_fraction,
    )


def conditional_weather_survival(model: WeatherSurvivalModel, snapshot: dict[str, Any],
                                 horizon_hours: int) -> float | None:
    if horizon_hours < 0:
        raise ValueError("horizon_hours must be non-negative")
    if not horizon_hours:
        return 1.0
    elapsed = float(snapshot["features"]["elapsed_hours"])
    if elapsed + horizon_hours > MAX_FOLLOWUP_HOURS:
        return None
    curve = conditional_weather_survival_curve(model, snapshot)
    return curve[horizon_hours - 1] if curve is not None else None


def conditional_weather_survival_curve(model: WeatherSurvivalModel, snapshot: dict[str, Any]) -> tuple[float, ...] | None:
    """Hold weather fixed at as-of; use the same absolute age cap as references."""
    features = dict(snapshot["features"])
    elapsed = float(features["elapsed_hours"])
    remaining = MAX_FOLLOWUP_HOURS - elapsed
    if not math.isfinite(elapsed) or elapsed < 0 or remaining <= 0:
        return None
    steps = math.ceil(remaining)
    matrix = np.asarray([_feature_vector(features, elapsed + step) for step in range(steps)], dtype=float)
    hazards = model.pipeline.predict_proba(matrix)[:, 1]
    survival, curve = 1.0, []
    for step, hazard in enumerate(hazards):
        survival *= (1.0 - float(hazard)) ** min(1.0, remaining - step)
        curve.append(min(1.0, max(0.0, survival)))
    return tuple(curve)
