"""Opt-in composition of evidence checks and field-verification questions, never controls."""

from datetime import timedelta
import hashlib
import re

from ml.hazard_registry import EVENT_CHECKS, MANUAL_FAMILIES, SITE_VARIABLES, load_registry
from ml.schemas import parse_utc
from ml.sources.hazard_feeds import alert_hazards
from ml.worker.combined import build_worker_outlook
from ml.worker.comprehensive_schema import (
    AlertAssessment,
    ComprehensiveOutlook,
    ContextAssessment,
    ContextSignal,
    LightningContext,
    LightningRecord,
    OfficialAlert,
    ReportAssessment,
    ReviewedReport,
    SourceAvailability,
    TrustPolicy,
    WorksiteHazard,
)
from ml.worker.schema import Evidence, Point, SiteContext
from ml.worker.spatial import distance_km, in_ring


def _covers(site, polygons):
    return any(
        in_ring(site, polygon.rings[0])
        and not any(in_ring(site, hole) for hole in polygon.rings[1:])
        for polygon in polygons
    )


def assess_alerts(
    site: SiteContext, alerts: list[OfficialAlert], as_of: str
) -> list[AlertAssessment]:
    now = parse_utc(as_of, "as_of")
    suppressed = set()
    for alert in alerts:
        if (
            alert.status == "Actual"
            and alert.message_type in ("Cancel", "Update")
            and all(
                parse_utc(t, "alert time") <= now
                for t in (alert.sent, alert.updated, alert.available_at)
            )
        ):
            suppressed.update(ref.rsplit("/alerts/", 1)[-1] for ref in alert.references)
    identities: dict[str, set[str]] = {}
    for alert in alerts:
        identities.setdefault(alert.id, set()).add(alert.model_dump_json())
    assessments = []
    for alert in alerts:
        reasons = []
        point_match = bool(
            alert.query_point
            and alert.query_site_id == site.id
            and distance_km(site, alert.query_point) <= 0.02
        )
        polygon_match = bool(alert.polygons and _covers(site, alert.polygons))
        matched = polygon_match if alert.polygons else point_match
        if len(identities[alert.id]) > 1:
            reasons.append("conflicting_duplicate_notice_id")
        if now - parse_utc(alert.available_at, "capture") > timedelta(hours=1):
            reasons.append("stale_alert_snapshot_current_state_unknown")
        if alert.status != "Actual" or alert.message_type not in ("Alert", "Update"):
            reasons.append("not_an_actual_current_alert")
        if alert.id.rsplit("/alerts/", 1)[-1] in suppressed:
            reasons.append("superseded_or_cancelled_source_notice_not_clearance")
        if any(
            parse_utc(t, "alert time") > now
            for t in (alert.sent, alert.updated, alert.available_at, alert.effective)
        ):
            reasons.append("notice_not_available_or_effective_as_of")
        if any(
            parse_utc(t, "source time") > parse_utc(alert.available_at, "available")
            for t in (alert.sent, alert.updated)
        ):
            reasons.append("notice_source_time_after_available")
        if any(parse_utc(t, "expiry") <= now for t in (alert.expires, alert.ends) if t):
            reasons.append("expired_source_notice")
        if not alert.polygons and not point_match:
            reasons.append("zone_only_no_verified_site_geometry")
        elif alert.polygons and not polygon_match:
            reasons.append("site_outside_alert_polygon_or_in_hole")
        status = (
            "issued_notice"
            if not reasons
            else "not_current"
            if any("expired" in r or "cancelled" in r for r in reasons)
            else "unmatched"
            if all("geometry" in r or "polygon" in r for r in reasons)
            else "rejected"
        )
        assessments.append(
            AlertAssessment(
                alert=alert,
                accepted=not reasons,
                status=status,
                reasons=reasons,
                site_spatial_match="polygon_intersects"
                if polygon_match
                else "provider_point_filter"
                if matched
                else "unverified",
            )
        )
    return assessments


def assess_report(site, report, as_of, policy):
    now, reasons = parse_utc(as_of, "as_of"), []
    if report.issuer not in policy.allowed_report_issuers:
        reasons.append("issuer_not_trusted_by_server_policy")
    if report.is_fixture and not policy.allow_fixture_reports:
        reasons.append("fixture_report_not_enabled")
    if report.site_id != site.id or distance_km(site, Point(lat=report.lat, lon=report.lon)) > 0.5:
        reasons.append("report_site_identity_or_pin_mismatch")
    if report.hazard_id not in load_registry():
        reasons.append("unknown_registry_hazard")
    if report.review_status != "confirmed" or report.reviewer_role not in (
        "supervisor",
        "asset_operator",
    ):
        reasons.append("human_confirmation_required")
    if report.kind == "asset_telemetry" and report.reviewer_role != "asset_operator":
        reasons.append("asset_operator_attestation_required")
    observed, available = (
        parse_utc(report.observed_at, "observed"),
        parse_utc(report.available_at, "available"),
    )
    reviewed = parse_utc(report.reviewed_at, "reviewed") if report.reviewed_at else None
    if reviewed is None or not observed <= reviewed <= available <= now:
        reasons.append("review_or_availability_chronology_invalid")
    if (
        observed > now
        or now - observed > timedelta(hours=policy.maximum_report_age_hours)
        or parse_utc(report.valid_to, "valid_to") <= now
    ):
        reasons.append("report_stale_future_or_expired")
    if report.state == "unknown":
        reasons.append("report_does_not_establish_presence")
    return ReportAssessment(report=report, accepted=not reasons, reasons=reasons)


def assess_context(site, signal, as_of):
    now, reasons = parse_utc(as_of, "as_of"), []
    issued, available = (
        parse_utc(signal.issued_at, "issue"),
        parse_utc(signal.available_at, "availability"),
    )
    if not issued <= available <= now:
        reasons.append("context_not_available_as_of")
    if signal.observed_at and parse_utc(signal.observed_at, "acquisition") > available:
        reasons.append("context_observation_after_availability")
    age_limit = 24 if signal.hazard_id in ("shaking", "geomagnetic_storm") else 24 * 7
    if now - issued > timedelta(hours=age_limit) or (
        signal.valid_to and parse_utc(signal.valid_to, "valid") <= now
    ):
        reasons.append("stale_or_expired_context")
    footprint = signal.footprint
    matched = (footprint.kind == "polygon" and _covers(site, [footprint])) or (
        footprint.kind == "global" and signal.hazard_id == "geomagnetic_storm"
    )
    if not matched:
        reasons.append("context_site_association_unverified")
    expected = {
        "shaking": ("USGS ShakeMap", "issued_model_estimate", "earthquake.usgs.gov"),
        "geomagnetic_storm": ("NOAA SWPC", "official_message", "services.swpc.noaa.gov"),
        "wildfire": ("NIFC", "mapped_observation", "services3.arcgis.com"),
        "drought": ("US Drought Monitor", "background_context", "droughtmonitor.unl.edu"),
        "floodplain": ("FEMA NFHL", "background_context", "hazards.fema.gov"),
    }
    from urllib.parse import urlparse

    if signal.hazard_id in expected:
        source, method, host = expected[signal.hazard_id]
        if (signal.source, signal.method, urlparse(signal.origin_url).hostname) != (
            source,
            method,
            host,
        ):
            reasons.append("context_source_method_mismatch")
    if not signal.source_version.strip():
        reasons.append("missing_context_source_version")
    return ContextAssessment(
        signal=signal,
        accepted=not reasons,
        reasons=reasons,
        site_spatial_match="model_grid_cell"
        if matched and signal.hazard_id == "shaking"
        else "global_context"
        if matched
        else "unverified",
    )


def _legacy_warning(assessment, site):
    alert = assessment.alert
    polygons = [p for p in alert.polygons if _covers(site, [p])]
    if not polygons:
        return None  # Provider point filtering is retained natively, never invented as a polygon/station.
    kinds = alert_hazards(alert.event)
    mapping = {
        "flood": "flood_context",
        "flash_flood": "flood_context",
        "high_wind": "wind",
        "thunderstorm_wind": "wind",
        "extreme_heat": "heat",
        "winter_storm": "winter",
        "frost_freeze": "winter",
        "fire_weather": "wildfire",
        "tsunami": "tsunami",
        "coastal_flood": "coastal_water",
        "marine_wind_waves": "waves",
        "surf": "waves",
        "air_quality": "air_quality",
        "fog": "visibility",
        "dust": "visibility",
    }
    kind = next((mapping[h] for h in kinds if h in mapping), None)
    if kind is None:
        return None  # Preserve native notice without inventing a legacy hazard classification.
    return Evidence(
        evidence_id="cap:" + hashlib.sha256(alert.id.encode()).hexdigest()[:24],
        publisher=alert.publisher,
        origin_url=alert.origin_url,
        source_record_id=alert.id,
        original_type=alert.event,
        hazard=kind,
        method="official_warning",
        variable="warning",
        value=alert.event,
        unit="text",
        issued_at=alert.updated,
        available_at=alert.available_at,
        valid_from=alert.effective,
        valid_to=min(
            (t for t in (alert.expires, alert.ends) if t), key=lambda t: parse_utc(t, "expiry")
        ),
        ingested_at=alert.ingested_at,
        source_version=alert.source_version,
        availability_basis="retrieved_by_pipeline",
        footprint=polygons[0],
        is_fixture=alert.is_fixture,
    )


def build_comprehensive_outlook(
    event_context,
    site_context,
    evidence,
    *,
    alerts=(),
    reports=(),
    context_signals=(),
    lightning_replay=(),
    source_states=(),
    trust_policy=None,
    predictor=None,
):
    """Trusted backend/library call; this function authenticates nobody and serves no endpoint."""
    site = SiteContext.model_validate(site_context)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}", site.id) or ".." in site.id:
        raise ValueError("Malformed trusted site identifier")
    if (
        len(evidence) > 200
        or len(alerts) > 600
        or len(reports) > 100
        or len(context_signals) > 100
        or len(lightning_replay) > 100
        or len(source_states) > 30
    ):
        raise ValueError("Comprehensive input bounds exceeded")
    now = event_context["as_of_utc"]
    errors = []

    def rows(values, model, label):
        result = []
        for i, value in enumerate(values):
            try:
                result.append(model.model_validate(value))
            except (TypeError, ValueError):
                errors.append(f"invalid_{label}_{i}")
        return result

    notices = assess_alerts(site, rows(alerts, OfficialAlert, "alert"), now)
    availability = rows(source_states, SourceAvailability, "source_state")
    for i, source in enumerate(availability):
        if source.last_success_at and parse_utc(source.last_success_at, "success") > parse_utc(
            now, "asof"
        ):
            availability[i] = source.model_copy(
                update={"state": "unavailable", "reason": "future_source_success_rejected"}
            )
        elif (
            source.state == "current"
            and source.last_success_at
            and parse_utc(now, "asof") - parse_utc(source.last_success_at, "success")
            > timedelta(hours=1)
        ):
            availability[i] = source.model_copy(
                update={
                    "state": "stale",
                    "reason": "snapshot_age_exceeds_research_freshness_policy",
                }
            )
    errors.extend(
        "source_" + source.state + ":" + source.provider
        for source in availability
        if source.state != "current"
    )
    checked_evidence = []
    requested_variables, rejected_variables = set(), set()
    from ml.worker.geometry import checked_polygon

    for i, row in enumerate(evidence):
        try:
            item = Evidence.model_validate(row)
            requested_variables.add(item.variable)
            if item.footprint.kind == "polygon":
                checked_polygon(item.footprint.rings)
            if item.variable == "pm25" and parse_utc(item.valid_to, "window end") <= parse_utc(
                item.valid_from, "window start"
            ):
                raise ValueError("Pollutant averaging window missing")
            checked_evidence.append(item)
        except (TypeError, ValueError):
            errors.append(f"invalid_evidence_or_geometry_{i}")
            if isinstance(row, Evidence):
                rejected_variables.add(row.variable)
            elif isinstance(row, dict) and isinstance(row.get("variable"), str):
                rejected_variables.add(row["variable"])
                requested_variables.add(row["variable"])
    report_rows = [
        assess_report(site, r, now, trust_policy or TrustPolicy())
        for r in rows(reports, ReviewedReport, "report")
    ]
    contexts = [
        assess_context(site, s, now) for s in rows(context_signals, ContextSignal, "context")
    ]
    for assessments, field in ((report_rows, "report"), (contexts, "signal")):
        identities = {}
        for assessment in assessments:
            item = getattr(assessment, field)
            identities.setdefault(item.id, set()).add(item.model_dump_json())
        for i, assessment in enumerate(assessments):
            if len(identities[getattr(assessment, field).id]) > 1:
                assessments[i] = assessment.model_copy(
                    update={
                        "accepted": False,
                        "reasons": assessment.reasons + ["conflicting_duplicate_source_id"],
                    }
                )
    lightning = []
    for strike in rows(lightning_replay, LightningRecord, "lightning"):
        reasons = []
        if (
            not parse_utc(strike.observed_at, "strike")
            <= parse_utc(strike.available_at, "available")
            <= parse_utc(now, "asof")
        ):
            reasons.append("replay_strike_not_available_as_of")
        if parse_utc(now, "asof") - parse_utc(strike.observed_at, "strike") > timedelta(hours=1):
            reasons.append("stale_replay_strike")
        lightning.append(
            LightningContext(
                record=strike,
                accepted=not reasons,
                distance_miles=distance_km(site, Point(lat=strike.lat, lon=strike.lon)) / 1.609344,
                reasons=reasons,
            )
        )
    warning_rows = [e for n in notices if n.accepted if (e := _legacy_warning(n, site)) is not None]
    # Only bounded, recognized native notices enter the old evidence layer.
    if len(evidence) > 200:
        raise ValueError("At most 200 environmental evidence rows")
    if len(checked_evidence) + len(warning_rows) > 200:
        warning_rows = []
        errors.append("legacy_evidence_budget_exceeded_notices_retained_separately")
    legacy = build_worker_outlook(
        event_context, site, checked_evidence + warning_rows, predictor=predictor
    )
    registry = load_registry()
    selected = {hid for hid, entry in registry.items() if entry.category in MANUAL_FAMILIES}
    selected.update(EVENT_CHECKS.get(event_context.get("event_type"), []))
    for n in notices:
        selected.update(alert_hazards(n.alert.event))
    selected.update(r.report.hazard_id for r in report_rows if r.report.hazard_id in registry)
    selected.update(c.signal.hazard_id for c in contexts)
    selected.update(
        hid
        for hid, variables in SITE_VARIABLES.items()
        if requested_variables.intersection(variables)
    )
    if lightning:
        selected.add("lightning")
    all_evidence = legacy["evidence"]
    for item in all_evidence:
        selected.update(
            hid
            for hid, variables in SITE_VARIABLES.items()
            if item["evidence"]["variable"] in variables
        )
    hazards = []
    for hid in sorted(selected):
        entry = registry[hid]
        sources, windows, spatial, methods, unknowns, numbers = [], [], [], [], [], []
        rejected = False
        if rejected_variables.intersection(SITE_VARIABLES.get(hid, [])):
            rejected = True
            unknowns.append("invalid_source_payload_geometry_or_averaging_window")
        for item in all_evidence:
            e = item["evidence"]
            if e["variable"] in SITE_VARIABLES.get(hid, []):
                if item["accepted"]:
                    sources.append(e["evidence_id"])
                    windows.append({"from": e["valid_from"], "to": e["valid_to"]})
                    spatial.append(item["spatial_match"]["kind"])
                    methods.append(e["method"])
                else:
                    rejected = True
                    unknowns.extend(item["reasons"])
        for n in notices:
            if hid not in alert_hazards(n.alert.event):
                continue
            if n.accepted:
                sources.append(n.alert.id)
                windows.append({"from": n.alert.effective, "to": n.alert.expires})
                spatial.append(n.site_spatial_match)
                methods.append("official_warning")
            else:
                rejected = True
                unknowns.extend(n.reasons)
        accepted_reports = [r for r in report_rows if r.report.hazard_id == hid and r.accepted]
        for r in report_rows:
            if r.report.hazard_id != hid:
                continue
            if r.accepted:
                sources.append(r.report.id)
                windows.append({"from": r.report.observed_at, "to": r.report.valid_to})
                spatial.append("trusted_site_and_pin")
                methods.append("reported")
            else:
                rejected = True
                unknowns.extend(r.reasons)
        for c in contexts:
            if c.signal.hazard_id != hid:
                continue
            if c.accepted:
                sources.append(c.signal.id)
                windows.append(
                    {"from": c.signal.issued_at, "to": c.signal.valid_to or c.signal.issued_at}
                )
                spatial.append(c.site_spatial_match)
                methods.append(
                    "issued_model_estimate"
                    if c.signal.method == "issued_model_estimate"
                    else "context"
                )
                if c.signal.value is not None:
                    numbers.append(
                        {
                            "source_id": c.signal.id,
                            "value": c.signal.value,
                            "unit": c.signal.unit,
                            "method": c.signal.method,
                        }
                    )
            else:
                rejected = True
                unknowns.extend(c.reasons)
        if hid == "lightning":
            for strike in lightning:
                if strike.accepted:
                    sources.append(strike.record.id)
                    windows.append(
                        {"from": strike.record.observed_at, "to": strike.record.observed_at}
                    )
                    spatial.append("strike_distance_context")
                    methods.append("context")
            unknowns.append("deterministic_strike_trigger_reset_and_clearance_deferred_to_Rudra")
        states = {r.report.state for r in accepted_reports}
        for environmental in legacy["site_hazards"]:
            if any(
                c["variable"] in SITE_VARIABLES.get(hid, []) for c in environmental["conditions"]
            ):
                unknowns.extend(
                    u for u in environmental["unknowns"] if "conflicting_source_values" in u
                )
        if len(states) > 1:
            unknowns.append("conflicting_reviewed_presence_reports")
        if entry.category in MANUAL_FAMILIES:
            unknowns.append("qualified_field_or_asset_verification_required_no_remote_inference")
        if not sources:
            unknowns.append("no_verified_site_evidence_presence_unknown")
        if states == {"absent"}:
            unknowns.append("reported_absence_is_not_clearance")
        status = (
            "unknown"
            if not sources
            else "partial"
            if rejected or len(states) > 1 or any("conflicting" in u for u in unknowns)
            else "reported_present"
            if states == {"present"}
            else "reported_absent"
            if states == {"absent"}
            else "evidence_available"
        )
        hazards.append(
            WorksiteHazard(
                hazard_id=hid,
                status=status,
                evidence_status="mixed"
                if sources and rejected
                else "accepted"
                if sources
                else "rejected"
                if rejected
                else "not_supplied",
                source_ids=sorted(set(sources)),
                observed_or_valid_windows=windows,
                site_spatial_match=sorted(set(spatial)),
                methods=sorted(set(methods)) or ["unknown"],
                description=entry.review_question,
                unknowns=sorted(set(unknowns)),
                numerical_evidence=numbers,
            )
        )
    # Preserve all existing partial states. New gaps cannot promote status or affect controls.
    legacy["contract_version"] = "2.1.0"
    if (
        any(h.status in ("unknown", "partial") for h in hazards)
        and legacy["status"] == "supported_research"
    ):
        legacy["status"] = "partial"
    legacy["unknowns"] = sorted(
        set(
            legacy["unknowns"]
            + errors
            + ["worksite_inspection_and_control_authority_remain_upstream"]
        )
    )
    legacy["is_demo_or_simulated"] |= (
        any(n.alert.is_fixture for n in notices)
        or any(r.report.is_fixture for r in report_rows)
        or any(c.signal.is_fixture for c in contexts)
        or bool(lightning)
    )
    return ComprehensiveOutlook(
        **legacy,
        worksite_hazards=hazards,
        official_notices=notices,
        reviewed_reports=report_rows,
        context_evidence=contexts,
        lightning_replay_context=lightning,
        source_availability=availability,
    ).model_dump(mode="json")
