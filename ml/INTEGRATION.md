# Backend Integration Contract

The accepted `feature/cache-ml` branch now includes Rudra's merged minimal FastAPI `/health` app and backend dependency/test scaffold. The backend still has no API schemas, active-event source, event activation, site data, auth policy, score pipeline, or ML import. This document defines the ML boundary only; it does not add a route or require a frontend change. Rudra remains the authority for event confirmation, role checks, final site score, deterministic alerts, and lightning timers.

## Primary callable

```python
from ml.predict import predict_active_event

outlook = predict_active_event(event_context)
```

Required fields:

- `event_id`: stable source/event identifier.
- `event_type`: currently exactly `Flood`.
- `event_status`: `confirmed_active` or `historical_replay`. Historical replay is always marked simulated.
- `as_of_utc`: timezone-aware ISO-8601 time.
- `event_start_utc`: required to condition on event age; unknown onset returns unavailable.
- `site_id`, `location.region`, or valid `location.lat` and `location.lon` association.
- Optional `location.spatial_match_quality`: `site_verified`, `point_nearby`, `region_only`, or `unknown`.
- Optional `recent_observations[]`: each item has a timezone-aware `valid_time_utc` no later than `as_of_utc`. These are validated but not consumed by this trained model.

The result is JSON serializable with `allow_nan=False`. An `ok` result contains `scope="conditional_on_confirmed_active_event"`, 6h/12h/24h recorded-event-ongoing probabilities and exact complements, remaining-duration quantiles (null when the tail is not identified within 168h), a separate conditional KM baseline, evidence-quality counts, version, and `trend="unknown"`. An unsupported event, missing model, missing age/location, invalid status, or future observation returns `status="unavailable"` (inactive/no event returns `not_applicable_no_confirmed_event`) with an empty `outcomes` object and no fabricated probabilities.

Example context below is synthetic and is not a real NOAA report:

```python
fixture_context = {
    "site_id": "eia-example-site-01",
    "event_id": "fixture-flood-001",
    "event_type": "Flood",
    "event_status": "historical_replay",
    "event_start_utc": "2024-09-10T10:00:00Z",
    "as_of_utc": "2024-09-10T16:00:00Z",
    "location": {
        "lat": 28.0,
        "lon": -82.7,
        "region": "example county",
        "spatial_match_quality": "region_only",
    },
    "recent_observations": [{
        "type": "precipitation_6h",
        "value": 18.0,
        "unit": "mm",
        "valid_time_utc": "2024-09-10T16:00:00Z",
        "source": "synthetic_fixture",
    }],
    "is_simulated": True,
}
outlook = predict_active_event(fixture_context)
if outlook["status"] == "ok":
    # Optional response field only after Rudra approves its API contract.
    response["event_outlook"] = outlook
```

Do not put raw Monte Carlo draws in APIs, Gemini prompts, or UI. The backend may expose a compact outlook only after it confirms the event and approves its response schema.

## Legacy `predict_site` compatibility

The original six keys remain. Probabilities, if available, are named `active_event_persists_6`, `_12`, and `_24`; these are not chances that an event starts. No event context returns `{}`. `model_component_0_10` is a neutral compatibility placeholder of `0.0`, `confidence` is `null`, and `data_quality.include_model_component_in_site_score` is always `false`. The backend must skip the component entirely, never add or subtract the placeholder, and must not let ML alter deterministic alerts.

```python
from ml.predict import predict_site

prediction = predict_site({"active_event_context": event_context})
if prediction["data_quality"]["include_model_component_in_site_score"]:
    approved_component = prediction["model_component_0_10"]
else:
    # Exclude the component; do not use its neutral placeholder in the score.
    approved_component = None
# Evaluate deterministic stop-work rules independently of this result.
```

## Artifact lifecycle and failure behavior

Train/backtest writes `ml/artifacts/active_event.joblib`, which is ignored and must be produced in the deployment build or installed through a trusted model-artifact process. Inference makes no network calls and does not train or simulate. Load only trusted artifacts from the matching model version. Missing/corrupt/unsupported artifacts return unavailable; the backend should retain existing deterministic behavior. Use a process-level backend cache if repeated disk loads are undesirable.

The backend README starts Uvicorn from `backend/`; in that launch context the repository root is not automatically on `sys.path`. Before importing `ml.predict` from a future route, Rudra should either install the ML package or add the repository root to the backend process import path. The backend import has not been tested because no ML endpoint or event context exists yet.

## Message for Rudra

> Cache's primary interface is `predict_active_event(event_context)`, conditional on a backend-confirmed active Flood and as-of time. The trained model currently uses NOAA Flood event age and month only; it does not consume weather/current site observations, and NOAA geography is regional. `recorded_event_end` is not a site-clearance signal. `predict_site` keeps the six legacy keys but uses explicit persistence names and sets `include_model_component_in_site_score=false`; exclude its zero placeholder. No API route or frontend change is required until you approve an optional response field. Deterministic alerts and lightning timers remain authoritative.
