"""T049B: feed refresh loop. Fake feeds only; no network."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import models as db
from app.ingestion import FeedCache, FeedError
from app.ingestion.settings import get_ingestion_settings
from app.main import app
from app.schemas import DataState, HazardType, Observation
from app.services.refresh import Feed, refresh_all

NOW = datetime(2026, 10, 17, 18, 0, tzinfo=UTC)
SITES = {"site-a": (25.76, -80.49), "site-b": (27.95, -82.46)}


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    db.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as s:
        s.add(db.Organization(id="org-1", name="Sunbelt"))
        for site_id, (lat, lon) in SITES.items():
            s.add(
                db.Site(
                    id=site_id,
                    name=site_id,
                    lat=lat,
                    lon=lon,
                    location_type="power_plant",
                    source="EIA-860M (representative)",
                )
            )
        s.flush()
        s.add(db.Team(id="team-a", organization_id="org-1", name="Crew A", site_id="site-a"))
        s.commit()
        yield s
    engine.dispose()


def reading(site, hazard_type, now, value=None, source="TEST", key="none", **extra):
    return Observation(
        id=f"{source}:{hazard_type}:{site.id}:{key}",
        site_id=site.id,
        source=source,
        hazard_type=hazard_type,
        value=value,
        label=extra.pop("label", f"{source} {hazard_type} {key}"),
        lat=extra.pop("lat", site.lat),
        lon=extra.pop("lon", site.lon),
        observed_at=extra.pop("observed_at", now),
        data_state=extra.pop("data_state", DataState.OBSERVED),
        **extra,
    )


def per_site(make) -> Feed:
    """A feed whose readings come from `make(site, now)` for each site."""
    hazard = make.hazard_type
    return Feed("TEST", hazard, lambda sites, now: [o for s in sites for o in make(s, now)])


def none_feed(hazard_type: HazardType):
    def make(site, now):
        return [reading(site, hazard_type, now, key=f"none:{now.isoformat()}")]

    make.hazard_type = hazard_type
    return per_site(make)


def quake_feed(magnitude=5.0):
    def make(site, now):
        return [
            reading(
                site,
                HazardType.EARTHQUAKE,
                now,
                value=magnitude,
                source="USGS",
                key="us7000x",
                source_ref="us7000x",
                observed_at=NOW - timedelta(minutes=20),
            )
        ]

    make.hazard_type = HazardType.EARTHQUAKE
    return per_site(make)


def strike_feed(miles: float, at: datetime):
    def make(site, now):
        return [
            reading(
                site,
                HazardType.LIGHTNING_STRIKE,
                now,
                value=miles,
                source="lightning-replay",
                key=f"strike:{at.isoformat()}",
                observed_at=at,
                data_state=DataState.SIMULATED,
                simulated=True,
            )
        ]

    make.hazard_type = HazardType.LIGHTNING_STRIKE
    return per_site(make)


def count(session, model, *where) -> int:
    return session.scalar(select(func.count()).select_from(model).where(*where))


def test_one_refresh_stores_readings_and_scores_every_site(session) -> None:
    feeds = [none_feed(HazardType.FLOOD_ALERT), none_feed(HazardType.LIGHTNING_STRIKE)]
    result = refresh_all(session, NOW, feeds)
    assert result.sites == 2 and result.observations == 4
    assert result.failed_feeds == [] and result.failed_sites == []
    for site_id in SITES:
        assert count(session, db.Observation, db.Observation.site_id == site_id) == 2
        assert count(session, db.HazardScore, db.HazardScore.site_id == site_id) == 1
    assert all(r.fetched_at is not None for r in session.scalars(select(db.Observation)))


def test_fixture_earthquake_sends_one_notice_and_repeat_sends_none(session) -> None:
    feeds = [quake_feed(5.0)]
    first = refresh_all(session, NOW, feeds)
    second = refresh_all(session, NOW + timedelta(minutes=5), feeds)
    assert first.notices == 1  # one USGS event, shared by both sites
    assert second.notices == 0
    notice = session.scalars(select(db.HazardNotice)).one()
    assert notice.hazard_label == "earthquake" and notice.instruction is None


def test_repeat_refresh_upserts_the_same_reading(session) -> None:
    feeds = [quake_feed(2.0)]
    refresh_all(session, NOW, feeds)
    refresh_all(session, NOW + timedelta(minutes=5), feeds)
    assert count(session, db.Observation) == 2  # one per site, not one per refresh


def test_regional_factor_reaches_the_stored_score(session) -> None:
    refresh_all(session, NOW, [quake_feed(5.0)])
    score = session.scalars(select(db.HazardScore).where(db.HazardScore.site_id == "site-a")).one()
    factors = {f["factor"]: f["contribution"] for f in score.factor_contributions}
    assert factors["earthquake"] == 1.5


def test_raising_feed_is_unavailable_and_others_still_run(session) -> None:
    def broken(sites, now):
        raise RuntimeError("feed down")

    feeds = [Feed("USGS", HazardType.EARTHQUAKE, broken), none_feed(HazardType.FLOOD_ALERT)]
    result = refresh_all(session, NOW, feeds)
    assert result.failed_feeds == ["USGS earthquake"]
    states = dict(
        session.execute(
            select(db.Observation.hazard_type, db.Observation.data_state).where(
                db.Observation.site_id == "site-a"
            )
        ).all()
    )
    assert states == {"earthquake": "unavailable", "flood_alert": "observed"}


def test_feed_cache_failure_is_stored_as_unavailable_not_none(session) -> None:
    cache = FeedCache("NWS", HazardType.FLOOD_ALERT, timedelta(minutes=60), timedelta(hours=6))

    def fail(site, now):
        raise FeedError("no response")

    feed = Feed(
        "NWS",
        HazardType.FLOOD_ALERT,
        lambda sites, now: [o for s in sites for o in cache.refresh(s, now, fail)],
    )
    refresh_all(session, NOW, [feed])
    rows = list(session.scalars(select(db.Observation)))
    assert len(rows) == 2 and {r.data_state for r in rows} == {"unavailable"}
    assert all(r.id.startswith("unavailable:") for r in rows)


def test_lightning_triggers_and_feed_outage_never_clears(session) -> None:
    strike = NOW - timedelta(minutes=2)
    first = refresh_all(session, NOW, [strike_feed(5.0, strike)])
    assert first.lightning == {"site-a": "triggered", "site-b": "triggered"}

    def down(sites, now):
        raise RuntimeError("lightning down")

    later = NOW + timedelta(minutes=45)  # past the 30-minute all-clear
    held = refresh_all(session, later, [Feed("lightning", HazardType.LIGHTNING_STRIKE, down)])
    assert held.lightning["site-a"] == "held"
    alert = session.scalars(select(db.Alert).where(db.Alert.site_id == "site-a")).one()
    assert alert.state == "active"

    healthy = later + timedelta(minutes=5)
    cleared = refresh_all(session, healthy, [none_feed(HazardType.LIGHTNING_STRIKE)])
    assert cleared.failed_sites == []
    assert cleared.lightning["site-a"] == "cleared"


def test_one_site_failing_does_not_stop_the_others(session, monkeypatch) -> None:
    import app.services.refresh as refresh

    real = refresh.score_site

    def flaky(session, site_id, now, **kwargs):
        if site_id == "site-a":
            raise RuntimeError("boom")
        return real(session, site_id, now, **kwargs)

    monkeypatch.setattr(refresh, "score_site", flaky)
    result = refresh_all(session, NOW, [none_feed(HazardType.FLOOD_ALERT)])
    assert result.failed_sites == ["site-a"]
    assert count(session, db.HazardScore, db.HazardScore.site_id == "site-b") == 1


def test_loop_is_off_by_default(monkeypatch) -> None:
    import app.main as main
    import app.services.refresh as refresh
    from app.ingestion.settings import IngestionSettings

    monkeypatch.delenv("FEED_REFRESH_ENABLED", raising=False)
    get_ingestion_settings.cache_clear()
    try:
        # The code default, not a developer's backend/.env (which may turn the loop on).
        defaults = IngestionSettings(_env_file=None)
        assert defaults.feed_refresh_enabled is False
        monkeypatch.setattr(main, "get_ingestion_settings", lambda: defaults)
        started = []
        monkeypatch.setattr(refresh, "run_forever", lambda stop: started.append(1))
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
        assert started == []
    finally:
        get_ingestion_settings.cache_clear()


def test_history_rescore_ignores_expired_alerts_and_old_fetches(session) -> None:
    """T076: a report confirmation rescores from stored history, not the latest fetch."""
    from app.services.scoring import score_site

    flood = {"value": "Flood Warning"}

    def make(site, now):
        value = flood["value"]
        return [
            reading(
                site,
                HazardType.FLOOD_ALERT,
                now,
                value=value,
                source="NWS",
                key=f"{value}:{now.isoformat()}",
                fetched_at=now,
                label=value or "No active NWS flood alerts",
            )
        ]

    make.hazard_type = HazardType.FLOOD_ALERT
    feeds = [per_site(make), none_feed(HazardType.LIGHTNING_STRIKE)]
    refresh_all(session, NOW, feeds)
    flood["value"] = None  # the warning expired
    later = NOW + timedelta(hours=2)
    refresh_all(session, later, feeds)

    rescored = score_site(session, "site-a", later + timedelta(minutes=1))
    points = {f.factor: f for f in rescored.factor_contributions}
    assert points["flood"].contribution == 0.0
    assert points["flood"].data_state is DataState.OBSERVED


def test_demo_site_is_frozen_while_other_sites_get_live_data(session) -> None:
    session.add(
        db.Site(
            id="demo-everglades", name="Demo", lat=25.39, lon=-80.58,
            location_type="demo_site", source="Demo scenario (simulated)",
        )
    )  # fmt: skip
    session.commit()
    result = refresh_all(session, NOW, [none_feed(HazardType.FLOOD_ALERT)])
    assert result.sites == 2  # site-a and site-b; never the demo site
    assert count(session, db.Observation, db.Observation.site_id == "demo-everglades") == 0
    assert count(session, db.HazardScore, db.HazardScore.site_id == "demo-everglades") == 0
    assert count(session, db.Observation, db.Observation.site_id == "site-a") == 1


def test_one_upsert_stores_a_batch_and_keeps_the_last_duplicate(session) -> None:
    from app.services.refresh import store_observations

    site = session.get(db.Site, "site-a")
    first = reading(site, HazardType.EARTHQUAKE, NOW, value=2.0, key="eq1")
    later = first.model_copy(update={"value": 3.5, "fetched_at": NOW})
    other = reading(site, HazardType.EARTHQUAKE, NOW, value=1.0, key="eq2")
    store_observations(session, [first, later, other])
    session.commit()
    rows = {r.id: r.value for r in session.scalars(select(db.Observation))}
    assert rows == {first.id: "3.5", other.id: "1.0"}
    store_observations(session, [])  # nothing to write is fine
