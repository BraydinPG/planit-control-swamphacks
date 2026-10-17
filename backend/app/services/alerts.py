"""Persist lightning stop-work alerts and acknowledgements (T048).

`apply_lightning_rule` runs the pure T046/T047 rule (`app.rules.lightning`) against the
site's stored lightning alert and writes the result:

- triggered: inserts a new alert row
- reset or cleared: updates the existing row (`triggered_at` never changes, so the row's
  hypertable key stays the same)
- none, unchanged, or held: writes nothing

Triggers, resets, clears, and acknowledgements each add an `AuditEvent`. The refresh loop
(`app.services.refresh`, T049B) calls this on a schedule.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.sites import alert_schemas
from app.db import models as db
from app.rules.lightning import LightningResult, Transition, evaluate_lightning
from app.schemas import Alert, AlertRule, Observation

RULE_ACTOR = "rule:lightning_stop_work"


def latest_lightning_alert(session: Session, site_id: str) -> db.Alert | None:
    return session.scalars(
        select(db.Alert)
        .where(db.Alert.site_id == site_id, db.Alert.rule == AlertRule.LIGHTNING_STOP_WORK)
        .order_by(db.Alert.triggered_at.desc())
        .limit(1)
    ).first()


def apply_lightning_rule(
    session: Session, site_id: str, observations: list[Observation], now: datetime
) -> LightningResult:
    row = latest_lightning_alert(session, site_id)
    current = alert_schemas(session, [row])[0] if row else None
    result = evaluate_lightning(site_id, observations, current, now)
    if result.transition is Transition.TRIGGERED:
        session.add(_new_row(result.alert))
    elif result.transition in (Transition.RESET, Transition.CLEARED):
        _update_row(row, result.alert)
    else:
        return result
    audit(session, RULE_ACTOR, f"alert.{result.transition.value}", result.alert.id, now)
    session.commit()
    return result


def acknowledge(session: Session, alert: db.Alert, user_id: str, now: datetime) -> bool:
    """Record one acknowledgement per user. Returns False when it already existed."""
    existing = session.scalars(
        select(db.Acknowledgement).where(
            db.Acknowledgement.alert_id == alert.id, db.Acknowledgement.user_id == user_id
        )
    ).first()
    if existing is not None:
        return False
    session.add(
        db.Acknowledgement(
            id=f"ack:{uuid4().hex}", alert_id=alert.id, user_id=user_id, acknowledged_at=now
        )
    )
    audit(session, user_id, "alert.acknowledge", alert.id, now)
    session.commit()
    return True


def audit(session: Session, actor: str, action: str, entity: str, now: datetime) -> None:
    session.add(
        db.AuditEvent(
            id=f"audit:{uuid4().hex}", actor=actor, action=action, entity=entity, created_at=now
        )
    )


def _new_row(alert: Alert) -> db.Alert:
    row = db.Alert(id=alert.id, site_id=alert.site_id, triggered_at=alert.triggered_at)
    _update_row(row, alert)
    return row


def _update_row(row: db.Alert, alert: Alert) -> None:
    row.rule = alert.rule
    row.state = alert.state
    row.latest_event_at = alert.latest_event_at
    row.clear_after = alert.clear_after
    row.distance_miles = alert.distance_miles
    row.trigger_observation_ids = list(alert.trigger_observation_ids)
    row.evidence = [e.model_dump(mode="json") for e in alert.evidence]
    row.simulated = alert.simulated
    row.is_prototype_rule = alert.is_prototype_rule
