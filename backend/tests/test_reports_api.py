"""T053: report creation and potential-hazard notices."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.gemini as gemini
from app.api.deps import get_db, get_now
from app.db import models as db
from app.main import app
from app.security import roles
from app.services.reports import miles_between, notice_recipients
from app.storage import LocalPhotoStore, get_photo_store
from tests import auth_fakes
from tests.auth_fakes import bearer, crew, supervisor, token

NOW = datetime(2026, 10, 17, 18, 0, tzinfo=UTC)
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
HOME = (25.7600, -80.4900)
NEAR = (25.7672, -80.4900)  # about 0.5 mi north
OTHER_ORG_NEAR = (25.7600, -80.4772)  # about 0.8 mi east
FAR = (26.1000, -81.2000)


def seed(session: Session) -> None:
    session.add_all(
        [db.Organization(id="org-1", name="Sunbelt"), db.Organization(id="org-2", name="Coastal")]
    )
    sites = {
        "site-a": HOME,
        "site-near": NEAR,
        "site-x": OTHER_ORG_NEAR,
        "site-b": FAR,
        "site-empty": HOME,
    }
    for site_id, (lat, lon) in sites.items():
        session.add(
            db.Site(
                id=site_id,
                name=site_id,
                lat=lat,
                lon=lon,
                location_type="power_plant",
                source="EIA-860M (representative)",
            )
        )
    session.flush()
    session.add_all(
        [
            db.Team(id="team-a", organization_id="org-1", name="Crew A", site_id="site-a"),
            db.Team(id="team-n", organization_id="org-1", name="Crew N", site_id="site-near"),
            db.Team(id="team-x", organization_id="org-2", name="Crew X", site_id="site-x"),
            db.Team(id="team-b", organization_id="org-1", name="Crew B", site_id="site-b"),
        ]
    )
    session.flush()
    session.add_all(
        [
            db.Membership(
                id="m-a",
                user_id="auth0|crew-a",
                organization_id="org-1",
                team_id="team-a",
                role="crew",
            ),
            db.Membership(
                id="m-b",
                user_id="auth0|crew-b",
                organization_id="org-1",
                team_id="team-b",
                role="crew",
            ),
            db.Membership(
                id="m-s1", user_id="auth0|supervisor-1", organization_id="org-1", role="supervisor"
            ),
            db.Membership(
                id="m-s2", user_id="auth0|supervisor-2", organization_id="org-2", role="supervisor"
            ),
        ]
    )
    session.commit()


class Harness:
    def __init__(self, photo_dir) -> None:
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        db.Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.photos = LocalPhotoStore(photo_dir)
        with self.factory() as session:
            seed(session)

    def override_db(self) -> Iterator[Session]:
        with self.factory() as session:
            yield session

    def rows(self, model):
        with self.factory() as session:
            return list(session.scalars(select(model)))


@pytest.fixture
def h(tmp_path) -> Iterator[Harness]:
    harness = Harness(tmp_path)
    app.dependency_overrides[get_db] = harness.override_db
    app.dependency_overrides[get_now] = lambda: NOW
    app.dependency_overrides[get_photo_store] = lambda: harness.photos
    # All report/confirmation tests are offline, even with local Gemini configuration.
    app.dependency_overrides[gemini.get_gemini_client] = lambda: gemini.GeminiClient(None, None, 1)
    auth_fakes.install(app)
    try:
        yield harness
    finally:
        app.dependency_overrides.clear()
        harness.engine.dispose()


@pytest.fixture
def client(h) -> TestClient:
    return TestClient(app)


def submit(client, headers=None, photo=JPEG, content_type="image/jpeg", **fields):
    form = {
        "site_id": "site-a",
        "category": "broken_pole_downed_line",
        "hazard_present": "true",
        "lat": str(HOME[0]),
        "lon": str(HOME[1]),
        **fields,
    }
    files = {"photo": ("pole.jpg", photo, content_type)} if photo is not None else None
    return client.post(
        "/api/reports", data=form, files=files, headers=headers or crew("auth0|crew-a")
    )


def test_fixture_distances() -> None:
    assert miles_between(*HOME, *NEAR) == pytest.approx(0.5, abs=0.05)
    assert miles_between(*HOME, *OTHER_ORG_NEAR) == pytest.approx(0.8, abs=0.05)
    assert miles_between(*HOME, *FAR) > 30


# ---- report persists ----


def test_present_report_persists_as_pending_with_photo(h, client) -> None:
    response = submit(client)
    assert response.status_code == 201
    report = response.json()
    assert report["review_status"] == "pending"
    assert (report["reporter_id"], report["team_id"], report["organization_id"]) == (
        "auth0|crew-a",
        "team-a",
        "org-1",
    )
    assert report["hazard_present"] is True
    assert report["note"] is None
    assert report["photo_url"].startswith("photos/") and report["photo_url"].endswith(".jpg")
    assert h.photos.load(report["photo_url"]) == JPEG
    assert report["created_at"].startswith("2026-10-17T18:00")
    [row] = h.rows(db.CrewReport)
    assert row.id == report["id"]


def test_report_appears_in_site_detail(h, client) -> None:
    report = submit(client, note="Pole leaning over the access road").json()
    detail = client.get("/api/sites/site-a", headers=supervisor()).json()
    [listed] = detail["reports"]
    assert listed["id"] == report["id"]
    assert listed["note"] == "Pole leaning over the access road"


# ---- potential notice ----


def test_present_report_creates_potential_notice_without_instruction(h, client) -> None:
    report = submit(client).json()
    [notice] = h.rows(db.HazardNotice)
    assert report["notice_id"] == notice.id
    assert notice.status == "potential"
    assert notice.hazard_label == "broken electrical pole or downed line"
    assert notice.instruction is None and notice.suggested_instruction is None
    assert notice.source == "crew_report" and notice.source_ref == report["id"]
    assert (notice.radius_miles, notice.radius_source) == (1.0, "default")


def test_recipients_inside_radius_are_notified_across_organizations(h, client) -> None:
    submit(client)
    [notice] = h.rows(db.HazardNotice)
    with h.factory() as session:
        recipients = notice_recipients(session, notice)
    assert recipients.team_ids == ["team-a", "team-n", "team-x"]
    assert recipients.supervisor_ids == ["auth0|supervisor-1", "auth0|supervisor-2"]

    def notice_ids(site_id: str, headers) -> list[str]:
        return [
            n["id"] for n in client.get(f"/api/sites/{site_id}", headers=headers).json()["notices"]
        ]

    assert notice_ids("site-near", supervisor()) == [notice.id]
    assert notice_ids("site-x", supervisor("auth0|supervisor-2")) == [notice.id]
    assert notice_ids("site-b", supervisor()) == []  # outside the radius
    delivered = sorted(e.entity for e in h.rows(db.AuditEvent) if e.action == "notice.deliver")
    assert delivered == [f"{notice.id}->{t}" for t in ("team-a", "team-n", "team-x")]


def test_flood_report_uses_the_5_mile_default(h, client) -> None:
    submit(client, category="flooding")
    [notice] = h.rows(db.HazardNotice)
    assert (notice.radius_miles, notice.radius_source) == (5.0, "default")
    assert notice.hazard_label == "flooding"


def test_gemini_radius_is_used_when_valid(h, client, monkeypatch) -> None:
    monkeypatch.setattr(gemini, "suggest_notice_radius", lambda *args: 2.5, raising=False)
    submit(client)
    [notice] = h.rows(db.HazardNotice)
    assert (notice.radius_miles, notice.radius_source) == (2.5, "gemini")


@pytest.mark.parametrize("bad", [0, -1, 60, None, "far"])
def test_invalid_or_unresponsive_gemini_radius_falls_back_to_default(
    h, client, monkeypatch, bad
) -> None:
    monkeypatch.setattr(gemini, "suggest_notice_radius", lambda *args: bad, raising=False)
    submit(client)
    [notice] = h.rows(db.HazardNotice)
    assert (notice.radius_miles, notice.radius_source) == (1.0, "default")


def test_gemini_error_falls_back_to_default(h, client, monkeypatch) -> None:
    def boom(*args):
        raise TimeoutError

    monkeypatch.setattr(gemini, "suggest_notice_radius", boom, raising=False)
    assert submit(client).status_code == 201
    [notice] = h.rows(db.HazardNotice)
    assert notice.radius_source == "default"


def test_absent_report_sends_no_notice_and_photo_is_optional(h, client) -> None:
    response = submit(client, category="on_site_fire", hazard_present="false", photo=None)
    assert response.status_code == 201
    assert response.json()["notice_id"] is None
    assert h.rows(db.HazardNotice) == []


# ---- rejected submissions ----


def test_present_report_requires_a_photo(h, client) -> None:
    assert submit(client, photo=None).status_code == 422
    assert h.rows(db.CrewReport) == []


def test_invalid_photo_is_rejected_and_nothing_is_stored(h, client, tmp_path) -> None:
    response = submit(client, photo=b"not a photo", content_type="image/jpeg")
    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "unsupported_type"
    assert h.rows(db.CrewReport) == [] and h.rows(db.HazardNotice) == []
    assert not any(p.is_file() for p in tmp_path.rglob("*"))


def test_bad_fields_are_rejected(h, client) -> None:
    assert submit(client, lat="95").status_code == 422
    assert submit(client, category="volcano").status_code == 422
    assert submit(client, note="x" * 1001).status_code == 422
    assert submit(client, site_id="nope").status_code == 404


def test_crew_can_only_report_for_their_own_site(h, client) -> None:
    assert submit(client, site_id="site-b").status_code == 403


def test_reporting_needs_permission_and_membership(h, client) -> None:
    no_permission = bearer(
        token(["crew"], permissions=[roles.READ_ASSIGNED_SITES], sub="auth0|crew-a")
    )
    assert submit(client, headers=no_permission).status_code == 403
    assert submit(client, headers=crew("auth0|stranger")).status_code == 403
    assert client.post("/api/reports").status_code == 401


def test_supervisor_reports_for_their_organizations_site(h, client) -> None:
    response = submit(client, headers=supervisor())
    assert response.status_code == 201
    assert response.json()["team_id"] == "team-a"
    assert submit(client, headers=supervisor("auth0|supervisor-2")).status_code == 403
    assert submit(client, headers=supervisor(), site_id="site-empty").status_code == 403


# ---- listing ----


def test_list_reports_respects_roles(h, client) -> None:
    submit(client)
    submit(client, headers=crew("auth0|crew-b"), site_id="site-b", lat=str(FAR[0]), lon=str(FAR[1]))
    crew_a = [r["site_id"] for r in client.get("/api/reports", headers=crew("auth0|crew-a")).json()]
    assert crew_a == ["site-a"]
    org_1 = client.get("/api/reports", headers=supervisor()).json()
    assert sorted(r["site_id"] for r in org_1) == ["site-a", "site-b"]
    assert client.get("/api/reports", headers=supervisor("auth0|supervisor-2")).json() == []
    filtered = client.get("/api/reports", params={"site_id": "site-b"}, headers=supervisor()).json()
    assert [r["site_id"] for r in filtered] == ["site-b"]


def test_report_creation_is_audited(h, client) -> None:
    report = submit(client).json()
    actions = {(e.action, e.entity) for e in h.rows(db.AuditEvent)}
    assert ("report.create", report["id"]) in actions
    assert ("notice.create", report["notice_id"]) in actions
