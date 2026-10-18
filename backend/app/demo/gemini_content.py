"""Gemini output for the demo sites, in production's shape, always present.

On real sites Gemini writes four things, and any of them can fall back when Gemini is
slow or its output fails a check. The demo should always show what production shows when
Gemini works, so each round of `app.demo.freshen` fills what is missing at demo sites:

- **Notice radius** (`app.gemini.radius`): the seeded notices use the category default.
  Each gets a radius Gemini would choose for that hazard, never wider than the stored one
  and never narrower than the demo site it covers, so who sees it doesn't change.
- **Instruction suggestion** (`app.gemini.instructions`): each demo notice the demo
  organization confirmed gets a written-in-advance suggestion, which its supervisor
  approved and sent unchanged two minutes after confirming. Every text passes the same
  clearance check as a real suggestion.
- **Next-day briefing** (`app.gemini.briefings`): when a demo site has no briefing, or its
  next-workday briefing fell back to the template, real Gemini drafts one with the
  production prompt. If Gemini fails again, `demo_briefing_draft` writes the outlook from
  the same inputs instead, stored as Gemini's.
- **Report analysis**: `app.demo.report_analysis`.

Nothing a tester or the real 6 PM job wrote is replaced, except a template briefing at a
demo site. Simulated demo content: a demo site says so only in its name (AGENTS.md rule 6
exception). Real sites are never read or written here.
"""

import logging
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import models as db
from app.demo.scenario import DEMO_ORG_ID, WILDLIFE_INSTRUCTION
from app.gemini.briefing_schedule import is_due
from app.gemini.briefings import (
    BriefingDraft,
    BriefingInputs,
    DraftHazard,
    ForecastSource,
    briefing_id,
    draft_with_gemini,
    gather_inputs,
    next_workday,
    store_briefing,
)
from app.gemini.client import GeminiClient
from app.gemini.instructions import claims_clearance
from app.outlook import EventOutlookService
from app.schemas import EvidenceKind, GeneratedBy, RecommendedAction
from app.schemas.hazards import NoticeStatus, RadiusSource
from app.services.refresh import DEMO_LOCATION_TYPE
from app.services.reports import miles_between

logger = logging.getLogger(__name__)

# What Gemini would choose for each seeded hazard (miles), by the notice's hazard label.
RADIUS_MILES = {
    "flooding": 4.0,
    "hurricane": 45.0,
    "earthquake": 20.0,
    "heat index exceedance": 8.0,
    "heavy rain": 6.0,
    "high wind": 8.0,
    "winter storm": 9.0,
    "wildlife": 0.5,
}
# The suggestion Gemini drafted for each seeded notice; the supervisor sent it unchanged.
INSTRUCTIONS = {
    "demo-notice-wildlife": WILDLIFE_INSTRUCTION,
    "demo-notice-flood": (
        "Keep vehicles on the paved access road and away from flooded canal banks. Do not "
        "wade into standing water; alligators may be close to the road."
    ),
    "demo-anomaly-flood": (
        "Do not drive or walk through water on the access roads. Stage trucks and "
        "equipment on high ground, and check the flood warning before each move."
    ),
    "demo-anomaly-flash-flood": (
        "Move crews and equipment away from creek beds and low water crossings now. Never "
        "drive into a flooded road; turn around and use the higher route."
    ),
    "demo-anomaly-heavy-rain": (
        "Expect slick ground and poor visibility. Keep vehicles on firm surfaces, stay "
        "out of trenches and off slopes, and stop work under the lightning alert."
    ),
    "demo-anomaly-hurricane": (
        "Secure loose materials and equipment, and keep crews out of bucket trucks and "
        "off elevated work. Stay ready to move to shelter on your supervisor's call."
    ),
    "demo-anomaly-heat": (
        "Do heavy tasks early, take a shaded rest break every hour, and drink water every "
        "15 minutes. Watch each other for signs of heat illness."
    ),
    "demo-anomaly-earthquake": (
        "Expect aftershocks. Inspect poles, lines and structures for new damage from a "
        "distance before approaching, and keep clear of anything that could fall."
    ),
    "demo-anomaly-high-wind": (
        "Do not use bucket trucks, cranes or ladders in high wind. Secure loose material "
        "and keep clear of trees and lines that could come down."
    ),
    "demo-anomaly-winter-storm": (
        "Allow extra travel time and use chains or traction tires. Clear ice from walkways, "
        "wear traction cleats and warm layers, and limit time in the cold."
    ),
}
SENT_AFTER = timedelta(minutes=2)


def ensure_demo_notices(session: Session, now: datetime) -> int:
    """Give the seeded demo notices their radius and sent instruction. Commits; returns
    how many notices or assessments changed."""
    sites = list(
        session.scalars(select(db.Site).where(db.Site.location_type == DEMO_LOCATION_TYPE))
    )
    notices = list(
        session.scalars(select(db.HazardNotice).where(db.HazardNotice.id.in_(list(INSTRUCTIONS))))
    )
    changed = 0
    for notice in notices:
        radius = RADIUS_MILES.get(notice.hazard_label.lower())
        if notice.radius_source == RadiusSource.DEFAULT and radius is not None:
            covered = [
                miles_between(s.lat, s.lon, notice.lat, notice.lon)
                for s in sites
                if miles_between(s.lat, s.lon, notice.lat, notice.lon) <= notice.radius_miles
            ]
            notice.radius_miles = min(
                notice.radius_miles,
                max([radius, *(math.ceil((d + 0.5) * 10) / 10 for d in covered)]),
            )
            notice.radius_source = RadiusSource.GEMINI
            changed += 1
        text = INSTRUCTIONS[notice.id]
        assessments = list(
            session.scalars(
                select(db.NoticeAssessment).where(db.NoticeAssessment.notice_id == notice.id)
            )
        )
        if not assessments and notice.status == NoticeStatus.CONFIRMED:
            changed += _instruct(notice, text, now)  # confirmed before per-organization rows
        for assessment in assessments:
            if assessment.organization_id == DEMO_ORG_ID:
                changed += _instruct(assessment, text, now)
    session.commit()
    return changed


def _instruct(row, text: str, now: datetime) -> int:
    """Fill a confirmation's suggestion and, when nothing was sent, send it unchanged."""
    if row.confirmed_at is None:
        return 0
    changed = 0
    if row.suggested_instruction is None:
        row.suggested_instruction = text
        changed = 1
    if row.instruction is None and row.instruction_sent_at is None:
        row.instruction = row.suggested_instruction
        row.instruction_sent_at = min(_aware(row.confirmed_at) + SENT_AFTER, now)
        changed = 1
    return changed


@dataclass
class DemoBriefings:
    """What a briefing needs from outside: Gemini, the NWS forecast, event outlooks."""

    gemini: GeminiClient
    forecasts: ForecastSource
    outlooks: EventOutlookService | None = None


def ensure_demo_briefings(session: Session, now: datetime, sources: DemoBriefings) -> list[str]:
    """Write each demo site's next-workday briefing when it is missing or a template.

    A site with no briefing at all gets one now; otherwise a missing one waits for the
    6 PM job's window, so demo briefings keep their usual schedule. Returns the ids written.
    """
    supervised = select(db.Membership.organization_id).where(db.Membership.role == "supervisor")
    sites = session.scalars(
        select(db.Site)
        .join(db.Team, db.Team.site_id == db.Site.id)
        .where(db.Site.location_type == DEMO_LOCATION_TYPE, db.Team.organization_id.in_(supervised))
        .order_by(db.Site.id)
    ).all()
    written = []
    for site in sites:
        if not site.timezone:
            continue
        tz = ZoneInfo(site.timezone)
        target = briefing_id(site.id, next_workday(now, tz)[0])
        existing = session.get(db.Briefing, target)
        if existing is not None and existing.generated_by != GeneratedBy.FALLBACK:
            continue
        has_any = session.scalar(
            select(db.Briefing.id).where(db.Briefing.site_id == site.id).limit(1)
        )
        if existing is None and has_any is not None and not is_due(now, tz):
            continue
        try:
            session.execute(delete(db.Briefing).where(db.Briefing.id == target))
            inputs = gather_inputs(session, site, tz, now, sources.forecasts, sources.outlooks)
            draft = draft_with_gemini(inputs, sources.gemini) or demo_briefing_draft(inputs)
            written.append(store_briefing(session, inputs, draft, GeneratedBy.GEMINI, now).id)
        except IntegrityError:  # the 6 PM job wrote it at the same moment
            session.rollback()
    return written


def demo_briefing_draft(inputs: BriefingInputs) -> BriefingDraft:
    """The outlook Gemini writes, from the same inputs: the workday forecast first, then
    what may carry over from now. Cites only supplied evidence and never claims clearance."""
    forecast = [e for e in inputs.evidence if e.kind == EvidenceKind.OBSERVATION]
    alerts = inputs.ids(EvidenceKind.ALERT)
    reports = inputs.ids(EvidenceKind.REPORT)
    factors = [e for e in inputs.evidence if e.id.startswith("factor:")]
    hazards = [DraftHazard(hazard=_sentence(e.label), evidence_ids=[e.id]) for e in forecast]
    hazards += [
        DraftHazard(
            hazard=f"May carry into the shift: {_lower_first(_name(e.label))}",
            evidence_ids=[e.id],
        )
        for e in factors
    ]
    hazards += [
        DraftHazard(hazard=e.label, evidence_ids=[e.id])
        for e in inputs.evidence
        if e.kind == EvidenceKind.MODEL_OUTPUT
    ]
    day = f"{inputs.workday:%A}"
    if forecast:
        peaks = "; ".join(_peak(e.label) for e in forecast[:3])
        summary = f"For {day}'s shift at {inputs.site_name}, plan around the forecast: {peaks}."
    else:
        summary = (
            f"The forecast for {day}'s shift at {inputs.site_name} was not available, so check "
            "the morning forecast before the crew leaves."
        )
    if factors:
        now_names = ", ".join(_lower_first(_name(e.label)) for e in factors[:3])
        summary += (
            f" Conditions now ({now_names}) may carry into the morning, so check alerts and "
            "site conditions again before work starts."
        )
    actions = []
    heat = [e.id for e in forecast if "heat index" in e.label.lower()]
    rain = [e.id for e in forecast if "precipitation" in e.label.lower()]
    if heat:
        actions.append(
            RecommendedAction(
                action="Schedule heavy work before the heat index peaks, and plan shaded rest "
                "and water breaks.",
                evidence_ids=heat,
            )
        )
    if rain:
        actions.append(
            RecommendedAction(
                action="Pack rain gear and plan routes on firm, high ground in case of rain.",
                evidence_ids=rain,
            )
        )
    if alerts:
        actions.append(
            RecommendedAction(
                action="At the start of the shift, check which alerts are still active. "
                "Stop-work alerts stay in force until the system clears them.",
                evidence_ids=alerts,
            )
        )
    if reports:
        actions.append(
            RecommendedAction(
                action="Brief the crew on the confirmed crew reports before work starts.",
                evidence_ids=reports,
            )
        )
    if forecast and len(actions) < 4:
        actions.append(
            RecommendedAction(
                action="Check the morning forecast update before the crew leaves.",
                evidence_ids=[e.id for e in forecast],
            )
        )
    return BriefingDraft(
        summary=summary[:700],
        hazards=hazards[:8],
        recommended_actions=actions[:4],
        unknowns=["Conditions at the site tomorrow morning have not been observed yet."],
    )


def _sentence(label: str) -> str:
    """ "Forecast heat index up to 113°F at 14:00 local (NWS)" without the source."""
    return label.rsplit(" (", 1)[0]


def _peak(label: str) -> str:
    """ "heat index up to 113°F at 14:00 local", for a sentence."""
    return _lower_first(_sentence(label).removeprefix("Forecast "))


def _name(label: str) -> str:
    """A score factor's label without its points, source or notes."""
    return label.split(" (", 1)[0]


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:]


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def check_instructions() -> list[str]:
    """Ids whose written-in-advance text would fail the real clearance check (tests)."""
    return [i for i, text in INSTRUCTIONS.items() if claims_clearance(text) or len(text) > 500]
