"""T050: optional active-event outlook as a separate advisory field on site detail."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from ml.schemas import validate_event_context
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db, get_now
from app.db import models as db
from app.main import app
from app.outlook import EventOutlookService, event_context_from_notice, get_event_outlook_service
from app.outlook import service as outlook_service
from app.schemas import ADVISORY_NOTICE, EventOutlook, HazardNotice, SiteSummary
from tests import auth_fakes
from tests.auth_fakes import supervisor

NOW = datetime(2026, 10, 17, 18, 0, tzinfo=UTC)
SITE = SiteSummary(
    id="site-a",
    name="Alpha Plant",
    lat=25.76,
    lon=-80.49,
    assigned_team=None,
    risk_score=None,
    risk_level=None,
    updated_at=None,
    active_alerts=0,
    top_factors=[],
    data_completeness=0.0,
    model_version="unscored",
)

# Shape of a real ok result from Cache's adapter (ml/INTEGRATION.md "Verified v2 output").
OK_RESULT = {
    "status": "ok",
    "scope": "conditional_on_confirmed_active_event",
    "site_id": "site-a",
    "event_id": "notice-flood",
    "event_type": "Flood",
    "as_of_utc": "2026-10-17T18:00:00Z",
    "generated_at_utc": "2026-10-17T18:00:01Z",
    "outcomes": {
        "recorded_event_ongoing_probability": {"6h": 0.71, "12h": 0.6, "24h": 0.47},
        "recorded_event_ended_probability": {"6h": 0.29, "12h": 0.4, "24h": 0.53},
        "remaining_duration_hours": {"p10": 2.0, "median": 22.0, "p90": None},
        "trend": "unknown",
    },
    "worker_context": {"limitations": ["Regional recorded events, not site conditions."]},
    "model_version": "noaa-flood-conditional-km-v2",
    "is_simulated": False,
    "production_eligibility": False,
}


def notice(status="confirmed", label="flooding", confirmed_minutes_ago=30, **extra):
    fields = dict(
        id="notice-flood",
        hazard_label=label,
        source="feed",
        source_ref="obs-flood-1",
        lat=25.76,
        lon=-80.49,
        radius_miles=5,
        radius_source="default",
        status=status,
        created_at=NOW - timedelta(hours=2),
    )
    if status == "confirmed":
        fields |= dict(
            confirmed_by="supervisor-1",
            confirmed_at=NOW - timedelta(minutes=confirmed_minutes_ago),
        )
    return HazardNotice(**(fields | extra))


# ---- event context (the approved backend contract) ----


def test_confirmed_flood_notice_builds_a_valid_event_context() -> None:
    context = event_context_from_notice(notice(), SITE, NOW)
    assert context["event_type"] == "Flood"
    assert context["event_status"] == "confirmed_active"
    assert context["site_id"] == "site-a"
    assert context["evidence"][0]["source"] == "supervisor_confirmed_hazard_notice"
    validate_event_context(context)  # Cache's own validator accepts it


@pytest.mark.parametrize(
    "candidate",
    [
        notice(status="potential"),
        notice(label="wildlife"),
        notice(confirmed_minutes_ago=-5),  # confirmed in the future
    ],
)
def test_only_confirmed_flood_notices_build_a_context(candidate) -> None:
    assert event_context_from_notice(candidate, SITE, NOW) is None


def test_simulated_evidence_marks_a_historical_replay() -> None:
    simulated = notice(evidence=[{"id": "e", "kind": "observation", "label": "Flood (simulated)"}])
    context = event_context_from_notice(simulated, SITE, NOW)
    assert context["event_status"] == "historical_replay"
    assert context["is_simulated"] is True
    validate_event_context(context)


# ---- service ----


def test_ok_result_maps_to_compact_outlook() -> None:
    service = EventOutlookService(lambda site, ctx: OK_RESULT)
    outlook = service.outlook(SITE, event_context_from_notice(notice(), SITE, NOW))
    assert outlook.status == "ok"
    assert outlook.ongoing_probability == {"6h": 0.71, "12h": 0.6, "24h": 0.47}
    assert outlook.remaining_hours_median == 22.0
    assert outlook.production_eligible is False
    assert outlook.advisory_notice == ADVISORY_NOTICE


def test_predictor_receives_only_site_identity_and_coordinates() -> None:
    seen = {}

    def predictor(site, ctx):
        seen.update(site)
        return OK_RESULT

    EventOutlookService(predictor).outlook(SITE, event_context_from_notice(notice(), SITE, NOW))
    assert seen == {"id": "site-a", "lat": 25.76, "lon": -80.49}


def test_predictor_error_is_unavailable_not_raised() -> None:
    def broken(site, ctx):
        raise RuntimeError("boom")

    outlook = EventOutlookService(broken).outlook(
        SITE, event_context_from_notice(notice(), SITE, NOW)
    )
    assert outlook.status == "unavailable"
    assert outlook.ongoing_probability == {}
    assert "RuntimeError" in outlook.limitations[0]


def test_malformed_result_is_unavailable() -> None:
    bad = OK_RESULT | {"outcomes": {"recorded_event_ongoing_probability": {"6h": "high"}}}
    outlook = EventOutlookService(lambda s, c: bad).outlook(
        SITE, event_context_from_notice(notice(), SITE, NOW)
    )
    assert outlook.status == "unavailable"


def test_missing_ml_package_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        outlook_service, "_load_predictor", lambda: (None, "ML package not importable")
    )
    outlook = EventOutlookService().outlook(SITE, event_context_from_notice(notice(), SITE, NOW))
    assert outlook.status == "unavailable"
    assert outlook.limitations == ["ML package not importable"]


def test_production_eligible_can_never_be_true() -> None:
    with pytest.raises(ValidationError):
        EventOutlook(
            status="ok",
            generated_at_utc=NOW,
            model_version="m",
            is_simulated=False,
            production_eligible=True,
        )


def test_real_adapter_without_artifact_is_unavailable(tmp_path) -> None:
    pytest.importorskip("sklearn", reason="Cache's adapter needs ml/requirements-lock.txt")
    from ml.backend_adapter import ActiveEventPredictor

    predictor = ActiveEventPredictor(tmp_path / "missing.joblib").predict_for_site
    outlook = EventOutlookService(predictor).outlook(
        SITE, event_context_from_notice(notice(), SITE, NOW)
    )
    assert outlook.status == "unavailable"


# ---- route: separate field, never changes score or alerts ----


def seed(session: Session, with_flood_notice: bool) -> None:
    session.add(
        db.Site(
            id="site-a",
            name="Alpha Plant",
            lat=25.76,
            lon=-80.49,
            location_type="power_plant",
            source="EIA-860M (representative)",
        )
    )
    session.flush()
    session.add_all(
        [
            db.HazardScore(
                id="score-1",
                site_id="site-a",
                risk_score=6.5,
                risk_level="high",
                factor_contributions=[],
                model_version="rules-0.1",
                model_is_fallback=False,
                confidence=1.0,
                data_completeness=1.0,
                created_at=NOW - timedelta(minutes=5),
            ),
            db.Alert(
                id="alert-1",
                site_id="site-a",
                rule="lightning_stop_work",
                state="active",
                triggered_at=NOW - timedelta(minutes=5),
                latest_event_at=NOW - timedelta(minutes=5),
                clear_after=NOW + timedelta(minutes=25),
                distance_miles=4.0,
            ),
        ]
    )
    if with_flood_notice:
        n = notice()
        session.add(
            db.HazardNotice(
                id=n.id,
                hazard_label=n.hazard_label,
                source=n.source,
                source_ref=n.source_ref,
                lat=n.lat,
                lon=n.lon,
                radius_miles=n.radius_miles,
                radius_source=n.radius_source,
                status=n.status,
                created_at=n.created_at,
                confirmed_by=n.confirmed_by,
                confirmed_at=n.confirmed_at,
                evidence=[],
            )
        )
    session.commit()


def get_detail(with_flood_notice: bool, service: EventOutlookService) -> dict:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    db.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        seed(session, with_flood_notice)

    def override_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_now] = lambda: NOW
    app.dependency_overrides[get_event_outlook_service] = lambda: service
    auth_fakes.install(app)
    try:
        response = TestClient(app, headers=supervisor()).get("/api/sites/site-a")
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
    assert response.status_code == 200
    return response.json()


def broken(site, ctx):
    raise RuntimeError("model down")


def test_no_confirmed_event_means_null_outlook() -> None:
    detail = get_detail(False, EventOutlookService(lambda s, c: OK_RESULT))
    assert detail["event_outlook"] is None


def test_confirmed_flood_notice_adds_the_outlook_field() -> None:
    detail = get_detail(True, EventOutlookService(lambda s, c: OK_RESULT))
    assert detail["event_outlook"]["status"] == "ok"
    assert detail["event_outlook"]["event_id"] == "notice-flood"


def test_unavailable_outlook_leaves_score_and_alerts_unchanged() -> None:
    without = get_detail(False, EventOutlookService(lambda s, c: OK_RESULT))
    ok = get_detail(True, EventOutlookService(lambda s, c: OK_RESULT))
    down = get_detail(True, EventOutlookService(broken))
    assert down["event_outlook"]["status"] == "unavailable"
    for detail in (ok, down):
        for key in ("risk_score", "risk_level", "score", "alerts", "active_alerts", "top_factors"):
            assert detail[key] == without[key], key
