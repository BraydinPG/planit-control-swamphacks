"""Backend side of the approved event-context contract (`ml/contracts.py` `EventContext`).

Rudra confirms activation. The model never infers it. An event context is built only from
a supervisor-confirmed hazard notice for flooding, the one event type Cache's model
supports (`ml.config.SUPPORTED_EVENT_TYPE`). Potential notices, other hazards, and NWS
watches or warnings on their own don't count as a confirmed active event.
"""

from datetime import datetime
from typing import Any

from app.ingestion import SiteLike
from app.schemas import HazardNotice, NoticeStatus

SUPPORTED_EVENT_TYPE = "Flood"
CONFIRMATION_SOURCE = "supervisor_confirmed_hazard_notice"


def is_confirmed_flood(notice: HazardNotice, now: datetime) -> bool:
    return (
        notice.status is NoticeStatus.CONFIRMED
        and notice.confirmed_at is not None
        and notice.confirmed_at <= now
        and "flood" in notice.hazard_label.casefold()
    )


def event_context_from_notice(
    notice: HazardNotice, site: SiteLike, now: datetime
) -> dict[str, Any] | None:
    """`EventContext` for a confirmed flood notice covering the site, or None."""
    if not is_confirmed_flood(notice, now):
        return None
    simulated = any("simulated" in e.label.casefold() for e in notice.evidence)
    return {
        "event_id": notice.id,
        "event_type": SUPPORTED_EVENT_TYPE,
        "event_status": "historical_replay" if simulated else "confirmed_active",
        "event_start_utc": _utc(notice.created_at),
        "as_of_utc": _utc(now),
        "site_id": site.id,
        "location": {
            "lat": notice.lat,
            "lon": notice.lon,
            "spatial_match_quality": "point_nearby",
        },
        "evidence": [
            {
                "id": notice.id,
                "source": CONFIRMATION_SOURCE,
                "available_at_utc": _utc(notice.confirmed_at),
            }
        ],
        "is_simulated": simulated,
    }


def _utc(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")
