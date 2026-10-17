"""Explicit hypothetical activations with real captures and clearly labeled synthetic cases."""

import copy
from datetime import timedelta
import json

from ml.collect_hazard_sources import FIXTURES
from ml.schemas import parse_utc


def activation(site, as_of, event_type):
    now = parse_utc(as_of, "as_of")
    return {
        "event_id": "hypothetical-" + event_type.replace(" ", "-").lower() + ":" + site["id"],
        "event_type": event_type,
        "event_status": "historical_replay",
        "site_id": site["id"],
        "event_start_utc": (now - timedelta(hours=6)).isoformat(),
        "as_of_utc": as_of,
        "event_definition": "noaa_positive_continuous_recorded_interval",
        "is_simulated": True,
        "location": {
            "lat": site["lat"],
            "lon": site["lon"],
            "region": "hypothetical activation, not a verified incident",
            "spatial_match_quality": "region_only",
        },
        "confirmation": {
            "source": "explicit hypothetical activation fixture",
            "record_id": "fixture-activation-v1",
            "confirmed_at": (now - timedelta(hours=5)).isoformat(),
            "available_at": (now - timedelta(hours=5)).isoformat(),
            "is_fixture": True,
        },
    }


def fixture_evidence(site, as_of, variable, hazard, value, unit, **changes):
    now = parse_utc(as_of, "asof")
    row = {
        "evidence_id": "fixture:" + variable,
        "publisher": "explicit synthetic fixture",
        "origin_url": "https://api.weather.gov/observations",
        "source_record_id": "fixture-matched-record",
        "original_type": "synthetic_" + variable,
        "hazard": hazard,
        "method": "observed",
        "variable": variable,
        "value": value,
        "unit": unit,
        "observed_at": as_of,
        "available_at": as_of,
        "ingested_at": as_of,
        "valid_from": as_of,
        "valid_to": as_of,
        "source_version": "synthetic-v1",
        "availability_basis": "fixture",
        "is_fixture": True,
        "footprint": {
            "kind": "point",
            "point": {"lat": site["lat"], "lon": site["lon"]},
            "precision": "Synthetic fixture sensor",
        },
    }
    if changes.get("method") == "issued_forecast":
        row.update(
            observed_at=None,
            issued_at=as_of,
            valid_to=(now + timedelta(hours=1)).isoformat(),
            footprint={
                "kind": "polygon",
                "rings": box(site),
                "precision": "Synthetic forecast grid",
            },
        )
    return {**row, **changes}


def box(site, radius=0.1):
    x, y = site["lon"], site["lat"]
    return [
        [
            [x - radius, y - radius],
            [x + radius, y - radius],
            [x + radius, y + radius],
            [x - radius, y + radius],
            [x - radius, y - radius],
        ]
    ]


def fixture_alert(site, as_of, event="Flash Flood Warning", **changes):
    now = parse_utc(as_of, "asof")
    return {
        "id": "fixture-cap:" + event.replace(" ", "-"),
        "event": event,
        "status": "Actual",
        "message_type": "Alert",
        "sent": (now - timedelta(minutes=10)).isoformat(),
        "updated": (now - timedelta(minutes=10)).isoformat(),
        "effective": (now - timedelta(minutes=10)).isoformat(),
        "expires": (now + timedelta(hours=1)).isoformat(),
        "available_at": as_of,
        "ingested_at": as_of,
        "source_version": "synthetic-cap-v1",
        "polygons": [{"kind": "polygon", "rings": box(site), "precision": "Synthetic CAP polygon"}],
        "zone_ids": [],
        "is_fixture": True,
        **changes,
    }


def fixture_report(site, as_of, hazard_id, **changes):
    now = parse_utc(as_of, "asof")
    return {
        "id": "fixture-report:" + hazard_id,
        "site_id": site["id"],
        "hazard_id": hazard_id,
        "issuer": "fixture-authorized-report-service",
        "kind": "crew_report",
        "state": "present",
        "review_status": "confirmed",
        "reviewer_role": "supervisor",
        "reviewed_at": as_of,
        "observed_at": (now - timedelta(minutes=5)).isoformat(),
        "available_at": as_of,
        "valid_to": (now + timedelta(hours=1)).isoformat(),
        "lat": site["lat"],
        "lon": site["lon"],
        "source_version": "synthetic-review-v1",
        "is_fixture": True,
        **changes,
    }


def scenarios():
    snapshot = json.loads((FIXTURES / "source_snapshot.json").read_text())
    sites = json.loads((FIXTURES / "backend_sites.json").read_text())
    index = {r["id"]: r["site"] for r in sites["records"]}
    first, second = [index[sid] for sid in sites["batch_site_ids"][:2]]
    now, stamp = parse_utc(snapshot["as_of_utc"], "asof"), snapshot["as_of_utc"]
    cases = []

    def add(name, event="Flood", site=first, *, evidence=None, **extra):
        request = {
            "event_context": activation(site, stamp, event),
            "site_context": copy.deepcopy(site),
            "evidence": copy.deepcopy(snapshot["evidence"] if evidence is None else evidence),
            "alerts": [],
            "reports": [],
            "context_signals": [],
            "lightning_replay": [],
        }
        request.update(extra)
        case = {"name": name, "is_actual_incident": False, "request": request}
        cases.append(case)
        return case

    for name, event, target in (
        ("real_local_rain_and_gauge_without_basin_or_datum", "Flood", first),
        ("real_wind_and_forecast_backend_identity", "High Wind", second),
    ):
        add(
            name,
            event,
            target,
            alerts=snapshot.get("site_alerts", {}).get(target["id"], []),
            source_states=[snapshot["site_alert_states"][target["id"]]]
            if target["id"] in snapshot.get("site_alert_states", {})
            else [],
        )
    real_notice = next(
        ((sid, alerts) for sid, alerts in snapshot.get("site_alerts", {}).items() if alerts), None
    )
    if real_notice:
        sid, alerts = real_notice
        add(
            "real_native_nws_notice_hypothetical_activation",
            "Winter Storm",
            index[sid],
            evidence=[],
            alerts=alerts,
            source_states=[snapshot["site_alert_states"][sid]],
        )
    linked = fixture_evidence(
        first,
        stamp,
        "gauge_height",
        "flood_context",
        1.2,
        "m",
        datum="synthetic_fixture_datum",
        footprint={
            "kind": "point",
            "point": {"lat": first["lat"], "lon": first["lon"]},
            "precision": "Synthetic basin-linked gauge",
            "site_id": first["id"],
            "relation": "verified_gauge_basin",
            "relation_evidence_id": "synthetic-basin-proof",
        },
    )
    add("fixture_verified_basin_and_datum_not_inundation", evidence=[linked])
    add("flash_flood_polygon", "Flash Flood", alerts=[fixture_alert(first, stamp)])
    stale = fixture_alert(first, stamp, expires=(now - timedelta(minutes=1)).isoformat())
    add("expired_flash_flood_notice", "Flash Flood", alerts=[stale])
    hole = fixture_alert(first, stamp)
    hole["polygons"][0]["rings"] += box(first, 0.01)
    add("flash_flood_polygon_hole_negative", "Flash Flood", alerts=[hole])
    add(
        "wind_units_and_station_distance",
        "High Wind",
        evidence=[
            fixture_evidence(first, stamp, "wind_gust", "wind", 20.0, "kn"),
            fixture_evidence(
                first,
                stamp,
                "wind_speed",
                "wind",
                35.0,
                "km/h",
                evidence_id="fixture-remote-wind",
                footprint={
                    "kind": "point",
                    "point": {"lat": 45.0, "lon": -120.0},
                    "precision": "Deliberately remote synthetic station",
                },
            ),
            fixture_evidence(
                first, stamp, "wind_speed_max", "wind", 30.0, "mph", method="issued_forecast"
            ),
        ],
    )
    thermal = [
        fixture_evidence(first, stamp, "temperature", "heat", 90.0, "F"),
        fixture_evidence(first, stamp, "relative_humidity", "heat", 70.0, "%"),
    ]
    add("heat_matched_inputs", "Heat", evidence=thermal)
    mismatched = copy.deepcopy(thermal)
    mismatched[1]["source_record_id"] = "different-record"
    add("heat_mismatched_inputs", "Heat", evidence=mismatched)
    stale_heat = copy.deepcopy(thermal)
    for e in stale_heat:
        e.update(
            observed_at=(now - timedelta(hours=4)).isoformat(),
            valid_from=(now - timedelta(hours=4)).isoformat(),
            valid_to=(now - timedelta(hours=4)).isoformat(),
        )
    add("heat_stale_inputs", "Heat", evidence=stale_heat)
    add(
        "tropical_wind_rain_coastal_unknown_intensity",
        "Hurricane",
        alerts=[fixture_alert(first, stamp, "Coastal Flood Warning")],
    )
    add(
        "lightning_restrike_contract_no_timer",
        "Lightning",
        evidence=[],
        lightning_replay=[
            {
                "id": "fixture-strike-1",
                "observed_at": (now - timedelta(minutes=12)).isoformat(),
                "available_at": stamp,
                "lat": first["lat"] + 0.01,
                "lon": first["lon"],
                "source_version": "synthetic-strikes-v1",
                "is_replay": True,
            },
            {
                "id": "fixture-strike-2",
                "observed_at": (now - timedelta(minutes=2)).isoformat(),
                "available_at": stamp,
                "lat": first["lat"] + 0.02,
                "lon": first["lon"],
                "source_version": "synthetic-strikes-v1",
                "is_replay": True,
            },
        ],
    )
    add(
        "winter_ice_and_reviewed_road_notice",
        "Winter Storm",
        evidence=[fixture_evidence(first, stamp, "ice_accretion", "winter", 0.1, "in")],
        reports=[fixture_report(first, stamp, "road_closure", kind="official_local_notice")],
    )
    add(
        "wildfire_hotspot_perimeter_smoke_fixtures",
        "Wildfire",
        evidence=[
            fixture_evidence(
                first,
                stamp,
                "thermal_detection",
                "wildfire",
                1.0,
                "detection",
                original_type="FIRMS_VIIRS_synthetic_detection",
            ),
            fixture_evidence(
                first,
                stamp,
                "pm25",
                "air_quality",
                25.0,
                "ug/m3",
                original_type="synthetic_PM25_1h_not_AQI",
                valid_from=(now - timedelta(hours=1)).isoformat(),
            ),
        ],
        context_signals=[
            {
                "id": "fixture-nifc-perimeter",
                "hazard_id": "wildfire",
                "method": "mapped_observation",
                "source": "NIFC",
                "origin_url": "https://services3.arcgis.com/fixture",
                "source_version": "synthetic-perimeter-v1",
                "issued_at": stamp,
                "observed_at": (now - timedelta(hours=1)).isoformat(),
                "available_at": stamp,
                "footprint": {
                    "kind": "polygon",
                    "rings": box(first),
                    "precision": "Synthetic perimeter, not actual NIFC geometry",
                },
                "value": None,
                "unit": "context",
                "description": "Synthetic perimeter for adapter contract; incident containment and future growth unknown",
                "is_fixture": True,
            }
        ],
    )
    probe = json.loads((FIXTURES / "real_shakemap_probe.json").read_text())
    if probe["signal"]:
        add(
            "real_shakemap_hypothetical_non_US_location",
            "Earthquake",
            probe["site"],
            evidence=[],
            context_signals=[probe["signal"]],
        )
    add(
        "quake_us_site_no_local_shaking_and_tsunami_fixture",
        "Earthquake",
        evidence=[],
        reports=[fixture_report(first, stamp, "tsunami", kind="official_local_notice")],
    )
    add(
        "coastal_datum_not_site_inundation",
        "Storm Surge/Tide",
        evidence=[
            fixture_evidence(
                first,
                stamp,
                "coastal_water_level",
                "coastal_water",
                3.0,
                "ft",
                datum="synthetic_MLLW",
            )
        ],
    )
    add(
        "tornado_hail_thunderstorm_unknown_models",
        "Tornado",
        evidence=[],
        alerts=[
            fixture_alert(first, stamp, "Tornado Warning"),
            fixture_alert(first, stamp, "Severe Thunderstorm Warning"),
        ],
    )
    add(
        "dust_fog_visibility_context",
        "Dust Storm",
        evidence=[fixture_evidence(first, stamp, "visibility", "visibility", 2.0, "km")],
    )
    add(
        "landslide_soft_ground_postfire_unknown",
        "Landslide",
        evidence=[],
        reports=[fixture_report(first, stamp, "saturated_ground", review_status="pending")],
    )
    add(
        "drought_soil_fireweather_context",
        "Drought",
        evidence=[],
        alerts=[fixture_alert(first, stamp, "Red Flag Warning")],
        context_signals=[
            {
                "id": "fixture-weekly-drought",
                "hazard_id": "drought",
                "method": "background_context",
                "source": "US Drought Monitor",
                "origin_url": "https://droughtmonitor.unl.edu/Data.aspx",
                "source_version": "synthetic-weekly-v1",
                "issued_at": stamp,
                "available_at": stamp,
                "footprint": {
                    "kind": "polygon",
                    "rings": box(first, 1.0),
                    "precision": "Synthetic coarse context",
                },
                "value": None,
                "unit": "context",
                "description": "Synthetic coarse weekly context, not soil under equipment",
                "is_fixture": True,
            }
        ],
    )
    add(
        "real_swpc_context_no_outage_prediction",
        "Geomagnetic Storm",
        evidence=[],
        context_signals=snapshot["context_signals"],
    )
    add("electrical_dangers_unknown_despite_weather", "Flood")
    reports = [
        fixture_report(first, stamp, hid, review_status="pending")
        for hid in (
            "chemical_release",
            "carbon_monoxide",
            "contaminated_water",
            "confined_space",
            "structural_collapse",
            "wildlife",
        )
    ]
    reports += [
        fixture_report(first, stamp, "downed_lines"),
        fixture_report(first, stamp, "wildlife", id="fixture-reviewed-wildlife"),
    ]
    add("reviewed_and_pending_utility_reports", evidence=[], reports=reports)
    add(
        "communications_and_access_only_reviewed_reports",
        evidence=[],
        reports=[
            fixture_report(
                first,
                stamp,
                "communications",
                kind="asset_telemetry",
                reviewer_role="asset_operator",
            ),
            fixture_report(first, stamp, "road_closure", review_status="ai_suggested"),
        ],
    )
    conflict = [
        fixture_evidence(first, stamp, "wind_gust", "wind", 10.0, "m/s"),
        fixture_evidence(
            first, stamp, "wind_gust", "wind", 30.0, "m/s", evidence_id="fixture-conflicting-gust"
        ),
    ]
    outside = fixture_alert(second, stamp, id="fixture-disjoint-cap")
    add(
        "compound_overlap_conflicts_disjoint_geography",
        "Hurricane",
        evidence=conflict,
        alerts=[
            fixture_alert(first, stamp),
            fixture_alert(first, stamp, "High Wind Warning"),
            outside,
        ],
    )
    add(
        "future_reanalysis_not_operational_feature",
        evidence=[
            fixture_evidence(
                first,
                stamp,
                "temperature",
                "heat",
                30.0,
                "C",
                publisher="ERA5 reanalysis",
                original_type="retrospective_reanalysis",
                method="issued_forecast",
                issued_at=(now + timedelta(hours=1)).isoformat(),
            )
        ],
    )
    forged = add("forged_future_activation_and_missing_evidence", evidence=[])
    forged["request"]["event_context"]["confirmation"]["confirmed_at"] = (
        now + timedelta(hours=1)
    ).isoformat()
    missing = add("malformed_coordinate_maps_to_validation_error", evidence=[])
    missing["request"]["site_context"]["lat"] = 999.0
    missing["expected_error"] = "invalid_request_422_upstream"
    add(
        "missing_credentials_and_failed_source_explicit",
        evidence=[],
        source_states=[
            {
                "provider": "EPA AirNow",
                "state": "unavailable",
                "attempted": False,
                "reason": "API credentials not supplied",
            },
            {
                "provider": "NASA FIRMS",
                "state": "fixture_only",
                "attempted": False,
                "reason": "MAP_KEY not supplied; static parser fixtures only",
            },
            {
                "provider": "NWS hypothetical outage",
                "state": "unavailable",
                "attempted": True,
                "reason": "Synthetic timeout; not an actual network failure",
            },
        ],
    )
    for case in cases:
        case["source_mode"] = (
            "Actual captured sources where supplied; all activation and synthetic fixture inputs explicitly labeled; not an actual worker incident"
        )
    return cases
