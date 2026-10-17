"""Right-censor-aware duration records and discrete-time hazard rows."""

from __future__ import annotations

import math
from collections import Counter
from typing import Any, Iterable

from ml.config import MAX_FOLLOWUP_HOURS
from ml.events import event_duration_hours


def duration_records(events: Iterable[dict[str, Any]], max_followup_hours: int = MAX_FOLLOWUP_HOURS
                     ) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Prepare survival observations; unknown ends are excluded, never called resolved."""
    records: list[dict[str, Any]] = []
    counts = {"events_total": 0, "complete_intervals": 0, "unknown_end_excluded": 0,
              "invalid_duration_excluded": 0, "administratively_censored": 0}
    for event in events:
        counts["events_total"] += 1
        duration = event_duration_hours(event)
        if duration is None:
            counts["unknown_end_excluded"] += 1
            continue
        if not math.isfinite(duration) or duration <= 0:
            counts["invalid_duration_excluded"] += 1
            continue
        observed = duration <= max_followup_hours
        records.append({
            "event_id": event.get("event_id"),
            "episode_id": event.get("episode_id") or event.get("event_id"),
            "event_type": event.get("event_type"),
            "start_month": int(str(event["start_utc"])[5:7]),
            "duration_hours": min(duration, float(max_followup_hours)),
            "event_observed": observed,
        })
        counts["complete_intervals" if observed else "administratively_censored"] += 1
    return records, counts


def discrete_time_hazard_rows(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expand event intervals into at-risk hours with an end-in-next-hour label."""
    record_list = list(records)
    events_per_episode = Counter(str(record["episode_id"]) for record in record_list)
    rows: list[dict[str, Any]] = []
    for record in record_list:
        duration = float(record["duration_hours"])
        observed = bool(record["event_observed"])
        episode_id = str(record["episode_id"])
        weight = 1.0 / events_per_episode[episode_id]
        interval_count = min(math.ceil(duration), MAX_FOLLOWUP_HOURS)
        for elapsed_hour in range(interval_count):
            ended_in_interval = observed and duration <= elapsed_hour + 1
            rows.append({
                "event_id": record.get("event_id"),
                "episode_id": episode_id,
                "features": {
                    "event_type": str(record.get("event_type") or ""),
                    "elapsed_hours": float(elapsed_hour),
                    "start_month": int(record["start_month"]),
                },
                "ended_in_next_hour": bool(ended_in_interval),
                "sample_weight": weight,
            })
            if ended_in_interval:
                break
    return rows
