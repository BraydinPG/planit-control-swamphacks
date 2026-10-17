"""T057, T058, T058A: next-day briefings, the template fallback, the 6 PM schedule, routes.

Gemini and the NWS forecast are fakes; the database is in-memory SQLite.
"""

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db import models as db
from app.gemini.briefing_schedule import is_due, run_due_briefings, site_timezone
from app.gemini.briefings import briefing_id, generate_site_briefing, next_workday
from app.gemini.client import GeminiClient
from app.main import app
from app.schemas import DataState, GeneratedBy, HazardType, Observation
from tests import auth_fakes
from tests.auth_fakes import crew, supervisor

NEW_YORK = ZoneInfo("America/New_York")
LOS_ANGELES = ZoneInfo("America/Los_Angeles")
# 18:30 in New York (EDT), 15:30 in Los Angeles (PDT).
EVENING_EAST = datetime(2026, 10, 17, 22, 30, tzinfo=UTC)
WORKDAY_START = datetime(2026, 10, 18, 11, 0, tzinfo=UTC)  # 07:00 EDT


def site(site_id: str, region: str, tz: str | None) -> db.Site:
    return db.Site(
        id=site_id, name=f"{site_id} plant", lat=40.0, lon=-75.0, location_type="power_plant",
        source="EIA-860M test", region=region, timezone=tz,
    )  # fmt: skip


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
                db.Organization(id="org-2", name="West Utility"),
                db.Organization(id="org-3", name="Crew-only Utility"),
                site("site-ny", "NY", "America/New_York"),
                site("site-la", "CA", "America/Los_Angeles"),
                site("site-empty", "NY", "America/New_York"),  # no team: never briefed
                site("site-alone", "NY", "America/New_York"),  # org has no supervisor
            ]
        )
        session.flush()
        session.add_all(
            [
                db.Team(id="team-ny", organization_id="org-1", name="NY crew", site_id="site-ny"),
                db.Team(id="team-la", organization_id="org-2", name="LA crew", site_id="site-la"),
                db.Team(id="team-3", organization_id="org-3", name="Solo", site_id="site-alone"),
            ]
        )
        session.flush()
        session.add_all(
            [
                db.Membership(
                    id="m1", user_id="auth0|crew-ny", organization_id="org-1",
                    team_id="team-ny", role="crew",
                ),
                db.Membership(
                    id="m2", user_id="auth0|sup-east", organization_id="org-1", role="supervisor"
                ),
                db.Membership(
                    id="m3", user_id="auth0|sup-west", organization_id="org-2", role="supervisor"
                ),
            ]
        )  # fmt: skip
        session.commit()
    yield make
    engine.dispose()


def forecast(label: str, value: float, valid_at: datetime, unit: str = "°F") -> Observation:
    return Observation(
        id=f"nws-fc:site-ny:{label}:{valid_at.isoformat()}",
        site_id="site-ny",
        source="NWS",
        hazard_type=HazardType.FORECAST,
        value=value,
        unit=unit,
        label=label,
        lat=40.0,
        lon=-75.0,
        observed_at=EVENING_EAST - timedelta(hours=1),
        valid_at=valid_at,
        data_state=DataState.FORECAST,
    )


FORECASTS = [
    forecast("Temperature", 88, WORKDAY_START + timedelta(hours=3)),
    forecast("Temperature", 97, WORKDAY_START + timedelta(hours=8)),  # the peak
    forecast("Temperature", 120, WORKDAY_START - timedelta(hours=2)),  # before the workday
    forecast("Precipitation probability", 60, WORKDAY_START + timedelta(hours=7), "%"),
]


def forecasts(site: db.Site, now: datetime) -> list[Observation]:
    return FORECASTS if site.id == "site-ny" else []


def gemini(reply: object | Exception | None) -> GeminiClient:
    """A configured client whose transport returns `reply` (dict as JSON, or raises)."""

    def transport(prompt: str, schema: type) -> str:
        if isinstance(reply, Exception):
            raise reply
        return reply if isinstance(reply, str) else json.dumps(reply)

    return GeminiClient("test-key", "test-model", 5.0, transport=transport)


NO_GEMINI = GeminiClient(None, None, 5.0)
PEAK_ID = FORECASTS[1].id


def draft(**overrides) -> dict:
    value = {
        "summary": "Hot afternoon with a chance of storms after 14:00.",
        "hazards": [{"hazard": "Heat", "risk_level": "moderate", "evidence_ids": [PEAK_ID]}],
        "recommended_actions": [
            {"action": "Schedule heavy work before noon.", "evidence_ids": [PEAK_ID]}
        ],
        "unknowns": ["Lightning data for tomorrow is not forecast."],
    }
    value.update(overrides)
    return value


def generate(factory, client: GeminiClient, now: datetime = EVENING_EAST):
    with factory() as session:
        return generate_site_briefing(
            session, session.get(db.Site, "site-ny"), NEW_YORK, now, client, forecasts
        )


# ---- T057: Gemini briefing ----


def test_gemini_briefing_cites_supplied_evidence(factory) -> None:
    briefing = generate(factory, gemini(draft()))
    assert briefing.generated_by == GeneratedBy.GEMINI
    supplied = {e.id for e in briefing.evidence}
    for item in [*briefing.hazards, *briefing.recommended_actions]:
        assert set(item.evidence_ids) <= supplied
    assert briefing.id == "briefing:site-ny:2026-10-18"
    assert briefing.forecast_window_start == WORKDAY_START
    assert briefing.forecast_window_end == WORKDAY_START + timedelta(hours=12)
    assert "Lightning data for tomorrow is not forecast." in briefing.unknowns


def test_risk_level_comes_from_the_computed_score_not_gemini(factory) -> None:
    briefing = generate(factory, gemini(draft()))
    with factory() as session:
        score = session.scalars(
            select(db.HazardScore).where(db.HazardScore.site_id == "site-ny")
        ).one()
    assert briefing.risk_level == score.risk_level
    score_evidence = next(e for e in briefing.evidence if e.id == "score:site-ny")
    assert score_evidence.label.endswith(f"data completeness {score.data_completeness:.0%}")


def test_forecast_evidence_is_the_workday_peak(factory) -> None:
    briefing = generate(factory, gemini(draft()))
    forecast_labels = [e.label for e in briefing.evidence if e.kind == "observation"]
    assert forecast_labels == [
        "Forecast precipitation probability up to 60% at 14:00 local (NWS)",
        "Forecast temperature up to 97°F at 15:00 local (NWS)",
    ]


@pytest.mark.parametrize(
    "reply",
    [
        draft(recommended_actions=[{"action": "Carry on.", "evidence_ids": ["made-up-id"]}]),
        draft(summary="Conditions look fine; it is safe to work all day."),
        draft(summary="The lightning alert is cleared, so work can resume."),
        "not json at all",
        TimeoutError("Gemini timed out"),
    ],
    ids=["unknown-evidence", "declares-safe", "clears-alert", "invalid-json", "timeout"],
)
def test_bad_or_failed_gemini_output_falls_back_to_the_template(factory, reply) -> None:
    briefing = generate(factory, gemini(reply))
    assert briefing.generated_by == GeneratedBy.FALLBACK
    assert "safe to work" not in briefing.summary


# ---- T058: template fallback ----


def test_briefing_remains_available_without_gemini(factory) -> None:
    briefing = generate(factory, NO_GEMINI)
    assert briefing.generated_by == GeneratedBy.FALLBACK
    assert briefing.summary.startswith("Template briefing for site-ny plant")
    supplied = {e.id for e in briefing.evidence}
    for item in [*briefing.hazards, *briefing.recommended_actions]:
        assert item.evidence_ids and set(item.evidence_ids) <= supplied
    assert any(PEAK_ID in a.evidence_ids for a in briefing.recommended_actions)


def test_missing_forecast_and_unknown_factors_are_listed_as_unknowns(factory) -> None:
    with factory() as session:
        briefing = generate_site_briefing(
            session, session.get(db.Site, "site-ny"), NEW_YORK, EVENING_EAST, NO_GEMINI,
            lambda s, n: [],
        )  # fmt: skip
    assert "NWS forecast for the workday is unavailable." in briefing.unknowns
    assert any(u.endswith(": unavailable") or u.endswith(": stale") for u in briefing.unknowns)


def test_generation_is_idempotent_per_workday(factory) -> None:
    first = generate(factory, NO_GEMINI)
    second = generate(factory, gemini(draft()), EVENING_EAST + timedelta(hours=2))
    assert second.id == first.id and second.generated_by == GeneratedBy.FALLBACK
    with factory() as session:
        assert len(session.scalars(select(db.Briefing)).all()) == 1


# ---- T058A: 6 PM site-local schedule ----


def run(factory, now: datetime, lookup=None) -> list[str]:
    with factory() as session:
        return [b.id for b in run_due_briefings(session, now, NO_GEMINI, forecasts, lookup)]


def test_site_past_6pm_gets_exactly_one_briefing_and_before_6pm_none(factory) -> None:
    before = EVENING_EAST - timedelta(hours=1)  # 17:30 in New York
    assert run(factory, before) == []
    assert run(factory, EVENING_EAST) == ["briefing:site-ny:2026-10-18"]
    assert run(factory, EVENING_EAST + timedelta(hours=1)) == []  # 19:30, same evening


def test_each_site_uses_its_own_time_zone(factory) -> None:
    assert run(factory, EVENING_EAST) == ["briefing:site-ny:2026-10-18"]  # LA is 15:30
    la_evening = datetime(2026, 10, 18, 1, 15, tzinfo=UTC)  # 18:15 PDT, 21:15 EDT
    assert run(factory, la_evening) == ["briefing:site-la:2026-10-18"]


def test_next_day_gets_a_new_briefing(factory) -> None:
    run(factory, EVENING_EAST)
    assert run(factory, EVENING_EAST + timedelta(days=1)) == ["briefing:site-ny:2026-10-19"]


def test_sites_without_a_team_are_never_briefed(factory) -> None:
    run(factory, EVENING_EAST)
    with factory() as session:
        assert session.get(db.Briefing, briefing_id("site-empty", next_workday(
            EVENING_EAST, NEW_YORK)[0])) is None  # fmt: skip


def test_organizations_without_a_supervisor_get_no_briefings(factory) -> None:
    with factory() as session:
        session.add(
            db.Membership(
                id="m4", user_id="auth0|crew-3", organization_id="org-3",
                team_id="team-3", role="crew",
            )
        )  # fmt: skip
        session.commit()
    assert run(factory, EVENING_EAST) == ["briefing:site-ny:2026-10-18"]  # not site-alone
    with factory() as session:
        session.add(
            db.Membership(
                id="m5", user_id="auth0|sup-3", organization_id="org-3", role="supervisor"
            )
        )
        session.commit()
    assert run(factory, EVENING_EAST) == ["briefing:site-alone:2026-10-18"]


def test_is_due_from_6pm_until_midnight() -> None:
    def at(hour: int, minute: int = 0) -> datetime:
        return datetime(2026, 10, 17, hour, minute, tzinfo=NEW_YORK)

    assert not is_due(at(17, 59), NEW_YORK)
    assert is_due(at(18), NEW_YORK)
    assert is_due(at(23, 59), NEW_YORK)
    assert not is_due(at(0, 5), NEW_YORK)


def test_time_zone_comes_from_nws_and_is_saved(factory) -> None:
    with factory() as session:
        place = session.get(db.Site, "site-empty")
        place.timezone = None
        assert site_timezone(session, place, lambda s: {"timeZone": "America/Chicago"}) == (
            ZoneInfo("America/Chicago")
        )
        assert session.get(db.Site, "site-empty").timezone == "America/Chicago"


def test_failed_nws_lookup_uses_the_state_zone_without_saving_it(factory) -> None:
    def down(_site):
        raise OSError("NWS unavailable")

    with factory() as session:
        place = session.get(db.Site, "site-empty")
        place.timezone = None
        assert site_timezone(session, place, down) == NEW_YORK
        assert place.timezone is None


# ---- routes ----


@pytest.fixture
def client(factory) -> Iterator[TestClient]:
    run(factory, EVENING_EAST)  # site-ny
    run(factory, datetime(2026, 10, 18, 1, 15, tzinfo=UTC))  # site-la

    def override() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override
    auth_fakes.install(app)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_crew_reads_their_organizations_briefings_only(client: TestClient) -> None:
    me = crew("auth0|crew-ny")
    assert client.get("/api/sites/site-ny/briefing", headers=me).json()["site_id"] == "site-ny"
    assert client.get("/api/sites/site-la/briefing", headers=me).status_code == 403
    assert [b["site_id"] for b in client.get("/api/briefings", headers=me).json()] == ["site-ny"]


def test_without_read_org_briefings_crew_reads_only_their_site(client: TestClient) -> None:
    from app.security import roles

    limited = auth_fakes.bearer(
        auth_fakes.token(["crew"], [roles.READ_ASSIGNED_SITES], sub="auth0|crew-ny")
    )
    assert client.get("/api/sites/site-ny/briefing", headers=limited).status_code == 200
    assert client.get("/api/briefings", headers=limited).status_code == 403


def test_supervisor_reads_their_organizations_briefings_only(client: TestClient) -> None:
    east = supervisor("auth0|sup-east")
    assert [b["site_id"] for b in client.get("/api/briefings", headers=east).json()] == ["site-ny"]
    assert client.get("/api/sites/site-ny/briefing", headers=east).status_code == 200
    assert client.get("/api/sites/site-la/briefing", headers=east).status_code == 403
    west = supervisor("auth0|sup-west")
    assert [b["site_id"] for b in client.get("/api/briefings", headers=west).json()] == ["site-la"]


def test_briefings_require_sign_in(client: TestClient) -> None:
    assert client.get("/api/briefings").status_code == 401
    assert client.get("/api/sites/site-ny/briefing").status_code == 401


def test_site_without_a_briefing_is_404(client: TestClient, factory) -> None:
    with factory() as session:
        session.add(db.Team(id="team-x", organization_id="org-1", name="X", site_id="site-empty"))
        session.commit()
    response = client.get("/api/sites/site-empty/briefing", headers=supervisor("auth0|sup-east"))
    assert response.status_code == 404
    assert "6 PM" in response.json()["detail"]


def test_there_is_no_manual_generation_route(client: TestClient) -> None:
    east = supervisor("auth0|sup-east")
    for path in ("/api/sites/site-ny/briefings", "/api/sites/site-ny/briefing", "/api/briefings"):
        assert client.post(path, headers=east).status_code in (404, 405)
