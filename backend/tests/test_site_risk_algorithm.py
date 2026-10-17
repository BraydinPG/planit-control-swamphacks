"""T051A qualification, bounded reporting, failure semantics and reproducible evaluation."""

import builtins
import json
import os
import subprocess
import sys
from datetime import timedelta
from itertools import permutations
from pathlib import Path

import pytest
from pydantic import ValidationError

import app.rules.score as scoring
from app.ingestion.nws_weather import RELATIVE_HUMIDITY, TEMPERATURE
from app.ingestion.settings import IngestionSettings
from app.rules.settings import RuleSettings
from app.schemas import DataState, HazardScore, HazardType
from tests.score_scenarios import (
    NOW,
    SITE,
    active_alert,
    defaults,
    flood,
    forecast_pair,
    healthy,
    lightning,
    reading,
    render_evaluation,
    report,
    scenarios,
    storm,
)

SETTINGS = defaults(RuleSettings)


@pytest.fixture(autouse=True)
def explicit_cache_settings(monkeypatch):
    monkeypatch.setattr(scoring, "get_ingestion_settings", lambda: defaults(IngestionSettings))


def run(observations=(), alerts=(), reports=(), **extra):
    return scoring.compute_score(
        SITE.id,
        list(observations),
        list(alerts),
        list(reports),
        NOW,
        settings=extra.pop("settings", SETTINGS),
        site=extra.pop("site", SITE),
        **extra,
    )


def factor(score, name):
    return next(f for f in score.factor_contributions if f.factor == name)


@pytest.mark.parametrize("case", scenarios(), ids=lambda case: case.id)
def test_fixed_scenarios(case):
    result = case.evaluate()
    assert result.risk_score == case.score
    assert result.data_completeness == case.completeness
    assert result.confidence == result.data_completeness
    assert HazardScore.model_validate_json(result.model_dump_json()) == result


def test_evaluation_artifact_is_exactly_reproducible():
    path = Path(__file__).resolve().parents[2] / "docs/site-risk-scoring-evaluation.json"
    assert path.read_text(encoding="utf-8") == render_evaluation()


def test_zero_with_no_evidence_is_unknown_not_a_healthy_zero():
    missing, current = run(), run(healthy())
    assert missing.risk_score == current.risk_score == 0
    # Frozen schema has no insufficient/unknown risk enum; this is a documented
    # consumer integration gap, never proof that missing conditions are low risk.
    assert missing.data_completeness == 0 and current.data_completeness == 1
    assert all(
        f.data_state == DataState.UNAVAILABLE and "unknown" in f.label.lower()
        for f in missing.factor_contributions
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"observed_at": NOW + timedelta(seconds=1)},
        {"fetched_at": NOW + timedelta(seconds=1)},
        {"valid_at": NOW + timedelta(seconds=1)},
        {"observed_at": NOW.replace(tzinfo=None)},
        {"fetched_at": NOW.replace(tzinfo=None)},
        {"observed_at": NOW, "fetched_at": NOW - timedelta(minutes=1)},
        {"source": "Gemini"},
        {"data_state": DataState.CREW_REPORTED},
        {"data_state": DataState.FORECAST},
        {"site_id": None},
        {"unit": "°C"},
        {"unit": None},
        {"value": float("nan")},
        {"value": float("inf")},
        {"value": "unmeasured"},
    ],
)
def test_unqualified_heat_never_becomes_a_current_zero(changes):
    invalid = reading(value=125).model_copy(update=changes)
    result = run([invalid, flood(), lightning()])
    heat = factor(result, "heat_index")
    assert heat.contribution == 0 and heat.data_state == DataState.UNAVAILABLE
    assert result.data_completeness == 0.67
    assert heat.evidence_id == invalid.id
    assert "excluded" in heat.label.lower()


@pytest.mark.parametrize(
    ("age", "state", "points"),
    [
        (60, DataState.OBSERVED, 2),
        (61, DataState.STALE, 2),
        (360, DataState.STALE, 2),
        (361, DataState.UNAVAILABLE, 0),
    ],
)
def test_weather_ages_cannot_be_disguised_by_a_fresh_fetch(age, state, points):
    result = run(
        [reading(value=125, observed_at=NOW - timedelta(minutes=age)), flood(), lightning()]
    )
    heat = factor(result, "heat_index")
    assert heat.data_state == state and heat.contribution == points
    assert result.data_completeness == (1 if state == DataState.OBSERVED else 0.67)


def test_event_issue_age_does_not_override_a_current_active_query():
    warning = flood(
        "Flood Warning", observed_at=NOW - timedelta(days=1), valid_at=NOW + timedelta(hours=1)
    )
    assert factor(run([warning]), "flood").data_state == DataState.OBSERVED
    assert factor(run([warning]), "flood").contribution == 2


def test_expired_tropical_warning_and_wrong_site_are_not_scored():
    expired = reading(HazardType.HURRICANE, "Hurricane Warning", "Expired", unit=None, valid_at=NOW)
    result = run(
        [expired, storm(site_id="other")],
        [active_alert(site_id="other")],
        [report(site_id="other")],
    )
    assert result.risk_score == 0
    assert factor(result, "hurricane").data_state == DataState.UNAVAILABLE
    assert factor(result, "lightning").data_state == DataState.UNAVAILABLE
    assert not any(f.factor == "crew_report" for f in result.factor_contributions)


@pytest.mark.parametrize(
    "changes",
    [
        {"valid_at": NOW - timedelta(seconds=1)},
        {"valid_at": NOW + timedelta(hours=13)},
        {"valid_at": None},
        {"observed_at": NOW + timedelta(minutes=1)},
        {"fetched_at": NOW + timedelta(minutes=1)},
    ],
)
def test_forecast_availability_and_horizon(changes):
    pair = [o.model_copy(update=changes) for o in forecast_pair()]
    heat = factor(run(pair), "heat_index")
    assert heat.data_state == DataState.UNAVAILABLE and heat.contribution == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"source_ref": "another-station"},
        {"lat": SITE.lat + 1},
        {"observed_at": NOW - timedelta(minutes=6)},
        {"source": "Unqualified"},
        {"source_ref": None},
        {"valid_at": NOW + timedelta(hours=3)},
        {"value": 101.0},
        {"value": -1.0},
        {"unit": "fraction"},
    ],
)
def test_temperature_and_humidity_cannot_be_cross_joined(changes):
    pair = forecast_pair()
    pair[1] = pair[1].model_copy(update=changes)
    heat = factor(run(pair), "heat_index")
    assert heat.data_state == DataState.UNAVAILABLE and heat.contribution == 0


def test_observed_heat_pair_and_stale_humidity_provenance():
    temp = reading(value=100, label=TEMPERATURE)
    humidity = reading(value=60, label=RELATIVE_HUMIDITY, unit="%", data_state=DataState.STALE)
    heat = factor(run([temp, humidity]), "heat_index")
    assert heat.contribution == 2 and heat.data_state == DataState.STALE
    assert humidity.id in heat.label and temp.id == heat.evidence_id


def test_raw_weather_does_not_add_another_heat_factor():
    extras = forecast_pair() + [
        reading(value=125),
        reading(value=100, label=TEMPERATURE),
        reading(value=60, label=RELATIVE_HUMIDITY, unit="%"),
    ]
    result = run(extras * 3)
    assert result.risk_score == 2
    assert len([f for f in result.factor_contributions if f.factor == "heat_index"]) == 1


def test_latest_feed_snapshot_replaces_old_warning_even_for_direct_callers():
    old = flood("Flood Warning", fetched_at=NOW - timedelta(minutes=10))
    none = flood()
    assert factor(run([old, none]), "flood").contribution == 0
    assert factor(run([old, none]), "flood").data_state == DataState.OBSERVED


def test_failed_feed_does_not_resurrect_an_old_current_warning():
    old = flood("Flood Warning", fetched_at=NOW - timedelta(minutes=10))
    failed = flood(data_state=DataState.UNAVAILABLE, label="Failed refresh")
    assert factor(run([old, failed]), "flood").data_state == DataState.UNAVAILABLE


def test_latest_lightning_fallback_cannot_reuse_older_live_coverage():
    old = lightning(
        id="old-live",
        fetched_at=NOW - timedelta(minutes=10),
        observed_at=NOW - timedelta(minutes=10),
    )
    replay = lightning(id="new-replay", source="lightning-replay", data_state=DataState.SIMULATED)
    result = run([reading(), flood(), old, replay])
    assert result.data_completeness == 0.67
    assert factor(result, "lightning").data_state == DataState.SIMULATED


def test_missing_alert_is_not_an_explicit_no_alert_observation():
    missing = flood(label="Missing alert payload")
    result = run([missing])
    assert factor(result, "flood").data_state == DataState.UNAVAILABLE
    assert result.data_completeness == 0


def test_optional_regional_outage_is_visible_but_does_not_redefine_p0_coverage():
    result = run(healthy() + [storm(data_state=DataState.UNAVAILABLE)])
    assert result.data_completeness == 1
    assert factor(result, "hurricane").data_state == DataState.UNAVAILABLE
    assert "hurricane" not in {f.factor for f in run(healthy()).factor_contributions}


def test_lightning_alert_survives_outage_and_elapsed_timer_without_mutation():
    alert = active_alert(clear_after=NOW - timedelta(minutes=1), distance_miles=None)
    before = alert.model_dump_json()
    result = run([lightning(data_state=DataState.UNAVAILABLE)], [alert])
    assert factor(result, "lightning").contribution == 3
    assert factor(result, "lightning").source == "deterministic lightning alert"
    assert result.data_completeness == 0
    assert alert.model_dump_json() == before and alert.state.value == "active"


@pytest.mark.parametrize(
    "changes",
    [
        {"state": "cleared"},
        {"triggered_at": NOW + timedelta(minutes=1)},
        {"latest_event_at": NOW + timedelta(minutes=1)},
    ],
)
def test_ineligible_alert_input_does_not_supply_points(changes):
    assert factor(run(alerts=[active_alert(**changes)]), "lightning").contribution == 0


@pytest.mark.parametrize(
    "changes",
    [{"simulated": True}, {"data_state": DataState.SIMULATED}, {"source": "lightning-replay"}],
)
def test_replay_markers_cannot_claim_live_completeness(changes):
    result = run([reading(), flood(), lightning(**changes)])
    assert result.data_completeness == 0.67
    assert factor(result, "lightning").data_state == DataState.SIMULATED


@pytest.mark.parametrize("kind", ["heat_index", "flood"])
def test_aged_replay_preserves_origin_as_well_as_stale_state(kind):
    replay = reading(value=125) if kind == "heat_index" else flood("Flood Warning")
    replay = replay.model_copy(
        update={
            "data_state": DataState.SIMULATED,
            "observed_at": NOW - timedelta(minutes=61),
            "fetched_at": NOW - timedelta(minutes=61),
        }
    )
    result = run([replay])
    assert factor(result, kind).data_state == DataState.STALE
    assert "simulated replay" in factor(result, kind).label
    assert result.data_completeness == 0


def test_report_caps_preserve_all_distinct_evidence_and_reviewed_category():
    reports = [report(f"r{i}", confirmed_category="wildlife") for i in range(5)]
    result = run(reports=reports)
    factors = [f for f in result.factor_contributions if f.factor == "crew_report"]
    assert [f.contribution for f in factors] == [1.5, 1.5, 0, 0, 0]
    assert {f.evidence_id for f in factors} == {r.id for r in reports}
    assert all("wildlife" in f.label for f in factors)
    assert all("cap" in f.label for f in factors[2:])


def test_shared_notice_scores_highest_severity_once_and_retains_other_report():
    result = run(
        reports=[
            report("low", confirmed_severity="low", notice_id="n"),
            report("high", notice_id="n"),
        ]
    )
    factors = [f for f in result.factor_contributions if f.factor == "crew_report"]
    assert [(f.evidence_id, f.contribution) for f in factors] == [("high", 1.5), ("low", 0)]
    assert "shared notice" in factors[1].label


def test_report_versions_use_latest_status_and_ties_prefer_exclusion():
    present = report()
    absent = report(hazard_present=False)
    rejected = report(review_status="rejected", reviewed_at=NOW)
    for versions in permutations([present, absent, rejected]):
        assert not any(
            f.factor == "crew_report" for f in run(reports=versions).factor_contributions
        )
    assert run(reports=[present, absent]).risk_score == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"created_at": NOW + timedelta(seconds=1)},
        {"reviewed_at": NOW + timedelta(seconds=1)},
        {"reviewed_at": NOW - timedelta(days=1)},
        {"reviewed_at": NOW.replace(tzinfo=None)},
    ],
)
def test_reports_not_known_as_of_snapshot_are_excluded(changes):
    assert run(reports=[report(**changes)]).risk_score == 0


def test_old_confirmed_hazard_does_not_silently_expire():
    old = report(created_at=NOW - timedelta(days=365), reviewed_at=NOW - timedelta(days=365))
    assert run(reports=[old]).risk_score == 1.5


def test_legacy_missing_severity_has_explicit_moderate_fallback():
    result = run(reports=[report(confirmed_severity=None)])
    assert result.risk_score == 1 and "legacy moderate" in factor(result, "crew_report").label


@pytest.mark.parametrize(("severity", "points"), [("low", 0.5), ("moderate", 1), ("high", 1.5)])
def test_reviewed_report_severity_weights(severity, points):
    assert run(reports=[report(confirmed_severity=severity)]).risk_score == points


def test_capped_report_credit_does_not_depend_on_order():
    inputs = [report("r1", confirmed_severity="low"), report("r2"), report("r3")]
    baseline = run(reports=inputs)
    for ordered in permutations(inputs):
        assert run(reports=ordered) == baseline


def test_previous_score_and_inputs_remain_unchanged():
    observations = healthy()
    previous = run([reading(value=125)])
    before = [o.model_dump_json() for o in observations]
    result = run(observations, previous=previous)
    assert result.previous_score == 2 and result.created_at == NOW
    assert [o.model_dump_json() for o in observations] == before
    assert run(previous=previous.model_copy(update={"site_id": "other"})).previous_score is None


def test_no_model_gemini_dependency_or_clearance_field(monkeypatch):
    original = builtins.__import__

    def block_ai(name, *args, **kwargs):
        if name.startswith(("ml", "sklearn", "app.gemini")):
            raise ImportError("AI deliberately unavailable")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", block_ai)
    result = run(healthy(), [active_alert()])
    assert result.risk_score == 3 and result.model_is_fallback is False
    payload = json.loads(result.model_dump_json())
    assert (
        not {"work_authorized", "all_clear", "safe", "clear_after", "hazard_probabilities"}
        & payload.keys()
    )


def test_fresh_process_inference_without_ml_or_gemini():
    backend = Path(__file__).resolve().parents[1]
    program = """
import builtins
from datetime import datetime, UTC
real_import = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.startswith(('ml', 'sklearn', 'app.gemini')):
        raise ImportError('AI unavailable for this check')
    return real_import(name, *args, **kwargs)
builtins.__import__ = guarded
from app.rules.score import compute_score
from app.rules.settings import RuleSettings
result = compute_score('synthetic-site', [], [], [], datetime(2026,10,17,tzinfo=UTC),
                       settings=RuleSettings(_env_file=None))
assert result.data_completeness == 0 and result.risk_score == 0
print(result.model_version)
"""
    env = dict(os.environ, PYTHONPATH=str(backend), GEMINI_API_KEY="", DEV_AUTH_BYPASS="false")
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=backend,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    assert result.stdout.strip() == scoring.MODEL_VERSION


@pytest.mark.parametrize(
    "overrides",
    [
        {"lightning_stop_work_points": -1},
        {"report_high_points": float("nan")},
        {"flood_watch_points": float("inf")},
        {"report_category_max_points": 11},
        {"heat_min_points": 3},
        {"flood_watch_points": 3},
        {"report_low_points": 2},
    ],
)
def test_invalid_weight_configuration_is_rejected(overrides):
    with pytest.raises(ValidationError):
        RuleSettings(_env_file=None, **overrides)


def test_custom_valid_weights_and_category_cap_are_respected():
    settings = RuleSettings(
        _env_file=None, lightning_stop_work_points=4, report_category_max_points=2
    )
    result = run(alerts=[active_alert()], reports=[report("r1"), report("r2")], settings=settings)
    assert result.risk_score == 6 and result.risk_level.value == "high"


def test_fractional_custom_report_weight_respects_category_budget():
    settings = RuleSettings(_env_file=None, report_low_points=0.016)
    result = run(
        reports=[report(f"r{i}", confirmed_severity="low") for i in range(200)], settings=settings
    )
    contributions = [
        f.contribution for f in result.factor_contributions if f.factor == "crew_report"
    ]
    assert sum(contributions) == pytest.approx(3)
    assert result.risk_score == 3 and len(contributions) == 200


@pytest.mark.parametrize("changes", [{"value": -1.0}, {"unit": "m/s"}, {"value": "unknown"}])
def test_malformed_nhc_intensity_is_unknown_not_qualifying(changes):
    result = run([storm().model_copy(update=changes)])
    hurricane = factor(result, "hurricane")
    assert hurricane.contribution == 0 and hurricane.data_state == DataState.UNAVAILABLE


@pytest.mark.parametrize(
    ("score", "band"),
    [
        (2.99, "low"),
        (3, "moderate"),
        (5.99, "moderate"),
        (6, "high"),
        (7.99, "high"),
        (8, "critical"),
        (10, "critical"),
    ],
)
def test_band_boundaries(score, band):
    assert scoring.risk_level(score).value == band


def test_bad_site_or_scoring_clock_fails_explicitly():
    with pytest.raises(ValueError, match="site must match"):
        run(site=type("InvalidSite", (), dict(id=SITE.id, lat=float("nan"), lon=0))())
    with pytest.raises(ValueError, match="timezone"):
        scoring.compute_score(SITE.id, [], [], [], NOW.replace(tzinfo=None))
