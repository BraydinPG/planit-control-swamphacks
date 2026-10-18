"""One controlled whole-path check, not real Auth0/Tiger Data acceptance.

Reuse NWS MockTransport JSON, existing test-only signed identities/memberships and
in-memory persistence. No network, account provisioning, application seed or bypass.
"""

import json
from datetime import timedelta

from sqlalchemy import select

from app.api.deps import get_now
from app.db import models as db
from app.ingestion.base import FeedError
from app.ingestion.nws_alerts import NwsFloodAlertFeed
from app.ingestion.nws_weather import NwsWeatherFeed
from app.main import app
from app.schemas import HazardType, SiteDetail
from app.services.refresh import Feed, refresh_all
from tests.auth_fakes import crew, supervisor
from tests.nws_fakes import FakeNws, cache, latest
from tests.test_hazards_api import absent, confirm, review
from tests.test_refresh import strike_feed
from tests.test_reports_api import NOW, submit
from tests.test_reports_api import client as client
from tests.test_reports_api import h as h


def test_environment_to_api_report_confirmation_and_failed_feed(h, client, tmp_path):
    clock = [NOW]
    app.dependency_overrides[get_now] = lambda: clock[0]
    raw = FakeNws()
    weather = NwsWeatherFeed(raw.client(), cache(HazardType.WEATHER))
    flood = NwsFloodAlertFeed(raw.client(), cache(HazardType.FLOOD_ALERT))

    def only_home(fetch):
        return lambda sites, now: fetch([s for s in sites if s.id == "site-a"], now)

    feeds = [
        Feed("NWS", HazardType.WEATHER, only_home(weather.fetch)),
        Feed("NWS", HazardType.FLOOD_ALERT, only_home(flood.fetch)),
    ]
    snapshots = []

    def capture(stage):
        response = client.get("/api/sites/site-a", headers=crew())
        assert response.status_code == 200
        payload = response.json()
        detail = SiteDetail.model_validate(payload)
        supervisor_detail = client.get("/api/sites/site-a", headers=supervisor()).json()
        rows = client.get("/api/sites", headers=supervisor()).json()
        summary = next(r for r in rows if r["id"] == "site-a")
        assert [r["id"] for r in rows] == [
            r["id"]
            for r in sorted(
                rows,
                key=lambda r: (
                    r["assigned_team"] is None,
                    r["risk_score"] is None,
                    -(r["risk_score"] or 0),
                    r["name"],
                ),
            )
        ]
        assert detail.risk_score == detail.score.risk_score
        assert detail.data_completeness == detail.score.data_completeness
        assert summary["risk_score"] == supervisor_detail["risk_score"] == detail.risk_score
        assert detail.model_version == detail.score.model_version == "rules-0.2"
        with h.factory() as session:
            stored = session.scalars(
                select(db.HazardScore)
                .where(db.HazardScore.site_id == "site-a")
                .order_by(db.HazardScore.created_at.desc())
            ).first()
            assert stored.risk_score == detail.risk_score
            assert stored.factor_contributions == [
                f.model_dump(mode="json") for f in detail.score.factor_contributions
            ]
            assert all(f in stored.factor_contributions for f in summary["top_factors"])
        snapshots.append(dict(stage=stage, sites=rows, detail=payload))
        return detail

    assert client.get("/api/sites").status_code == 401
    assert client.get("/api/sites/site-b", headers=crew()).status_code == 403
    with h.factory() as session:
        assert not refresh_all(session, clock[0], feeds).failed_sites
    initial = capture("canned_nws_ingested")
    assert initial.score.risk_score == 5.1  # eligible forecast HI + one Flood Watch

    # Change agency-shaped source JSON, not the stored score or frontend response.
    raw.routes["/stations/KTMB/observations/latest"] = latest(heat_index=51.7)
    clock[0] += timedelta(minutes=5)
    with h.factory() as session:
        assert not refresh_all(session, clock[0], feeds).failed_sites
    changed = capture("changed_source_observation")
    assert changed.risk_score == 6 and changed.score.previous_score == initial.risk_score

    pending = submit(client, category="wildlife").json()
    assert capture("pending_report").risk_score == 6
    assert (
        client.post(f"/api/hazards/{pending['notice_id']}/confirm", headers=crew()).status_code
        == 403
    )
    assert confirm(client, pending["notice_id"]).status_code == 200
    confirmed = capture("confirmed_present_report")
    assert confirmed.risk_score == 7 and confirmed.score.previous_score == 6
    assert any(
        f.factor == "crew_report" and f.evidence_id == pending["id"]
        for f in confirmed.score.factor_contributions
    )
    assert any(o.id.startswith("nws-obs:") for o in confirmed.observations)

    absent_id = absent(client)["id"]
    assert review(client, absent_id).status_code == 200
    rejected_id = absent(client)["id"]
    assert review(client, rejected_id, decision="rejected").status_code == 200
    assert capture("absent_and_rejected_excluded").risk_score == 7

    clock[0] += timedelta(minutes=1)
    with h.factory() as session:
        refresh_all(session, clock[0], feeds + [strike_feed(4.2, clock[0])])
    triggered = capture("replayed_lightning_trigger")
    assert triggered.risk_score == 10 and triggered.alerts[0].state.value == "active"
    clear_after = triggered.alerts[0].clear_after

    def unavailable(*_args):
        raise FeedError("Controlled fixture outage")

    raw.fail = True
    clock[0] = NOW + timedelta(minutes=40)  # beyond the server's lightning window
    with h.factory() as session:
        result = refresh_all(
            session, clock[0], feeds + [Feed("lightning", HazardType.LIGHTNING_STRIKE, unavailable)]
        )
        assert not result.failed_sites and result.failed_feeds
    held = capture("failed_feed_held_alert")
    assert held.risk_score == 10 and held.data_completeness == 0
    assert held.alerts[0].state.value == "active" and held.alerts[0].clear_after == clear_after
    assert any(f.data_state.value == "stale" for f in held.score.factor_contributions)

    # Public synthetic evidence only, retained in pytest's temporary test directory
    # for optional frontend-client/render inspection, never a production fixture.
    (tmp_path / "scoring-workflow.json").write_text(
        json.dumps(
            dict(
                evidence_type="controlled_mocktransport_test_identities_in_memory_db",
                real_auth0_or_tiger_data_verified=False,
                snapshots=snapshots,
            )
        ),
        encoding="utf-8",
    )
