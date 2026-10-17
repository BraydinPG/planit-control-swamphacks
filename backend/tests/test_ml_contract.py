"""Optional integration checks when backend and ML dependencies are installed."""

import json

import pytest
from pydantic import ValidationError

from app.schemas import ModelOutput, SiteSummary

pytest.importorskip("sklearn", reason="ML contract integration needs ml/requirements-lock.txt")

from ml.backend_adapter import ActiveEventPredictor
from ml.predict import predict_site
from ml.tests.test_prediction import active_context, training_events
from ml.train import fit_models, save_models
from unittest.mock import patch


@pytest.mark.parametrize("active", [False, True])
def test_canonical_model_output_accepts_actual_ml_payload_without_score_approval(active):
    features = {}
    model = None
    if active:
        model = fit_models(training_events(), minimum_events=1, minimum_episodes=1)
        features["active_event_context"] = active_context()
    payload = predict_site(features, model=model)
    canonical = ModelOutput.model_validate(payload)
    assert canonical.confidence is None
    assert canonical.data_quality.completeness is None
    assert canonical.data_quality.include_model_component_in_site_score is False
    assert canonical.factor_contributions == []
    json.loads(canonical.model_dump_json())
    payload["data_quality"]["include_model_component_in_site_score"] = True
    with pytest.raises(ValidationError):
        ModelOutput.model_validate(payload)


def test_published_site_summary_passes_the_cached_ml_boundary_unchanged(tmp_path):
    model = fit_models(training_events(), minimum_events=1, minimum_episodes=1)
    artifact = save_models(model, tmp_path / "model.joblib")
    site = SiteSummary.model_validate({
        "id": "fixture-site", "name": "Synthetic representative site", "lat": 28, "lon": -82,
        "assigned_team": None, "risk_score": 9, "risk_level": "critical",
        "updated_at": "2024-06-01T06:00:00Z", "active_alerts": 1,
        "top_factors": [], "data_completeness": 0.5, "model_version": "deterministic-fixture",
    })
    original = site.model_dump_json()
    outlook = ActiveEventPredictor(artifact).predict_for_site(site.model_dump(mode="json"), active_context())
    assert outlook["status"] == "ok"
    assert outlook["site_id"] == site.id
    assert site.model_dump_json() == original


@pytest.mark.parametrize("event_type", ["Flash Flood", "Heat Index Exceedance"])
def test_expansion_horizons_fit_existing_contract_and_stay_excluded(event_type):
    from ml.tests.test_multidisaster import entry, context
    rows = [{**row, "event_type": event_type} for row in training_events() * 3]
    model = fit_models(rows, event_type=event_type, minimum_events=1, minimum_episodes=1)
    record = {**entry(model), "event_type": event_type}
    event = {**context(), "event_type": event_type}
    if event_type == "Heat Index Exceedance":
        record["category"] = "heat"
        event["station_id"] = "722020-12839"
    with patch("ml.dispatch.read_registry", return_value={"events": {event_type: record}}):
        payload = predict_site({"active_event_context": event}, model=model)
    canonical = ModelOutput.model_validate(payload)
    assert set(canonical.hazard_probabilities) == {"active_event_persists_1", "active_event_persists_3", "active_event_persists_6"}
    assert not canonical.data_quality.include_model_component_in_site_score
    assert canonical.confidence is None
