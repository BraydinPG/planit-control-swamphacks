"""Read and check the Tiger Data URL without opening a connection."""

import os
from urllib.parse import parse_qs, urlparse

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "host.docker.internal"})
_ACCEPTED_SSLMODES = frozenset({"require", "verify-ca", "verify-full"})


class DatabaseSettingsError(ValueError):
    """DATABASE_URL is missing or does not meet the Tiger Cloud SSL rule."""


def get_database_url() -> str:
    """Return DATABASE_URL after applying the Tiger Cloud SSL rule."""
    raw = os.environ.get("DATABASE_URL", "").strip()
    if not raw:
        raise DatabaseSettingsError(
            "DATABASE_URL is not set. Copy backend/.env.example to backend/.env."
        )
    return _validate(raw)


def validate_database_url() -> str | None:
    """Check DATABASE_URL when it is set. An unset URL does not block app startup."""
    raw = os.environ.get("DATABASE_URL", "").strip()
    if not raw:
        return None
    return _validate(raw)


def _validate(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in {"postgresql", "postgres"}:
        raise DatabaseSettingsError("DATABASE_URL must use the postgresql scheme.")
    host = (parsed.hostname or "").lower()
    if not host:
        raise DatabaseSettingsError("DATABASE_URL must include a host.")
    if host in _LOCAL_HOSTS:
        return url
    sslmode = parse_qs(parsed.query).get("sslmode", [""])[0].lower()
    if sslmode not in _ACCEPTED_SSLMODES:
        raise DatabaseSettingsError(
            "Tiger Cloud DATABASE_URL must include sslmode=require. "
            "verify-ca and verify-full are also accepted."
        )
    return url


def to_driver_url(url: str) -> str:
    """Use the psycopg driver without changing the URL stored in the environment."""
    if url.startswith("postgresql+psycopg://"):
        return url
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url
