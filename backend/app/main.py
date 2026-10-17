"""PlanIT Control FastAPI application.

All API routes live in this FastAPI app under backend/app/. Do not add a second API server.
"""

from fastapi import FastAPI

app = FastAPI(title="PlanIT Control API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check. Reports only that the process is up, not upstream feed status."""
    return {"status": "ok"}
