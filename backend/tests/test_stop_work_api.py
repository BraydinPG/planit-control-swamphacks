"""T049C: tiered stop-work alerts persist, audit, and list most dangerous first."""

from datetime import timedelta

from sqlalchemy import select

from app.db import models as db
from app.rules.lightning import Transition
from app.schemas import AlertRule, DataState, HazardType, Observation
from app.services.alerts import apply_stop_work_rules
from tests.test_alerts_api import T0, strike
from tests.test_alerts_api import client as client  # noqa: F401
from tests.test_alerts_api import h as h  # noqa: F401


def warning(event: str | None, hazard_type=HazardType.SEVERE_STORM, site="site-a", **extra):
    fields = dict(
        id=f"nws:{site}:{event}",
        site_id=site,
        source="NWS",
        hazard_type=hazard_type,
        value=event,
        label=event or "No active alerts",
        source_ref=f"urn:{event}",
        lat=25.76,
        lon=-80.49,
        observed_at=T0 - timedelta(minutes=20),
        data_state=DataState.OBSERVED,
    )
    return Observation(**(fields | extra))


def apply(h, observations, site="site-a"):
    with h.factory() as session:
        return apply_stop_work_rules(session, session.get(db.Site, site), observations, h.now)


def test_tornado_warning_persists_with_tier_and_label(h, client) -> None:
    results = apply(h, [warning("Tornado Warning")])
    assert results[AlertRule.TORNADO].transition is Transition.TRIGGERED
    assert results[AlertRule.LIGHTNING_STOP_WORK].transition is Transition.NONE
    [alert] = client.get("/api/alerts").json()
    assert alert["rule"] == "tornado"
    assert alert["danger_tier"] == 1
    assert alert["event_label"] == "Tornado Warning"
    assert alert["clear_after"] is None
    assert alert["is_prototype_rule"] is True


def test_warning_lifecycle_is_persisted_and_audited(h, client) -> None:
    apply(h, [warning("Severe Thunderstorm Warning")])
    h.now = T0 + timedelta(minutes=5)
    started = apply(h, [warning(None)])[AlertRule.SEVERE_THUNDERSTORM]
    assert started.transition is Transition.RESET
    [alert] = client.get("/api/alerts").json()
    assert alert["clear_after"].startswith("2026-10-17T18:35")
    h.now = T0 + timedelta(minutes=35)
    assert apply(h, [warning(None)])[AlertRule.SEVERE_THUNDERSTORM].transition is (
        Transition.CLEARED
    )
    assert client.get("/api/alerts").json() == []
    with h.factory() as session:
        events = [
            (e.actor, e.action)
            for e in session.scalars(select(db.AuditEvent).order_by(db.AuditEvent.created_at))
        ]
    assert events == [
        ("rule:severe_thunderstorm", "alert.triggered"),
        ("rule:severe_thunderstorm", "alert.reset"),
        ("rule:severe_thunderstorm", "alert.cleared"),
    ]


def test_feed_outage_holds_the_alert_and_writes_nothing(h, client) -> None:
    apply(h, [warning("Tornado Warning")])
    h.now = T0 + timedelta(hours=3)
    down = warning(None, data_state=DataState.UNAVAILABLE)
    assert apply(h, [down])[AlertRule.TORNADO].transition is Transition.HELD
    [alert] = client.get("/api/alerts").json()
    assert alert["state"] == "active" and alert["clear_after"] is None


def test_lightning_keeps_its_own_rule_inside_apply_stop_work_rules(h, client) -> None:
    results = apply(h, [strike(4.2, T0)])
    assert results[AlertRule.LIGHTNING_STOP_WORK].transition is Transition.TRIGGERED
    [alert] = client.get("/api/alerts").json()
    assert alert["rule"] == "lightning_stop_work"
    assert alert["is_prototype_rule"] is False
    assert alert["event_label"] == "Lightning 4.2 mi from site"


def test_active_alerts_list_most_dangerous_tier_first_and_hide_nothing(h, client) -> None:
    # Newest first would put flood (tier 3) on top; tiers put the flash flood first.
    h.now = T0 - timedelta(minutes=10)
    apply(h, [warning("Flash Flood Warning", HazardType.FLOOD_ALERT)])
    h.now = T0
    apply(h, [strike(4.2, T0)])
    h.now = T0 + timedelta(minutes=1)
    apply(
        h,
        [
            warning("Flash Flood Warning", HazardType.FLOOD_ALERT, id="ffw"),
            warning("Flood Warning", HazardType.FLOOD_ALERT, id="flw"),
        ],
    )
    listed = client.get("/api/alerts").json()
    assert [(a["rule"], a["danger_tier"]) for a in listed] == [
        ("flash_flood", 1),
        ("lightning_stop_work", 2),
        ("flood", 3),
    ]
    detail = client.get("/api/sites/site-a").json()
    assert [a["rule"] for a in detail["alerts"]] == ["flash_flood", "lightning_stop_work", "flood"]
