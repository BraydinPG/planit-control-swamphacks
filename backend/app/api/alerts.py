"""`GET /api/alerts` and `POST /api/alerts/{id}/acknowledge` (T048).

Access (spec.md section 8): supervisors see and acknowledge every alert. Crew see and
acknowledge only alerts for their team's site. Acknowledging needs `acknowledge:alerts`.

The countdown comes from each alert's `clear_after`, which only the deterministic rule
sets. The UI shows the remaining time and never decides the site is clear. The
response's `Date` header gives server time, so clients can correct for clock skew.
"""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.api.deps import get_now
from app.api.sites import DbSession, alert_schemas, visible_site_ids
from app.db import models as db
from app.schemas import Alert, AlertState
from app.security import AuthenticatedUser, CurrentUser, require_permission, roles
from app.services.alerts import acknowledge

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

Now = Annotated[datetime, Depends(get_now)]
Acknowledger = Annotated[CurrentUser, Depends(require_permission(roles.ACKNOWLEDGE_ALERTS))]
ALERT_LIMIT = 200


@router.get("", response_model=list[Alert])
def list_alerts(
    user: AuthenticatedUser,
    session: DbSession,
    state: Literal["active", "cleared", "all"] = "active",
    site_id: Annotated[str | None, Query(description="Only this site's alerts")] = None,
) -> list[Alert]:
    """Alerts the caller may see, newest trigger first. Defaults to active alerts."""
    query = select(db.Alert).order_by(db.Alert.triggered_at.desc()).limit(ALERT_LIMIT)
    visible = visible_site_ids(session, user)
    if visible is not None:
        query = query.where(db.Alert.site_id.in_(visible))
    if site_id is not None:
        query = query.where(db.Alert.site_id == site_id)
    if state != "all":
        query = query.where(db.Alert.state == state)
    return alert_schemas(session, list(session.scalars(query).all()))


@router.post("/{alert_id}/acknowledge", response_model=Alert)
def acknowledge_alert(alert_id: str, user: Acknowledger, session: DbSession, now: Now) -> Alert:
    """Record the caller and time. Repeating it returns the existing acknowledgement."""
    row = session.scalars(select(db.Alert).where(db.Alert.id == alert_id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    visible = visible_site_ids(session, user)
    if visible is not None and row.site_id not in visible:
        raise HTTPException(status_code=403, detail="This alert is not for your team's site")
    if row.state != AlertState.ACTIVE:
        raise HTTPException(status_code=409, detail="Only an active alert can be acknowledged")
    acknowledge(session, row, user.sub, now)
    return alert_schemas(session, [row])[0]
