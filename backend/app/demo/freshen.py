"""Keep the demo sites looking current, on the server, with no laptop involved.

Live feeds skip demo sites (`location_type="demo_site"`), so their seeded readings would
read "stale" after an hour and drop out of the 24-hour window, their lightning timers would
run out, and "event began 2 h ago" would keep growing. Instead, `keep_demo_fresh` slides
each demo site forward in time: every time-based row at the site moves by the same delta,
so each relative age stays what the seed set ("strike 6 min ago", "confirmed 1 h 50 min
ago") and the newest reading is current.

Moved at each demo site:

- readings and alerts (hypertables keyed on their time column): deleted and inserted again
  with shifted times. Ids stay the same, so notice sources, alert triggers and
  acknowledgements still resolve. Alert evidence times move too.
- acknowledgements of those alerts, and crew reports with their review times and their
  stored analysis (`enrichment`) times.
- the site's notices (sourced from its readings or reports) with their evidence times, and
  every organization's assessment of them. Evidence and confirmation move together, so an
  `event_start` stays before `confirmed_at` and the duration outlook stays available.

Then the site is rescored at `now`, so its score reads as just updated; the value doesn't
change. Nothing is removed, so a tester's own reports, confirmations and acknowledgements at
demo sites ride along. Briefings (dated windows, written by the 6 PM job) and audit events
(history) are left alone. Real sites are never read or written.

The delta is `now` minus the newest `fetched_at` among the site's readings, so sliding twice
at the same `now` changes nothing. A past event never moves past `now`: the seed's own
confirmations and anything a tester did since the last slide are newer than the readings,
so they stop at "just now". Timers and forecast times may lie ahead and move freely.

Each round also fills the Everglades report's seeded analysis when it has none
(`app.demo.report_analysis`), and links the public "Try demo" guests
(`ensure_guest_memberships`): a seed clears the demo organization's memberships, and the
guests' scope comes from theirs.

`run_forever` repeats the slide every `FEED_REFRESH_SECONDS` next to the live feed loop
(`app.services.refresh.run_forever`), so it runs only where `FEED_REFRESH_ENABLED` is on:
the server. One-shot: `python -m app.demo freshen`.
"""

import asyncio
import logging
from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, insert, or_, select
from sqlalchemy.orm import Session

from app.db import models as db
from app.demo.report_analysis import ensure_demo_report_analysis
from app.demo.scenario import DEMO_ORG_ID, DEMO_TEAM_ID
from app.ingestion import runtime
from app.security.dependencies import GUEST_USER_IDS
from app.services.refresh import DEMO_LOCATION_TYPE
from app.services.scoring import score_site

log = logging.getLogger(__name__)

# Smaller gaps aren't worth a rewrite; readings stay fresh for an hour.
MIN_DELTA = timedelta(minutes=1)


def keep_demo_fresh(session: Session, now: datetime) -> dict[str, timedelta]:
    """Slide every demo site to `now`. Returns the delta of each site that moved.

    A failure at one site rolls back that site only and never raises.
    """
    now = now.astimezone(UTC)
    try:
        ensure_guest_memberships(session)
    except Exception as exc:
        session.rollback()
        runtime.event("demo_guests_failed", failure=True, exception_type=type(exc).__name__)
    site_ids = list(
        session.scalars(
            select(db.Site.id)
            .where(db.Site.location_type == DEMO_LOCATION_TYPE)
            .order_by(db.Site.id)
        )
    )
    session.commit()
    moved = {}
    for site_id in site_ids:
        try:
            delta = slide_site(session, site_id, now)
        except Exception as exc:
            session.rollback()
            runtime.event(
                "demo_freshen_failed",
                failure=True,
                site_id=site_id,
                exception_type=type(exc).__name__,
            )
            continue
        if delta is not None:
            moved[site_id] = delta
    try:
        ensure_demo_report_analysis(session, now)
    except Exception as exc:
        session.rollback()
        runtime.event(
            "demo_report_analysis_failed", failure=True, exception_type=type(exc).__name__
        )
    if moved:
        runtime.event(
            "demo_freshened",
            sites=len(moved),
            minutes=round(max(moved.values()).total_seconds() / 60, 1),
        )
    return moved


# The guests' rows: crew on the Everglades team, and a supervisor of the demo organization.
GUEST_MEMBERSHIPS = {
    "crew": ("demo-membership-guest-crew", DEMO_TEAM_ID),
    "supervisor": ("demo-membership-guest-supervisor", None),
}


def ensure_guest_memberships(session: Session) -> bool:
    """Link the read-only demo guests (`X-Demo-Role`) to the demo organization. Idempotent;
    commits. False, changing nothing, when the demo organization or team isn't seeded."""
    if (
        session.get(db.Organization, DEMO_ORG_ID) is None
        or session.get(db.Team, DEMO_TEAM_ID) is None
    ):
        return False
    for role, (membership_id, team_id) in GUEST_MEMBERSHIPS.items():
        session.merge(
            db.Membership(
                id=membership_id,
                user_id=GUEST_USER_IDS[role],
                organization_id=DEMO_ORG_ID,
                team_id=team_id,
                role=role,
                display_name=f"Demo guest {role} (read-only)",
            )
        )
    session.commit()
    return True


def slide_site(session: Session, site_id: str, now: datetime) -> timedelta | None:
    """Move one demo site's time-based rows forward so its newest reading is at `now`, then
    rescore it. Commits; returns the delta, or None when the site is already current."""
    readings = db.Observation.__table__
    anchor = session.scalar(
        select(func.max(func.coalesce(readings.c.fetched_at, readings.c.observed_at))).where(
            readings.c.site_id == site_id
        )
    )
    if anchor is None:
        return None
    delta = now - _aware(anchor)
    if delta < MIN_DELTA:
        return None

    slide = _Slide(delta, now)
    observation_ids = [
        row["id"]
        for row in _move(
            session, db.Observation, site_id, slide, ("observed_at", "fetched_at"), ("valid_at",)
        )
    ]
    alert_ids = [
        row["id"]
        for row in _move(
            session, db.Alert, site_id, slide, ("triggered_at", "latest_event_at"), ("clear_after",)
        )
    ]
    slide.rows(
        session.scalars(
            select(db.Acknowledgement).where(db.Acknowledgement.alert_id.in_(alert_ids))
        ),
        "acknowledged_at",
    )
    reports = list(session.scalars(select(db.CrewReport).where(db.CrewReport.site_id == site_id)))
    slide.rows(reports, "created_at", "reviewed_at")
    for report in reports:
        if report.enrichment:
            report.enrichment = slide.analysis(report.enrichment)

    notices = list(
        session.scalars(
            select(db.HazardNotice).where(
                or_(
                    db.HazardNotice.source_ref.in_(observation_ids + [r.id for r in reports]),
                    # Products the seed names after the site, without a stored reading.
                    db.HazardNotice.source_ref.startswith(f"{site_id}:", autoescape=True),
                )
            )
        )
    )
    slide.rows(notices, "created_at", "confirmed_at", "instruction_sent_at")
    for notice in notices:
        notice.evidence = slide.evidence(notice.evidence)
    slide.rows(
        session.scalars(
            select(db.NoticeAssessment).where(
                db.NoticeAssessment.notice_id.in_([n.id for n in notices])
            )
        ),
        "confirmed_at",
        "instruction_sent_at",
    )
    session.flush()
    score_site(session, site_id, now)  # commits the slide and the new score together
    return delta


@dataclass(frozen=True)
class _Slide:
    """Moves times forward by `delta`. A past event never lands after `now`: something a
    tester did since the last slide is newer than the readings, so it stops at "just now"
    instead of moving into the future (where a confirmation would no longer count)."""

    delta: timedelta
    now: datetime

    def past(self, value: datetime | None) -> datetime | None:
        return None if value is None else min(_aware(value) + self.delta, self.now)

    def ahead(self, value: datetime | None) -> datetime | None:
        """Times that may lie ahead: a timer's end, a forecast's valid time."""
        return None if value is None else _aware(value) + self.delta

    def rows(self, rows: Iterable, *columns: str) -> None:
        for row in rows:
            for column in columns:
                setattr(row, column, self.past(getattr(row, column)))

    def analysis(self, enrichment: dict) -> dict:
        """A report's stored analysis (JSON): its time and its evidence times."""
        moved = {**enrichment, "evidence": self.evidence(enrichment.get("evidence"))}
        if enrichment.get("analyzed_at"):
            moved["analyzed_at"] = self._json_time(enrichment["analyzed_at"])
        return moved

    def _json_time(self, at: str) -> str:
        moved = self.past(datetime.fromisoformat(at)).isoformat()
        return moved.replace("+00:00", "Z") if at.endswith("Z") else moved

    def evidence(self, items: list | None) -> list:
        """Evidence is stored as JSON; move each item's `observed_at`, keeping its format."""
        shifted = []
        for item in items or []:
            at = item.get("observed_at") if isinstance(item, dict) else None
            if at:
                item = {**item, "observed_at": self._json_time(at)}
            shifted.append(item)
        return shifted


def _move(
    session: Session,
    model,
    site_id: str,
    slide: _Slide,
    past: tuple[str, ...],
    ahead: tuple[str, ...],
) -> list[dict]:
    """Delete a hypertable's rows at the site and insert them again with shifted times.

    Their time column is part of the key, and an update could move a row across chunks.
    """
    table = model.__table__
    rows = [
        dict(row)
        for row in session.execute(
            delete(table).where(table.c.site_id == site_id).returning(*table.c)
        ).mappings()
    ]
    for row in rows:
        row.update({c: slide.past(row[c]) for c in past})
        row.update({c: slide.ahead(row[c]) for c in ahead})
        if "evidence" in row:
            row["evidence"] = slide.evidence(row["evidence"])
    if rows:
        session.execute(insert(table), rows)
    return rows


def _aware(value: datetime) -> datetime:
    """Treat naive timestamps from the driver as UTC."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


async def run_forever(
    stop: asyncio.Event,
    interval: float,
    sessions: Callable[[], AbstractContextManager[Session]] | None = None,
) -> None:
    """Slide the demo sites, wait `interval` seconds, repeat until `stop` is set.

    Errors are logged and never end the loop or reach the live feed loop beside it.
    """
    if sessions is None:
        from app.db import get_session as sessions

    def once() -> dict[str, timedelta]:
        with sessions() as session:
            return keep_demo_fresh(session, datetime.now(UTC))

    while not stop.is_set():
        try:
            await asyncio.to_thread(once)
        except Exception as exc:
            runtime.event("demo_freshen_failed", failure=True, exception_type=type(exc).__name__)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            pass
