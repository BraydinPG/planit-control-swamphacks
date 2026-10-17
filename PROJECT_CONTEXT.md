# PlanIT Control: shared project context

Read this verified index first, then `AGENTS.md`, `spec.md`, `tasks.md` and relevant source. Keep this short; detailed evidence belongs in the linked guides.

## Last verified: 2026-10-17
- Explicit user transfer: Cache owns remaining frontend implementation/integration, formerly Nick. Prior attribution and T030 remain preserved. Claude's later visual redesign requires separate authorization.
- Phase 4 branch `feature/cache-live-integration-checks`, based on reviewed main `4e94c52` (initial phase-4 base `9ba1b7c`). PR #19 merged as `64cf632` during this run; this continuation now targets main, with no duplicate parent diff.
- Rudra's T050/T048 and new T052/T053 (`db2022e`, `4dec720`, PR #20/#21) are inherited unchanged. Published report list/create is connected separately from still-unavailable review/instructions. Nick now owns T054/T054A/T055 under Rudra review.
- Rudra completed T049B: feed refresh loop in `backend/app/services/refresh.py` stores every feed's Observations, runs the lightning rule and feed notices, and rescores each site. Off by default (`FEED_REFRESH_ENABLED`); one-shot `python -m app.services.refresh`. A raising feed is stored as unavailable; one site's failure doesn't stop the others. Full backend suite 387 passed.
- Rudra completed T049A: prototype hurricane/earthquake rules in `backend/app/rules/regional.py` (score factors, P1, outside data completeness) and feed-detected "potential {hazard}" notices in `backend/app/services/feed_notices.py` (default radius 50/25 mi, one notice per event, fresh readings only). `compute_score` takes an optional `site`. Tests: `backend/tests/test_regional_rules.py`; full backend suite 378 passed.
- T031-T038 foundation/demo acceptance passed; T032-T038 checked with implementation/evidence in this checkpoint. T063-T068 remain unchecked, with exact dependencies in `docs/INTEGRATION_STATUS.md`.
- Vite: http://localhost:5173/; interactive simulated crew/supervisor app, 55 map/list points, reporting/review/instruction flow and exact-site research advisory.
- Foundation evidence: `docs/frontend-acceptance.json`. Phase 4: 39 frontend checks, 400 backend/probe checks (393+7), lint/TypeScript/build/Ruff and 1440/390/320 browser workflow checks; exact evidence in `docs/phase4-integration-verification.json`.
- Clean committed frontend export `4a9e44f`: npm ci/build and full static-bundle demo browser acceptance pass without local env/Python/ML artifacts. No whole-app/deployment acceptance claimed.
- Actual health 200; protected site reads directly and via Vite proxy return 401. No real signed-in site data, report persistence, Auth0 tenant login or Gemini response was verified.
- Actual readiness: no local DATABASE_URL, Auth0 SPA/backend values, Gemini settings or Vultr credentials. Seeded organizations/teams/memberships/accounts remain unknown. Five actual anonymous/dev-header denial checks return 401; invalid token returns 503 (Auth0 unavailable), not validated token rejection. No authenticated read or real DB write verified.

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
- Live T048 alert calls and T053 report reads/create enabled; live present reports require a photo. Separate review/notice/AI capabilities remain disabled. T050 compact field is separate; 2.1 remains exact-site demo only, with null local probabilities and explicit unknown hazards.
- Full guide: `frontend/INTEGRATION.md`; real setup/acceptance: `frontend/LIVE_INTEGRATION.md`; task/live matrix: `docs/INTEGRATION_STATUS.md`; visual boundaries: `docs/FRONTEND_REDESIGN_HANDOFF.md`.
- New CLI: `node frontend/scripts/check-live-integration.mjs --python <backend Python> --check-database`. Redacted settings, source/running OpenAPI, anonymous checks and bounded read-only DB inspection; expected exit 2 while blocked. Private optional token wrapper is documented; no automatic task completion.
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
- Rudra: review T053 client/photo requirement and Nick's backend confirmation/instruction/report-score changes. Nick: T054/T054A/T055 per current backlog. Cache does not edit those backend paths.
- Braydin: configure real tenant/roles/audience, Tiger Data/seed assignments, durable photo storage and Gemini endpoints/fallbacks. No secrets in Git.
- Cache: next integration is T063 when real configuration is available, then T064-T068 after actual server prerequisites. No remaining authorized live acceptance can be completed with mock credentials alone.
- 2026-10-17 UTC: phase-4 diagnostics/tests and T053 frontend wiring update this index/cross-scope docs; Cache leaves every task checkbox unchanged. T052/T053 owner completions arrived from reviewed main. See CROSS_SCOPE_CHANGES for exact paths and publication refs.
- Foundation PR [#19](https://github.com/BraydinPG/planit-control-swamphacks/pull/19) is merged; its implementation/metadata head was `8af5b9d`. Phase-4 review PR [#24](https://github.com/BraydinPG/planit-control-swamphacks/pull/24) is open against main; initial implementation `ff35b7b`. Latest reviewed T049A/T049B main was merged to resolve its context-only conflict, preserving Rudra's notes. Bypass/background refresh remain disabled for local acceptance. Rudra coordinates review/merge; no automatic merge or deployment.
