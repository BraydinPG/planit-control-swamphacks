"""Leakage-resistant active-event snapshots and episode-grouped data splits."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from ml.config import SNAPSHOT_OFFSETS_HOURS

FEATURE_ALLOWLIST = ("event_type", "elapsed_hours", "start_month")


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("event timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def build_active_snapshots(events: Iterable[dict[str, Any]],
                           offsets_hours: tuple[int, ...] = SNAPSHOT_OFFSETS_HOURS
                           ) -> list[dict[str, Any]]:
    """Create at most one, six-, and twelve-hour snapshots per recorded event."""
    snapshots: list[dict[str, Any]] = []
    for event in events:
        start_value = event.get("start_utc")
        end_value = event.get("end_utc")
        if not start_value or not end_value:
            continue
        start = _parse_timestamp(str(start_value))
        end = _parse_timestamp(str(end_value))
        if end <= start:
            continue
        episode_id = str(event.get("episode_id") or event.get("event_id") or "")
        event_id = str(event.get("event_id") or "")
        if not episode_id or not event_id:
            continue
        for elapsed_hours in offsets_hours:
            if elapsed_hours < 0:
                raise ValueError("snapshot offsets cannot be negative")
            as_of = start + timedelta(hours=elapsed_hours)
            if as_of >= end:
                continue
            remaining_hours = (end - as_of).total_seconds() / 3600
            horizons = (6, 12, 24)
            labels = {
                f"recorded_event_ongoing_{horizon}h": remaining_hours > horizon
                for horizon in horizons
            }
            snapshots.append({
                "event_id": event_id,
                "episode_id": episode_id,
                "event_year": start.year,
                "as_of_utc": as_of.isoformat().replace("+00:00", "Z"),
                "features": {
                    "event_type": str(event.get("event_type") or ""),
                    "elapsed_hours": float(elapsed_hours),
                    "start_month": start.month,
                },
                "labels": {
                    "remaining_duration_hours": remaining_hours,
                    **labels,
                },
                "label_quality": event.get("label_quality", "recorded_event_interval"),
                "geometry_quality": event.get("geometry_quality", "unknown"),
            })
    return snapshots


def validate_snapshot_features(snapshot: dict[str, Any]) -> None:
    """Fail closed when a predictor includes a non-allowlisted field."""
    features = snapshot.get("features")
    if not isinstance(features, dict):
        raise ValueError("snapshot.features must be an object")
    unexpected = set(features).difference(FEATURE_ALLOWLIST)
    missing = set(FEATURE_ALLOWLIST).difference(features)
    if unexpected:
        raise ValueError(f"forbidden predictor fields: {', '.join(sorted(unexpected))}")
    if missing:
        raise ValueError(f"missing predictor fields: {', '.join(sorted(missing))}")
    if not isinstance(features["event_type"], str) or not features["event_type"]:
        raise ValueError("features.event_type must be a non-empty string")
    if not isinstance(features["elapsed_hours"], (int, float)) or features["elapsed_hours"] < 0:
        raise ValueError("features.elapsed_hours must be non-negative")
    if not isinstance(features["start_month"], int) or not 1 <= features["start_month"] <= 12:
        raise ValueError("features.start_month must be in [1, 12]")


def split_events_by_episode(events: Iterable[dict[str, Any]], *, train_end_year: int = 2023,
                            validation_year: int = 2024, test_year: int = 2025
                            ) -> dict[str, list[dict[str, Any]]]:
    """Keep episodes intact and purge outcomes crossing a fit/selection cutoff.

    Earliest-start assignment alone leaks labels when an episode continues into
    the next evaluation year. Purge those episodes from every split instead.
    """
    if not train_end_year < validation_year < test_year:
        raise ValueError("split years must be strictly chronological")
    event_list = list(events)
    group_year: dict[str, int] = {}
    group_bounds: dict[str, tuple[datetime, datetime]] = {}
    for event in event_list:
        episode_id = str(event.get("episode_id") or event.get("event_id") or "")
        start_value = event.get("start_utc")
        if not episode_id or not start_value:
            continue
        start = _parse_timestamp(str(event.get("episode_start_utc") or start_value))
        end = _parse_timestamp(str(event.get("episode_end_utc") or event.get("end_utc") or start_value))
        year = start.year
        group_year[episode_id] = min(year, group_year.get(episode_id, year))
        previous = group_bounds.get(episode_id, (start, end))
        group_bounds[episode_id] = (min(start, previous[0]), max(end, previous[1]))

    boundaries = (datetime(train_end_year + 1, 1, 1, tzinfo=timezone.utc),
                  datetime(test_year, 1, 1, tzinfo=timezone.utc))
    purged = {group for group, (start, end) in group_bounds.items()
              if any(start < boundary < end for boundary in boundaries)}

    split: dict[str, list[dict[str, Any]]] = {"train": [], "validation": [], "test": [], "excluded": []}
    for event in event_list:
        episode_id = str(event.get("episode_id") or event.get("event_id") or "")
        year = group_year.get(episode_id)
        if year is None or episode_id in purged:
            split["excluded"].append(event)
        elif year <= train_end_year:
            split["train"].append(event)
        elif year == validation_year:
            split["validation"].append(event)
        elif year == test_year:
            split["test"].append(event)
        else:
            split["excluded"].append(event)
    group_sets = {name: {str(event.get("episode_id") or event.get("event_id")) for event in rows}
                  for name, rows in split.items() if name != "excluded"}
    if (group_sets["train"] & group_sets["validation"] or
            group_sets["train"] & group_sets["test"] or
            group_sets["validation"] & group_sets["test"]):
        raise RuntimeError("episode leakage detected across chronological splits")
    return split


def split_snapshots_by_episode(snapshots: Iterable[dict[str, Any]],
                               event_splits: dict[str, list[dict[str, Any]]]
                               ) -> dict[str, list[dict[str, Any]]]:
    """Route snapshots using event split assignments, never splitting snapshots of a group."""
    assignments: dict[str, str] = {}
    for split_name, rows in event_splits.items():
        if split_name == "excluded":
            continue
        for event in rows:
            group_id = str(event.get("episode_id") or event.get("event_id") or "")
            previous = assignments.setdefault(group_id, split_name)
            if previous != split_name:
                raise RuntimeError(f"episode {group_id} was assigned to multiple splits")
    output = {"train": [], "validation": [], "test": [], "excluded": []}
    for snapshot in snapshots:
        group_id = str(snapshot.get("episode_id") or "")
        split_name = assignments.get(group_id, "excluded")
        output[split_name].append(snapshot)
    return output
