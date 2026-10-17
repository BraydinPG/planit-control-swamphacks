"""Shared types for ingestion adapters."""

from datetime import datetime
from typing import Protocol

from app.schemas import DataState, HazardType, Observation


class SiteLike(Protocol):
    """Anything with a site id and coordinates: a DB `Site`, a `SiteSummary`, or a test stub."""

    id: str
    lat: float
    lon: float


class FeedError(Exception):
    """A feed could not produce a trustworthy result. Callers mark the feed unavailable."""


def unavailable_observation(
    site: SiteLike, source: str, hazard_type: HazardType, label: str, now: datetime
) -> Observation:
    """Placeholder that says "we don't know", never "no hazard"."""
    return Observation(
        source=source,
        hazard_type=hazard_type,
        value=None,
        lat=site.lat,
        lon=site.lon,
        observed_at=now,
        data_state=DataState.UNAVAILABLE,
        site_id=site.id,
        label=label,
    )
