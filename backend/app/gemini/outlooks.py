"""How long a confirmed hazard is expected to last, as briefing and instruction evidence (T058B).

The estimate is Cache's conditional event outlook (T050), which the site detail route
already shows. Here it becomes one plain sentence that a briefing or a suggested
instruction can cite. It stays an advisory estimate: it never changes the score or
alerts, and the wording avoids anything that reads as an all-clear.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.sites import event_outlook_for, load_notices
from app.db import models as db
from app.outlook import EventOutlookService
from app.schemas import EventOutlook, Evidence, EvidenceKind
from app.services.reports import miles_between


def site_outlook(
    session: Session, site: db.Site, now: datetime, outlooks: EventOutlookService
) -> EventOutlook | None:
    """The outlook for the newest confirmed event covering the site, or None."""
    return event_outlook_for(outlooks, site, load_notices(session, site), now)


def notice_outlook(
    session: Session, notice: db.HazardNotice, now: datetime, outlooks: EventOutlookService
) -> EventOutlook | None:
    """The outlook for one confirmed notice, at the nearest site its radius covers."""
    covered = [
        (miles_between(notice.lat, notice.lon, site.lat, site.lon), site.id, site)
        for site in session.scalars(select(db.Site)).all()
    ]
    covered = [c for c in covered if c[0] <= notice.radius_miles]
    if not covered:
        return None
    site = min(covered, key=lambda c: (c[0], c[1]))[2]
    notices = [n for n in load_notices(session, site) if n.id == notice.id]
    return event_outlook_for(outlooks, site, notices, now)


def describe(outlook: EventOutlook) -> str | None:
    """One plain sentence about the expected duration, or None when there's no estimate."""
    median = outlook.remaining_hours_median
    if outlook.status != "ok" or median is None:
        return None
    event = (outlook.event_type or "event").lower()
    sentence = f"Confirmed {event}: likely to continue for {_more(median)}"
    low, high = outlook.remaining_hours_p10, outlook.remaining_hours_p90
    if low is not None and high is not None and high > low:
        sentence += f" (likely range {_hours(low)} to {_hours(high)})"
    source = "simulated replay, " if outlook.is_simulated else ""
    return (
        f"{sentence}. Advisory estimate ({source}{outlook.model_version}) from past "
        "recorded events; it does not change alerts or authorize work."
    )


def outlook_evidence(outlook: EventOutlook) -> Evidence | None:
    sentence = describe(outlook)
    if sentence is None:
        return None
    return Evidence(
        id=f"outlook:{outlook.event_id or outlook.event_type or 'event'}",
        kind=EvidenceKind.MODEL_OUTPUT,
        label=sentence,
        observed_at=outlook.as_of_utc,
    )


def missing_estimate(outlook: EventOutlook) -> str:
    """An `unknowns` entry for a confirmed event without a usable estimate."""
    event = (outlook.event_type or "event").lower()
    reason = outlook.limitations[0] if outlook.limitations else outlook.status
    return f"Expected duration of the confirmed {event} is unavailable ({reason})."


def _more(hours: float) -> str:
    if hours < 1:
        return "less than an hour more"
    rounded = round(hours)
    return f"about {rounded} more hour" + ("" if rounded == 1 else "s")


def _hours(hours: float) -> str:
    if hours < 1:
        return "under 1 hour"
    rounded = round(hours)
    return f"{rounded} hour" + ("" if rounded == 1 else "s")
