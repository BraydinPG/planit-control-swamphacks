"""Deterministic production inference for confirmed, already-active Flood events."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from ml.config import HORIZONS_HOURS, MODEL_PATH, SUPPORTED_EVENT_TYPE
from ml.schemas import ACTIVE_STATUSES, INACTIVE_STATUSES, PREDICTION_SCOPE, not_applicable_result, unavailable_result, validate_event_context
from ml.train import (
    MINIMUM_AT_RISK_SUPPORT,
    SurvivalModels,
    conditional_km_survival,
    conditional_logistic_survival,
    conditional_quantile,
    km_support_at,
    load_models,
)


def _finite_probability(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return min(1.0, max(0.0, float(value)))


def _json_safe(result: dict[str, Any]) -> dict[str, Any]:
    """Reject non-finite numeric values before returning an API payload."""
    json.dumps(result, allow_nan=False)
    return result


def _has_location_association(context: dict[str, Any]) -> bool:
    if isinstance(context.get("site_id"), str) and context["site_id"].strip():
        return True
    location = context.get("location")
    if not isinstance(location, dict):
        return False
    if isinstance(location.get("region"), str) and location["region"].strip():
        return True
    return location.get("lat") is not None and location.get("lon") is not None


def _quality_status(context: dict[str, Any], support: int, stale_observation_count: int) -> str:
    if stale_observation_count:
        return "degraded_stale_observations"
    location = context.get("location") or {}
    match_quality = location.get("spatial_match_quality", "unknown") if isinstance(location, dict) else "unknown"
    if support < MINIMUM_AT_RISK_SUPPORT or match_quality in {"unknown", "region_only"}:
        return "limited_historical_regional_support"
    return "historical_event_model_only"


def _stale_observation_count(context: dict[str, Any]) -> int:
    observations = context.get("recent_observations", [])
    return sum(
        1 for observation in observations
        if str(observation.get("freshness", observation.get("data_state", ""))).casefold() == "stale"
    )


def _outcomes(models: SurvivalModels, elapsed_hours: float, start_month: int) -> dict[str, Any] | None:
    ongoing: dict[str, float] = {}
    ended: dict[str, float] = {}
    baseline: dict[str, float | None] = {}
    for horizon in HORIZONS_HOURS:
        model_survival = conditional_logistic_survival(models, elapsed_hours, start_month, horizon)
        baseline_survival = conditional_km_survival(models, elapsed_hours, horizon)
        if model_survival is None:
            return None
        probability = _finite_probability(model_survival)
        if probability is None:
            return None
        key = f"{horizon}h"
        ongoing[key] = probability
        ended[key] = 1.0 - probability
        baseline[key] = _finite_probability(baseline_survival)

    max_remaining = models.max_followup_hours - elapsed_hours
    if max_remaining <= 0:
        return None
    return {
        "recorded_event_ongoing_probability": ongoing,
        "recorded_event_ended_probability": ended,
        "remaining_duration_hours": {
            "p10": conditional_quantile(models, elapsed_hours, start_month, 0.10),
            "median": conditional_quantile(models, elapsed_hours, start_month, 0.50),
            "p90": conditional_quantile(models, elapsed_hours, start_month, 0.90),
            "tail_horizon_hours": models.max_followup_hours,
            "tail_beyond_24h": ongoing["24h"] > 0.0,
        },
        "baseline_recorded_event_ongoing_probability": baseline,
        "trend": "unknown",
        "trend_basis": "no_validated_time_varying_severity_labels",
    }


def predict_active_event(event_context: dict[str, Any], *, model: SurvivalModels | None = None,
                         artifact_path: Path = MODEL_PATH) -> dict[str, Any]:
    """Predict recorded-event persistence conditional on an active supported event.

    No training, network calls, or stochastic simulation occurs during inference.
    """
    if not isinstance(event_context, dict):
        return _json_safe(unavailable_result(event_context, "event_context must be a JSON object"))
    status = event_context.get("event_status")
    if status in INACTIVE_STATUSES or not event_context.get("event_id"):
        return _json_safe(not_applicable_result(event_context, "no confirmed active event was supplied"))
    if status not in ACTIVE_STATUSES:
        return _json_safe(unavailable_result(event_context, "event_status is not a supported confirmed-active state"))
    try:
        context = validate_event_context(event_context)
    except (TypeError, ValueError) as error:
        return _json_safe(unavailable_result(event_context, str(error)))

    if context["event_type"].casefold() != SUPPORTED_EVENT_TYPE.casefold():
        return _json_safe(unavailable_result(context, f"event type {context['event_type']!r} is not supported"))
    if not _has_location_association(context):
        return _json_safe(unavailable_result(context, "a site, region, or valid location association is required"))
    event_start = context.get("_event_start_datetime")
    if event_start is None:
        return _json_safe(unavailable_result(context, "event_start_utc is required to condition on event age"))

    try:
        fitted = model if model is not None else load_models(artifact_path)
    except (OSError, ValueError, EOFError) as error:
        return _json_safe(unavailable_result(context, f"trained model artifact unavailable: {error}"))
    if not isinstance(fitted, SurvivalModels):
        return _json_safe(unavailable_result(context, "supplied model artifact has an unsupported schema"))
    if fitted.event_type.casefold() != context["event_type"].casefold():
        return _json_safe(unavailable_result(context, "event type does not match the trained model"))

    elapsed_hours = max(0.0, (context["_as_of_datetime"] - event_start).total_seconds() / 3600)
    support = km_support_at(fitted, elapsed_hours)
    outcomes = _outcomes(fitted, elapsed_hours, event_start.month)
    if outcomes is None:
        return _json_safe(unavailable_result(context, "model support does not cover the requested age and horizons"))

    location = context.get("location") or {}
    match_quality = location.get("spatial_match_quality", "unknown") if isinstance(location, dict) else "unknown"
    stale_observations = _stale_observation_count(context)
    limitations = [
        "NOAA event intervals describe regional recorded events, not verified site conditions.",
        "Historical weather and live site measurements are not included in this trained model.",
        "Recorded event resolution does not mean site conditions are safe or work may resume.",
    ]
    result = {
        "status": "ok",
        "scope": PREDICTION_SCOPE,
        "site_id": context.get("site_id"),
        "event_id": context["event_id"],
        "event_type": context["event_type"],
        "as_of_utc": context["as_of_utc"],
        "outcomes": outcomes,
        "worker_context": {
            "summary": "Historical NOAA flood intervals estimate recorded-event persistence only; local conditions remain unverified.",
            "limitations": limitations,
            "never_interpret_as_all_clear": True,
        },
        "evidence_quality": {
            "status": _quality_status(context, support, stale_observations),
            "spatial_match_quality": match_quality,
            "training_event_count": fitted.training_event_count,
            "training_episode_count": fitted.training_episode_count,
            "support_at_current_event_age": support,
            "stale_observation_count": stale_observations,
            "available_features": ["event_type", "elapsed_hours", "start_month"],
            "missing_features": ["historical_weather", "current_site_measurements", "verified_site_hazard"],
        },
        "model_version": fitted.model_version,
        "is_simulated": bool(context.get("is_simulated", False) or status == "historical_replay"),
    }
    return _json_safe(result)


def predict_site(features: dict[str, Any], *, model: SurvivalModels | None = None,
                 artifact_path: Path = MODEL_PATH) -> dict[str, Any]:
    """Compatibility adapter; never predicts hazard onset or contributes to score."""
    if not isinstance(features, dict):
        features = {}
    event_context = features.get("active_event_context")
    if not isinstance(event_context, dict):
        result = not_applicable_result(features, "no active_event_context was supplied")
    else:
        result = predict_active_event(event_context, model=model, artifact_path=artifact_path)

    probabilities: dict[str, float] = {}
    if result["status"] == "ok":
        probabilities = {
            f"active_event_persists_{horizon}": result["outcomes"]["recorded_event_ongoing_probability"][f"{horizon}h"]
            for horizon in HORIZONS_HOURS
        }
    return _json_safe({
        "hazard_probabilities": probabilities,
        "model_component_0_10": 0.0,
        "factor_contributions": [],
        "confidence": None,
        "model_version": result["model_version"],
        "data_quality": {
            "status": "not_approved_for_score",
            "prediction_scope": PREDICTION_SCOPE,
            "event_type": result.get("event_type"),
            "event_status": event_context.get("event_status") if isinstance(event_context, dict) else None,
            "as_of_utc": result.get("as_of_utc"),
            "include_model_component_in_site_score": False,
            "confidence_status": "not_calibrated",
            "outlook_status": result["status"],
            "evidence_quality": result.get("evidence_quality", {}).get("status"),
        },
    })
