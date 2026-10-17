"""Adversarial, source-contract and disconnected worksite acceptance tests."""

import copy
from datetime import timedelta
import json
from unittest.mock import patch
from urllib.error import HTTPError

import pytest
from pydantic import ValidationError

from ml.collect_hazard_sources import FIXTURES
from ml.hazard_registry import FEMA_CROSSWALK, MANUAL_FAMILIES, load_registry
from ml.hazard_rehearsal import DEMO_POLICY, check_rehearsal_scope, run, verify_fixtures
from ml.hazard_scenarios import activation, box, fixture_alert, fixture_evidence, fixture_report
from ml.schemas import parse_utc
from ml.sources.bounded import RestrictedRedirect, snapshot, validate_url
from ml.sources.hazard_feeds import modern_water, parse_alerts, shakemap_at_site, swpc_messages
from ml.worker.comprehensive import assess_alerts, build_comprehensive_outlook
from ml.worker.comprehensive_schema import (
    ComprehensiveOutlook,
    ComprehensiveRequest,
    OfficialAlert,
    SourceAvailability,
    to_legacy,
)
from ml.worker.evidence import assess
from ml.worker.geometry import checked_polygon, geojson_polygons
from ml.worker.identity import reconcile_site
from ml.worker.schema import Evidence, SiteContext, WorkerOutlook

SITES = json.loads((FIXTURES / "backend_sites.json").read_text())
INDEX = {r["id"]: r for r in SITES["records"]}
SITE = INDEX[SITES["batch_site_ids"][0]]["site"]
STAMP = json.loads((FIXTURES / "source_snapshot.json").read_text())["as_of_utc"]
NOW = parse_utc(STAMP, "asof")


class UnavailablePredictor:
    def predict_for_site(self, site, event):
        return {"status": "unavailable", "model_version": "fixture-no-artifact", "outcomes": {}}


def compose(**kwargs):
    return build_comprehensive_outlook(
        activation(SITE, STAMP, "Flood"),
        SITE,
        kwargs.pop("evidence", []),
        predictor=UnavailablePredictor(),
        **kwargs,
    )


def hazard(outlook, hid):
    return next(h for h in outlook["worksite_hazards"] if h["hazard_id"] == hid)


def test_registry_crosswalks_and_no_prediction_inflation():
    entries = load_registry()
    census = json.loads(
        (FIXTURES.parents[1] / "reports/worker_outlook/noaa_census.json").read_text()
    )
    raw = [name for entry in entries.values() for name in entry.raw_noaa_types]
    assert len(FEMA_CROSSWALK) == 18 and len(raw) == len(set(raw)) == 54
    assert set(raw) == set(census["categories"])
    assert sum(e.historical_record_count for e in entries.values()) == 349030
    assert len(entries) > len(raw) and all(not e.operational_eligibility for e in entries.values())
    for name in ("strong_wind", "snow", "ice_storm"):
        assert not entries[name].eligible_outcomes and "disabled" in entries[name].validation_status


def test_all_manual_dangers_unknown_even_with_high_weather_values():
    weather = fixture_evidence(SITE, STAMP, "wind_gust", "wind", 100.0, "m/s")
    result = compose(evidence=[weather])
    for entry in load_registry().values():
        if entry.category in MANUAL_FAMILIES:
            item = hazard(result, entry.id)
            assert item["status"] == "unknown" and not item["source_ids"]
            assert item["probability"] is item["severity"] is None
            assert item["needs_field_verification"] and not item["production_eligibility"]


@pytest.mark.parametrize("review_status", ["pending", "rejected", "ai_suggested"])
def test_upload_or_ai_suggestion_cannot_confirm(review_status):
    result = compose(
        reports=[fixture_report(SITE, STAMP, "downed_lines", review_status=review_status)],
        trust_policy=DEMO_POLICY,
    )
    assert not result["reviewed_reports"][0]["accepted"]
    assert hazard(result, "downed_lines")["status"] == "unknown"


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"issuer": "forged-issuer"}, "issuer_not_trusted"),
        ({"reviewer_role": "crew"}, "human_confirmation"),
        ({"site_id": "another-site"}, "identity_or_pin"),
        ({"lat": 0.0}, "identity_or_pin"),
        ({"reviewed_at": None}, "chronology"),
        ({"observed_at": (NOW + timedelta(hours=1)).isoformat()}, "chronology"),
        ({"available_at": (NOW + timedelta(hours=1)).isoformat()}, "chronology"),
        ({"valid_to": (NOW - timedelta(minutes=1)).isoformat()}, "expired"),
        ({"kind": "asset_telemetry"}, "asset_operator"),
    ],
)
def test_report_provenance_site_role_and_time(changes, reason):
    result = compose(
        reports=[fixture_report(SITE, STAMP, "downed_lines", **changes)], trust_policy=DEMO_POLICY
    )
    assessed = result["reviewed_reports"][0]
    assert not assessed["accepted"] and any(reason in r for r in assessed["reasons"])


def test_default_policy_does_not_trust_claimed_confirmation():
    result = compose(reports=[fixture_report(SITE, STAMP, "downed_lines")])
    assert not result["reviewed_reports"][0]["accepted"]


def test_confirmed_report_and_absence_never_become_clearance():
    present = compose(
        reports=[fixture_report(SITE, STAMP, "downed_lines")], trust_policy=DEMO_POLICY
    )
    absent = compose(
        reports=[fixture_report(SITE, STAMP, "downed_lines", state="absent")],
        trust_policy=DEMO_POLICY,
    )
    assert hazard(present, "downed_lines")["status"] == "reported_present"
    assert hazard(absent, "downed_lines")["status"] == "reported_absent"
    assert "reported_absence_is_not_clearance" in hazard(absent, "downed_lines")["unknowns"]
    assert absent["not_work_clearance"] and not absent["production_eligibility"]


def test_conflicting_report_ids_and_presence_fail_closed():
    first = fixture_report(SITE, STAMP, "wildlife")
    altered = {**first, "state": "absent"}
    duplicate = compose(reports=[first, altered], trust_policy=DEMO_POLICY)
    assert all(not a["accepted"] for a in duplicate["reviewed_reports"])
    distinct = compose(
        reports=[first, {**altered, "id": "another-review"}], trust_policy=DEMO_POLICY
    )
    assert hazard(distinct, "wildlife")["status"] == "partial"


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"status": "Test"}, "not_an_actual"),
        ({"message_type": "Cancel"}, "not_an_actual"),
        ({"expires": (NOW - timedelta(minutes=1)).isoformat()}, "expired"),
        ({"effective": (NOW + timedelta(minutes=1)).isoformat()}, "not_available_or_effective"),
        ({"polygons": []}, "zone_only"),
        (
            {
                "available_at": (NOW - timedelta(hours=2)).isoformat(),
                "ingested_at": (NOW - timedelta(hours=2)).isoformat(),
            },
            "stale_alert_snapshot",
        ),
    ],
)
def test_native_alert_lifecycle_and_missing_geometry(changes, reason):
    item = OfficialAlert.model_validate(fixture_alert(SITE, STAMP, **changes))
    result = assess_alerts(SiteContext.model_validate(SITE), [item], STAMP)[0]
    assert not result.accepted and any(reason in r for r in result.reasons)


def test_polygon_hole_multipolygon_and_disjoint_geography():
    outer, hole = box(SITE)[0], box(SITE, 0.01)[0]
    warning = OfficialAlert.model_validate(
        fixture_alert(
            SITE,
            STAMP,
            polygons=[{"kind": "polygon", "rings": [outer, hole], "precision": "hole test"}],
        )
    )
    assert not assess_alerts(SiteContext.model_validate(SITE), [warning], STAMP)[0].accepted
    second = {**SITE, "lat": SITE["lat"] + 2}
    polygons = geojson_polygons({"type": "MultiPolygon", "coordinates": [box(second), box(SITE)]})
    warning = OfficialAlert.model_validate(fixture_alert(SITE, STAMP, polygons=polygons))
    assert assess_alerts(SiteContext.model_validate(SITE), [warning], STAMP)[0].accepted


def test_cancellation_references_preserved_without_alert_mutation():
    original = fixture_alert(SITE, STAMP)
    cancel = fixture_alert(
        SITE, STAMP, id="fixture-cancel", message_type="Cancel", references=[original["id"]]
    )
    result = compose(alerts=[original, cancel])
    assert not any(a["accepted"] for a in result["official_notices"])
    assert any("cancelled_source_notice" in r for r in result["official_notices"][0]["reasons"])
    assert "active_alerts" not in result and "all_clear_at" not in result


def test_conflicting_native_notice_id_rejected():
    alert = fixture_alert(SITE, STAMP)
    result = compose(alerts=[alert, {**alert, "event": "High Wind Warning"}])
    assert all(not a["accepted"] for a in result["official_notices"])


def test_point_query_provenance_matches_exact_site_and_cannot_override_holes():
    alert = fixture_alert(
        SITE,
        STAMP,
        polygons=[],
        query_site_id=SITE["id"],
        query_point={"lat": SITE["lat"], "lon": SITE["lon"]},
        query_url=f"https://api.weather.gov/alerts/active?point={SITE['lat']},{SITE['lon']}",
    )
    result = compose(alerts=[alert])
    assert result["official_notices"][0]["accepted"]
    assert result["official_notices"][0]["site_spatial_match"] == "provider_point_filter"
    assert not any(e["evidence"]["source_record_id"] == alert["id"] for e in result["evidence"])
    with_hole = {
        **alert,
        "polygons": [
            {"kind": "polygon", "rings": box(SITE) + box(SITE, 0.01), "precision": "test hole"}
        ],
    }
    assert not compose(alerts=[with_hole])["official_notices"][0]["accepted"]
    forged = {**alert, "query_site_id": "different-id"}
    assert not compose(alerts=[forged])["official_notices"][0]["accepted"]


@pytest.mark.parametrize(
    "rings",
    [
        [[[0.0, 0.0], [1.0, 1.0], [0.0, 1.0], [1.0, 0.0], [0.0, 0.0]]],
        [[[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [0.0, 0.0]]],
        [[[179.0, 0.0], [-179.0, 0.0], [-179.0, 1.0], [179.0, 0.0]]],
        [
            [[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 0.0]],
            [[3.0, 3.0], [4.0, 3.0], [4.0, 4.0], [3.0, 3.0]],
        ],
    ],
)
def test_invalid_geometry_rejected(rings):
    with pytest.raises(ValueError):
        checked_polygon(rings)


def test_native_parser_does_not_turn_invalid_response_into_empty_success():
    receipt = {"sha256": "fixture", "retrieved_at_utc": STAMP}
    with pytest.raises(ValueError):
        parse_alerts({"error": "upstream failed"}, receipt)
    alerts, errors = parse_alerts(
        {"type": "FeatureCollection", "features": [{"properties": {}}]}, receipt
    )
    assert not alerts and errors == ["invalid_native_alert_0"]
    assert parse_alerts({"type": "FeatureCollection", "features": []}, receipt) == ([], [])


def test_gauge_datum_and_basin_not_fabricated_by_modern_api():
    payload = {
        "features": [
            {
                "id": "reading-1",
                "geometry": {"coordinates": [SITE["lon"], SITE["lat"]]},
                "properties": {
                    "parameter_code": "63160",
                    "monitoring_location_id": "USGS-fixture",
                    "time": STAMP,
                    "value": "3.2",
                    "unit_of_measure": "ft",
                    "approval_status": "Provisional",
                    "qualifier": None,
                },
            }
        ]
    }
    receipt = {
        "url": "https://api.waterdata.usgs.gov/ogcapi/v1/collections/continuous/items",
        "sha256": "fixture",
        "retrieved_at_utc": STAMP,
    }
    row = modern_water(payload, receipt)[0]
    checked = assess(SiteContext.model_validate(SITE), row, STAMP)
    assert row.datum is None and not checked.accepted
    assert {
        "missing_vertical_datum",
        "gauge_basin_relation_unverified",
        "source_quality_flags",
    } <= set(checked.reasons)


def test_swpc_does_not_relabel_radio_or_particle_messages_as_geomagnetic():
    row = {
        "product_id": "K04A",
        "issue_datetime": STAMP.rstrip("Z").replace("T", " "),
        "message": "synthetic Kp context",
    }
    receipt = {"sha256": "fixture", "retrieved_at_utc": STAMP}
    result = swpc_messages(
        [row, {**row, "product_id": "XM5A"}, {**row, "product_id": "EF3A"}], receipt
    )
    assert len(result) == 1 and result[0].value is None


def test_shakemap_actual_grid_provenance_and_outside_region():
    x, y = SITE["lon"], SITE["lat"]
    rows = "\n".join(f"{x + dx} {y + dy} 5.5" for dx in (-0.1, 0, 0.1) for dy in (-0.1, 0, 0.1))
    xml = f'''<shakemap_grid event_id="fixture-event" process_timestamp="{STAMP}"><grid_specification lon_min="{x - 0.1}" lon_max="{x + 0.1}" lat_min="{y - 0.1}" lat_max="{y + 0.1}" nominal_lon_spacing="0.1" nominal_lat_spacing="0.1"/><grid_field name="LON" index="1" units="dd"/><grid_field name="LAT" index="2" units="dd"/><grid_field name="MMI" index="3" units="intensity"/><grid_data>{rows}</grid_data></shakemap_grid>'''.encode()
    receipt = {
        "url": "https://earthquake.usgs.gov/product/shakemap/fixture/grid.xml",
        "sha256": "fixture",
        "retrieved_at_utc": STAMP,
    }
    signal = shakemap_at_site(xml, receipt, SiteContext.model_validate(SITE))
    assert signal.value == 5.5 and signal.method == "issued_model_estimate"
    assert signal.source_metadata["node_lat"] == y
    other = SiteContext.model_validate({**SITE, "lat": y + 5})
    assert shakemap_at_site(xml, receipt, other) is None
    with pytest.raises(ValueError):
        shakemap_at_site(b'<!DOCTYPE x [<!ENTITY x "unsafe">]><x/>', receipt, other)


@pytest.mark.parametrize("mutation", ["coordinate", "state", "version", "id", "future", "stale"])
def test_identity_reconciliation_not_blind_string_join(mutation):
    candidate, index, asof = copy.deepcopy(SITE), copy.deepcopy(INDEX), STAMP
    if mutation == "coordinate":
        candidate["lat"], candidate["lon"] = candidate["lon"], candidate["lat"]
    if mutation == "state":
        index[candidate["id"]]["state"] = "AK"
    if mutation == "version":
        candidate["source_version"] = "unknown-revision"
    if mutation == "id":
        candidate["id"] = "eia-" + INDEX[SITE["id"]]["plant_id"]
    if mutation == "future":
        asof = "2025-01-01T00:00:00Z"
    if mutation == "stale":
        asof = "2028-01-01T00:00:00Z"
    with pytest.raises(ValueError):
        reconcile_site(candidate, index, asof)


def test_legacy_contract_and_21_migration_are_compatible_and_inputs_immutable():
    evidence = [fixture_evidence(SITE, STAMP, "wind_gust", "wind", 20.0, "kn")]
    before = copy.deepcopy(evidence)
    result = compose(evidence=evidence)
    old = to_legacy(result)
    assert old["contract_version"] == "2.0.0" and "worksite_hazards" not in old
    WorkerOutlook.model_validate(old)
    assert result["contract_version"] == "2.1.0" and evidence == before
    assert all(h["probability"] is None for h in result["worksite_hazards"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("not_work_clearance", False),
        ("production_eligibility", True),
        ("operational_evaluation_eligible", True),
        ("research_only", False),
    ],
)
def test_output_cannot_be_downgraded_or_promoted_to_operational(field, value):
    result = compose()
    with pytest.raises(ValidationError):
        ComprehensiveOutlook.model_validate({**result, field: value})


def test_client_cannot_supply_server_trust_policy():
    payload = {
        "event_context": activation(SITE, STAMP, "Flood"),
        "site_context": SITE,
        "evidence": [],
        "trust_policy": {"allowed_report_issuers": ["forged"]},
    }
    with pytest.raises(ValidationError):
        ComprehensiveRequest.model_validate(payload)


def test_observation_window_future_and_retrospective_sources_rejected():
    row = Evidence.model_validate(
        fixture_evidence(
            SITE,
            STAMP,
            "temperature",
            "heat",
            25.0,
            "C",
            valid_to=(NOW + timedelta(hours=1)).isoformat(),
        )
    )
    assert (
        "observation_window_ends_after_as_of"
        in assess(SiteContext.model_validate(SITE), row, STAMP).reasons
    )
    row = fixture_evidence(
        SITE,
        STAMP,
        "temperature",
        "heat",
        25.0,
        "C",
        publisher="ERA5 reanalysis",
        method="issued_forecast",
        issued_at=STAMP,
    )
    result = compose(evidence=[row])
    assert not result["evidence"][0]["accepted"]


def test_air_quality_units_and_averaging_window_not_invented():
    pm = fixture_evidence(SITE, STAMP, "pm25", "air_quality", 25.0, "ug/m3")
    result = compose(evidence=[pm])
    assert hazard(result, "pm25")["status"] == "unknown"
    assert any("invalid_evidence" in u for u in result["unknowns"])
    valid = {**pm, "valid_from": (NOW - timedelta(hours=1)).isoformat()}
    checked = compose(evidence=[valid])
    assert (
        checked["evidence"][0]["accepted"] and checked["evidence"][0]["evidence"]["unit"] == "ug/m3"
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://api.weather.gov/alerts",
        "https://evil.example/data",
        "https://user:secret@api.weather.gov/alerts",
        "https://api.weather.gov:444/alerts",
        "https://api.weather.gov/alerts?api_key=secret",
    ],
)
def test_snapshot_destinations_reject_secrets_and_untrusted_urls(url):
    with pytest.raises(ValueError):
        validate_url(url)


def test_redirect_destination_is_checked_before_following():
    with pytest.raises(ValueError):
        RestrictedRedirect().redirect_request(
            None, None, 302, "redirect", {}, "https://evil.example/data"
        )


def test_immutable_snapshot_cache_size_and_hash(tmp_path):
    class Response:
        headers = {"Content-Length": "2", "Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, limit):
            return b"{}"

        def geturl(self):
            return "https://api.weather.gov/alerts/active"

    with patch("ml.sources.bounded.build_opener") as opener:
        opener.return_value.open.return_value = Response()
        raw, receipt = snapshot("https://api.weather.gov/alerts/active", tmp_path, "fixture.json")
        assert len(raw) == receipt["bytes"] == 2
        snapshot("https://api.weather.gov/alerts/active", tmp_path, "fixture.json")
        assert opener.return_value.open.call_count == 1
    (tmp_path / "fixture.json").write_bytes(b"tampered")
    with pytest.raises(ValueError):
        snapshot("https://api.weather.gov/alerts/active", tmp_path, "fixture.json")
    with pytest.raises(ValueError):
        snapshot("https://api.weather.gov/alerts/active", tmp_path, "../escape")


def test_retry_limit_preserves_unavailability(tmp_path):
    with patch("ml.sources.bounded.build_opener") as opener, patch("ml.sources.bounded.time.sleep"):
        opener.return_value.open.side_effect = HTTPError(
            "https://api.weather.gov/alerts/active", 503, "unavailable", {}, None
        )
        with pytest.raises(RuntimeError):
            snapshot("https://api.weather.gov/alerts/active", tmp_path, "outage.json", retries=2)
        assert opener.return_value.open.call_count == 2 and not (tmp_path / "outage.json").exists()


def test_failure_states_are_explicit_and_never_zero_risk():
    result = compose(
        source_states=[
            {
                "provider": "AirNow",
                "state": "unavailable",
                "attempted": False,
                "reason": "Credentials unavailable",
            }
        ]
    )
    assert result["source_availability"][0]["state"] == "unavailable"
    assert "risk_score" not in result
    with pytest.raises(ValueError):
        SourceAvailability(provider="NWS", state="current", attempted=True, reason="unproven")


def test_full_disconnected_scenarios_and_50_site_batch(tmp_path):
    verify_fixtures()
    report = run(tmp_path, predictor=UnavailablePredictor())
    assert report["scenarios_passed"] >= 20 and report["sites"] >= 50
    assert report["identity_reconciled_sites"] == report["sites"]
    assert report["new_site_probability_models"] == 0 and report["no_network_enforced"]
    assert report["sites_without_trusted_live_crew_or_asset_feed"] == report["sites"]


def test_real_point_query_receipts_and_snapshot_counts():
    data = json.loads((FIXTURES / "source_snapshot.json").read_text())
    assert data["counts"]["point_alert_sites_retrieved"] == 50
    assert len(data["site_alert_states"]) == 50
    for sid, alerts in data["site_alerts"].items():
        for alert in alerts:
            typed = OfficialAlert.model_validate(alert)
            assert typed.query_site_id == sid and typed.query_point is not None
            assert not typed.is_fixture and typed.source_version
    assert data["counts"]["nws_alerts"] == len(data["alerts"])


def test_rehearsal_permission_contract_requires_scope_and_replay():
    request = {"event_context": activation(SITE, STAMP, "Flood"), "site_context": SITE}
    check_rehearsal_scope("crew", frozenset({SITE["id"]}), request)
    for role, ids in (
        ("crew", frozenset()),
        ("supervisor", frozenset()),
        ("anonymous", frozenset({SITE["id"]})),
    ):
        with pytest.raises(PermissionError):
            check_rehearsal_scope(role, ids, request)
    request["event_context"]["event_status"] = "confirmed_active"
    with pytest.raises(PermissionError):
        check_rehearsal_scope("supervisor", frozenset({SITE["id"]}), request)


def test_canonical_schemas_and_fixture_requests_match_runtime_contract():
    for name, model in (
        ("comprehensive_request.schema.json", ComprehensiveRequest),
        ("comprehensive_outlook.schema.json", ComprehensiveOutlook),
    ):
        assert json.loads((FIXTURES / name).read_text()) == model.model_json_schema()
    for i in (1, 2, 3):
        ComprehensiveRequest.model_validate(
            json.loads((FIXTURES / f"example_{i}_request.json").read_text())
        )
        ComprehensiveOutlook.model_validate(
            json.loads((FIXTURES / f"example_{i}_response.json").read_text())
        )


@pytest.mark.parametrize(
    "event_type", ["Tornado", "Wildfire", "Earthquake", "Strong Wind", "Ice Storm", "Heavy Snow"]
)
def test_wrong_flood_artifact_cannot_supply_other_category_probabilities(event_type):
    class WrongPredictor:
        def predict_for_site(self, site, event):
            return {
                "status": "ok",
                "artifact_version": "noaa-flood-pooled-logistic-v2",
                "model_version": "wrong-flood-output",
                "data_version": "wrong-fixture-data",
                "outcomes": {"recorded_event_ongoing_probability": {"6h": 0.9}},
            }

    result = build_comprehensive_outlook(
        activation(SITE, STAMP, event_type), SITE, [], predictor=WrongPredictor()
    )
    assert result["event_outlook"]["status"] == "unavailable"
    assert not result["event_outlook"]["ongoing_probability"]
