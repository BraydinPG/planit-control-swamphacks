"""Prototype hurricane and earthquake rules (T049A).

Hurricanes and earthquakes are regional events near a site, not on-site observations.
Both rules read Braydin's `hurricane` and `earthquake` Observations
(`app.ingestion.hurricanes`, `app.ingestion.earthquakes`) and never call a feed.

Hurricane:
- An NWS Hurricane Warning or Tropical Storm Warning for the site point qualifies.
  Watches are shown but don't qualify.
- An NHC active storm whose center is within `hurricane_storm_distance_miles` (50 mi)
  of the site qualifies. Exactly the distance qualifies.

Earthquake:
- A USGS event with magnitude at or above `earthquake_min_magnitude` (4.0) whose
  epicenter is within `earthquake_distance_miles` (25 mi) of the site qualifies.

All distances, magnitudes, and points are prototype settings in `RuleSettings`, not
official policy.

Each qualifying reading is a `Detection`. `app.services.feed_notices` turns detections
into "potential {hazard}" notices. Each rule also gives one score factor.

Data states:
- "None" readings (`value=None`) and unavailable placeholders never qualify.
- Stale readings still count in the score, labeled stale, so old bad news isn't ignored.
  They don't create new notices: a notice was already sent when the reading was fresh.
- A factor appears only when its feed has reported and the caller passes the site. A
  feed that never ran adds no factor, and these P1 feeds don't count toward
  `data_completeness`.
"""

from dataclasses import dataclass

from app.ingestion.base import SiteLike
from app.ingestion.geo import distance_miles
from app.rules.settings import RuleSettings
from app.schemas import DataState, FactorContribution, HazardType, Observation

HURRICANE = "hurricane"
EARTHQUAKE = "earthquake"
NHC = "NHC"
NWS = "NWS"
TROPICAL_WARNINGS = frozenset({"Hurricane Warning", "Tropical Storm Warning"})


@dataclass(frozen=True)
class Detection:
    """One qualifying reading. `key` identifies the event for notice deduplication."""

    hazard: str  # HURRICANE or EARTHQUAKE
    hazard_label: str  # used in "potential {hazard_label}"
    key: str
    observation: Observation
    distance_miles: float | None
    lat: float  # notice center
    lon: float


def hurricane_detections(
    site: SiteLike, observations: list[Observation], settings: RuleSettings
) -> list[Detection]:
    found: list[Detection] = []
    for o in _readings(site.id, observations, HazardType.HURRICANE):
        if o.data_state is DataState.UNAVAILABLE:
            continue
        if o.source == NWS and o.value in TROPICAL_WARNINGS:
            label = "hurricane" if o.value == "Hurricane Warning" else "tropical storm"
            key = f"nws-tropical:{o.source_ref or o.id}:{site.id}"
            found.append(Detection(HURRICANE, label, key, o, 0.0, site.lat, site.lon))
        elif o.source == NHC and _number(o.value) is not None:
            miles = distance_miles(site.lat, site.lon, o.lat, o.lon)
            if miles <= settings.hurricane_storm_distance_miles:
                key = f"nhc:{o.source_ref or o.id}:{site.id}"
                found.append(Detection(HURRICANE, "hurricane", key, o, miles, o.lat, o.lon))
    return found


def earthquake_detections(
    site: SiteLike, observations: list[Observation], settings: RuleSettings
) -> list[Detection]:
    found: list[Detection] = []
    for o in _readings(site.id, observations, HazardType.EARTHQUAKE):
        if o.data_state is DataState.UNAVAILABLE:
            continue
        magnitude = _number(o.value)
        if magnitude is None or magnitude < settings.earthquake_min_magnitude:
            continue
        miles = distance_miles(site.lat, site.lon, o.lat, o.lon)
        if miles <= settings.earthquake_distance_miles:
            # The epicenter is shared by every site, so one notice per event.
            key = f"usgs-eq:{o.source_ref or o.id}"
            found.append(Detection(EARTHQUAKE, "earthquake", key, o, miles, o.lat, o.lon))
    return found


def hurricane_factor(
    site: SiteLike | None, observations: list[Observation], settings: RuleSettings
) -> FactorContribution | None:
    if site is None:
        return None  # distance to the site is unknown, so the rule can't run
    readings = _readings(site.id, observations, HazardType.HURRICANE)
    if not readings:
        return None
    detections = hurricane_detections(site, observations, settings)
    if detections:
        best = max(detections, key=lambda d: (d.distance_miles == 0.0, d.observation.observed_at))
        o = best.observation
        where = "for the site" if o.source == NWS else f"{best.distance_miles:.0f} mi from site"
        return _factor(
            HURRICANE,
            f"{o.value if o.source == NWS else (o.label or 'NHC storm')} {where} "
            f"(prototype {settings.hurricane_storm_distance_miles:g} mi rule)",
            settings.hurricane_points,
            o,
            value=best.distance_miles,
            unit="mi",
        )
    return _quiet(HURRICANE, "Hurricane", readings)


def earthquake_factor(
    site: SiteLike | None, observations: list[Observation], settings: RuleSettings
) -> FactorContribution | None:
    if site is None:
        return None  # distance to the site is unknown, so the rule can't run
    readings = _readings(site.id, observations, HazardType.EARTHQUAKE)
    if not readings:
        return None
    detections = earthquake_detections(site, observations, settings)
    if detections:
        best = max(detections, key=lambda d: (d.observation.value, d.observation.observed_at))
        o = best.observation
        return _factor(
            EARTHQUAKE,
            f"M{float(o.value):.1f} earthquake {best.distance_miles:.0f} mi from site "
            f"(prototype M{settings.earthquake_min_magnitude:g}+ within "
            f"{settings.earthquake_distance_miles:g} mi rule)",
            settings.earthquake_points,
            o,
            value=float(o.value),
            unit=o.unit,
        )
    return _quiet(EARTHQUAKE, "Earthquake", readings)


def _readings(
    site_id: str, observations: list[Observation], hazard_type: HazardType
) -> list[Observation]:
    """This site's readings of one hazard type, including unavailable placeholders."""
    return [
        o for o in observations if o.hazard_type == hazard_type and o.site_id in (None, site_id)
    ]


def _quiet(factor: str, name: str, readings: list[Observation]) -> FactorContribution:
    usable = [o for o in readings if o.data_state is not DataState.UNAVAILABLE]
    if not usable:
        return FactorContribution(
            factor=factor,
            label=f"{name} status unknown (feed unavailable)",
            contribution=0.0,
            source=readings[0].source,
            data_state=DataState.UNAVAILABLE,
            is_prototype=True,
        )
    latest = max(usable, key=lambda o: o.observed_at)
    label = latest.label if latest.value is None else f"No qualifying {name.lower()} near site"
    return _factor(factor, label or f"No qualifying {name.lower()}", 0.0, latest)


def _factor(
    factor: str,
    label: str,
    points: float,
    o: Observation,
    value: float | str | None = None,
    unit: str | None = None,
) -> FactorContribution:
    return FactorContribution(
        factor=factor,
        label=label,
        contribution=points,
        value=value,
        unit=unit,
        source=o.source,
        observed_at=o.observed_at,
        data_state=o.data_state,
        is_prototype=True,
        evidence_id=o.id,
    )


def _number(value: object) -> float | None:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return None
