"""Site species context: IPaC parsing, regional matching, outages, Gemini grounding,
the `GET /api/sites/{id}/species` route, and proof that it never changes scores or alerts.

IPaC and critical habitat responses are recorded fixtures served through
`httpx.MockTransport`; no test touches the network.
"""

import json
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db, get_now
from app.db import models as db
from app.gemini import GeminiClient
from app.gemini.species import SpeciesFacts, word_species
from app.main import app
from app.schemas import DataState, GeneratedBy, MatchBasis, SiteSpeciesContext
from app.species import crithab, ipac
from app.species.geometry import clip_to_box, square
from app.species.service import (
    COVERAGE_UNKNOWN,
    SpeciesContextService,
    _facts,
    get_species_service,
)
from app.species.settings import SpeciesSettings
from tests import auth_fakes
from tests.auth_fakes import crew, supervisor

FIXTURES = Path(__file__).resolve().parents[1] / "app" / "species" / "fixtures"
IPAC_JSON = json.loads((FIXTURES / "ipac_everglades.json").read_text(encoding="utf-8"))
CRITHAB_JSON = json.loads((FIXTURES / "crithab_everglades_proposed.geojson").read_text())
EMPTY_LAYER = {"type": "FeatureCollection", "features": []}
NOW = datetime(2026, 10, 17, 18, 0, tzinfo=UTC)
SITE = SimpleNamespace(id="site-a", lat=25.76, lon=-80.49)
SETTINGS = SpeciesSettings(_env_file=None)

ALLIGATOR = "ipac:Population$Sid[8396]"
INDIGO = "ipac:Population$Sid[173]"
MANATEE = "ipac:Population$Sid[7]"


# ---- fakes ----


def handler(
    ipac_response: Callable[[], httpx.Response] | None = None,
    crithab_response: Callable[[], httpx.Response] | None = None,
    calls: list[str] | None = None,
) -> httpx.MockTransport:
    def respond(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request.url.path)
        if request.url.path.endswith("/resources"):
            return ipac_response() if ipac_response else httpx.Response(200, json=IPAC_JSON)
        if crithab_response:
            return crithab_response()
        layer = request.url.path.split("/")[-2]
        return httpx.Response(200, json=CRITHAB_JSON if layer == "2" else EMPTY_LAYER)

    return httpx.MockTransport(respond)


def service(
    transport: httpx.MockTransport | None = None,
    wording: Callable[[list[SpeciesFacts]], dict[str, str] | None] = lambda facts: None,
) -> SpeciesContextService:
    transport = transport or handler()
    return SpeciesContextService(
        SETTINGS,
        ipac.IpacClient(SETTINGS.ipac_resources_url, 5, transport),
        crithab.CritHabClient(SETTINGS.crithab_service_url, 5, transport),
        wording,
    )


def by_id(context: SiteSpeciesContext) -> dict:
    return {s.id: s for s in context.species}


def fail(status: int = 503) -> Callable[[], httpx.Response]:
    return lambda: httpx.Response(status, text="down")


def timeout() -> httpx.Response:
    raise httpx.ReadTimeout("slow")


# ---- IPaC parsing and regional matching ----


def test_recorded_ipac_response_parses_every_population() -> None:
    result = ipac.parse_resources(IPAC_JSON)
    assert len(result.populations) == 27
    assert result.api_version == "1.2.0"
    assert result.location_description == "Miami-Dade County, Florida"
    assert result.offices[0].name == "Florida Ecological Services Field Office"
    gator = next(p for p in result.populations if p.common_name == "American alligator")
    assert gator.status == "Similarity of Appearance (Threatened)"
    assert gator.status_code == "SAT"


def test_every_ipac_species_is_regional_range_never_a_sighting() -> None:
    context = service().context(SITE, NOW)
    assert context.data_state == DataState.OBSERVED
    assert {s.match_basis for s in context.species} == {MatchBasis.REGIONAL_RANGE}
    assert all("not a sighting" in s.match_note.lower() for s in context.species)
    assert all("not a sighting" in s.summary.lower() for s in context.species)
    assert "not a sighting" in context.caveat.lower()


def test_conditional_population_is_possible_context() -> None:
    payload = json.loads(json.dumps(IPAC_JSON))
    payload["resources"]["populationsBySid"]["Population$Sid[8396]"]["conditional"] = True
    context = service(handler(lambda: httpx.Response(200, json=payload))).context(SITE, NOW)
    assert by_id(context)[ALLIGATOR].match_basis == MatchBasis.POSSIBLE_REGIONAL_CONTEXT


def test_water_moccasin_is_not_invented_and_coverage_gap_is_stated() -> None:
    context = service().context(SITE, NOW)
    names = {(s.common_name or "").lower() for s in context.species}
    assert not any("moccasin" in n or "cottonmouth" in n for n in names)
    assert COVERAGE_UNKNOWN in context.unknowns


# ---- protection and encounter are independent ----


def test_protected_without_encounter_guidance_stays_unknown() -> None:
    manatee = by_id(service().context(SITE, NOW))[MANATEE]
    assert manatee.protection.status == "Threatened"
    assert manatee.protection.critical_habitat_here is True
    assert manatee.encounter is None  # not reviewed, which is not "harmless"


def test_protected_with_no_sourced_hazard_keeps_hazard_null() -> None:
    indigo = by_id(service().context(SITE, NOW))[INDIGO]
    assert indigo.protection.status == "Threatened"
    assert indigo.encounter is not None
    assert indigo.encounter.hazard is None
    assert indigo.encounter.review_status == "pending_review"


def test_missing_status_does_not_remove_encounter_guidance() -> None:
    payload = json.loads(json.dumps(IPAC_JSON))
    population = payload["resources"]["populationsBySid"]["Population$Sid[8396]"]["population"]
    del population["listingStatusName"]
    del population["listingStatusCode"]
    gator = by_id(service(handler(lambda: httpx.Response(200, json=payload))).context(SITE, NOW))[
        ALLIGATOR
    ]
    assert gator.protection.status is None
    assert "not supplied" in gator.summary
    assert gator.encounter is not None and gator.encounter.actions


def test_entries_cite_their_sources() -> None:
    context = service().context(SITE, NOW)
    for entry in context.species:
        assert entry.protection.evidence_id in entry.evidence_ids
        assert entry.protection.source == "USFWS IPaC Location API 1.2.0"
        assert entry.protection.as_of == NOW
        if entry.encounter:
            assert entry.encounter.evidence_id in entry.evidence_ids
            assert entry.encounter.source_url.startswith("https://")


def test_species_with_guidance_are_listed_first() -> None:
    species = service().context(SITE, NOW).species
    with_guidance = [s.encounter is not None for s in species]
    assert with_guidance == sorted(with_guidance, reverse=True)


# ---- failures: never "no species" ----


@pytest.mark.parametrize(
    "response",
    [fail(503), fail(429), fail(404), timeout, lambda: httpx.Response(200, text="<html>")],
    ids=["503", "rate-limit", "404", "timeout", "malformed"],
)
def test_ipac_failure_is_unavailable_not_empty(response) -> None:
    context = service(handler(response)).context(SITE, NOW)
    assert context.data_state == DataState.UNAVAILABLE
    assert context.species == []
    assert context.fetched_at is None
    assert any("does not mean nothing is there" in u for u in context.unknowns)


def test_missing_species_map_is_unavailable() -> None:
    bad = lambda: httpx.Response(200, json={"resources": {"apiVersion": "1.2.0"}})  # noqa: E731
    assert service(handler(bad)).context(SITE, NOW).data_state == DataState.UNAVAILABLE


def test_failed_refresh_shows_stale_data_with_its_age() -> None:
    down = {"ipac": False}
    transport = handler(lambda: fail()() if down["ipac"] else httpx.Response(200, json=IPAC_JSON))
    svc = service(transport)
    assert svc.context(SITE, NOW).data_state == DataState.OBSERVED
    down["ipac"] = True
    later = NOW + SETTINGS.cache_for + timedelta(minutes=1)
    context = svc.context(SITE, later)
    assert context.data_state == DataState.STALE
    assert len(context.species) == 27
    assert context.fetched_at == NOW
    assert any("could not be refreshed" in u for u in context.unknowns)


def test_stale_data_expires_to_unavailable() -> None:
    down = {"ipac": False}
    svc = service(
        handler(lambda: fail()() if down["ipac"] else httpx.Response(200, json=IPAC_JSON))
    )
    svc.context(SITE, NOW)
    down["ipac"] = True
    context = svc.context(SITE, NOW + SETTINGS.unavailable_after + timedelta(minutes=1))
    assert context.data_state == DataState.UNAVAILABLE
    assert context.species == []


def test_cache_avoids_repeat_lookups_and_backs_off_after_failure() -> None:
    calls: list[str] = []
    svc = service(handler(calls=calls))
    svc.context(SITE, NOW)
    svc.context(SITE, NOW + timedelta(hours=1))
    assert sum(c.endswith("/resources") for c in calls) == 1

    calls.clear()
    failing = service(handler(fail(), calls=calls))
    failing.context(SITE, NOW)
    failing.context(SITE, NOW + timedelta(minutes=1))
    assert sum(c.endswith("/resources") for c in calls) == 1


def test_critical_habitat_outage_is_independent_of_species() -> None:
    context = service(handler(crithab_response=fail())).context(SITE, NOW)
    assert context.data_state == DataState.OBSERVED
    assert len(context.species) == 27
    assert context.critical_habitat_state == DataState.UNAVAILABLE
    assert context.critical_habitat == []


def test_arcgis_error_body_is_a_failure() -> None:
    error = lambda: httpx.Response(200, json={"error": {"code": 400}})  # noqa: E731
    context = service(handler(crithab_response=error)).context(SITE, NOW)
    assert context.critical_habitat_state == DataState.UNAVAILABLE


# ---- critical habitat boundaries ----


def test_critical_habitat_keeps_source_status_and_date() -> None:
    (area,) = service().context(SITE, NOW).critical_habitat
    assert area.common_name == "West Indian Manatee"
    assert area.status == "Proposed"
    assert area.federal_register == "89FR78134 78198"
    assert str(area.published) == "2024-09-24"
    assert area.geometry["type"] == "MultiPolygon"
    assert area.source_url.endswith("/FeatureServer/2")


def test_boundary_outside_window_is_kept_without_geometry() -> None:
    far = json.loads(json.dumps(CRITHAB_JSON))
    far["features"][0]["geometry"] = {
        "type": "Polygon",
        "coordinates": [[[-70, 40], [-69, 40], [-69, 41], [-70, 40]]],
    }
    area = crithab.parse_features(far, 2, square(25.76, -80.49, 3), "https://x")[0]
    assert area.geometry is None
    assert "not drawn" in area.geometry_note


def test_clip_keeps_only_the_part_inside_the_box() -> None:
    box = (0.0, 0.0, 1.0, 1.0)
    clipped = clip_to_box(
        {"type": "Polygon", "coordinates": [[[-1, -1], [2, -1], [2, 0.5], [-1, 0.5], [-1, -1]]]},
        box,
    )
    ring = clipped["coordinates"][0][0]
    assert ring[0] == ring[-1]
    assert all(0 <= x <= 1 and 0 <= y <= 0.5 for x, y in ring)
    assert clip_to_box({"type": "Point", "coordinates": [0, 0]}, box) is None
    assert clip_to_box(None, box) is None


# ---- Gemini wording: grounded or template ----


def gemini(answer: dict | Exception) -> GeminiClient:
    def transport(prompt: str, schema: type[BaseModel]) -> str:
        if isinstance(answer, Exception):
            raise answer
        return json.dumps(answer)

    return GeminiClient("test-key", "test-model", 5.0, transport)


def facts() -> list[SpeciesFacts]:
    return [_facts(e) for e in service().context(SITE, NOW).species]


def line(species_id: str, summary: str, evidence: list[str] | None = None) -> dict:
    return {"species_id": species_id, "summary": summary, "evidence": evidence or [species_id]}


def word(*lines: dict) -> dict[str, str] | None:
    return word_species(facts(), client=gemini({"species": list(lines), "unknowns": []}))


def test_grounded_line_is_accepted() -> None:
    text = (
        "American alligator, federal status Similarity of Appearance (Threatened). "
        "Keep your distance and never feed it."
    )
    assert word(line(ALLIGATOR, text, [ALLIGATOR, "guidance:american-alligator"])) == {
        ALLIGATOR: text
    }


@pytest.mark.parametrize(
    ("species_id", "summary", "evidence"),
    [
        (ALLIGATOR, "American alligator is Endangered.", None),  # status changed
        (ALLIGATOR, "Similarity of Appearance (Threatened). Safe to approach.", None),
        (ALLIGATOR, "Similarity of Appearance (Threatened). Was seen at the site.", None),
        (ALLIGATOR, "Similarity of Appearance (Threatened). Call 555-0100.", None),
        (ALLIGATOR, "Similarity of Appearance (Threatened).", ["ipac:other"]),
        (MANATEE, "Threatened manatee. Keep away from the water.", None),  # advice not supplied
        (MANATEE, "Threatened manatee, which is harmless.", None),
        ("ipac:invented", "Water moccasin, venomous.", None),
    ],
    ids=["status", "safe", "sighting", "number", "evidence", "advice", "harmless", "invented"],
)
def test_ungrounded_lines_are_rejected(species_id: str, summary: str, evidence) -> None:
    assert word(line(species_id, summary, evidence)) is None


@pytest.mark.parametrize(
    "answer", [TimeoutError("slow"), RuntimeError("boom"), {"species": "nope"}]
)
def test_gemini_failure_uses_the_template(answer) -> None:
    assert word_species(facts(), client=gemini(answer)) is None


def test_unconfigured_gemini_uses_the_template() -> None:
    context = service(wording=word_species).context(SITE, NOW)
    assert context.generated_by == GeneratedBy.FALLBACK
    assert {s.summary_by for s in context.species} == {GeneratedBy.FALLBACK}


def test_accepted_wording_replaces_only_its_species() -> None:
    text = "Threatened West Indian Manatee, listed here by range."
    context = service(wording=lambda f: {MANATEE: text}).context(SITE, NOW)
    species = by_id(context)
    assert species[MANATEE].summary == text
    assert species[MANATEE].summary_by == GeneratedBy.GEMINI
    assert species[ALLIGATOR].summary_by == GeneratedBy.FALLBACK
    assert context.generated_by == GeneratedBy.GEMINI


def test_prompt_carries_status_and_no_presence_rule() -> None:
    seen: list[str] = []

    def transport(prompt: str, schema: type[BaseModel]) -> str:
        seen.append(prompt)
        return json.dumps({"species": [], "unknowns": []})

    word_species(facts(), client=GeminiClient("k", "m", 5.0, transport))
    assert "Similarity of Appearance (Threatened)" in seen[0]
    assert "Never say it was seen" in seen[0]


def test_crew_reports_never_reach_gemini(client: TestClient) -> None:
    seen: list[list[SpeciesFacts]] = []
    svc = service(wording=lambda f: seen.append(f) or None)
    app.dependency_overrides[get_species_service] = lambda: svc
    assert client.get("/api/sites/site-a/species").status_code == 200
    supplied = json.dumps([f.__dict__ for f in seen[0]], default=list)
    assert "culvert" not in supplied and "report-" not in supplied


# ---- route, access, and crew reports ----


def seed(session: Session) -> None:
    session.add(db.Organization(id="org-1", name="Sunbelt Utility"))
    source = "test site"
    session.add_all(
        [
            db.Site(
                id="site-a",
                name="Alpha",
                lat=25.76,
                lon=-80.49,
                location_type="power_plant",
                source=source,
            ),
            db.Site(
                id="site-b",
                name="Bravo",
                lat=26.1,
                lon=-81.2,
                location_type="power_plant",
                source=source,
            ),
            db.Site(
                id="site-c",
                name="Charlie",
                lat=27.9,
                lon=-82.4,
                location_type="power_plant",
                source=source,
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            db.Team(id="team-a", organization_id="org-1", name="Line Crew A", site_id="site-a"),
            db.Team(id="team-b", organization_id="org-1", name="Crew B", site_id="site-b"),
        ]
    )
    session.flush()
    session.add_all(
        [
            db.Membership(
                id="m-crew",
                user_id="auth0|crew-a",
                organization_id="org-1",
                team_id="team-a",
                role="crew",
            ),
            db.Membership(
                id="m-sup", user_id="auth0|supervisor-1", organization_id="org-1", role="supervisor"
            ),
            db.HazardScore(
                id="score-a",
                site_id="site-a",
                risk_score=6.5,
                risk_level="high",
                factor_contributions=[],
                model_version="rules-0.2",
                model_is_fallback=False,
                confidence=0.7,
                data_completeness=0.8,
                created_at=NOW - timedelta(minutes=5),
            ),
            db.Alert(
                id="alert-a",
                site_id="site-a",
                rule="lightning_stop_work",
                state="active",
                triggered_at=NOW - timedelta(minutes=10),
                latest_event_at=NOW - timedelta(minutes=3),
                clear_after=NOW + timedelta(minutes=27),
                simulated=True,
            ),
            db.HazardNotice(
                id="notice-gator",
                hazard_label="wildlife",
                source="crew_report",
                source_ref="report-confirmed",
                lat=25.76,
                lon=-80.49,
                radius_miles=1,
                radius_source="default",
                status="confirmed",
                confirmed_by="auth0|supervisor-1",
                confirmed_at=NOW - timedelta(minutes=20),
                created_at=NOW - timedelta(minutes=30),
            ),
        ]
    )
    report = dict(
        organization_id="org-1",
        team_id="team-a",
        site_id="site-a",
        reporter_id="auth0|crew-a",
        lat=25.76,
        lon=-80.49,
    )
    session.add_all(
        [
            db.CrewReport(
                id="report-confirmed",
                category="wildlife",
                hazard_present=True,
                review_status="pending",
                notice_id="notice-gator",
                note="Alligator by the culvert",
                created_at=NOW - timedelta(minutes=30),
                **report,
            ),
            db.CrewReport(
                id="report-pending",
                category="wildlife",
                hazard_present=True,
                review_status="pending",
                created_at=NOW - timedelta(minutes=8),
                **report,
            ),
            db.CrewReport(
                id="report-rejected",
                category="wildlife",
                hazard_present=False,
                review_status="rejected",
                created_at=NOW - timedelta(hours=2),
                **report,
            ),
            db.CrewReport(
                id="report-pole",
                category="broken_pole_downed_line",
                hazard_present=True,
                review_status="pending",
                created_at=NOW - timedelta(minutes=4),
                **report,
            ),
        ]
    )
    session.commit()


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    db.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        seed(session)

    def override_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    svc = service()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_now] = lambda: NOW
    app.dependency_overrides[get_species_service] = lambda: svc
    auth_fakes.install(app)
    try:
        test_client = TestClient(app, headers=supervisor())
        test_client.factory = factory
        yield test_client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_route_returns_contract_for_team_site(client: TestClient) -> None:
    response = client.get("/api/sites/site-a/species")
    assert response.status_code == 200
    context = SiteSpeciesContext.model_validate(response.json())
    assert context.site_id == "site-a"
    assert len(context.species) == 27


def test_site_without_team_has_no_species_context(client: TestClient) -> None:
    response = client.get("/api/sites/site-c/species")
    assert response.status_code == 404
    assert response.json()["detail"]["reason"] == "no_team"


def test_unknown_site_is_404(client: TestClient) -> None:
    assert client.get("/api/sites/nope/species").status_code == 404


def test_crew_reads_only_their_team_site(client: TestClient) -> None:
    assert client.get("/api/sites/site-a/species", headers=crew()).status_code == 200
    assert client.get("/api/sites/site-b/species", headers=crew()).status_code == 403


def test_anonymous_request_is_rejected(client: TestClient) -> None:
    assert client.get("/api/sites/site-a/species", headers={"Authorization": ""}).status_code == 401


def test_crew_wildlife_reports_are_separate_with_review_state(client: TestClient) -> None:
    context = client.get("/api/sites/site-a/species").json()
    reports = {r["report_id"]: r for r in context["wildlife_reports"]}
    assert set(reports) == {"report-confirmed", "report-pending", "report-rejected"}
    assert reports["report-confirmed"]["confirmation"] == "confirmed"
    assert reports["report-confirmed"]["match_basis"] == "confirmed_report"
    assert reports["report-pending"]["confirmation"] == "pending"
    assert reports["report-pending"]["match_basis"] == "unknown"
    assert reports["report-rejected"]["confirmation"] == "rejected"
    # Background species context never claims a report.
    assert all(s["match_basis"] != "confirmed_report" for s in context["species"])


def counts(client: TestClient) -> dict[str, int]:
    with client.factory() as session:
        return {
            model.__tablename__: session.scalar(select(func.count()).select_from(model))
            for model in (
                db.HazardScore,
                db.Alert,
                db.Acknowledgement,
                db.CrewReport,
                db.HazardNotice,
                db.Observation,
            )
        }


def test_species_context_never_changes_score_alerts_or_reports(client: TestClient) -> None:
    before_rows = counts(client)
    before_detail = client.get("/api/sites/site-a").json()
    before_list = client.get("/api/sites").json()
    before_alerts = client.get("/api/alerts").json()

    assert client.get("/api/sites/site-a/species").status_code == 200
    assert client.get("/api/sites/site-a/species", headers=crew()).status_code == 200

    assert counts(client) == before_rows
    assert client.get("/api/sites/site-a").json() == before_detail
    assert client.get("/api/sites").json() == before_list
    assert client.get("/api/alerts").json() == before_alerts
    assert before_detail["risk_score"] == 6.5
    assert before_detail["alerts"][0]["state"] == "active"


def test_route_is_get_only(client: TestClient) -> None:
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)("/api/sites/site-a/species").status_code == 405


def test_recorded_demo_gemini_response_passes_the_grounding_check() -> None:
    recorded = json.loads((FIXTURES / "gemini_species_everglades.json").read_text("utf-8"))
    accepted = word_species(facts(), client=gemini(recorded["response"]))
    assert accepted is not None
    assert len(accepted) == len(recorded["response"]["species"])
