"""FORESITE FastAPI application.

All API routes live in this FastAPI app under backend/app/. Do not add a second API server.
"""

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.api import alerts, hazards, reports, sites, species, teams
from app.db import validate_database_url
from app.gemini import router as gemini_router
from app.gemini.briefing_schedule import start_briefing_scheduler
from app.ingestion.settings import get_ingestion_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load documented Tiger Data settings and start the background jobs.

    The 6 PM briefing schedule (T058A) runs in a background thread. The feed refresh loop
    (T049B) starts only when FEED_REFRESH_ENABLED is true. Startup never waits on Tiger
    Data, the feeds, or Gemini.
    """
    validate_database_url()
    briefings = start_briefing_scheduler()
    stop = asyncio.Event()
    task = None
    if get_ingestion_settings().feed_refresh_enabled:
        from app.services.refresh import run_forever

        task = asyncio.create_task(run_forever(stop))
    try:
        yield
    finally:
        if briefings is not None:
            briefings.stop()
        if task is not None:
            # Don't wait for an in-flight refresh: its thread finishes or dies with the process.
            stop.set()
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


app = FastAPI(title="FORESITE API", version="0.1.0", lifespan=lifespan)
app.include_router(sites.router)
app.include_router(alerts.router)
app.include_router(reports.router)
app.include_router(hazards.router)
app.include_router(species.router)
app.include_router(teams.router)
app.include_router(gemini_router.router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check. Reports only that the process is up, not upstream feed status."""
    return {"status": "ok"}
