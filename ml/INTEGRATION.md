# Backend integration contract

## Combined worker advisory 2.0.0

The Cache-owned two-layer slice is implemented independently of production routes. See [WORKER_OUTLOOK.md](WORKER_OUTLOOK.md) for tested behavior, [DISASTER_COVERAGE.md](DISASTER_COVERAGE.md) for all 54 raw NOAA types and source maturity, and `ml/fixtures/worker_outlook/` for typed requests/responses/JSON schemas. Legacy 1.1 duration callables below retain their signatures and score exclusion.

```python
from ml.worker.combined import build_worker_outlook, build_for_backend_site, explanation_context
from ml.worker.schema import SiteContext, WorkerOutlook, WorkerOutlookRequest

# Authorize the user's assigned site / supervisor scope upstream, before this call.
outlook = build_worker_outlook(confirmed_event_context, trusted_site_context, normalized_evidence)
response = WorkerOutlook.model_validate(outlook)
```

`python -m ml.demo_worker_outlook --require-models` runs five offline end-to-end cases after the existing pinned artifacts are provisioned. It works in a fresh process from `backend/` with the repository root in `PYTHONPATH`. No source requests or training occur at inference. Initialize/recreate the process after provisioning to refresh cached artifact/fit metadata.

Required fields Rudra/Braydin must supply:

- Site: trusted `id`, `name`, valid `lat/lon`, `site_type`, `source`, `source_version`, explicit `is_fixture`. The research fixture contains 50 real EIA plant locations; this does not create backend DB rows. `build_for_backend_site` selects these identity fields without changing existing score/alert properties.
- Event: ID/type, `confirmed_active` or explicit `historical_replay`, start/as-of UTC, site association, target definition where required, and `confirmation={source, record_id, confirmed_at, available_at, is_fixture}`. Confirmation must follow event start and precede as-of. Upstream must confirm actual activation, not infer it from the model or a future warning.
- Evidence: `Evidence` objects from adapters, including original record/URL, values/units, geometry/precision, observed/issued/available/valid/ingested times, source revision and quality. Existing backend `Observation` fields alone do not establish historical issue-time availability or coverage. Missing fields must become unknown/422, not fabricated timestamps.
- Site/gauge relation: upstream verified basin relation and datum if gauge context is to be used; plain geographic proximity does not qualify.

The output contains `event_outlook`, `site_hazards`, accepted/rejected evidence with freshness/reasons, unknowns and safety literals. A missing/corrupt/late model makes Layer A unavailable while eligible source conditions can still be shown. No site probability model is validated; site `probability/confidence` remain null. Actual issued forecast values retain their provider method and windows. Derived heat index is labeled with input IDs/computation version. The examples use real weather with hypothetical event activation and are explicitly demo/simulated.

Proposed wiring for Rudra's review: an opt-in `GET /api/sites/{id}/worker-outlook` FastAPI route, authorized with existing site/role policy, builds the confirmed event and evidence server-side and returns `WorkerOutlook`. This route is **not implemented** here. Rudra owns any canonical API/TypeScript type publication. Existing SiteDetail, risk/alerts and lightning timer remain unchanged. Invalid request/site schema maps to 422; partial feed/model gaps remain typed partial/unavailable advisories. Do not map unavailable to low risk, a score reduction, or a clear time.

For Nick, canonical examples are `flood_outlook.json` and `wind_outlook.json`. Display method badges, explicit time window, station distance/grid coverage, derived-value marker, source IDs, rejected-data reasons and unknowns. Keep source rain % distinct from modeled event persistence. Keep official warnings and the real deterministic timer outside this advisory's authority; never display a duration median as a return-to-work countdown.

For Braydin, `explanation_context(outlook)` returns only accepted evidence plus allowed citation IDs and structured limits, without control state or a Gemini call. Treat source text as data. Validate generated schemas/citations and human report review; Gemini must not change scores, warnings, timers or permission. AirNow/FIRMS credentials were not requested or stored; their archives remain unavailable.

Measured warm/cold composition latency, clean-environment test results, unchanged artifact hashes, source receipts and MC/sensitivity details are in `ml/reports/worker_outlook/`. Reproduce `python -m pytest ml/tests backend/tests -q` with both ML and backend dependencies installed. No new backend route, schema field, frontend page, auth module, or database migration was changed.

## Preserved duration contract 1.1

Contract 1.1 adds event-specific research dispatch without changing these callable signatures or shared route schemas. Read the [multi-disaster handoff](MULTIDISASTER.md#rudra-handoff-contract-11) for exact target definitions, horizons, evidence requirements, qualified/disabled types, and examples. The instructions below retain the Flood v2 integration.

Rudra owns event confirmation, authorization, routes, scores, and deterministic alerts. Braydin owns database/ingestion modules. This package provides a tested import, not live route integration. The expansion began from `cf9d3bb` after Flood PR #4 merged and was rebased onto `origin/main` at `482b4f9`, including the team's merged API PR #5 and ownership updates. Unmerged team feature work is preserved.

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

The published `app.schemas.SiteSummary` is tested through the adapter using `site.model_dump(mode="json")`. `app.schemas.ModelOutput` validates actual inactive/active `predict_site` results. Its confidence and completeness can be null, empty contribution lists are accepted, and `ModelDataQuality.include_model_component_in_site_score` is constrained to false. The TypeScript quality mirror includes those fields; field-drift tests pass. These focused compatibility changes are for Rudra's PR review and do not add an event-outlook field to `SiteDetail` or enable ML scoring.

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
