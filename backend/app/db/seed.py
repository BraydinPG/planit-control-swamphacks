"""Prepare an empty Tiger Data database for later demo data.

Run from backend/:

    python -m app.db.seed

This creates the schema if needed and inserts no sites, observations, or demo
scenario. Rudra fills those contents in T069.
"""

import os

from sqlalchemy import create_engine, text

from app.db.connection import get_database_url, to_driver_url
from app.db.init import initialize_database, load_env_file


def seed_database() -> None:
    """Ensure the schema exists and leave demo rows for Rudra."""
    load_env_file()
    initialize_database()
    engine = create_engine(to_driver_url(get_database_url()), pool_pre_ping=True)
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def main() -> None:
    try:
        seed_database()
    except Exception as exc:
        message = str(exc)
        secret = os.environ.get("DATABASE_URL", "")
        if secret:
            message = message.replace(secret, "DATABASE_URL")
            message = message.replace(to_driver_url(secret), "DATABASE_URL")
        raise SystemExit(message) from None
    print("Database seeded with no demo rows. Demo scenario contents are left for Rudra.")


if __name__ == "__main__":
    main()
