"""As-of, unit and geography gates shared by descriptive hazard evaluators."""

from datetime import timedelta
from pydantic import ValidationError

from ml.schemas import parse_utc
from ml.worker.schema import Evidence, EvidenceAssessment, SiteContext
from ml.worker.spatial import associate

UNITS = {
    "temperature": {"C", "F"},
    "heat_index": {"C", "F"},
    "relative_humidity": {"%"},
    "wind_speed": {"m/s", "mph", "km/h", "kn"},
    "wind_gust": {"m/s", "mph", "km/h", "kn"},
    "rainfall": {"mm", "in"},
    "rain_probability": {"%"},
    "gauge_height": {"m", "ft"},
    "coastal_water_level": {"m", "ft"},
    "wave_height": {"m", "ft"},
    "visibility": {"m", "km", "mi"},
    "earthquake_magnitude": {"magnitude"},
    "geomagnetic_kp": {"Kp"},
    "warning": {"text"},
    "air_quality_index": {"AQI"},
    "pm25": {"ug/m3"},
    "thermal_detection": {"detection"},
    "ice_accretion": {"mm", "in"},
    "snow_depth": {"mm", "in"},
}
for _variable in ("wind_speed_min", "wind_speed_max"):
    UNITS[_variable] = UNITS["wind_speed"]
VARIABLE_HAZARDS = {
    "temperature": {"heat", "winter"},
    "heat_index": {"heat"},
    "relative_humidity": {"heat"},
    "wind_speed": {"wind"},
    "wind_gust": {"wind"},
    "rainfall": {"rain"},
    "rain_probability": {"rain"},
    "gauge_height": {"flood_context"},
    "coastal_water_level": {"coastal_water"},
    "wave_height": {"waves"},
    "visibility": {"visibility"},
    "earthquake_magnitude": {"earthquake"},
    "geomagnetic_kp": {"space_weather"},
    "air_quality_index": {"air_quality"},
    "pm25": {"air_quality"},
    "thermal_detection": {"wildfire"},
    "ice_accretion": {"winter"},
    "snow_depth": {"winter"},
}
for _variable in ("wind_speed_min", "wind_speed_max"):
    VARIABLE_HAZARDS[_variable] = {"wind"}


def canonical_value(evidence: Evidence) -> tuple[float | str, str]:
    value, unit = evidence.value, evidence.unit
    if isinstance(value, str):
        return value, unit
    if evidence.variable in ("temperature", "heat_index"):
        return ((value - 32) / 1.8 if unit == "F" else value), "C"
    factors = {
        "mph": (0.44704, "m/s"),
        "km/h": (1 / 3.6, "m/s"),
        "kn": (0.5144444444444445, "m/s"),
        "ft": (0.3048, "m"),
        "in": (25.4, "mm"),
        "mi": (1609.344, "m"),
        "km": (1000, "m"),
    }
    factor, canonical = factors.get(unit, (1, unit))
    return value * factor, canonical


def assess(
    site: SiteContext,
    evidence: Evidence,
    as_of_utc: str,
    *,
    maximum_station_km: float = 25,
    observation_max_age_hours: float = 2,
    forecast_max_age_hours: float = 24,
) -> EvidenceAssessment:
    as_of = parse_utc(as_of_utc, "as_of_utc")
    if (
        not 0 <= maximum_station_km <= 100
        or not 0 < observation_max_age_hours <= 24
        or not 0 < forecast_max_age_hours <= 48
    ):
        raise ValueError("association/freshness policy exceeds bounded research configuration")
    match = associate(site, evidence, maximum_station_km=maximum_station_km)
    reasons = []
    if evidence.value_basis == "derived":
        reasons.append("external_derivation_requires_recomputation")
    if evidence.source_version is None or not evidence.source_version.strip():
        reasons.append("missing_data_version")
    if evidence.available_at is None or evidence.availability_basis == "unknown":
        reasons.append("historical_availability_unknown")
    elif parse_utc(evidence.available_at, "available_at") > as_of:
        reasons.append("available_after_as_of")
    if (
        parse_utc(evidence.ingested_at, "ingested_at") < as_of
        and evidence.available_at
        and parse_utc(evidence.available_at, "available_at")
        > parse_utc(evidence.ingested_at, "ingested_at")
    ):
        reasons.append("invalid_availability_chronology")
    for name in ("observed_at", "issued_at"):
        value = getattr(evidence, name)
        if value and parse_utc(value, name) > as_of:
            reasons.append(name + "_after_as_of")
        if (
            value
            and evidence.available_at
            and parse_utc(value, name) > parse_utc(evidence.available_at, "available_at")
        ):
            reasons.append(name + "_after_available_at")
    if evidence.method == "retrospective" or evidence.data_state == "retrospective":
        reasons.append("retrospective_not_operational_as_of")
    if any(
        word in (evidence.publisher + ":" + evidence.original_type).lower()
        for word in ("era5", "hurdat", "reanalysis", "best_track")
    ):
        reasons.append("known_retrospective_source_not_issued_forecast")
    if (
        evidence.hazard == "infrastructure" or evidence.original_type == "crew_report"
    ) and evidence.human_review_status != "confirmed":
        reasons.append("human_review_required")
    if evidence.data_state in ("stale", "missing"):
        reasons.append(evidence.data_state + "_source")
    if evidence.method == "observed" and evidence.observed_at:
        age = (as_of - parse_utc(evidence.observed_at, "observed_at")).total_seconds() / 3600
        if age > observation_max_age_hours:
            reasons.append("stale_observation")
        if parse_utc(evidence.valid_from, "valid_from") > as_of:
            reasons.append("observation_valid_after_as_of")
    if evidence.method in ("issued_forecast", "official_warning"):
        if parse_utc(evidence.valid_to, "valid_to") <= as_of:
            reasons.append("expired_issued_product")
        if parse_utc(evidence.valid_from, "valid_from") > as_of + timedelta(hours=48):
            reasons.append("outside_48h_planning_window")
        if (
            evidence.issued_at
            and (as_of - parse_utc(evidence.issued_at, "issued_at")).total_seconds() / 3600
            > forecast_max_age_hours
        ):
            reasons.append("stale_forecast_run")
    if evidence.value is None:
        reasons.append("missing_measurement")
    if evidence.variable not in UNITS or evidence.unit not in UNITS.get(evidence.variable, set()):
        reasons.append("unsupported_or_conflicting_unit")
    if evidence.variable != "warning" and evidence.hazard not in VARIABLE_HAZARDS.get(
        evidence.variable, set()
    ):
        reasons.append("variable_hazard_mismatch")
    if isinstance(evidence.value, str) and evidence.variable != "warning":
        reasons.append("non_numeric_measurement")
    if evidence.quality_flags:
        reasons.append("source_quality_flags")
    if evidence.variable in ("coastal_water_level", "gauge_height") and not evidence.datum:
        reasons.append("missing_vertical_datum")
    if match.kind in ("no_supported_association", "county_only_context", "uncertain"):
        reasons.append("unsupported_local_association")
    if (
        evidence.hazard == "flood_context"
        and evidence.variable == "gauge_height"
        and match.kind != "verified_gauge_basin"
    ):
        reasons.append("gauge_basin_relation_unverified")
    if evidence.hazard == "wind" and match.kind == "track_center_distance":
        reasons.append("storm_center_is_not_wind_footprint")
    if type(evidence.value) in (int, float):
        if (
            evidence.variable in ("relative_humidity", "rain_probability")
            and not 0 <= evidence.value <= 100
        ):
            reasons.append("out_of_range_measurement")
        if (
            evidence.variable
            in (
                "wind_speed",
                "wind_gust",
                "rainfall",
                "wave_height",
                "visibility",
                "snow_depth",
                "ice_accretion",
            )
            and evidence.value < 0
        ):
            reasons.append("out_of_range_measurement")
    freshness = (
        "retrospective"
        if any("retrospective" in reason for reason in reasons)
        else "future"
        if any("after_as_of" in reason for reason in reasons)
        else "stale"
        if any("stale" in reason or "expired" in reason for reason in reasons)
        else "unknown"
        if "historical_availability_unknown" in reasons
        else "issued_valid"
        if evidence.method in ("issued_forecast", "official_warning")
        else "current"
    )
    return EvidenceAssessment(
        evidence=evidence,
        accepted=not reasons,
        spatial_match=match,
        reasons=sorted(set(reasons)),
        freshness=freshness,
    )


def normalize_batch(
    site: SiteContext, rows: list[Evidence | dict], as_of_utc: str, **policies
) -> tuple[list[EvidenceAssessment], list[str]]:
    assessments, errors, seen = [], [], {}
    if len(rows) > 200:
        raise ValueError("at most 200 evidence rows per outlook")
    for index, row in enumerate(rows):
        try:
            evidence = row if isinstance(row, Evidence) else Evidence.model_validate(row)
        except (ValidationError, TypeError, ValueError):
            errors.append(f"invalid_evidence_row_{index}")
            continue
        encoded = evidence.model_dump_json()
        if evidence.evidence_id in seen:
            if seen[evidence.evidence_id] != encoded:
                errors.append("conflicting_duplicate_evidence_id:" + evidence.evidence_id)
                assessments = [
                    a.model_copy(
                        update={
                            "accepted": False,
                            "reasons": a.reasons + ["conflicting_duplicate_evidence_id"],
                        }
                    )
                    if a.evidence.evidence_id == evidence.evidence_id
                    else a
                    for a in assessments
                ]
            continue
        seen[evidence.evidence_id] = encoded
        assessments.append(assess(site, evidence, as_of_utc, **policies))
    return assessments, errors
