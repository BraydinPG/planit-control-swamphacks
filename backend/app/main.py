"""PlanIT Control FastAPI application.

All API routes live in this FastAPI app under backend/app/. Do not add a second API server.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import alerts, sites
from app.db import validate_database_url


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load documented Tiger Data settings. Do not open a connection here."""
    validate_database_url()
    yield


app = FastAPI(title="PlanIT Control API", version="0.1.0", lifespan=lifespan)
app.include_router(sites.router)
app.include_router(alerts.router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check. Reports only that the process is up, not upstream feed status."""
    return {"status": "ok"}
