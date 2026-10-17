"""T050A: one advisory card per confirmed event on `GET /api/sites/{id}`.

In-memory SQLite and fake JWTs. Cards come from Cache's real adapter (`ml/event_outlooks`)
where its dependencies are installed; the model artifact is replaced or absent, so these
check admission and wiring, not forecast skill or live Auth0/Tiger Data.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_now
from app.db import models as db
from app.demo import DEMO_SITE_ID
from app.main import app
from app.outlook import EventOutlooksService, event_inputs
from app.outlook import events as outlook_events
from app.outlook.context import event_context_from_notice
from app.schemas import CrewReport, EventOutlookCard, HazardNotice, Observation, SiteSummary
from tests import auth_fakes
from tests.auth_fakes import crew, supervisor
from tests.test_demo_seed import CREW, NOW, OUTLOOKS, SUPERVISOR, factory, seeded  # noqa: F401

SITE = SiteSummary(
    id="site-a", name="Site A", lat=25.76, lon=-80.49, assigned_team=None, risk_score=None,
    risk_level=None, updated_at=None, active_alerts=0, top_factors=[], data_completeness=0,
    model_version="unscored",
)  # fmt: skip
T = datetime(2026, 10, 17, 18, 0, tzinfo=UTC)


def notice(id="n-1", label="flooding", status="confirmed", start=True, evidence=(), **extra):
    items = list(evidence)
    if start:
        items.append(
            {"id": f"{id}:start", "kind": "event_start", "label": "Event began",
             "observed_at": T - timedelta(hours=2)}
        )  # fmt: skip
    fields = dict(
        id=id, hazard_label=label, source="feed", source_ref="obs-1", lat=25.76, lon=-80.49,
        radius_miles=5, radius_source="default", status=status,
        created_at=T - timedelta(minutes=50), evidence=items,
    )  # fmt: skip
    if status == "confirmed":
        fields |= dict(confirmed_by="sup", confirmed_at=T - timedelta(minutes=40))
    return HazardNotice(**(fields | extra))


def warning(value: str, site_id: str = "site-a", id: str = "obs-1") -> Observation:
    return Observation(
        id=id, site_id=site_id, source="NWS", hazard_type="flood_alert", value=value,
        lat=25.76, lon=-80.49, observed_at=T - timedelta(hours=3), data_state="observed",
    )  # fmt: skip


def report(category="flooding", **extra) -> CrewReport:
    fields = dict(
        id="r-1", organization_id="org", team_id="team", site_id="site-a", reporter_id="crew",
        category=category, hazard_present=True, lat=25.76, lon=-80.49,
        review_status="confirmed", reviewed_by="sup", reviewed_at=T - timedelta(minutes=20),
        created_at=T - timedelta(minutes=30),
    )  # fmt: skip
    return CrewReport(**(fields | extra))


# ---- event start: the T050A bug ----


def test_notice_creation_time_is_never_the_event_start() -> None:
    context = event_context_from_notice(notice(start=False), SITE, T)
    assert context["event_start_utc"] is None  # not notice.created_at
    [event] = event_inputs(SITE, [notice(start=False)], [], [warning("Flood Warning")], T)
    assert event["event_start_utc"] is None


def test_trusted_start_is_used_and_must_precede_confirmation() -> None:
    [event] = event_inputs(SITE, [notice()], [], [warning("Flood Warning")], T)
    assert event["event_start_utc"] == "2026-10-17T16:00:00Z"
    late = {"id": "late", "kind": "event_start", "label": "x", "observed_at": T}  # after confirm
    [event] = event_inputs(SITE, [notice(start=False, evidence=[late])], [], [], T)
    assert event["event_start_utc"] is None


def test_singular_outlook_reports_a_missing_start_as_unavailable() -> None:
    outlook = OUTLOOKS.outlook(SITE, event_context_from_notice(notice(start=False), SITE, T))
    assert outlook.status == "unavailable"
    assert "event start" in outlook.limitations[0]


# ---- event identification ----


@pytest.mark.parametrize(
    ("value", "evidence", "expected"),
    [
        ("Flood Warning", [], "Flood"),
        ("Flash Flood Warning", [], "Flash Flood"),
        (None, [{"id": "e", "kind": "observation", "label": "NWS Flash Flood Warning"}],
         "Flash Flood"),
        (None, [], "Flooding (category not identified)"),
    ],
)  # fmt: skip
def test_flood_and_flash_flood_are_separate_targets(value, evidence, expected) -> None:
    observations = [warning(value)] if value else []
    [event] = event_inputs(SITE, [notice(evidence=evidence)], [], observations, T)
    assert event["event_type"] == expected
    definition = "noaa_recorded_flood_interval" if expected == "Flood" else None
    assert event["event_definition"] == definition


def test_a_notices_own_source_outranks_another_site_warning() -> None:
    flash = warning("Flash Flood Warning", id="obs-2")
    [event] = event_inputs(SITE, [notice()], [], [warning("Flood Warning"), flash], T)
    assert event["event_type"] == "Flood"


def test_only_confirmed_notices_become_events() -> None:
    assert event_inputs(SITE, [notice(status="potential")], [], [warning("Flood Warning")], T) == []


def test_site_association_and_local_evidence() -> None:
    [here] = event_inputs(SITE, [notice()], [report()], [warning("Flood Warning")], T)
    assert here["association"]["method"] == "site_verified"
    assert [o["id"] for o in here["observations"]] == ["r-1"]
    elsewhere = warning("Flood Warning", site_id="site-b")
    [away] = event_inputs(SITE, [notice()], [report(review_status="pending")], [elsewhere], T)
    assert away["association"]["method"] == "regional_context"
    assert away["observations"] == []  # pending reports are not evidence


def test_official_types_carry_the_provider_event_id() -> None:
    storm = Observation(
        id="obs-1", site_id="site-a", source="NHC", hazard_type="hurricane", value=120,
        source_ref="AL092024", lat=26.0, lon=-84.0, observed_at=T, data_state="observed",
    )  # fmt: skip
    [event] = event_inputs(SITE, [notice(label="hurricane")], [], [storm], T)
    assert (event["event_type"], event["event_id"]) == ("Hurricane (Typhoon)", "AL092024")
    assert event["official_product_id"] == "AL092024"


# ---- the service: independent cards, never breaking the route ----


def test_ml_unavailable_gives_one_unavailable_card_per_event(monkeypatch) -> None:
    monkeypatch.setattr(outlook_events, "_load_builder", lambda: (None, "ML missing (Test)"))
    inputs = event_inputs(
        SITE, [notice("a"), notice("b", label="wildlife")], [], [warning("Flood Warning")], T
    )
    cards = EventOutlooksService().cards(SITE, inputs, T)
    assert [(c.event_id, c.status, c.forecast.kind) for c in cards] == [
        ("a", "unavailable", "unavailable"),
        ("b", "unavailable", "unavailable"),
    ]
    assert all(c.forecast.reason.startswith("Prediction unavailable") for c in cards)


def test_a_failing_batch_never_raises() -> None:
    def boom(request, products):
        raise RuntimeError("model exploded")

    inputs = event_inputs(SITE, [notice()], [], [warning("Flood Warning")], T)
    [card] = EventOutlooksService(builder=boom).cards(SITE, inputs, T)
    assert (card.status, card.forecast.reason_code) == ("unavailable", "prediction_failed")


def test_unidentified_flood_is_explained_not_guessed() -> None:
    inputs = event_inputs(SITE, [notice()], [], [], T)
    [card] = EventOutlooksService(builder=lambda r, p: []).cards(SITE, inputs, T)
    assert card.forecast.reason_code == "flood_category_unidentified"
    assert "Flash Flood" in card.forecast.reason


@pytest.fixture
def real_adapter():
    pytest.importorskip("sklearn", reason="Cache's adapter needs ml/requirements-lock.txt")
    return pytest.importorskip("ml.event_outlooks")


def test_live_flood_needs_current_local_evidence(real_adapter) -> None:
    service = EventOutlooksService()
    no_report = event_inputs(SITE, [notice()], [], [warning("Flood Warning")], T)
    [card] = service.cards(SITE, no_report, T)
    assert card.forecast.reason_code == "local_confirmation_missing"
    stale = report(created_at=T - timedelta(hours=3), reviewed_at=T - timedelta(hours=2))
    old = event_inputs(SITE, [notice()], [stale], [warning("Flood Warning")], T)
    [card] = service.cards(SITE, old, T)
    assert card.forecast.reason_code == "stale_local_confirmation"


def test_archived_official_product_is_not_a_current_forecast(real_adapter) -> None:
    from ml.event_outlooks.examples import official_products

    products = official_products()
    storm = Observation(
        id="obs-1", site_id="site-a", source="NHC", hazard_type="hurricane", value=120,
        source_ref="AL092024", lat=26.0, lon=-84.0, observed_at=T, data_state="observed",
    )  # fmt: skip
    inputs = event_inputs(SITE, [notice(label="hurricane")], [], [storm], T)
    inputs[0]["official_product_id"] = "helene-015"
    [card] = EventOutlooksService(official_products=products).cards(SITE, inputs, T)
    assert card.status == "unavailable"  # a 2024 archive capture is not current here
    missing = event_inputs(SITE, [notice(label="hurricane")], [], [storm], T)
    [card] = EventOutlooksService().cards(SITE, missing, T)
    assert card.forecast.reason_code == "official_forecast_missing"


# ---- the route, on the T069 demo ----


@pytest.fixture
def api(seeded) -> Iterator[TestClient]:  # noqa: F811
    def override_db() -> Iterator[Session]:
        with seeded() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_now] = lambda: NOW + timedelta(minutes=1)
    auth_fakes.install(app)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("headers", [crew(CREW), supervisor(SUPERVISOR)], ids=["crew", "sup"])
def test_demo_site_shows_independent_cards_without_touching_score(
    api,
    seeded,  # noqa: F811
    headers,
) -> None:
    def state():
        with seeded() as session:
            score = session.scalars(
                select(db.HazardScore).where(db.HazardScore.site_id == DEMO_SITE_ID)
            ).all()
            alerts = session.scalars(select(db.Alert).where(db.Alert.site_id == DEMO_SITE_ID)).all()
            return len(score), [(a.state, a.clear_after) for a in alerts]

    before = state()
    detail = api.get(f"/api/sites/{DEMO_SITE_ID}", headers=headers).json()
    assert state() == before  # reading outlooks never rescored or touched an alert
    cards = [EventOutlookCard.model_validate(c) for c in detail["event_outlooks"]]
    ids = [c.event_id for c in cards]
    assert len(ids) == len(set(ids))
    by_type = {c.event_type: c for c in cards}
    assert {"Flood", "Flash Flood", "Wildlife"} <= set(by_type)
    assert by_type["Flood"].presentation == "replay" and by_type["Flood"].is_simulated
    assert by_type["Wildlife"].status == "unavailable"
    assert all(
        c.production_eligibility is False and c.site_hazard_probability is None for c in cards
    )
    assert detail["event_outlook"]["event_id"] == "demo-notice-flood"  # singular unchanged
    for example in [c for c in cards if c.presentation == "historical_example"]:
        assert example.is_simulated
        assert example.limitations[0].startswith("Historical example")
