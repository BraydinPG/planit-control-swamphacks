"""Backend side of the approved event-context contract (`ml/contracts.py` `EventContext`).

Rudra confirms activation. The model never infers it. An event context is built only from
a supervisor-confirmed hazard notice for flooding, the one event type Cache's model
supports (`ml.config.SUPPORTED_EVENT_TYPE`). Potential notices, other hazards, and NWS
watches or warnings on their own don't count as a confirmed active event.

Event start (T050A fix): the context uses only trusted event-start evidence, an
`event_start` Evidence item written server-side on the notice. A notice's `created_at` or
a warning's issue time is not the event's start, so without that evidence the start is
None and the outlook is unavailable rather than conditioned on the wrong event age.
"""

from datetime import datetime
from typing import Any

from app.ingestion import SiteLike
from app.schemas import EvidenceKind, HazardNotice, NoticeStatus

SUPPORTED_EVENT_TYPE = "Flood"
CONFIRMATION_SOURCE = "supervisor_confirmed_hazard_notice"


def is_confirmed_flood(notice: HazardNotice, now: datetime) -> bool:
    """A confirmed flood notice for the Flood model. Flash Flood is a different target."""
    return (
        is_confirmed(notice, now)
        and "flood" in notice.hazard_label.casefold()
        and not any("flash flood" in e.label.casefold() for e in notice.evidence)
    )


def is_confirmed(notice: HazardNotice, now: datetime) -> bool:
    return (
        notice.status is NoticeStatus.CONFIRMED
        and notice.confirmed_at is not None
        and notice.confirmed_at <= now
    )


# Same value as app.services.refresh.DEMO_LOCATION_TYPE (importing it here would cycle).
DEMO_LOCATION_TYPE = "demo_site"


def is_simulated(notice: HazardNotice, site: object | None = None) -> bool:
    """A replay, never a current event: the evidence says simulated, or the site is a demo
    site (`location_type="demo_site"`), whose data is all simulated."""
    return getattr(site, "location_type", None) == DEMO_LOCATION_TYPE or any(
        "simulated" in e.label.casefold() for e in notice.evidence
    )


def trusted_event_start(notice: HazardNotice) -> datetime | None:
    """The earliest server-written event start that precedes confirmation, else None."""
    starts = [
        e.observed_at
        for e in notice.evidence
        if e.kind == EvidenceKind.EVENT_START
        and e.observed_at is not None
        and (notice.confirmed_at is None or e.observed_at <= notice.confirmed_at)
    ]
    return min(starts) if starts else None


def event_context_from_notice(
    notice: HazardNotice, site: SiteLike, now: datetime
) -> dict[str, Any] | None:
    """`EventContext` for a confirmed flood notice covering the site, or None.

    `event_start_utc` is None when no trusted start exists; the service then reports the
    outlook unavailable instead of calling the model.
    """
    if not is_confirmed_flood(notice, now):
        return None
    simulated = is_simulated(notice, site)
    start = trusted_event_start(notice)
    return {
        "event_id": notice.id,
        "event_type": SUPPORTED_EVENT_TYPE,
        "event_status": "historical_replay" if simulated else "confirmed_active",
        "event_start_utc": _utc(start) if start else None,
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
