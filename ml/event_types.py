"""Explicit targets and source semantics; a parsed type is not model support."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EventType:
    category: str
    horizons: tuple[int, ...] = (6, 12, 24)
    candidate: bool = False
    limitation: str = "NOAA regional recorded interval, not verified worksite exposure or safety."


NOAA_EVENT_TYPES = {
    "Flood": EventType("flood", candidate=True),
    "Flash Flood": EventType("flash_flood", (1, 3, 6), True),
    "Thunderstorm Wind": EventType("thunderstorm_wind", limitation="Damage/point reports do not establish a continuous thunderstorm lifetime or intensity trajectory."),
    "High Wind": EventType("high_wind", candidate=True),
    "Strong Wind": EventType("strong_wind", (1, 3, 6), True),
    "Hurricane (Typhoon)": EventType("tropical_cyclone", limitation="Regional NOAA episodes are not cyclone identities; use NHC storm-grouped tracks/advisories."),
    "Tropical Storm": EventType("tropical_cyclone", limitation="Regional reports cannot replace NHC storm identity or advisory-time measurements."),
    "Tropical Depression": EventType("tropical_cyclone", limitation="Regional reports cannot replace NHC storm identity or advisory-time measurements."),
    "Excessive Heat": EventType("heat", limitation="Administrative reporting intervals are not measured station heat-index threshold exceedances."),
    "Heat": EventType("heat", limitation="Use separately derived observed station threshold episodes; NOAA administrative duration is not local heat exposure."),
    "Heavy Rain": EventType("heavy_rain", (1, 3, 6), True),
    "Wildfire": EventType("wildfire", limitation="No stable incident identity or containment time series in these NOAA rows; recorded end is not containment."),
    "Winter Storm": EventType("winter_storm", candidate=True),
    "Ice Storm": EventType("ice_storm", candidate=True),
    "Heavy Snow": EventType("heavy_snow", candidate=True),
}


def event_slug(event_type: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "_", event_type.lower()).strip("_")


def model_version_for(event_type: str) -> str:
    if event_type == "Flood":
        return "noaa-flood-pooled-logistic-v2"
    return f"active-{event_slug(event_type)}-pooled-logistic-v1"
