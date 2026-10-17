"""Create the Tiger Data schema and hypertables.

Run from backend/:

    python -m app.db.init
"""

import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.db.connection import get_database_url, to_driver_url
from app.db.models import Base

# Columns added after a table was first created. `create_all` never alters existing
# tables, so each runs as an idempotent ALTER.
ADDED_COLUMNS = (
    ("sites", "timezone", "VARCHAR"),
    ("crew_reports", "location_source", "VARCHAR"),  # T053A
    ("crew_reports", "location_accuracy_m", "DOUBLE PRECISION"),
    ("crew_reports", "site_distance_miles", "DOUBLE PRECISION"),
    ("briefings", "risk_score", "DOUBLE PRECISION"),  # T058C
    ("briefings", "data_completeness", "DOUBLE PRECISION"),
)

HYPERTABLES = (
    ("observations", "observed_at"),
    ("alerts", "triggered_at"),
    ("audit_events", "created_at"),
)


def load_env_file() -> None:
    """Load backend/.env without overriding variables already set in the process."""
    path = Path(__file__).resolve().parents[2] / ".env"
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def initialize_database(engine: Engine | None = None) -> None:
    """Enable TimescaleDB, create tables, and convert the time-ordered tables."""
    if engine is None:
        load_env_file()
        engine = create_engine(to_driver_url(get_database_url()), pool_pre_ping=True)
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
    with engine.begin() as connection:
        Base.metadata.create_all(connection)
        for table, column, sql_type in ADDED_COLUMNS:
            connection.execute(
                text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {sql_type}")
            )
        for table, column in HYPERTABLES:
            connection.execute(
                text(f"SELECT create_hypertable('{table}', '{column}', if_not_exists => TRUE)")
            )


def main() -> None:
    try:
        initialize_database()
    except Exception as exc:
        message = str(exc)
        for secret in (os.environ.get("DATABASE_URL", ""),):
            if secret:
                message = message.replace(secret, "DATABASE_URL")
                message = message.replace(to_driver_url(secret), "DATABASE_URL")
        raise SystemExit(message) from None
    print("Database initialized. Hypertables: observations, alerts, audit_events.")


if __name__ == "__main__":
    main()
