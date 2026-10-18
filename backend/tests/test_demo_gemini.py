"""Demo sites always show Gemini output in production's shape (`app.demo.gemini_content`)."""

from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import delete, select

from app.api.sites import load_notices
from app.db import models as db
from app.demo import DEMO_ORG_ID
from app.demo.anomalies import ANOMALIES
from app.demo.gemini_content import (
    INSTRUCTIONS,
    DemoBriefings,
    check_instructions,
    ensure_demo_briefings,
    ensure_demo_notices,
)
from app.demo.scenario import WILDLIFE_INSTRUCTION
from app.gemini.briefings import next_workday
from app.schemas import DataState, GeneratedBy, HazardType, Observation
from app.schemas.hazards import RadiusSource
from tests.test_briefings import NO_GEMINI, gemini
from tests.test_demo_anomalies import anomalies as anomalies  # noqa: F401
from tests.test_demo_anomalies import factory as factory  # noqa: F401
from tests.test_demo_seed import NOW, OUTLOOKS

LATER = NOW + timedelta(minutes=1)
DEMO_SITES = [f"demo-{a.key}" for a in ANOMALIES] + ["demo-everglades"]


@pytest.fixture
def demo(anomalies):  # noqa: F811
    return anomalies[0]


def coverage(session) -> dict[str, set[str]]:
    return {
        site_id: {n.id for n in load_notices(session, session.get(db.Site, site_id))}
        for site_id in DEMO_SITES
    }


def test_written_instructions_pass_the_real_clearance_check() -> None:
    assert check_instructions() == []


def test_seeded_notices_get_a_gemini_radius_and_a_sent_instruction(demo) -> None:
    with demo() as session:
        before = coverage(session)
        radii = {n.id: n.radius_miles for n in session.scalars(select(db.HazardNotice))}
        assert ensure_demo_notices(session, LATER) > 0
        assert coverage(session) == before  # nobody gains or loses a notice
        seeded = session.scalars(
            select(db.HazardNotice).where(db.HazardNotice.id.in_(list(INSTRUCTIONS)))
        ).all()
        assert seeded
        for notice in seeded:
            assert notice.radius_source == RadiusSource.GEMINI
            assert notice.radius_miles <= radii[notice.id]
            assert notice.radius_miles == round(notice.radius_miles, 1)  # reads cleanly
        rows = session.scalars(
            select(db.NoticeAssessment).where(db.NoticeAssessment.organization_id == DEMO_ORG_ID)
        ).all()
        assert rows
        for row in rows:
            assert row.instruction == row.suggested_instruction == INSTRUCTIONS[row.notice_id]
            assert row.confirmed_at <= row.instruction_sent_at <= LATER.replace(tzinfo=None)
        wildlife = session.get(db.HazardNotice, "demo-notice-wildlife")
        assert wildlife.instruction == WILDLIFE_INSTRUCTION
        assert ensure_demo_notices(session, LATER) == 0  # filled once


def test_a_supervisors_own_instruction_is_kept(demo) -> None:
    with demo() as session:
        row = session.scalars(
            select(db.NoticeAssessment).where(db.NoticeAssessment.organization_id == DEMO_ORG_ID)
        ).first()
        row.instruction, row.instruction_sent_at = "Tester's own words.", LATER
        session.commit()
        ensure_demo_notices(session, LATER)
        session.refresh(row)
        assert row.instruction == "Tester's own words."
        assert row.suggested_instruction == INSTRUCTIONS[row.notice_id]


def forecasts(site: db.Site, now) -> list[Observation]:
    """A hot afternoon with a chance of rain in each demo site's next workday."""
    _, start, _ = next_workday(now, ZoneInfo(site.timezone))
    return [
        Observation(
            id=f"fc:{site.id}:{label}", site_id=site.id, source="NWS",
            hazard_type=HazardType.FORECAST, value=value, unit=unit, label=label,
            lat=site.lat, lon=site.lon, observed_at=now, valid_at=start + timedelta(hours=7),
            data_state=DataState.FORECAST,
        )
        for label, value, unit in (
            ("Heat index", 113.0, "°F"),
            ("Precipitation probability", 60.0, "%"),
        )
    ]  # fmt: skip


def test_demo_briefings_look_ahead_even_when_gemini_fails(demo) -> None:
    sources = DemoBriefings(NO_GEMINI, forecasts, OUTLOOKS)
    with demo() as session:
        session.execute(delete(db.Briefing))
        session.commit()
        written = ensure_demo_briefings(session, LATER, sources)
        assert len(written) == len(DEMO_SITES)
        for row in session.scalars(select(db.Briefing)):
            assert row.generated_by == GeneratedBy.GEMINI
            assert row.summary.startswith("For ")
            assert "heat index up to 113°F" in row.summary
            supplied = {e["id"] for e in row.evidence}
            cited = {
                i for item in row.hazards + row.recommended_actions for i in item["evidence_ids"]
            }
            assert cited <= supplied
            assert row.recommended_actions[0]["action"].startswith("Schedule heavy work")
            assert row.hazards[0]["hazard"].startswith("Forecast")
        # Nothing to do until a briefing is missing in the 6 PM window or falls back.
        assert ensure_demo_briefings(session, LATER, sources) == []
        heat = session.scalars(select(db.Briefing).where(db.Briefing.site_id == "demo-heat")).one()
        heat.generated_by = GeneratedBy.FALLBACK
        session.commit()
        assert ensure_demo_briefings(session, LATER, sources) == [heat.id]


def test_demo_briefings_use_gemini_when_it_answers(demo) -> None:
    reply = {
        "summary": "Tomorrow afternoon the heat index peaks; plan heavy work early.",
        "hazards": [
            {"hazard": "Heat index near 113°F", "evidence_ids": ["fc:demo-heat:Heat index"]}
        ],
        "recommended_actions": [],
        "unknowns": [],
    }
    with demo() as session:
        session.execute(delete(db.Briefing))
        session.commit()
        ensure_demo_briefings(session, LATER, DemoBriefings(gemini(reply), forecasts, OUTLOOKS))
        heat = session.scalars(select(db.Briefing).where(db.Briefing.site_id == "demo-heat")).one()
        assert heat.summary == reply["summary"]
