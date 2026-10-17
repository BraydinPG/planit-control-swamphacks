# Backend integration contract

Rudra owns event confirmation, authorization, routes, scores, and deterministic alerts. Braydin owns database/ingestion modules. The integrated backend exposes only `GET /health`; frontend/auth remain starter/placeholders. This package provides a tested import, not live route integration. Team scope from `origin/main` at `5bde676` is preserved alongside conditional active-event scope.

## Import and lifecycle

Provision using `ml/QUICKSTART.md`. Initialize one predictor per backend process using a trusted local receipt. Hash checking verifies identity; never deserialize an artifact from an untrusted sender.

```python
import json
from ml.config import MODEL_PATH
from ml.backend_adapter import ActiveEventPredictor

receipt = json.loads(MODEL_PATH.with_suffix(".manifest.json").read_text(encoding="utf-8"))
predictor = ActiveEventPredictor(MODEL_PATH, expected_sha256=receipt["artifact_sha256"])

# In Rudra's authorized route, after confirming the event:
event_outlook = predictor.predict_for_site(site, event_context)
# Separate optional response field after approval; no score/alert mutation.
```

The site uses shared `id`, `lat`, and `lon` fields. The adapter rejects invalid coordinates or conflicting site IDs, preserves inputs, and never infers exposure. Event-location coordinates remain independent of site coordinates; `site_association` records the representative monitored location separately.

`from ml.predict import predict_active_event` also works directly. It loads the default artifact per call; the adapter loads once. Recreate the adapter after provisioning if initialization found no model. Inference never fits, accesses the network, or runs Monte Carlo.

When starting in `backend/`, put the repository root on Python's import path:

```powershell
# From repository root:
$env:PYTHONPATH = (Get-Location).Path
Set-Location backend
# Use an environment containing backend and ML dependencies.
python -m uvicorn app.main:app --port 8000
```

A fresh-process test starts in `backend/` with this import path and runs the real adapter. It does not add an endpoint or bypass Auth0.

## Context and result

Types are in `ml/contracts.py`; runtime validation is in `ml/schemas.py`.

- Require event ID/type, confirmed-active or historical-replay status, timezone-aware as-of time, and known event start no later than as-of.
- Require a site ID, region, or valid coordinate pair. Spatial match quality is explicit; coordinates do not establish verified exposure.
- Observations require finite values and valid time no later than as-of. Supplied acquisition times must also precede as-of; absent acquisition times are counted. These observations are validated but not model predictors.
- Optional evidence requires ID, source, and availability time no later than as-of. Missing provenance is labeled; supplied provenance is not independently verified. Rudra must confirm activation/evidence.

Exact synthetic input (not a real event or site):

```json
{
  "site_id": "eia-example-site-01",
  "event_id": "fixture-flood-001",
  "event_type": "Flood",
  "event_status": "historical_replay",
  "event_start_utc": "2024-09-10T10:00:00Z",
  "as_of_utc": "2024-09-10T16:00:00Z",
  "location": {"lat": 28.0, "lon": -82.7, "region": "example county", "spatial_match_quality": "region_only"},
  "evidence": [{"id": "fixture-active-confirmation", "source": "synthetic_fixture_not_real_event_evidence", "available_at_utc": "2024-09-10T16:00:00Z"}],
  "is_simulated": true
}
```

Verified v2 output excerpt:

```json
{
  "status": "ok",
  "scope": "conditional_on_confirmed_active_event",
  "estimator": "kaplan_meier",
  "model_version": "noaa-flood-conditional-km-v2",
  "production_eligibility": false,
  "is_simulated": true,
  "outcomes": {
    "recorded_event_ongoing_probability": {"6h": 0.7093663911845713, "12h": 0.6049586776859471, "24h": 0.47300275482093423},
    "recorded_event_ended_probability": {"6h": 0.29063360881542866, "12h": 0.39504132231405287, "24h": 0.5269972451790658},
    "remaining_duration_hours": {"p10": 2.0, "median": 22.0, "p90": null, "tail_horizon_hours": 168, "max_remaining_hours": 162.0, "tail_beyond_24h": true},
    "trend": "unknown",
    "trend_basis": "no_validated_time_varying_severity_labels"
  }
}
```

The complete result adds IDs, as-of/generation time, evidence sources, support/missingness/acquisition-time counts, artifact version/training policy, KM reference probabilities, and limitations. The full fixture/result and measured latency are in `ml/reports/purged_v2/adapter_smoke.json`. Unidentified duration quantiles are null. The 168h limit is total event age, with current remaining support given separately.

Inactive/no event returns `not_applicable_no_confirmed_event`. Invalid input, unsupported type, unavailable/corrupt model, insufficient support, or unsupported horizons returns `unavailable`; both return empty outcomes and the no-clearance warning. Results are strict JSON. Probabilities are deterministic; generation time records the call. Logistic is explicit research comparison via `predict_active_event(context, estimator="logistic")`.

## Compatibility and Rudra checklist

`predict_site` retains the original six keys. Pass context via `features["active_event_context"]`. Probability names are `active_event_persists_6`, `_12`, `_24`; no context yields an empty dictionary. The score component 0.0 is an excluded placeholder, confidence is null, and `include_model_component_in_site_score=false`. Skip this component entirely. No outlook lowers risk, clears alerts, or authorizes work.

1. Provision alongside backend dependencies and verify the trusted receipt.
2. Approve the optional response field and supply authorized site/event/as-of evidence.
3. Initialize one predictor per process; expose simulated/unavailable/limited states.
4. Keep scores, Gemini, deterministic alerts, and lightning timers independent.
5. Run the backend import test and ML smoke; add a route acceptance test once the route exists.

Copy-ready handoff: Cache exports a tested conditional Flood outlook through `ActiveEventPredictor` and `predict_active_event`. KM is default because corrected 2024 validation favors it. V2 purges boundary episodes. The compatibility score component stays excluded. Weather remains ERA5 retrospective research, trend is unknown, and all outputs remain production-ineligible advisory evidence. No result establishes site clearance. T050 remains Rudra's integration task.
