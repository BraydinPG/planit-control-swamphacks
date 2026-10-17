"""Database session for other routes to import.

The engine is created on first use, so importing this module does not connect.
"""

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.connection import get_database_url, to_driver_url


@lru_cache
def get_engine() -> Engine:
    return create_engine(to_driver_url(get_database_url()), pool_pre_ping=True)


def get_session() -> Session:
    """Open a session. The caller closes it."""
    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return factory()
