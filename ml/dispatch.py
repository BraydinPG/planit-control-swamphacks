"""Fail-closed registry dispatch for separately evaluated research targets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ml.config import ARTIFACT_DIR, REPORT_DIR
from ml.event_types import NOAA_EVENT_TYPES
from ml.schemas import PREDICTION_SCOPE, evidence_references, parse_utc, prediction_metadata, unavailable_result
from ml.train import MINIMUM_AT_RISK_SUPPORT, SurvivalModels, km_support_at, load_models

REGISTRY_PATH = REPORT_DIR / "multidisaster/registry.json"


def read_registry(path: Path = REGISTRY_PATH) -> dict:
    registry = json.loads(path.read_text(encoding="utf-8"))
    if registry.get("contract_version") != "1.1" or not isinstance(registry.get("events"), dict):
        raise ValueError("unsupported expansion registry")
    return registry


def resolve_artifact(entry: dict) -> Path:
    # The reviewed local registry is trusted configuration, never caller input.
    root = (ARTIFACT_DIR / "multidisaster").resolve()
    path = (ARTIFACT_DIR / entry["artifact"]).resolve()
    if not path.is_relative_to(root) or path.suffix != ".joblib":
        raise ValueError("registry artifact must be inside the expansion artifact directory")
    return path


def load_entry_model(entry: dict) -> SurvivalModels:
    return load_models(resolve_artifact(entry), expected_sha256=entry["artifact_sha256"],
                       expected_event_type=entry["event_type"])


def _metadata(context: dict, entry: dict | None) -> dict:
    event_type = context["event_type"]
    category = entry.get("category") if entry else (NOAA_EVENT_TYPES[event_type].category if event_type in NOAA_EVENT_TYPES else "unknown")
    return {"contract_version": "1.1", "event_category": category,
            "applicable_location": prediction_metadata(context)["applicable_location"], "research_only": True,
            "operational_evaluation_eligible": False, "data_version": entry.get("data_version") if entry else None,
            "event_definition": entry.get("event_definition") if entry else context.get("event_definition"),
            "target": entry.get("target") if entry else None}


def predict_expansion(context: dict, *, model: SurvivalModels | None = None,
                      registry: dict | None = None, model_cache: dict | None = None) -> dict[str, Any]:
    """Context is already schema validated; no I/O except trusted local artifacts."""
    from ml.predict import _outcomes, _stale_observation_count

    entry = None

    def unavailable(reason: str) -> dict:
        return {**unavailable_result(context, reason), **_metadata(context, entry)}

    try:
        registry = registry if registry is not None else read_registry()
        entry = registry["events"].get(context["event_type"])
    except (OSError, KeyError, ValueError, TypeError):
        return unavailable("multi-disaster registry unavailable or invalid")
    if not entry or entry.get("status") != "evaluated_research" or entry.get("prediction_eligible") is not True:
        failures = ", ".join(entry.get("qualification_failures", [])) if entry else ""
        return unavailable("event type has no qualified research model" + (": " + failures if failures else ""))
    if context.get("event_definition") != entry["event_definition"]:
        return unavailable("event_definition must match the separately evaluated target")
    if context.get("_event_start_datetime") is None:
        return unavailable("event_start_utc is required to condition on event age")
    location = context.get("location") or {}
    if not (location.get("region") or (location.get("lat") is not None and location.get("lon") is not None)):
        return unavailable("an applicable historical region or verified location is required")
    if context["event_status"] == "confirmed_active":
        if location.get("spatial_match_quality") != "site_verified" or not context.get("site_id"):
            return unavailable("new targets require a caller-verified event/site association")
        if not context.get("evidence") or any("valid_time_utc" not in item for item in context["evidence"]):
            return unavailable("new targets require timestamped local confirmation evidence")
        age = max((context["_as_of_datetime"] - parse_utc(item["valid_time_utc"], "evidence.valid_time_utc")).total_seconds() / 3600 for item in context["evidence"])
        if age > 1 or _stale_observation_count(context):
            return unavailable("local confirmation evidence must be current within one hour")
    if entry["category"] == "heat":
        from ml.sources.stations import STATION_IDS
        if context.get("station_id") not in STATION_IDS:
            return unavailable("heat target is limited to the three evaluated stations")
        if context["event_status"] == "confirmed_active":
            return unavailable("heat station-to-worksite transfer is not validated; use an explicit historical replay")
    elapsed = (context["_as_of_datetime"] - context["_event_start_datetime"]).total_seconds() / 3600
    if elapsed < entry["minimum_event_age_hours"]:
        return unavailable("event is younger than the evaluated continuous-activity definition")
    try:
        if model is not None:
            fitted = model
        elif model_cache is not None:
            key = (entry["event_type"], entry["artifact_sha256"])
            if key not in model_cache:
                model_cache[key] = load_entry_model(entry)
            fitted = model_cache[key]
        else:
            fitted = load_entry_model(entry)
    except Exception as error:
        return unavailable(f"event-specific artifact unavailable ({type(error).__name__})")
    if not isinstance(fitted, SurvivalModels) or fitted.event_type != entry["event_type"] or fitted.model_version != entry["artifact_model_version"]:
        return unavailable("event-specific model identity mismatch")
    support = km_support_at(fitted, elapsed)
    if support < MINIMUM_AT_RISK_SUPPORT:
        return unavailable("insufficient training risk-set support at this event age")
    outcomes = _outcomes(fitted, elapsed, context["_event_start_datetime"].month,
                         entry["selected_estimator"], tuple(entry["supported_horizons_hours"]))
    if outcomes is None:
        return unavailable("event-specific model does not cover this age and horizon")
    evidence = evidence_references(context)
    return {**prediction_metadata(context), **_metadata(context, entry),
            "status": "ok", "scope": PREDICTION_SCOPE, "outcomes": outcomes,
            "estimator": entry["selected_estimator"], "model_version": entry["artifact_model_version"] + ":" + entry["selected_estimator"],
            "artifact_version": fitted.model_version, "selection_basis": "fixed_validation_rule;_test_not_used_to_tune",
            "worker_context": {"summary": "Conditional historical event outlook for the stated research target.",
                               "limitations": entry["limitations"], "never_interpret_as_all_clear": True},
            "evidence_quality": {"status": "retrospective_research;_local_transfer_not_validated",
                                 "training_event_count": fitted.training_event_count,
                                 "training_episode_count": fitted.training_episode_count,
                                 "support_at_current_event_age": support,
                                 "data_completeness": None, "completeness_status": "not_a_calibrated_scalar",
                                 "confidence": None, "uncertainty_basis": "heldout_group_bootstrap_intervals_and_reliability_in_model_card",
                                 "model_card": "ml/reports/multidisaster/" + Path(entry["artifact"]).stem + ".json",
                                 "spatial_match_quality": location.get("spatial_match_quality", "unknown"),
                                 "available_features": ["event_type", "elapsed_hours", "start_month"],
                                 "missing_features": ["worksite_exposure", "historical_issue_time_vintage", "severity_trajectory"],
                                 "historical_asof_availability_verified": False,
                                 "evidence_ids": [item["id"] for item in evidence],
                                 "evidence_references": evidence,
                                 "provenance_status": "supplied_not_independently_verified" if evidence else "historical_replay_only"}}
