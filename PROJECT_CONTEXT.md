# PlanIT Control: shared project context

Read this verified index first, then `AGENTS.md`, `spec.md`, `tasks.md` and relevant source. Keep this short; detailed evidence belongs in the linked guides.

## T055 checkpoint: 2026-10-17
- PR #26 integration: incorporated reviewed main `9b395f0` into this feature branch, preserving Rudra's T049A regional factors (`compute_score(site=...)`), T049B current-observation refresh input/background lifecycle and T073 outage tests. Feed-created notices now persist the same supervisor receipt needed by T054; source-notice confirmation integration tested. Post-integration backend: 487 passed, zero skipped, one existing deprecation (10.72s); Ruff lint/format (109 files) and whitespace checks pass. No PR merge into main or deployment.
- Delivery: implementation `61b9263` committed and pushed to `origin/feature/nick-hazard-confirmation`; review PR #26 opened against main: https://github.com/BraydinPG/planit-control-swamphacks/pull/26. T054/T054A/T055 are ready for Rudra review; no PR merge into main or deployment performed.
- Same `feature/nick-hazard-confirmation` branch: T054 crew-hazard confirmation now atomically persists a refreshed deterministic site score with the report/notice/audits. Scoring failure rolls back confirmation; absent review and instruction send do not refresh scores. T055 checked after acceptance; Rudra handoff: `docs/T055_IMPLEMENTATION.md`.
- Scoring uses all confirmed-present site reports, without the UI's 50-report display limit. Existing weights, default severity, cap, evidence IDs, freshness and ML exclusion preserved. Only the reporting site's score changes; lightning/alerts/countdowns unchanged.
- `score_site` retains default commit behavior and adds `commit=False` for caller-owned transactions; per-site PostgreSQL row lock, UUID score IDs and monotonically ordered version timestamps prevent competing/same-time refresh ambiguity. DB tables and API fields unchanged.
- Full backend verification with ML integrations: 409 passed, zero skipped, one existing Starlette/httpx deprecation (10.01s); Ruff lint/format (103 files) pass. Ten new report-score checks include separate-connection concurrent distinct confirmations, exclusions, older reports and score/audit rollback. No live PostgreSQL/tenant/provider or frontend acceptance claimed. Earlier checkpoints below record prior behavior/test counts.

## T054A checkpoint: 2026-10-17
- Follow-up verification with declared ML dependencies available: full backend `python -m pytest -q -rs` passes 399 tests with zero skips (9.06s), including the previously skipped ML contract/adapter integration checks. One existing Starlette/httpx deprecation warning. Ruff lint, formatting (102 files), pip dependency check and Git whitespace check pass. No implementation changes in this verification run.
- Same `feature/nick-hazard-confirmation` branch: confirmation now obtains a validated unsent draft through `app.gemini.suggest_confirmed_instruction`; null/manual entry on missing configuration, provider error or invalid output. Helper/export added as a focused required integration; Braydin handoff in `docs/T054A_IMPLEMENTATION.md`.
- New `POST /api/hazards/{id}/instruction` accepts the confirming supervisor's final text with supervisor role and send permission. Atomic send-once update and per-team audits deliver through site detail to teams currently inside the stored radius. Drafts are private to the confirmer; no auto-send, new radius, score, alert or countdown mutation.
- Fresh checks: 73 focused tests; full backend 393 passed, 2 optional ML integration checks skipped, one existing Starlette/httpx deprecation; backend Ruff lint/format pass. Tests use synthetic Gemini responses and separate-connection race checks. No live provider/tenant/database deployment or frontend acceptance claimed.
- T054A checked after its backend acceptance. T055 stays open. Existing schemas, DB tables, migrations, dependency manifests, frontend and auth internals preserved; prior T054/frontend checkpoints below describe earlier verification states.

## T054 checkpoint: 2026-10-17
- Branch `feature/nick-hazard-confirmation`: Nick's authorized backend T054 adds `POST /api/hazards/{id}/confirm` and `POST /api/reports/{id}/review`; Rudra reviews integration. Guide: `docs/T054_IMPLEMENTATION.md`.
- T053 is present/checked in this checkout. Its report creation now snapshots supervisor delivery receipts as audit events. Confirmation requires the recorded recipient and supervisor role/permission; old notices without receipts fail closed. First confirmation is atomic; report/notice/reviewer/time/audits commit together. No new database tables or shared API fields.
- Absent reports can be reviewed only by their organization's supervisor; site-detail reads now keep absent reports inside that organization. Optional reviewer notes are audit records, preserving the crew note.
- Fresh backend verification: `python -m pytest -q -rs`: 363 passed, 2 skipped (optional ML dependencies absent), one existing Starlette/httpx deprecation. Backend Ruff lint/format and Git whitespace checks pass. Concurrent separate-connection confirmation and audit-failure rollback covered; no live Tiger Data/Auth0/Gemini deployment verification.
- T054 checked after acceptance. T054A Gemini/instruction send and T055 refreshed-score persistence remain open; suggestion/generated-by are null. No frontend capability, deterministic alert, ML, migration, manifest or auth-internal changes. Earlier frontend handoff below is historical and predates T053/T054 availability.

## Last verified: 2026-10-17
- Explicit user transfer: Cache owns remaining frontend implementation/integration, formerly Nick. Prior attribution and T030 remain preserved. Claude's later visual redesign requires separate authorization.
- Branch `feature/cache-frontend-workflows`, targeting main `723a5b8`. PR #16 (T030) and #17 (`140d118`, ownership/T031) merged during this run; the new branch preserves them and incorporates reviewed main via `dc35458`. T032-T038 implementation: `3fbd98f`.
- Rudra completed T073: `backend/tests/test_feed_failures.py` (32 tests) covers stale/unavailable for all six feeds and confirms no outage clears a lightning alert. Fixed the lightning score factor labeling a fully unavailable feed as stale. Full backend suite 419 passed.
- Rudra completed T049B: feed refresh loop in `backend/app/services/refresh.py` stores every feed's Observations, runs the lightning rule and feed notices, and rescores each site. Off by default (`FEED_REFRESH_ENABLED`); one-shot `python -m app.services.refresh`. A raising feed is stored as unavailable; one site's failure doesn't stop the others. Full backend suite 387 passed.
- Rudra completed T049A: prototype hurricane/earthquake rules in `backend/app/rules/regional.py` (score factors, P1, outside data completeness) and feed-detected "potential {hazard}" notices in `backend/app/services/feed_notices.py` (default radius 50/25 mi, one notice per event, fresh readings only). `compute_score` takes an optional `site`. Tests: `backend/tests/test_regional_rules.py`; full backend suite 378 passed.
- Rudra published T050 (`9d73a77`) and T048 (`944471f`, PR #18). Their canonical backend/fixtures/types were inherited from main unchanged, with no Cache-authored backend/API diff.
- T031-T038 foundation/demo acceptance passed; T032-T038 checked with implementation/evidence in this checkpoint. T063-T068 remain unchecked, with exact dependencies in `docs/INTEGRATION_STATUS.md`.
- Vite: http://localhost:5173/; interactive simulated crew/supervisor app, 55 map/list points, reporting/review/instruction flow and exact-site research advisory.
- 23 focused frontend tests, lint/TypeScript/build and 1440/390/320 browser workflows passed. Current merged branch backend suite: 297 passed, one existing dependency deprecation. Earlier branch/export checks were 266/282 passed. See `docs/frontend-acceptance.json`.
- Clean committed frontend export `4a9e44f`: npm ci/build and full static-bundle demo browser acceptance pass without local env/Python/ML artifacts. No whole-app/deployment acceptance claimed.
- Actual health 200; protected site reads directly and via Vite proxy return 401. No real signed-in site data, report persistence, Auth0 tenant login or Gemini response was verified.
- Local Auth0/Tiger Data settings and missing report/notice/Gemini routes block real integration. Published alert listing/acknowledgement is connected and mock-tested. No production deployment, bypass, model retraining or ML contract changes.

## Ownership and safety
- Cache: `ml/**` plus remaining frontend composition/data access/pages/components/styles/tests and integration preparation under this explicit transfer.
- Rudra: canonical API/types/fixtures, backend routes, deterministic alerts/scoring and shared coordination.
- Braydin: Auth0 internals, Tiger Data/database/ingestion/Gemini and deployment under current AGENTS; no credential or backend rewrite by Cache.
- Nick retains prior attribution; no parallel remaining UI implementation is assigned. See `docs/CROSS_SCOPE_CHANGES.md` for exact paths, dependency/commit/PR evidence.
- EIA plants are representative locations, not active jobs. Unknown is not zero/low risk.
- ML estimates recorded-event persistence conditional on a confirmed event or explicit replay. No onset, local injury probability, alert downgrade or work authorization.
- Recorded event end and elapsed lightning countdown never establish worksite clearance. Rudra owns deterministic state; human review confirms reports/instructions.

## Frontend navigation and run
```powershell
cd frontend
npm ci
npm run dev -- --host localhost --port 5173 --strictPort
```
- Node 24; default explicit fixture/demo mode needs no Python, artifact, Auth0 or database. Local demo namespace `planit:frontend-demo:v1`; photos memory-only.
- `App.tsx`: mode composition; `application/*`: existing Auth0 integration/session state; `api/contracts.ts` and `http-client.ts`: shared interface/HTTP; `demo/client.ts`: isolated simulated mutations.
- `pages/ConnectedPages.tsx`: shared views; `components/data/*`: reusable status/alerts/notices/map/advisory; existing `components/shell/*`: responsive navigation.
- Canonical `frontend/src/types/api.ts` and `src/fixtures/*.json` unchanged. Approved public ML exports in `src/demo/generated/*`; no Python inference in browser.
- `VITE_USE_FIXTURES=false` uses existing provider/guard and bearer-token API, rejects bypass roles; no fixture fallback. Empty API base uses Vite's /api proxy to existing FastAPI:8000. Production requires owner routing.
- Live alert reads/acknowledgement enabled for T048, with server Date clock correction; report/notice/AI capabilities disabled until routes exist. T050 canonical compact field displayed if supplied; 2.1 panel is exact-site demo only, with null local probabilities and explicit unknown hazards.
- Full guide: `frontend/INTEGRATION.md`; task/live matrix: `docs/INTEGRATION_STATUS.md`; visual boundaries: `docs/FRONTEND_REDESIGN_HANDOFF.md`.
- Browser checks: `node scripts/check-shell.mjs http://localhost:5173/`; focused tests: `node --test --test-concurrency=1 tests/status.test.mjs tests/data.test.mjs`. Screenshots ignored under `.shell-check/`.

## Existing ML package (unchanged)
- `ml/predict.py`: predict_active_event and safe predict_site compatibility. `ml/backend_adapter.py`: ActiveEventPredictor; `ml/dispatch.py`: per-type/hash model dispatch.
- `ml/worker/combined.py`: build_worker_outlook (2.0); `ml/worker/comprehensive.py`: build_comprehensive_outlook (2.1 additive). Verify imports in source.
- Six research duration targets: Flood, Flash Flood, High Wind, Heavy Rain, Winter Storm, observed Heat Index Exceedance. Strong Wind/Ice Storm/Heavy Snow disabled; no supported intensity/trajectory prognosis.
- 349,030 NOAA rows / 54 original labels; grouped chronological validation, inspected 2025 holdout, baseline selection and existing artifact hashes preserved. No new backtest in this frontend run.
- Inventory: `ml/hazard_registry.json`, `HAZARD_COVERAGE_AUDIT.md`, `SOURCE_INVENTORY_DIFF.md`; full method/evaluation: `METHODOLOGY.md`, `EVALUATION.md`, `MULTIDISASTER.md`.
- Sources: `ml/source_catalog.json`, `ml/fixtures/hazard_coverage/`, `ml/reports/hazard_coverage/`. 50 reconciled backend reference identities; previous qualified environmental coverage 2/50 and notices 10/50. Real captures pair with hypothetical activations.
- Handoffs/provisioning: `ml/HAZARD_INTEGRATION.md`, `ml/WORKER_OUTLOOK.md`, `ml/WORKER_PREVIEW.md`, `ml/INTEGRATION.md`. Offline 31-scenario/50-site rehearsal and T087 preview already implemented.
- Full 2.1 live endpoint needs owner-approved schema/provenance/permissions. Manual electrical/structural/chemical/access/wildlife states remain unverified without trusted field evidence; no personal injury probabilities.
- Monte Carlo stays offline arithmetic/sensitivity research; never UI trajectories or proof of safety.

## Current owner handoff and shared-file log
- Rudra: review T048 client and implement/test report/photo/review and notice confirmation/instruction routes; retain canonical T050 and review Leaflet frontend dependency; keep scores/alerts isolated.
- Braydin: configure real tenant/roles/audience, Tiger Data/seed assignments, durable photo storage and Gemini endpoints/fallbacks. No secrets in Git.
- Cache: next integration is T063 when real configuration is available, then T064-T068 after actual server prerequisites. No remaining authorized live acceptance can be completed with mock credentials alone.
- 2026-10-17 UTC: T031 owner transfer/check-off in `140d118` updates AGENTS/tasks/context. `3fbd98f` changes only T032-T038 boxes after their checks and updates the context/coordination docs; no adjacent owner tasks changed.
- Published review PR [#19](https://github.com/BraydinPG/planit-control-swamphacks/pull/19), open against main, implementation head `8834867`. Earlier delivery commits: `3fbd98f`, reviewed-main incorporation `dc35458`, T048 client `4a9e44f`. Metadata-only follow-up records this publication. Rudra coordinates review/merge; no automatic merge or deployment.
