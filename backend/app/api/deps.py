"""Shared route dependencies. Tests override these with `app.dependency_overrides`."""

from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db import DatabaseSettingsError, get_session


def get_db() -> Iterator[Session]:
    """One Tiger Data session per request, closed afterwards.

    Without a usable DATABASE_URL, routes answer 503 instead of crashing.
    """
    try:
        session = get_session()
    except DatabaseSettingsError as exc:
        raise HTTPException(status_code=503, detail="Database is not configured") from exc
    try:
        yield session
    finally:
        session.close()


def get_now() -> datetime:
    """Request time, used for freshness. Overridable so tests are deterministic."""
    return datetime.now(UTC)
