"""PlanIT Control FastAPI application.

All API routes live in this FastAPI app under backend/app/. Do not add a second API server.
"""

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.api import alerts, hazards, reports, sites
from app.db import validate_database_url
from app.ingestion.settings import get_ingestion_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load documented Tiger Data settings. Do not open a connection here.

    Starts the feed refresh loop (T049B) only when FEED_REFRESH_ENABLED is true.
    """
    validate_database_url()
    if not get_ingestion_settings().feed_refresh_enabled:
        yield
        return
    from app.services.refresh import run_forever

    stop = asyncio.Event()
    task = asyncio.create_task(run_forever(stop))
    try:
        yield
    finally:
        # Don't wait for an in-flight refresh: its thread finishes or dies with the process.
        stop.set()
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="PlanIT Control API", version="0.1.0", lifespan=lifespan)
app.include_router(sites.router)
app.include_router(alerts.router)
app.include_router(reports.router)
app.include_router(hazards.router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check. Reports only that the process is up, not upstream feed status."""
    return {"status": "ok"}
