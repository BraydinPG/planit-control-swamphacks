# Comprehensive worker advisory: opt-in contract 2.1.0

This Cache-owned library adds explicit worksite verification questions, native official notices, reviewed-report contracts and contextual source estimates. It serves no endpoint, validates no Auth0 token and changes no route, score, warning, work permission or timer. All outputs remain research-only and operationally ineligible.

## Run the complete offline acceptance package

From the repository root in PowerShell:

```powershell
./ml/setup.ps1 -ProvisionModel
$MlPython = '.\ml\.venv\Scripts\python.exe'
& $MlPython -m ml.provision_expansion --download
& $MlPython -m ml.hazard_rehearsal --require-models
```

The last line is the one-command **31-scenario + 50-site** acceptance run after provisioning. It blocks socket connections, validates requests/responses, checks fixture hashes and writes concise scenario/site reports under `ml/reports/hazard_coverage/`. It needs no API keys, private data or live services. Omit `--require-models` to test disconnected missing-artifact fallback; source conditions still work while Layer A is unavailable. Install `backend/requirements-dev.txt` to run `python -m pytest ml/tests backend/tests -q`.

`--benchmark` measures 30 warm calls for the first two examples, cold Flood artifact initialization, response validation, single-worker batch time and traced Python allocations. The memory figure is not whole-process RSS. `--export` intentionally refreshes canonical payloads/schemas and normalized fixture hashes. Registry/source-report rebuilds (`python -m ml.hazard_registry`, `python -m ml.hazard_inventory`) use committed data only. No command here runs a historical backtest or Monte Carlo at inference.

Only `python -m ml.collect_hazard_sources --collect --site-alerts` intentionally acquires bounded agency snapshots. It uses the already-pinned EIA workbook and read-only backend selector, then caches responses with hashes. Re-running a cached capture preserves its original vintage. It is a research acquisition tool, not a live ingestion daemon. AirNow/AQS/FIRMS credentials are not read or supplied.

## Compatibility and exact imports for Rudra

Existing `build_worker_outlook()` returns the same strict **2.0.0** shape. `predict_active_event`, `predict_site`, `ActiveEventPredictor` and the 1.1 model contract remain intact. The only old evidence-gate hardening rejects observed windows ending after as-of. Existing duration fits, selection and disabled-model gates are unchanged.

```python
from ml.worker.comprehensive import build_comprehensive_outlook
from ml.worker.comprehensive_schema import (
    ComprehensiveOutlook, ComprehensiveRequest, TrustPolicy, to_legacy,
)

# Authorize the authenticated user's organization/team/assigned site FIRST.
# All following inputs come from trusted server storage/ingestion, not client assertions.
policy = TrustPolicy(allowed_report_issuers=frozenset({"your-reviewed-report-service"}))
result = build_comprehensive_outlook(
    confirmed_event_context, trusted_site_context, normalized_evidence,
    alerts=native_nws_notices,
    reports=reviewed_server_reports,
    context_signals=qualified_context_products,
    source_states=source_availability,
    trust_policy=policy,
)
response = ComprehensiveOutlook.model_validate(result)
legacy_response = to_legacy(response)  # Explicit strict 2.0 conversion when needed.
```

A strict 2.0 consumer cannot directly parse extra 2.1 fields; keep the old callable or use `to_legacy()`. Do not silently substitute the new envelope in a shared API. `ComprehensiveRequest` describes normalized server inputs; it is not a proposed public ingestion body. `trust_policy` and a principal/role are deliberately absent from its JSON schema. Default report trust is empty/deny.

New fields are `registry_version`, `worksite_hazards`, `official_notices`, `reviewed_reports`, `context_evidence`, `lightning_replay_context`, `source_availability` and `trust_boundary`. Each worksite item retains null probability/severity, source IDs, method, windows, association, unknowns and `needs_field_verification=true`. CAP severity is a provider field, not a worker-safety grade. Source MMI is a modeled shaking estimate, not damage or injury severity.

The three full canonical request/response pairs and standalone JSON schemas are in `ml/fixtures/hazard_coverage/`. Examples 1/2 use the actual backend-selected plants `eia860m-FL-59611` and `eia860m-AZ-68414`; example 3 includes an actual NWS point-relevant notice. **All event activations are hypothetical replays.** Real source records do not verify an actual disaster or worker incident at those plants.

Required trusted inputs:

- Site ID/name/coordinates/type, actual source revision and fixture state. Backend `SiteDetail.source` alone does not supply a revision hash. Never infer a missing revision from request time.
- Actual confirmed activation or labeled replay, event type/start/as-of and confirmation source/record/review/availability. An official warning, weather value or model prediction does not itself confirm event onset.
- Evidence values, units, acquisition/observation, issue/update, availability, valid interval, ingestion time, geometry, version and QC. Revised archives/reanalysis cannot masquerade as earlier operational features.
- Report issuer, immutable record/site/hazard IDs, pin, observation/review/availability/expiry, review state and supervisor/asset-operator authority, verified upstream. Uploads, crew suggestions and Gemini labels remain unconfirmed; no automatic classification or alert mutation occurs.
- Independently verified basin/site relationship and datum before using a gauge. The five modern USGS stage readings have no such transfer and remain rejected. No gauge-to-inundation-depth mapping is implemented.

Invalid request/site/coordinate/schema/version inputs map to **422** in future FastAPI wiring. Direct library ingestion retains invalid individual source rows as explicit gaps while valid data remain usable. Missing/corrupt/late/wrong-category artifacts yield unavailable Layer A. Partial evidence and empty queries never mean zero risk. Current main's site routes and nullable scores are preserved. Auth0/assigned-site route checks remain a real dependency; no production permission verification is claimed by the fixture rehearsal.

Proposed route for Rudra's review only: opt-in authenticated `GET /api/sites/{site_id}/worker-outlook`, assembling trusted inputs server-side and returning a separate 2.1 advisory. No route is implemented here. Publish shared backend/TypeScript types only after review; keep advisory output out of deterministic scoring, official orders, alerts, report instructions and lightning clearance.

## Notice, report and source rules

NWS notices preserve sent/updated/effective/onset/ends/expires, actual/test status, alert/update/cancel type, references, geometry, zones, severity/certainty/urgency, retrieval time and version. Polygon holes and multi-polygons are checked; malformed/self-crossing/dateline geometry fails closed. Cancellation/supersession/expiration changes source currency only, never existing control state. A research freshness policy marks captures older than one hour stale.

Where no polygon exists, only a captured NWS `point=lat,lon` query tied to the same trusted site can establish `provider_point_filter` relevance. The receipt URL and query coordinates are checked. This is not fabricated polygon coverage or an on-site measurement; an excluding polygon/hole still wins. Zone-only national records stay unmatched. Successful empty queries are distinguished from retrieval/parse failure and never imply work clearance.

Reviewed reports require a server-whitelisted issuer, correct site/pin, review role, chronology and freshness. The prototype pin-association bound is 500m, not a hazard radius or safety boundary. Contradictory presence reports remain partial; a reported absence remains a historical statement, not clearance. Fixture reports require an explicitly enabled fixture policy, never used as an authentication substitute. The CLI's role/site scope rehearsal accepts replay activation only; it is not a token validator or deployable auth dependency.

USGS v1 stage, native ShakeMap and SWPC messages have separate provenance. The real ShakeMap covers Pakistan and no US EIA batch point; its synthetic location example is labeled. The grid is automatic and its uncertainty product was not retrieved. SWPC non-K radio/particle messages are not relabeled geomagnetic; message prose is not parsed into expiry or site outages. PM2.5 needs an explicit averaging window, keeps concentration units, and never becomes AQI by conversion. Heat index needs exact time/source/footprint-matched eligible inputs; WBGT, wet bulb, personalized illness and work/rest rules are unsupported.

## Nick: render the actual statuses

Use the 2.1 response/schema fixtures rather than inventing UI fields. Show separate badges for observed readings, actual issued forecasts/notices, modeled ShakeMap context, reviewed reports, research duration, synthetic/replay data, stale, rejected and unknown. A source value and a derived heat index need different labels. Show validity/age, source IDs, polygon/point-filter/station association and rejection reasons.

`worksite_hazards.status` is `evidence_available`, `reported_present`, `reported_absent`, `partial` or `unknown`; it is not a risk ranking. `evidence_status` distinguishes accepted/mixed/rejected/not-supplied. Keep source precipitation percent separate from regional persistence. Never show duration as countdown-to-clearance, imply line de-energization from weather, or hide the deterministic alert/timer behind an unavailable advisory. Loading/error/degraded UI can use partial results and explicit source availability; no frontend files are changed here.

## Braydin: trusted provenance and authentication dependencies

Supply Auth0 organization/team/assigned-site authorization upstream, reviewed source records and confirmed activation provenance. Schema validity, a claimed issuer or `review_status=confirmed` is not proof of authenticity. Do not accept those claims directly from a browser. Main's EIA IDs come from the actual selector; the batch checks membership, state/plant association, source revision, coordinates and vintage. It does not inspect deployed DB contents, work orders or independent state-boundary GIS.

No live reviewed report/asset feed, universal DOT/evacuation feed, site gauge relation, authenticated AirNow/FIRMS archive or new local probability model is supplied. [SOURCE_INVENTORY_DIFF.md](SOURCE_INVENTORY_DIFF.md) lists provider access and migration details. The existing 2.0 `explanation_context(to_legacy(response))` gives Gemini accepted legacy evidence only. Newly native point notices/reports/context are excluded from that helper until Braydin publishes an equally strict allowlisted evidence/citation adapter; never send the whole unchecked request or source prose as instructions.

## Verification and sign-off

Full test/build results are in `ml/reports/hazard_coverage/validation.json`; replay coverage/performance in `acceptance.json`, and per-site counts in `site_batch.json`. Normalized JSON fixture digests explicitly normalize CRLF to LF for clean Git exports on Windows/Linux; original HTTP byte hashes remain exact and unchanged. Scenario manifests record canonical request hashes and a deterministic factory rather than duplicating captured weather thirty times.

The [146-entry registry](hazard_registry.json) and [hazard audit](HAZARD_COVERAGE_AUDIT.md) distinguish trained/backtested/disabled, real retrieval, qualified site evidence, fixture contracts, context, blocked sources and teammate dependencies. No new learned site probability or operational validation was performed. Existing per-category chronological/KM comparisons remain in [MULTIDISASTER.md](MULTIDISASTER.md) and [EVALUATION.md](EVALUATION.md); reviewed 2025 data are not a pristine holdout. Offline Monte Carlo checks distribution arithmetic/sensitivity only, not historical predictive skill.

Next owner actions: (1) Rudra reviews the frozen opt-in envelope and authorized route proposal; (2) Braydin connects real auth/activation/provenance and report feeds; (3) Nick renders methods/unknowns from canonical responses. No ML result, missing evidence or confirmed-absence report can downgrade deterministic alerts or grant work authorization.
