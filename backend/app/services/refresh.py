"""Feed refresh loop (T049B).

One refresh, for every site:

1. Fetch each feed adapter (`fetch(sites, now)`). Adapters handle freshness through
   `FeedCache`: a failed fetch returns stale readings or an unavailable placeholder.
2. Store the returned Observations. Each site's readings are written in one upsert on
   the (id, observed_at) key, so a cached reading fetched again updates its row instead
   of duplicating it, and a remote database costs one round trip per site, not one per
   reading.
3. Run the lightning stop-work rule (T046–T048), send source-detected potential notices
   (T049A), and rescore the site (T051), all from the readings just fetched.

Failure handling:
- A feed that raises outright, not through `FeedCache`, gets one unavailable placeholder
  per site, so its state reads "unknown", never "no hazard". The other feeds still run.
- A failure while processing one site rolls back that site's work and moves on.
- A feed outage can't clear a lightning alert. The rule holds it until a healthy reading.

Demo sites (`location_type="demo_site"`, the T069 seed) are skipped: live feeds never
overwrite their scripted, simulated scenario, which `python -m app.demo` controls. Every
other site gets live data.

The background loop starts from the FastAPI lifespan only when `FEED_REFRESH_ENABLED` is
true (off by default). For a one-shot refresh: `python -m app.services.refresh`.
"""

import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.db import models as db
from app.ingestion import unavailable_observation
from app.ingestion.base import SiteLike
from app.ingestion.settings import get_ingestion_settings
from app.schemas import HazardType, Observation
from app.services.alerts import apply_lightning_rule
from app.services.feed_notices import send_feed_notices
from app.services.scoring import score_site

log = logging.getLogger(__name__)

Fetch = Callable[[list[SiteLike], datetime], list[Observation]]


@dataclass(frozen=True)
class Feed:
    name: str  # source name for the unavailable placeholder
    hazard_type: HazardType
    fetch: Fetch


@dataclass
class RefreshResult:
    sites: int = 0
    observations: int = 0
    failed_feeds: list[str] = field(default_factory=list)
    failed_sites: list[str] = field(default_factory=list)
    notices: int = 0
    lightning: dict[str, str] = field(default_factory=dict)  # site id -> transition


def default_feeds() -> list[Feed]:
    """Every built adapter. Imported here so importing this module fetches nothing."""
    from app.ingestion import (
        earthquakes,
        flood_gauges,
        hurricanes,
        lightning,
        nws_alerts,
        nws_weather,
    )

    return [
        Feed("NWS", HazardType.WEATHER, nws_weather.fetch),
        Feed("NWS", HazardType.FLOOD_ALERT, nws_alerts.fetch),
        Feed("lightning", HazardType.LIGHTNING_STRIKE, lightning.fetch),
        Feed("NHC/NWS", HazardType.HURRICANE, hurricanes.fetch),
        Feed("USGS", HazardType.EARTHQUAKE, earthquakes.fetch),
        Feed("USGS", HazardType.FLOOD_GAUGE, flood_gauges.fetch),
    ]


# Sites the feeds never touch: the frozen, scripted demo scenario.
DEMO_LOCATION_TYPE = "demo_site"


def refresh_all(session: Session, now: datetime, feeds: list[Feed] | None = None) -> RefreshResult:
    feeds = default_feeds() if feeds is None else feeds
    live = db.Site.location_type != DEMO_LOCATION_TYPE
    sites = list(session.scalars(select(db.Site).where(live).order_by(db.Site.id)))
    # End the read before fetching (~20 min for every feed and site): an open transaction
    # holds locks that would stall migrations and every request queued behind them.
    session.commit()
    result = RefreshResult(sites=len(sites))

    by_site: dict[str, list[Observation]] = defaultdict(list)
    for feed in feeds:
        for o in _fetch(feed, sites, now, result):
            if o.site_id is not None:
                by_site[o.site_id].append(o)

    for site in sites:
        fetched = by_site.get(site.id, [])
        try:
            fetched = [_storable(o, now) for o in fetched]
            store_observations(session, fetched)
            session.commit()
            result.observations += len(fetched)
            lightning = apply_lightning_rule(session, site.id, fetched, now)
            result.lightning[site.id] = lightning.transition.value
            result.notices += len(send_feed_notices(session, site, fetched, now))
            score_site(session, site.id, now, observations=fetched)
        except Exception:
            session.rollback()
            log.exception("Refresh failed for site %s", site.id)
            result.failed_sites.append(site.id)
    return result


def _fetch(feed: Feed, sites: list[db.Site], now: datetime, result: RefreshResult):
    try:
        return feed.fetch(sites, now)
    except Exception:
        log.exception("Feed %s %s failed", feed.name, feed.hazard_type)
        result.failed_feeds.append(f"{feed.name} {feed.hazard_type}")
        label = f"{feed.name} {feed.hazard_type} unavailable (refresh failed)"
        return [unavailable_observation(s, feed.name, feed.hazard_type, label, now) for s in sites]


def _storable(o: Observation, now: datetime) -> Observation:
    """Give unavailable placeholders an id, and stamp `fetched_at` if the adapter didn't.

    Stale readings keep their original `fetched_at`, so they never look current.
    """
    update: dict = {}
    if not o.id:
        update["id"] = (
            f"unavailable:{o.source}:{o.hazard_type}:{o.site_id}:{o.observed_at.isoformat()}"
        )
    if o.fetched_at is None:
        update["fetched_at"] = now
    return o.model_copy(update=update) if update else o


def store_observations(session: Session, observations: list[Observation]) -> None:
    """Upsert readings in one statement on the (id, observed_at) key."""
    columns = [c.name for c in db.Observation.__table__.columns]
    rows: dict[tuple, dict] = {}
    for o in observations:  # the last copy of a key wins; one statement can't update twice
        row = observation_row(o)
        rows[(row.id, row.observed_at)] = {c: getattr(row, c) for c in columns}
    if not rows:
        return
    dialect = session.get_bind().dialect.name
    insert = postgresql_insert if dialect == "postgresql" else sqlite_insert
    statement = insert(db.Observation).values(list(rows.values()))
    keys = ("id", "observed_at")
    session.execute(
        statement.on_conflict_do_update(
            index_elements=list(keys),
            set_={c: statement.excluded[c] for c in columns if c not in keys},
        )
    )


def observation_row(o: Observation) -> db.Observation:
    return db.Observation(
        id=o.id,
        site_id=o.site_id,
        source=o.source,
        hazard_type=o.hazard_type,
        value=None if o.value is None else str(o.value),
        unit=o.unit,
        lat=o.lat,
        lon=o.lon,
        observed_at=o.observed_at,
        valid_at=o.valid_at,
        data_state=o.data_state,
        simulated=o.simulated,
        label=o.label,
        source_ref=o.source_ref,
        fetched_at=o.fetched_at,
    )


async def run_forever(stop: asyncio.Event) -> None:
    """Refresh, wait `FEED_REFRESH_SECONDS`, repeat until `stop` is set."""
    from app.db import get_session

    interval = get_ingestion_settings().feed_refresh_seconds

    def once() -> RefreshResult:
        with get_session() as session:
            return refresh_all(session, datetime.now(UTC))

    while not stop.is_set():
        try:
            result = await asyncio.to_thread(once)
            log.info("Feed refresh: %s", result)
        except Exception:
            log.exception("Feed refresh failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            pass


def main() -> None:
    from app.db import get_session
    from app.db.init import load_env_file

    load_env_file()  # like `python -m app.demo`: read backend/.env (DATABASE_URL, feeds)
    logging.basicConfig(level=logging.INFO)
    with get_session() as session:
        print(refresh_all(session, datetime.now(UTC)))


if __name__ == "__main__":
    main()
