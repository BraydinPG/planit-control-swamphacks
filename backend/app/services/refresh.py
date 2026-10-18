"""Feed refresh loop (T049B).

One refresh, for every site:

1. Fetch each feed adapter (`fetch(sites, now)`). Adapters handle freshness through
   `FeedCache`: a failed fetch returns stale readings or an unavailable placeholder.
2. Store the returned Observations. Each site's readings are written in one upsert on
   the (id, observed_at) key, so a cached reading fetched again updates its row instead
   of duplicating it, and a remote database costs one round trip per site, not one per
   reading.
3. Run the stop-work rules (lightning T046–T048, prototype tiered rules T049C), send
   source-detected potential notices (T049A), and rescore the site (T051), all from the
   readings just fetched.

Failure handling:
- A feed that raises outright, not through `FeedCache`, gets one unavailable placeholder
  per site, so its state reads "unknown", never "no hazard". The other feeds still run.
- A failure while processing one site rolls back that site's work and moves on.
- A feed outage can't clear a stop-work alert. The rule holds it until a healthy reading.

Demo sites (`location_type="demo_site"`, the T069 seed) are skipped: live feeds never
overwrite their scripted, simulated scenario, which `python -m app.demo` controls. Every
other site gets live data.

The background loop starts from the FastAPI lifespan only when `FEED_REFRESH_ENABLED` is
true (off by default). For a one-shot refresh: `python -m app.services.refresh`.
"""

import argparse
import asyncio
import json
import logging
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Event

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.db import models as db
from app.ingestion import runtime, unavailable_observation
from app.ingestion.base import SiteLike
from app.ingestion.settings import get_ingestion_settings
from app.schemas import AlertRule, HazardType, Observation
from app.services.alerts import apply_stop_work_rules
from app.services.feed_notices import send_feed_notices
from app.services.scoring import score_site

log = logging.getLogger(__name__)

Fetch = Callable[[list[SiteLike], datetime], list[Observation]]


@dataclass(frozen=True)
class Feed:
    name: str  # source name for the unavailable placeholder
    hazard_type: HazardType
    fetch: Fetch
    # Internal coverage expectations for adapters that emit more than one source/kind.
    outputs: tuple[tuple[str, HazardType], ...] = ()


@dataclass
class RefreshResult:
    sites: int = 0
    observations: int = 0
    failed_feeds: list[str] = field(default_factory=list)
    failed_sites: list[str] = field(default_factory=list)
    notices: int = 0
    lightning: dict[str, str] = field(default_factory=dict)  # site id -> transition
    # site id -> {prototype stop-work rule -> transition}, only rules that changed or held
    stop_work: dict[str, dict[str, str]] = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)


def default_feeds() -> list[Feed]:
    """Every built adapter. Imported here so importing this module fetches nothing."""
    from app.ingestion import (
        earthquakes,
        flood_gauges,
        hurricanes,
        lightning,
        nws_alerts,
        nws_weather,
        severe_storms,
    )

    return [
        Feed(
            "NWS",
            HazardType.WEATHER,
            nws_weather.fetch,
            (("NWS", HazardType.WEATHER), ("NWS", HazardType.FORECAST)),
        ),
        Feed("NWS", HazardType.FLOOD_ALERT, nws_alerts.fetch),
        Feed("NWS", HazardType.SEVERE_STORM, severe_storms.fetch),
        Feed("lightning", HazardType.LIGHTNING_STRIKE, lightning.fetch),
        Feed(
            "NHC/NWS",
            HazardType.HURRICANE,
            hurricanes.fetch,
            (("NHC", HazardType.HURRICANE), ("NWS", HazardType.HURRICANE)),
        ),
        Feed("USGS", HazardType.EARTHQUAKE, earthquakes.fetch),
        Feed("USGS", HazardType.FLOOD_GAUGE, flood_gauges.fetch),
    ]


# Sites the feeds never touch: the frozen, scripted demo scenario.
DEMO_LOCATION_TYPE = "demo_site"


def refresh_all(
    session: Session, now: datetime, feeds: list[Feed] | None = None, *, cancel: Event | None = None
) -> RefreshResult:
    settings = get_ingestion_settings()
    with runtime.round_scope(settings.feed_round_budget_seconds, cancel) as run:
        started = time.monotonic()
        result = _refresh_all(session, now, feeds, run)
        run.phases["total"] = time.monotonic() - started
        result.metrics.update(run.report())
        runtime.event(
            "feed_round_complete",
            sites=result.sites,
            failed_sites=len(result.failed_sites),
            duration_seconds=run.phases["total"],
            coverage=result.metrics.get("coverage", {}),
        )
        return result


def _refresh_all(session, now, feeds, run):
    feeds = default_feeds() if feeds is None else feeds
    live = db.Site.location_type != DEMO_LOCATION_TYPE
    rows = list(session.scalars(select(db.Site).where(live).order_by(db.Site.id)))
    sites = [runtime.SiteSnapshot(s.id, s.lat, s.lon, s.region) for s in rows]
    # End the read before network I/O: an open transaction
    # holds locks that would stall migrations and every request queued behind them.
    session.commit()
    result = RefreshResult(sites=len(sites))
    invalid = [s for s in sites if not runtime.valid_site(s)]
    result.failed_sites.extend(s.id for s in invalid)
    for site in invalid:
        runtime.event(
            "feed_invalid_site",
            failure=True,
            site_id=site.id,
            region=runtime.region_of(site),
            final_state="unavailable",
            exception_type="InvalidCoordinates",
        )
    sites = [s for s in sites if runtime.valid_site(s)]
    result.metrics.update(sites_valid=len(sites), fully_processed_sites=0)

    by_site: dict[str, list[Observation]] = defaultdict(list)
    feed_seconds = {}
    for feed in feeds:
        started = time.monotonic()
        with runtime.labels(
            feed=f"{feed.name}/{feed.hazard_type.value}",
            region="shared",
            affected_group="all_live_sites",
        ):
            observations = _fetch(feed, sites, now, result)
        feed_seconds[f"{feed.name}/{feed.hazard_type.value}"] = time.monotonic() - started
        for o in observations:
            if o.site_id is not None:
                by_site[o.site_id].append(o)
    run.phases["fetch"] = sum(feed_seconds.values())
    result.metrics["feed_seconds"] = feed_seconds
    result.metrics["coverage"] = _coverage(by_site)
    result.metrics["complete_feed_sites"] = sum(
        all(o.data_state.value not in {"stale", "unavailable"} for o in by_site.get(s.id, []))
        and bool(by_site.get(s.id))
        for s in sites
    )
    result.metrics["partial_feed_sites"] = len(sites) - result.metrics["complete_feed_sites"]

    for site in sites:
        if run.cancel.is_set():
            result.metrics["cancelled"] = True
            break
        fetched = by_site.get(site.id, [])
        try:
            current = session.get(db.Site, site.id)
            if current is None or (current.lat, current.lon) != (site.lat, site.lon):
                raise ValueError("Site changed during retrieval")
            fetched = [_storable(o, now) for o in fetched]
            started = time.monotonic()
            store_observations(session, fetched)
            session.commit()
            run.phases["persistence"] += time.monotonic() - started
            result.observations += len(fetched)
            started = time.monotonic()
            outcomes = apply_stop_work_rules(session, current, fetched, now)
            result.lightning[site.id] = outcomes[AlertRule.LIGHTNING_STOP_WORK].transition.value
            changed = {
                rule.value: r.transition.value
                for rule, r in outcomes.items()
                if rule is not AlertRule.LIGHTNING_STOP_WORK
                and r.transition.value not in ("none", "unchanged")
            }
            if changed:
                result.stop_work[site.id] = changed
            result.notices += len(send_feed_notices(session, current, fetched, now))
            run.phases["alerts_and_notices"] += time.monotonic() - started
            started = time.monotonic()
            score_site(session, site.id, now, observations=fetched)
            run.phases["scoring"] += time.monotonic() - started
            result.metrics["fully_processed_sites"] += 1
        except Exception as exc:
            session.rollback()
            runtime.event(
                "feed_persistence_failed",
                failure=True,
                site_id=site.id,
                region=runtime.region_of(site),
                exception_type=type(exc).__name__,
            )
            result.failed_sites.append(site.id)
    return result


def _fetch(feed: Feed, sites: list[SiteLike], now: datetime, result: RefreshResult):
    try:
        observations = list(feed.fetch(sites, now))
        allowed = {s.id for s in sites}
        if any(not isinstance(o, Observation) or o.site_id not in allowed for o in observations):
            raise ValueError("Feed returned an invalid site association")
        covered = {(o.site_id, o.source, o.hazard_type) for o in observations}
        observations += [
            unavailable_observation(
                s, source, kind, "Feed returned no result; conditions unknown", now
            )
            for s in sites
            for source, kind in (feed.outputs or ((feed.name, feed.hazard_type),))
            if (s.id, source, kind) not in covered
            # Custom single-output adapters may use a more specific source name.
            and (feed.outputs or not any(o.site_id == s.id for o in observations))
        ]
        return observations
    except Exception as exc:
        runtime.event(
            "feed_failed",
            failure=True,
            provider=feed.name,
            hazard_type=feed.hazard_type.value,
            exception_type=type(exc).__name__,
        )
        result.failed_feeds.append(f"{feed.name} {feed.hazard_type}")
        return [
            unavailable_observation(s, source, kind, "Feed unavailable (refresh failed)", now)
            for s in sites
            for source, kind in (feed.outputs or ((feed.name, feed.hazard_type),))
        ]


def _coverage(by_site):
    result = defaultdict(lambda: defaultdict(int))
    for rows in by_site.values():
        grouped = defaultdict(list)
        for row in rows:
            grouped[f"{row.source}/{row.hazard_type.value}"].append(row)
        for key, items in grouped.items():
            states = {o.data_state.value for o in items}
            if any(o.label and "Not covered by this provider" in o.label for o in items):
                status = "not_covered"
            elif states <= {"unavailable"}:
                status = "unavailable"
            elif states <= {"stale", "unavailable"}:
                status = "stale"
            elif states & {"stale", "unavailable"}:
                status = "partial"
            elif all(o.value is None for o in items):
                status = "no_qualifying_result"
            else:
                status = "current"
            result[key][status] += 1
    return {k: dict(v) for k, v in result.items()}


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
    cancel = Event()

    def once() -> RefreshResult:
        with get_session() as session:
            return refresh_all(session, datetime.now(UTC), cancel=cancel)

    while not stop.is_set():
        try:
            result = await asyncio.to_thread(once)
            log.info(
                "Feed refresh: sites=%s observations=%s failed_sites=%s failed_feeds=%s",
                result.sites,
                result.observations,
                len(result.failed_sites),
                len(result.failed_feeds),
            )
        except asyncio.CancelledError:
            cancel.set()
            raise
        except Exception as exc:
            runtime.event("feed_round_failed", failure=True, exception_type=type(exc).__name__)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            pass


def main() -> None:
    from app.db import get_session
    from app.db.init import load_env_file

    load_env_file()  # like `python -m app.demo`: read backend/.env (DATABASE_URL, feeds)
    parser = argparse.ArgumentParser(
        description="One manually invoked live refresh; never starts a scheduler"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Show non-secret configuration readiness without connecting or writing",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        help="Save structured per-feed metrics; never contains credentials",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    settings = get_ingestion_settings()
    import os

    from sqlalchemy.engine import make_url

    database = os.environ.get("DATABASE_URL")
    ready = {
        "database_configured": bool(database),
        "feed_refresh_enabled": settings.feed_refresh_enabled,
        "nws_user_agent_configured": bool(settings.nws_user_agent),
    }
    if database:
        try:
            url = make_url(database)
            ready["target"] = {
                "driver": url.drivername,
                "host": url.host,
                "port": url.port,
                "database": url.database,
            }
        except Exception:
            ready["database_configured"] = False
            ready["configuration_error"] = "Invalid database URL"
    print(json.dumps({"preflight": ready}))
    if args.check_only:
        return
    if settings.feed_refresh_enabled:
        raise SystemExit(
            "Disable FEED_REFRESH_ENABLED before a manual refresh; coordinate the single job owner."
        )
    if not ready["database_configured"]:
        raise SystemExit("DATABASE_URL is missing or invalid; no refresh performed.")
    try:
        with get_session() as session:
            result = refresh_all(session, datetime.now(UTC))
    except Exception as exc:
        runtime.event("feed_round_failed", failure=True, exception_type=type(exc).__name__)
        raise SystemExit("Refresh failed; see sanitized feed diagnostics.") from None
    report = asdict(result)
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    compact = {
        **report,
        "metrics": {k: v for k, v in result.metrics.items() if k != "site_feed_outcomes"},
    }
    print(json.dumps(compact))


if __name__ == "__main__":
    main()
