"""T058B: a confirmed hazard's expected duration in briefings and instruction suggestions."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import models as db
from app.gemini import GeminiClient, suggest_confirmed_instruction
from app.gemini.briefings import FORBIDDEN_PHRASES, generate_site_briefing
from app.gemini.outlooks import describe, notice_outlook
from app.outlook import EventOutlookService
from app.outlook.service import to_outlook
from app.schemas import EventOutlook, EvidenceKind, GeneratedBy

NEW_YORK = ZoneInfo("America/New_York")
EVENING = datetime(2026, 10, 17, 22, 30, tzinfo=UTC)  # 18:30 EDT
NOTICE_ID = "notice-flood"

# Shape of an ok result from Cache's adapter, as in test_event_outlook.py.
OK_RESULT = {
    "status": "ok",
    "event_id": NOTICE_ID,
    "event_type": "Flood",
    "as_of_utc": "2026-10-17T22:30:00Z",
    "generated_at_utc": "2026-10-17T22:30:01Z",
    "outcomes": {
        "recorded_event_ongoing_probability": {"6h": 0.71, "12h": 0.6, "24h": 0.47},
        "remaining_duration_hours": {"p10": 2.0, "median": 6.2, "p90": 14.0},
        "trend": "unknown",
    },
    "worker_context": {"limitations": ["Regional recorded events, not site conditions."]},
    "model_version": "noaa-flood-conditional-km-v2",
    "is_simulated": False,
}


def outlooks(result: dict | Exception = OK_RESULT) -> EventOutlookService:
    def predictor(site: dict, context: dict) -> dict:
        if isinstance(result, Exception):
            raise result
        return result

    return EventOutlookService(predictor)


def outlook(**outcomes) -> EventOutlook:
    result = json.loads(json.dumps(OK_RESULT))
    result["outcomes"]["remaining_duration_hours"].update(outcomes)
    return to_outlook(result)


@pytest.fixture
def factory() -> Iterator[sessionmaker]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    db.Base.metadata.create_all(engine)
    make = sessionmaker(bind=engine, expire_on_commit=False)
    with make() as session:
        session.add_all(
            [
                db.Organization(id="org-1", name="East Utility"),
                db.Site(
                    id="site-ny", name="NY plant", lat=40.0, lon=-75.0,
                    location_type="power_plant", source="test", region="NY",
                    timezone="America/New_York",
                ),
                db.Site(
                    id="site-far", name="Far plant", lat=40.1, lon=-75.0,
                    location_type="power_plant", source="test", region="NY",
                    timezone="America/New_York",
                ),
            ]
        )  # fmt: skip
        session.flush()
        session.add(db.Team(id="team-ny", organization_id="org-1", name="NY", site_id="site-ny"))
        session.add(
            db.Membership(id="m1", user_id="auth0|sup", organization_id="org-1", role="supervisor")
        )
        session.commit()
    yield make
    engine.dispose()


def add_notice(factory, status: str = "confirmed", label: str = "flooding") -> None:
    with factory() as session:
        session.add(
            db.HazardNotice(
                id=NOTICE_ID, hazard_label=label, source="crew_report", source_ref="report-1",
                lat=40.0, lon=-75.0, radius_miles=5.0, radius_source="default", status=status,
                created_at=EVENING - timedelta(hours=1), confirmed_by="auth0|sup",
                confirmed_at=EVENING - timedelta(minutes=30), evidence=[],
            )
        )  # fmt: skip
        session.commit()


def briefing(factory, service: EventOutlookService, client: GeminiClient | None = None):
    with factory() as session:
        return generate_site_briefing(
            session,
            session.get(db.Site, "site-ny"),
            NEW_YORK,
            EVENING,
            client or GeminiClient(None, None, 5.0),
            lambda site, now: [],
            service,
        )


# ---- the sentence ----


def test_estimate_reads_as_plain_words() -> None:
    sentence = describe(outlook())
    assert sentence.startswith("Confirmed flood: likely to continue for about 6 more hours")
    assert "(likely range 2 hours to 14 hours)" in sentence
    assert "Advisory estimate" in sentence


def test_short_estimates_never_read_as_zero() -> None:
    sentence = describe(outlook(p10=0.2, median=0.4, p90=3.0))
    assert "less than an hour more" in sentence
    assert "under 1 hour to 3 hours" in sentence
    assert "0 hours" not in sentence


def test_open_ended_range_is_left_out() -> None:
    assert "likely range" not in describe(outlook(p90=None))


def test_unavailable_or_missing_median_has_no_sentence() -> None:
    assert describe(outlook(median=None)) is None
    assert describe(to_outlook({**OK_RESULT, "status": "unavailable"})) is None


def test_sentence_never_reads_as_an_all_clear() -> None:
    text = describe(outlook()).lower()
    assert not any(phrase in text for phrase in FORBIDDEN_PHRASES)


# ---- briefings ----


def test_briefing_cites_the_expected_duration(factory) -> None:
    add_notice(factory)
    result = briefing(factory, outlooks())
    estimate = [e for e in result.evidence if e.kind == EvidenceKind.MODEL_OUTPUT]
    assert [e.id for e in estimate] == [f"outlook:{NOTICE_ID}"]
    assert "about 6 more hours" in estimate[0].label
    assert any(estimate[0].id in h.evidence_ids for h in result.hazards)  # template cites it


def test_gemini_briefing_may_cite_the_estimate(factory) -> None:
    add_notice(factory)
    draft = {
        "summary": "Flooding is expected to continue for about six more hours (estimate).",
        "hazards": [
            {"hazard": "Flooding", "risk_level": "low", "evidence_ids": [f"outlook:{NOTICE_ID}"]}
        ],
        "recommended_actions": [],
        "unknowns": [],
    }
    client = GeminiClient("k", "m", 5.0, transport=lambda p, s: json.dumps(draft))
    assert briefing(factory, outlooks(), client).generated_by == GeneratedBy.GEMINI


def test_unavailable_estimate_is_listed_as_unknown(factory) -> None:
    add_notice(factory)
    result = briefing(factory, outlooks(RuntimeError("model down")))
    assert not [e for e in result.evidence if e.kind == EvidenceKind.MODEL_OUTPUT]
    assert any(u.startswith("Expected duration of the confirmed flood") for u in result.unknowns)


@pytest.mark.parametrize(("status", "label"), [("potential", "flooding"), ("confirmed", "fire")])
def test_no_confirmed_flood_means_no_duration(factory, status: str, label: str) -> None:
    add_notice(factory, status, label)
    result = briefing(factory, outlooks())
    assert not [e for e in result.evidence if e.kind == EvidenceKind.MODEL_OUTPUT]
    assert not [u for u in result.unknowns if "Expected duration" in u]


def test_briefing_without_an_outlook_service_is_unchanged(factory) -> None:
    add_notice(factory)
    with factory() as session:
        result = generate_site_briefing(
            session, session.get(db.Site, "site-ny"), NEW_YORK, EVENING,
            GeminiClient(None, None, 5.0), lambda site, now: [],
        )  # fmt: skip
    assert not [e for e in result.evidence if e.kind == EvidenceKind.MODEL_OUTPUT]


# ---- instruction suggestions ----


def instruction_client(answer: dict, seen: list[str]) -> GeminiClient:
    def transport(prompt: str, schema: type[BaseModel]) -> str:
        seen.append(prompt)
        return json.dumps(answer)

    return GeminiClient("k", "m", 5.0, transport=transport)


def suggest(client: GeminiClient, estimate: EventOutlook | None):
    return suggest_confirmed_instruction(
        hazard_label="flooding",
        radius_miles=5.0,
        source="crew_report",
        evidence=[{"id": "report-1", "kind": "report", "label": "Crew report: flooding"}],
        client=client,
        outlook=estimate,
    )


def test_instruction_draft_may_cite_the_estimate() -> None:
    seen: list[str] = []
    answer = {
        "suggested_instruction": "Keep crews away from standing water; flooding is expected "
        "to continue for several more hours.",
        "evidence": ["report-1", f"outlook:{NOTICE_ID}"],
        "unknowns": [],
    }
    result = suggest(instruction_client(answer, seen), outlook())
    assert result.ok
    assert "about 6 more hours" in seen[0]


def test_instruction_cannot_cite_an_estimate_it_was_not_given() -> None:
    answer = {
        "suggested_instruction": "Keep crews away from standing water.",
        "evidence": [f"outlook:{NOTICE_ID}"],
        "unknowns": [],
    }
    assert not suggest(instruction_client(answer, []), None).ok


def test_notice_outlook_uses_the_nearest_covered_site(factory) -> None:
    add_notice(factory)
    seen: list[str] = []

    def predictor(site: dict, context: dict) -> dict:
        seen.append(site["id"])
        return OK_RESULT

    with factory() as session:
        notice = session.get(db.HazardNotice, NOTICE_ID)
        assert notice_outlook(session, notice, EVENING, EventOutlookService(predictor))
        notice.radius_miles = 0.001
        notice.lat = 0.0
        assert notice_outlook(session, notice, EVENING, EventOutlookService(predictor)) is None
    assert seen == ["site-ny"]
