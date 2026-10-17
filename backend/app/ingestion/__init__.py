"""Live-feed ingestion adapters. Each adapter exposes `fetch(sites, now) -> list[Observation]`.

Rudra owns the NWS feeds and the shared cache; Braydin owns the other adapters (AGENTS.md).
"""

from app.ingestion.base import FeedError, SiteLike, unavailable_observation
from app.ingestion.cache import FeedCache

__all__ = ["FeedCache", "FeedError", "SiteLike", "unavailable_observation"]
