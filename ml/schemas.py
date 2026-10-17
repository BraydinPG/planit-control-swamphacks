"""Input and output validation for conditional active-event predictions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

HORIZONS_HOURS = (6, 12, 24)
ACTIVE_STATUSES = {"confirmed_active", "historical_replay"}
INACTIVE_STATUSES = {"inactive", "resolved", "not_active", "no_event"}
SPATIAL_MATCH_QUALITIES = {"site_verified", "point_nearby", "region_only", "unknown"}
PREDICTION_SCOPE = "conditional_on_confirmed_active_event"


def parse_utc(value: Any, field_name: str) -> datetime:
    """Parse a timezone-aware timestamp and normalize it to UTC."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a timezone-aware ISO-8601 string")
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError(f"{field_name} is not a valid ISO-8601 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone")
    return parsed.astimezone(timezone.utc)


def validate_event_context(context: Any) -> dict[str, Any]:
    """Validate a confirmed event and reject evidence newer than its as-of time."""
    if not isinstance(context, dict):
        raise ValueError("event_context must be a JSON object")

    event_id = context.get("event_id")
    event_type = context.get("event_type")
    status = context.get("event_status")
    if not isinstance(event_id, str) or not event_id.strip():
        raise ValueError("event_id is required")
    if not isinstance(event_type, str) or not event_type.strip():
        raise ValueError("event_type is required")
    if status not in ACTIVE_STATUSES:
        raise ValueError("event_status must be confirmed_active or historical_replay")

    as_of = parse_utc(context.get("as_of_utc"), "as_of_utc")
    event_start_value = context.get("event_start_utc")
    event_start = parse_utc(event_start_value, "event_start_utc") if event_start_value else None
    if event_start and event_start > as_of:
        raise ValueError("event_start_utc cannot be later than as_of_utc")

    location = context.get("location")
    if location is not None:
        if not isinstance(location, dict):
            raise ValueError("location must be a JSON object")
        latitude = location.get("lat")
        longitude = location.get("lon")
        if latitude is not None and (not isinstance(latitude, (int, float)) or not -90 <= latitude <= 90):
            raise ValueError("location.lat must be between -90 and 90")
        if longitude is not None and (not isinstance(longitude, (int, float)) or not -180 <= longitude <= 180):
            raise ValueError("location.lon must be between -180 and 180")
        quality = location.get("spatial_match_quality", "unknown")
        if quality not in SPATIAL_MATCH_QUALITIES:
            raise ValueError("location.spatial_match_quality is unsupported")

    observations = context.get("recent_observations", [])
    if not isinstance(observations, list):
        raise ValueError("recent_observations must be a list")
    for index, observation in enumerate(observations):
        if not isinstance(observation, dict):
            raise ValueError(f"recent_observations[{index}] must be a JSON object")
        valid_time = parse_utc(observation.get("valid_time_utc"), f"recent_observations[{index}].valid_time_utc")
        if valid_time > as_of:
            raise ValueError(f"recent_observations[{index}] is newer than as_of_utc")
        value = observation.get("value")
        if value is not None and (not isinstance(value, (int, float)) or not __import__("math").isfinite(value)):
            raise ValueError(f"recent_observations[{index}].value must be finite numeric data")

    normalized = dict(context)
    normalized["as_of_utc"] = as_of.isoformat().replace("+00:00", "Z")
    normalized["event_start_utc"] = event_start.isoformat().replace("+00:00", "Z") if event_start else None
    normalized["_as_of_datetime"] = as_of
    normalized["_event_start_datetime"] = event_start
    return normalized


def not_applicable_result(context: Any, reason: str) -> dict[str, Any]:
    """Return an explicit no-event result without implying zero risk."""
    return {
        "status": "not_applicable_no_confirmed_event",
        "scope": PREDICTION_SCOPE,
        "site_id": context.get("site_id") if isinstance(context, dict) else None,
        "event_id": context.get("event_id") if isinstance(context, dict) else None,
        "event_type": context.get("event_type") if isinstance(context, dict) else None,
        "as_of_utc": context.get("as_of_utc") if isinstance(context, dict) else None,
        "outcomes": {},
        "worker_context": {
            "summary": "No conditional event outlook is available because no confirmed active event was supplied.",
            "limitations": [reason],
            "never_interpret_as_all_clear": True,
        },
        "evidence_quality": {"status": "not_applicable", "available_features": [], "missing_features": []},
        "model_version": "unavailable",
        "is_simulated": bool(context.get("is_simulated", False)) if isinstance(context, dict) else False,
    }


def unavailable_result(context: Any, reason: str) -> dict[str, Any]:
    """Return an explicit unavailable result without invented probabilities."""
    return {
        "status": "unavailable",
        "scope": PREDICTION_SCOPE,
        "site_id": context.get("site_id") if isinstance(context, dict) else None,
        "event_id": context.get("event_id") if isinstance(context, dict) else None,
        "event_type": context.get("event_type") if isinstance(context, dict) else None,
        "as_of_utc": context.get("as_of_utc") if isinstance(context, dict) else None,
        "outcomes": {},
        "worker_context": {
            "summary": "A conditional event outlook could not be produced from the available evidence.",
            "limitations": [reason],
            "never_interpret_as_all_clear": True,
        },
        "evidence_quality": {"status": "unavailable", "available_features": [], "missing_features": []},
        "model_version": "unavailable",
        "is_simulated": bool(context.get("is_simulated", False)) if isinstance(context, dict) else False,
    }
