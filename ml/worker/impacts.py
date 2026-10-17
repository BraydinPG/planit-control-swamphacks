"""Source-grounded site conditions, with no learned local hazard probabilities."""

import hashlib

from ml.worker.evidence import canonical_value, normalize_batch
from ml.worker.schema import Condition, Evidence, SiteContext, SiteHazard


def _derived_heat(assessments):
    from ml.sources.stations import heat_index_f

    additions = []
    temperatures = [
        a
        for a in assessments
        if a.accepted and a.evidence.variable == "temperature" and a.evidence.hazard == "heat"
    ]
    humidities = [
        a for a in assessments if a.accepted and a.evidence.variable == "relative_humidity"
    ]
    for temperature in temperatures:
        t = temperature.evidence
        for humidity in humidities:
            h = humidity.evidence
            same = (
                t.source_version == h.source_version
                and t.source_record_id == h.source_record_id
                and t.publisher == h.publisher
                and t.method == h.method
                and t.valid_from == h.valid_from
                and t.valid_to == h.valid_to
                and t.issued_at == h.issued_at
                and t.observed_at == h.observed_at
                and t.footprint == h.footprint
            )
            if not same:
                continue
            celsius, _ = canonical_value(t)
            fahrenheit = celsius * 1.8 + 32
            if not 80 <= fahrenheit <= 110 or not 0 <= h.value <= 100:
                continue
            version = "NWS-Rothfusz-shade-80to110F-v1"
            identifier = hashlib.sha256(
                (t.evidence_id + ":" + h.evidence_id + ":" + version).encode()
            ).hexdigest()[:24]
            derived = Evidence.model_validate(
                {
                    **t.model_dump(),
                    "evidence_id": identifier,
                    "publisher": "PlanIT calculation from " + t.publisher,
                    "original_type": "derived_NWS_heat_index",
                    "variable": "heat_index",
                    "value": heat_index_f(fahrenheit, h.value),
                    "unit": "F",
                    "value_basis": "derived",
                    "derived_from_evidence_ids": [t.evidence_id, h.evidence_id],
                    "computation_version": version,
                    "is_fixture": t.is_fixture or h.is_fixture,
                }
            )
            additions.append(temperature.model_copy(update={"evidence": derived}))
    return additions


EXPECTED = {
    "Flood": ("rain", "flood_context"),
    "Flash Flood": ("rain", "flood_context"),
    "Heavy Rain": ("rain", "flood_context"),
    "High Wind": ("wind",),
    "Strong Wind": ("wind",),
    "Heat": ("heat",),
    "Excessive Heat": ("heat",),
    "Heat Index Exceedance": ("heat",),
    "Hurricane (Typhoon)": ("wind", "rain", "coastal_water"),
    "Tropical Storm": ("wind", "rain", "coastal_water"),
    "Tropical Depression": ("wind", "rain"),
    "Wildfire": ("wildfire", "air_quality"),
    "Earthquake": ("earthquake",),
    "Winter Storm": ("winter", "wind"),
    "Heavy Snow": ("winter",),
    "Ice Storm": ("winter",),
    "Thunderstorm Wind": ("wind", "rain"),
}
PLANNING = {
    "wind": "Wind values describe their stated station or forecast footprint; site gusts and unseen equipment damage remain unverified.",
    "heat": "Temperature and humidity describe ambient conditions; heat index is not personal strain, WBGT, or a work/rest prescription.",
    "rain": "Rain amount/probability refers to the stated accumulation or forecast window; it is not a flood-depth probability.",
    "flood_context": "Gauge/warning context does not measure site water depth, energized water, access, or ground bearing strength.",
    "earthquake": "Magnitude and epicenter distance do not certify local shaking, structural integrity, or equipment condition.",
    "coastal_water": "Water level is relative to the stated station datum; it is not a site inundation depth.",
    "space_weather": "Planetary conditions provide regional context, without a site outage or grid failure prediction.",
    "wildfire": "Detections or mapped perimeters do not establish containment, spread, or an evacuation route.",
    "air_quality": "Sensor AQI/concentration is location-specific and does not measure personal exposure.",
}


def predict_site_impact(
    site_context: SiteContext | dict,
    event_outlook: dict,
    evidence: list[Evidence | dict],
    *,
    as_of_utc: str,
    **policies,
) -> dict:
    """Return typed environmental context; Layer A probabilities never enter this calculation."""
    site = (
        site_context
        if isinstance(site_context, SiteContext)
        else SiteContext.model_validate(site_context)
    )
    assessments, errors = normalize_batch(site, evidence, as_of_utc, **policies)
    assessments += _derived_heat(assessments)
    kinds = set(EXPECTED.get(event_outlook.get("event_type"), ())) | {
        a.evidence.hazard for a in assessments
    }
    if not kinds:
        kinds = {"infrastructure"}
    hazards = []
    for kind in sorted(kinds):
        related = [a for a in assessments if a.evidence.hazard == kind]
        accepted = [a for a in related if a.accepted]
        unknowns = sorted({reason for a in related for reason in a.reasons})
        conditions = []
        for item in accepted:
            value, unit = canonical_value(item.evidence)
            conditions.append(
                Condition(
                    evidence_id=item.evidence.evidence_id,
                    method=item.evidence.method,
                    variable=item.evidence.variable,
                    value=value,
                    unit=unit,
                    valid_from=item.evidence.valid_from,
                    valid_to=item.evidence.valid_to,
                    spatial_match=item.spatial_match,
                    datum=item.evidence.datum,
                    value_basis=item.evidence.value_basis,
                    derived_from_evidence_ids=item.evidence.derived_from_evidence_ids,
                    computation_version=item.evidence.computation_version,
                )
            )
        # Expose simultaneous conflicting measurements, never silently choose the lower value.
        for index, left in enumerate(conditions):
            for right in conditions[index + 1 :]:
                if (
                    left.variable == right.variable
                    and left.method == right.method
                    and left.valid_from == right.valid_from
                    and left.valid_to == right.valid_to
                    and left.value != right.value
                ):
                    unknowns.append("conflicting_source_values:" + left.variable)
        if not accepted:
            unknowns.append("no_eligible_site_evidence")
        if kind == "earthquake":
            unknowns.append("local_shaking_and_structural_condition_unknown")
        if kind == "heat":
            unknowns.append("physiological_exposure_and_work_rest_policy_not_modeled")
        methods = {item.evidence.method for item in accepted}
        status = (
            "unavailable"
            if not accepted
            else "partial"
            if unknowns or len(methods) > 1
            else "official_warning"
            if "official_warning" in methods
            else next(iter(methods))
        )
        hazards.append(
            SiteHazard(
                kind=kind,
                status=status,
                conditions=conditions,
                evidence_ids=[a.evidence.evidence_id for a in accepted],
                unknowns=sorted(set(unknowns)),
                planning_context=PLANNING.get(
                    kind,
                    "Only supplied authoritative evidence is represented; local consequences are not inferred.",
                ),
                warning_evidence_ids=[
                    a.evidence.evidence_id
                    for a in accepted
                    if a.evidence.method == "official_warning"
                ],
            )
        )
    return {"site_hazards": hazards, "evidence": assessments, "unknowns": errors}
