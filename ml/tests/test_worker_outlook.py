"""Offline spatial/time/provenance and worker-safety acceptance checks."""

import copy
import hashlib
import json
import os
import subprocess
import sys
from unittest.mock import patch
import zipfile

import pytest
from pydantic import ValidationError

from ml.config import PACKAGE_ROOT
from ml.demo_worker_outlook import scenarios
from ml.events import normalize_noaa_row
from ml.predict import predict_active_event
from ml.schemas import parse_utc
from ml.sources.eia_research import parse_workbook
from ml.sources.worker_feeds import (
    airnow_reporting_area,
    coops,
    earthquake_catalog,
    ndbc_observations,
    nws_alerts,
    nws_hourly,
    nws_observation,
    swpc_kp,
)
from ml.tests.test_prediction import training_events
from ml.train import fit_models
from ml.worker.combined import build_for_backend_site, build_worker_outlook, explanation_context
from ml.worker.evidence import assess, canonical_value, normalize_batch
from ml.worker.impacts import predict_site_impact
from ml.worker.schema import (
    Evidence,
    EventOutlook,
    Point,
    SiteContext,
    SiteHazard,
    WorkerOutlook,
    WorkerOutlookRequest,
)
from ml.worker.spatial import associate, distance_km

TIME = "2026-10-17T05:00:00Z"
ROOT = PACKAGE_ROOT.parent


def site():
    return SiteContext(
        id="fixture-site",
        name="Synthetic test location",
        lat=28.0,
        lon=-82.0,
        site_type="fixture_site",
        source="synthetic fixture",
        source_version="fixture-v1",
        is_fixture=True,
    )


def evidence(**changes):
    base = {
        "evidence_id": "fixture-observation",
        "publisher": "synthetic_fixture",
        "origin_url": "https://api.weather.gov/observations",
        "source_record_id": "fixture-record",
        "original_type": "synthetic_wind",
        "hazard": "wind",
        "method": "observed",
        "variable": "wind_speed",
        "value": 10.0,
        "unit": "m/s",
        "observed_at": TIME,
        "available_at": TIME,
        "ingested_at": TIME,
        "valid_from": TIME,
        "valid_to": TIME,
        "source_version": "fixture-v1",
        "availability_basis": "fixture",
        "is_fixture": True,
        "footprint": {
            "kind": "point",
            "point": {"lat": 28.0, "lon": -82.0},
            "precision": "synthetic station",
        },
    }
    return Evidence.model_validate({**base, **changes})


class FixturePredictor:
    def __init__(self):
        self.models = {
            name: fit_models(
                [{**r, "event_type": name} for r in training_events() * 3],
                event_type=name,
                minimum_events=1,
                minimum_episodes=1,
            )
            for name in ("Flood", "High Wind")
        }

    def predict_for_site(self, site, event):
        if event["event_type"] not in self.models:
            return {"status": "unavailable", "model_version": "unavailable", "outcomes": {}}
        return predict_active_event(event, model=self.models[event["event_type"]])


@pytest.fixture(scope="module")
def predictor():
    return FixturePredictor()


@pytest.mark.parametrize(
    "changes,reason",
    [
        (
            {"available_at": "2026-10-17T06:00:00Z", "ingested_at": "2026-10-17T06:00:00Z"},
            "available_after_as_of",
        ),
        ({"issued_at": "2026-10-17T06:00:00Z"}, "issued_at_after_as_of"),
        ({"observed_at": "2026-10-17T06:00:00Z"}, "observed_at_after_as_of"),
        (
            {"available_at": None, "availability_basis": "unknown"},
            "historical_availability_unknown",
        ),
        (
            {"method": "retrospective", "data_state": "retrospective"},
            "retrospective_not_operational_as_of",
        ),
        ({"original_type": "ERA5_reanalysis"}, "known_retrospective_source_not_issued_forecast"),
        ({"unit": "knots-per-hour"}, "unsupported_or_conflicting_unit"),
        ({"value": None}, "missing_measurement"),
        ({"data_state": "stale"}, "stale_source"),
        ({"source_version": None}, "missing_data_version"),
        ({"quality_flags": ["suspect"]}, "source_quality_flags"),
        ({"value": -1.0}, "out_of_range_measurement"),
        (
            {"observed_at": "2026-10-17T00:00:00Z", "valid_from": "2026-10-17T00:00:00Z"},
            "stale_observation",
        ),
        ({"hazard": "rain"}, "variable_hazard_mismatch"),
    ],
)
def test_time_unit_and_provenance_gates(changes, reason):
    result = assess(site(), evidence(**changes), TIME)
    assert not result.accepted and reason in result.reasons


@pytest.mark.parametrize(
    "field,value",
    [
        ("value", float("nan")),
        ("value", float("inf")),
        ("value", True),
        ("observed_at", "2026-10-17T05:00:00"),
        ("origin_url", "https://api.weather.gov/x?token=secret"),
    ],
)
def test_bad_measurement_or_secret_origin_rejected(field, value):
    with pytest.raises(ValidationError):
        evidence(**{field: value})


def test_geodesic_and_coordinate_order():
    assert distance_km(Point(lat=0.0, lon=0.0), Point(lat=0.0, lon=1.0)) == pytest.approx(
        111.195, abs=0.001
    )
    assert distance_km(Point(lat=0.0, lon=179.0), Point(lat=0.0, lon=-179.0)) == pytest.approx(
        222.39, abs=0.01
    )
    match = associate(
        site(),
        evidence(
            footprint={
                "kind": "point",
                "point": {"lat": 28.0, "lon": -82.1},
                "precision": "fixture",
            }
        ),
    )
    assert match.distance_km == pytest.approx(match.distance_miles * 1.609344)
    with pytest.raises(ValidationError):
        Point(lat=True, lon=-82.0)
    with pytest.raises(ValidationError):
        Point(lat=-82.0, lon=280.0)


def test_polygon_holes_boundaries_and_different_site_binding():
    outer = [[-83.0, 27.0], [-81.0, 27.0], [-81.0, 29.0], [-83.0, 29.0], [-83.0, 27.0]]
    hole = [[-82.1, 27.9], [-81.9, 27.9], [-81.9, 28.1], [-82.1, 28.1], [-82.1, 27.9]]
    assert (
        associate(
            site(),
            evidence(footprint={"kind": "polygon", "rings": [outer], "precision": "fixture"}),
        ).kind
        == "polygon_intersects"
    )
    assert (
        associate(
            site(),
            evidence(footprint={"kind": "polygon", "rings": [outer, hole], "precision": "fixture"}),
        ).kind
        == "no_supported_association"
    )
    assert not assess(
        site(),
        evidence(
            footprint={
                "kind": "point",
                "point": {"lat": 28.0, "lon": -82.0},
                "precision": "fixture",
                "site_id": "other",
            }
        ),
        TIME,
    ).accepted


def test_county_and_hurricane_center_do_not_become_local_wind():
    county = evidence(footprint={"kind": "regional", "precision": "county only"})
    assert not assess(site(), county, TIME).accepted
    center = evidence(original_type="NHC_track_center")
    assert "storm_center_is_not_wind_footprint" in assess(site(), center, TIME).reasons


def test_gauge_requires_datum_and_basin_not_just_distance():
    gauge = evidence(variable="gauge_height", hazard="flood_context", unit="ft")
    assert {"missing_vertical_datum", "gauge_basin_relation_unverified"}.issubset(
        assess(site(), gauge, TIME).reasons
    )
    valid = evidence(
        variable="gauge_height",
        hazard="flood_context",
        unit="ft",
        datum="station_local_gage_datum",
        footprint={
            "kind": "point",
            "point": {"lat": 28.0, "lon": -82.0},
            "precision": "fixture",
            "site_id": site().id,
            "relation": "verified_gauge_basin",
            "relation_evidence_id": "upstream-fixture-basin-proof",
        },
    )
    assert assess(site(), valid, TIME).accepted
    assert canonical_value(valid) == (3.048, "m")


def test_forecast_is_issued_before_asof_with_explicit_future_window():
    forecast = evidence(
        method="issued_forecast",
        observed_at=None,
        issued_at="2026-10-17T04:00:00Z",
        valid_from="2026-10-17T06:00:00Z",
        valid_to="2026-10-17T07:00:00Z",
    )
    assert assess(site(), forecast, TIME).accepted
    expired = forecast.model_copy(update={"valid_to": TIME, "valid_from": "2026-10-17T04:00:00Z"})
    assert "expired_issued_product" in assess(site(), expired, TIME).reasons
    late = forecast.model_copy(update={"issued_at": "2026-10-17T05:30:00Z"})
    assert not assess(site(), late, TIME).accepted


def test_duplicate_id_conflict_is_visible_and_rejected():
    results, errors = normalize_batch(site(), [evidence(), evidence(value=1.0)], TIME)
    assert len(results) == 1 and not results[0].accepted and errors


@pytest.mark.parametrize(
    "unit,value,expected",
    [("mph", 10.0, 4.4704), ("km/h", 36.0, 10.0), ("kn", 10.0, 5.144444444444445)],
)
def test_wind_unit_conversion(unit, value, expected):
    actual, canonical = canonical_value(evidence(unit=unit, value=value))
    assert actual == pytest.approx(expected) and canonical == "m/s"


def test_unreviewed_crew_hazards_cannot_be_inferred():
    pending = evidence(
        hazard="infrastructure",
        variable="warning",
        unit="text",
        value="downed line",
        original_type="crew_report",
        human_review_status="pending",
    )
    assert "human_review_required" in assess(site(), pending, TIME).reasons
    assert assess(
        site(), pending.model_copy(update={"human_review_status": "confirmed"}), TIME
    ).accepted


def test_site_results_ignore_layer_a_probability_and_expose_conflict():
    inputs = [evidence(), evidence(evidence_id="second", value=2.0)]
    a = predict_site_impact(
        site(), {"event_type": "High Wind", "probability": 0.01}, inputs, as_of_utc=TIME
    )
    b = predict_site_impact(
        site(), {"event_type": "High Wind", "probability": 0.99}, inputs, as_of_utc=TIME
    )
    assert a == b and a["site_hazards"][0].probability is None
    assert "conflicting_source_values:wind_speed" in a["site_hazards"][0].unknowns


def test_local_probability_and_unsupported_quantiles_are_schema_forbidden():
    with pytest.raises(ValidationError):
        SiteHazard(
            kind="wind",
            status="unavailable",
            conditions=[],
            probability=0.1,
            evidence_ids=[],
            unknowns=[],
            planning_context="fixture",
        )
    with pytest.raises(ValidationError):
        EventOutlook(
            status="supported_research",
            target="fixture",
            model_version="fixture",
            data_version="fixture",
            ongoing_probability={"6h": 0.5},
            remaining_duration_hours={"p99": 12.0},
            limitations=[],
        )


@pytest.mark.parametrize("index", range(5))
def test_two_layer_scenarios_are_typed_and_do_not_mutate_controls(index, predictor):
    case = scenarios()[index]
    case["site_context"] = dict(
        case["site_context"],
        risk_score=9,
        active_alerts=2,
        lightning_all_clear_at="unchanged",
        official_warning_status="active",
    )
    before = copy.deepcopy(case)
    with patch("urllib.request.urlopen", side_effect=AssertionError("network during inference")):
        result = build_for_backend_site(
            case["event_context"], case["site_context"], case["evidence"], predictor=predictor
        )
    WorkerOutlook.model_validate_json(json.dumps(result, allow_nan=False))
    assert case == before and result["not_work_clearance"] and not result["production_eligibility"]
    assert not result["operational_evaluation_eligible"] and result["is_demo_or_simulated"]
    assert all(h["probability"] is None for h in result["site_hazards"])
    assert not {
        "risk_score",
        "active_alerts",
        "lightning_all_clear_at",
        "all_clear_at",
        "work_permission",
    }.intersection(result)
    if index < 2:
        assert result["event_outlook"]["status"] == "supported_research"
        assert any(h["conditions"] for h in result["site_hazards"])
    elif index == 2:
        assert not any(h["conditions"] for h in result["site_hazards"])
    elif index == 3:
        assert result["event_outlook"]["status"] == "unavailable"
        assert any(h["warning_evidence_ids"] for h in result["site_hazards"])
    else:
        assert "local_shaking_and_structural_condition_unknown" in result["unknowns"]


def test_corrupt_or_missing_artifact_and_future_confirmation_fail_closed(tmp_path):
    from ml.backend_adapter import ActiveEventPredictor

    case = scenarios()[0]
    path = tmp_path / "corrupt.joblib"
    path.write_bytes(b"invalid")
    result = build_worker_outlook(
        case["event_context"],
        case["site_context"],
        case["evidence"],
        predictor=ActiveEventPredictor(path, expected_sha256="0" * 64),
    )
    assert result["event_outlook"]["status"] == "unavailable"
    context = copy.deepcopy(case["event_context"])
    context["confirmation"]["available_at"] = "2099-01-01T00:00:00Z"
    result = build_worker_outlook(context, case["site_context"], case["evidence"])
    assert (
        not result["event_outlook"]["ongoing_probability"]
        and "event_confirmation_or_context_invalid" in result["unknowns"]
    )


def test_request_contract_reuses_legacy_active_event_guard():
    case = scenarios()[0]
    WorkerOutlookRequest.model_validate(
        {k: case[k] for k in ("event_context", "site_context", "evidence")}
    )
    bad = copy.deepcopy(case)
    bad["event_context"]["event_status"] = "not_confirmed"
    with pytest.raises(ValidationError):
        WorkerOutlookRequest.model_validate(
            {k: bad[k] for k in ("event_context", "site_context", "evidence")}
        )


def test_backend_working_directory_fresh_process_has_offline_demo(tmp_path):
    completed = subprocess.run(
        [sys.executable, "-m", "ml.demo_worker_outlook", "--output-dir", str(tmp_path)],
        cwd=ROOT / "backend",
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads((tmp_path / "demo_runtime.json").read_text())["cases"] == 5


def receipt():
    return {"retrieved_at_utc": TIME, "sha256": "a" * 64, "url": "https://api.weather.gov/fixture"}


def test_nws_forecast_range_units_and_run_vintage_are_retained():
    p = {
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[-83.0, 27.0], [-81.0, 27.0], [-81.0, 29.0], [-83.0, 29.0], [-83.0, 27.0]]
            ],
        },
        "properties": {
            "generatedAt": TIME,
            "updateTime": "2026-10-17T04:00:00Z",
            "periods": [
                {
                    "startTime": "2026-10-17T06:00:00Z",
                    "endTime": "2026-10-17T07:00:00Z",
                    "temperature": 90,
                    "temperatureUnit": "F",
                    "windSpeed": "5 to 10 mph",
                    "probabilityOfPrecipitation": {"value": 70.0, "unitCode": "wmoUnit:percent"},
                }
            ],
        },
    }
    readings = nws_hourly(p, receipt())
    assert {r.variable for r in readings} == {
        "temperature",
        "rain_probability",
        "wind_speed_min",
        "wind_speed_max",
    }
    assert all(r.issued_at == TIME for r in readings)
    assert [r.value for r in readings if r.variable.startswith("wind_speed")] == [5.0, 10.0]


def test_nws_missing_observation_is_not_zero_and_alert_cancellation_is_not_clearance():
    p = {
        "id": "fixture",
        "geometry": {"coordinates": [-82.0, 28.0]},
        "properties": {"timestamp": TIME, "temperature": {"value": None}},
    }
    assert nws_observation(p, receipt()) == []
    assert nws_alerts({"features": [{"properties": {"messageType": "Cancel"}}]}, receipt()) == []


def test_coops_missing_measurement_and_datum_are_explicit():
    p = {
        "metadata": {"id": "fixture", "lat": "28", "lon": "-82"},
        "data": [{"t": "2026-10-17 05:00", "v": "", "f": "0,0,0,0"}],
    }
    assert coops(p, receipt(), product="water_level", datum="MLLW") == []
    p["data"][0]["v"] = "1.2"
    row = coops(p, receipt(), product="water_level", datum="MLLW")[0]
    assert row.datum == "MLLW" and row.unit == "m"
    with pytest.raises(ValueError):
        coops({"error": {"message": "not available"}}, receipt(), product="humidity")


def test_usgs_updated_catalog_is_not_available_at_occurrence_time():
    epoch = int(parse_utc(TIME, "time").timestamp() * 1000)
    rows = earthquake_catalog(
        {
            "features": [
                {
                    "id": "fixture",
                    "geometry": {"coordinates": [-82.0, 28.0, 10.0]},
                    "properties": {
                        "mag": 5.0,
                        "magType": "mw",
                        "time": epoch - 100000,
                        "updated": epoch,
                    },
                }
            ]
        },
        receipt(),
    )
    assert rows[0].observed_at < rows[0].issued_at and rows[0].available_at == TIME
    assert not assess(site(), rows[0], "2026-10-17T04:59:00Z").accepted


@pytest.mark.parametrize(
    "payload",
    [
        [["time_tag", "Kp"], ["2026-10-17 03:00:00", "2.0"]],
        [{"time_tag": "2026-10-17T03:00:00", "Kp": 2.0}],
    ],
)
def test_swpc_both_official_formats(payload):
    row = swpc_kp(payload, receipt())[0]
    assert row.value == 2.0 and row.footprint.kind == "global"


def test_ndbc_missing_and_visibility_nautical_miles_are_not_guessed():
    text = "#YY MM DD hh mm WSPD GST WVHT VIS\n#yr mo dy hr mn m/s m/s m nmi\n2026 10 17 05 00 MM 8.0 1.2 2.0\n"
    rows = ndbc_observations(text, receipt(), lat=28.0, lon=-82.0, station_id="fixture")
    assert "wind_speed" not in {r.variable for r in rows}
    assert next(r for r in rows if r.variable == "visibility").value == 3704.0


def test_airnow_ambiguous_local_time_rejected_and_reporting_area_not_site():
    row = {
        "LocalTimeZone": "EDT",
        "DateObserved": "2026-10-17",
        "HourObserved": 1,
        "ReportingArea": "fixture",
        "ParameterName": "PM2.5",
        "AQI": 50,
        "Latitude": 28.0,
        "Longitude": -82.0,
    }
    normalized = airnow_reporting_area([row], receipt())[0]
    assert normalized.observed_at == TIME and not assess(site(), normalized, TIME).accepted
    with pytest.raises(ValueError):
        airnow_reporting_area([{**row, "LocalTimeZone": "LT"}], receipt())


def test_eia_workbook_schema_validation_and_duplicate_plants(tmp_path):
    path = tmp_path / "fixture.xlsx"
    shared = ["Plant ID", "Plant Name", "Plant State", "Latitude", "Longitude", "fixture"]
    strings = (
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        + "".join("<si><t>" + s + "</t></si>" for s in shared)
        + "</sst>"
    )
    header = "".join(f'<c r="{c}1" t="s"><v>{i}</v></c>' for i, c in enumerate("ABCDE"))
    data = '<c r="A2"><v>1</v></c><c r="B2" t="s"><v>5</v></c><c r="C2" t="s"><v>5</v></c><c r="D2"><v>28</v></c><c r="E2"><v>-82</v></c>'
    sheet = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row>'
        + header
        + "</row><row>"
        + data
        + "</row><row>"
        + data
        + "</row></sheetData></worksheet>"
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/sharedStrings.xml", strings)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    plants, quality = parse_workbook(path, "synthetic-v1")
    assert len(plants) == 1 and quality["repeated_generator_location_rows"] == 1


def test_all_noaa_types_remain_verbatim_and_inventory_totals_reconcile():
    census = json.loads((PACKAGE_ROOT / "reports/worker_outlook/noaa_census.json").read_text())
    assert sum(row["records"] for row in census["categories"].values()) == 349030
    assert len(census["categories"]) == 54
    for name in census["categories"]:
        row = {
            "EVENT_ID": "fixture",
            "EPISODE_ID": "fixture",
            "EVENT_TYPE": name,
            "BEGIN_DATE_TIME": "10-SEP-24 10:00:00",
            "END_DATE_TIME": "10-SEP-24 10:00:00",
            "CZ_TIMEZONE": "EDT-4",
            "STATE": "FLORIDA",
            "CZ_TYPE": "C",
            "CZ_NAME": "fixture",
        }
        assert normalize_noaa_row(row, 2024, allow_zero_duration=True)["event_type"] == name


def test_fifty_real_sites_have_unique_ids_valid_coordinates_and_provenance():
    sites = json.loads(
        (PACKAGE_ROOT / "fixtures/worker_outlook/representative_sites.json").read_text()
    )
    assert len(sites) == len({s["id"] for s in sites}) == 50
    for row in sites:
        parsed = SiteContext.model_validate(row)
        assert not parsed.is_fixture and parsed.source.startswith("EIA-860M")


def test_zero_measurement_is_not_zero_risk_or_work_clearance():
    result = predict_site_impact(
        site(), {"event_type": "High Wind"}, [evidence(value=0.0)], as_of_utc=TIME
    )
    hazard = result["site_hazards"][0]
    assert hazard.conditions[0].value == 0.0 and hazard.probability is None
    assert "exposure is unverified" in hazard.conditions[0].spatial_match.limitation


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ({"data_version": None}, "event_model_missing_data_version"),
        (
            {"outcomes": {"recorded_event_ongoing_probability": {"6h": 1.1}}},
            "invalid_event_artifact_output",
        ),
        (
            {
                "outcomes": {
                    "recorded_event_ongoing_probability": {"6h": 0.5},
                    "remaining_duration_hours": {"p99": 5.0},
                }
            },
            "invalid_event_artifact_output",
        ),
    ],
)
def test_invalid_model_identity_or_outcomes_have_no_estimates(mutation, reason):
    class BadPredictor:
        def predict_for_site(self, *args):
            return {
                "status": "ok",
                "model_version": "fixture",
                "artifact_version": "noaa-flood-pooled-logistic-v2",
                "data_version": "fixture",
                "outcomes": {"recorded_event_ongoing_probability": {"6h": 0.5}},
                **mutation,
            }

    case = scenarios()[0]
    result = build_worker_outlook(
        case["event_context"], case["site_context"], [], predictor=BadPredictor()
    )
    assert result["event_outlook"]["ongoing_probability"] == {} and reason in result["unknowns"]


def test_historical_replay_before_bundle_fit_cannot_use_future_fit(predictor):
    case = scenarios()[0]
    ctx = copy.deepcopy(case["event_context"])
    ctx.update(as_of_utc="2024-06-01T06:00:00Z", event_start_utc="2024-06-01T00:00:00Z")
    ctx["confirmation"].update(
        confirmed_at="2024-06-01T05:00:00Z", available_at="2024-06-01T05:00:00Z"
    )
    result = build_worker_outlook(ctx, case["site_context"], case["evidence"], predictor=predictor)
    assert result["event_outlook"]["status"] == "unavailable"
    assert "event_model_fit_cutoff_after_as_of" in result["unknowns"]
    assert not any(e["accepted"] for e in result["evidence"])


def test_retrieval_cannot_be_backdated_and_polygon_dateline_requires_split():
    with pytest.raises(ValidationError):
        evidence(availability_basis="retrieved_by_pipeline", ingested_at="2026-10-17T06:00:00Z")
    with pytest.raises(ValidationError):
        evidence(
            footprint={
                "kind": "polygon",
                "rings": [[[179.0, 0.0], [-179.0, 0.0], [-179.0, 1.0], [179.0, 0.0]]],
                "precision": "ambiguous dateline",
            }
        )


def test_export_hash_receipts_and_generated_contracts_match():
    folder = PACKAGE_ROOT / "fixtures/worker_outlook"
    bundle = json.loads((folder / "real_evidence.json").read_text())
    receipt = json.loads((PACKAGE_ROOT / "reports/worker_outlook/feed_snapshot.json").read_text())
    checksum = hashlib.sha256(
        json.dumps(bundle, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    assert checksum == receipt["canonical_export_sha256"]
    versions = {r["sha256"] for r in receipt["sources"]}
    for rows in bundle["evidence_by_site"].values():
        for row in rows:
            parsed = Evidence.model_validate(row)
            assert parsed.source_version in versions and not parsed.is_fixture
    for name, model in (
        ("worker_outlook", WorkerOutlook),
        ("worker_request", WorkerOutlookRequest),
    ):
        assert (
            json.loads((folder / (name + ".schema.json")).read_text()) == model.model_json_schema()
        )


def test_explanation_payload_excludes_rejected_evidence_and_control_state(predictor):
    case = scenarios()[0]
    outlook = build_worker_outlook(
        case["event_context"], case["site_context"], case["evidence"], predictor=predictor
    )
    payload = explanation_context(outlook)
    assert payload["allowed_evidence_ids"] == [
        a["evidence"]["evidence_id"] for a in outlook["evidence"] if a["accepted"]
    ]
    assert payload["not_work_clearance"] and not {"risk_score", "active_alerts"}.intersection(
        payload
    )


def test_unknown_future_artifact_version_cannot_inherit_fit_policy():
    from ml.worker.combined import _fit_policy

    with pytest.raises(ValueError):
        _fit_policy("Flood", "future-unreviewed-v99")


def test_heat_index_derived_only_from_matched_eligible_inputs():
    temperature = evidence(variable="temperature", hazard="heat", value=90.0, unit="F")
    humidity = evidence(
        evidence_id="fixture-rh", variable="relative_humidity", hazard="heat", value=70.0, unit="%"
    )
    result = predict_site_impact(
        site(), {"event_type": "Heat"}, [temperature, humidity], as_of_utc=TIME
    )
    index = next(
        c for h in result["site_hazards"] for c in h.conditions if c.variable == "heat_index"
    )
    assert index.value == pytest.approx((105.9220206 - 32) / 1.8) and index.value_basis == "derived"
    assert set(index.derived_from_evidence_ids) == {temperature.evidence_id, humidity.evidence_id}
    mismatch = humidity.model_copy(update={"source_version": "different-source"})
    other = predict_site_impact(
        site(), {"event_type": "Heat"}, [temperature, mismatch], as_of_utc=TIME
    )
    assert not any(c.variable == "heat_index" for h in other["site_hazards"] for c in h.conditions)


def test_external_derived_values_are_not_trusted_without_recomputation():
    fabricated = evidence(
        variable="heat_index",
        hazard="heat",
        value=80.0,
        unit="F",
        value_basis="derived",
        derived_from_evidence_ids=["missing"],
    )
    assert "external_derivation_requires_recomputation" in assess(site(), fabricated, TIME).reasons


def test_pre_event_warning_cannot_be_confirmation_of_already_active_event(predictor):
    case = scenarios()[0]
    ctx = copy.deepcopy(case["event_context"])
    start = parse_utc(ctx["event_start_utc"], "start")
    ctx["confirmation"]["confirmed_at"] = (
        start - __import__("datetime").timedelta(hours=1)
    ).isoformat()
    result = build_worker_outlook(ctx, case["site_context"], case["evidence"], predictor=predictor)
    assert result["event_outlook"]["ongoing_probability"] == {}
    assert "event_confirmation_or_context_invalid" in result["unknowns"]
