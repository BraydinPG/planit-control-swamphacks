"""PlanIT Control FastAPI application.

All API routes live in this FastAPI app under backend/app/. Do not add a second API server.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import alerts, reports, sites
from app.db import validate_database_url
from app.gemini import router as gemini_router
from app.gemini.briefing_schedule import start_briefing_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load documented Tiger Data settings and start the 6 PM briefing schedule (T058A).

    The schedule runs in a background thread; startup never waits on Tiger Data or Gemini.
    """
    validate_database_url()
    briefings = start_briefing_scheduler()
    yield
    if briefings is not None:
        briefings.stop()


app = FastAPI(title="PlanIT Control API", version="0.1.0", lifespan=lifespan)
app.include_router(sites.router)
app.include_router(alerts.router)
app.include_router(reports.router)
app.include_router(gemini_router.router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check. Reports only that the process is up, not upstream feed status."""
    return {"status": "ok"}
