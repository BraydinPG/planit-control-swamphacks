# PlanIT Control: shared project context

Read this verified index first, then `AGENTS.md`, `spec.md`, `tasks.md` and relevant source. Keep this short; detailed evidence belongs in the linked guides.

## Last verified: 2026-10-17
- Explicit user transfer: Cache owns remaining frontend implementation/integration, formerly Nick. Prior attribution and T030 remain preserved. Claude's later visual redesign requires separate authorization.
- Branch `feature/cache-functional-frontend`, stacked on open PR #16 head `84e3936`; base `feature/cache-t030-app-shell`. First checkpoint `140d118` completes T031.
- Main `2e79cb6` separately includes Rudra's merged T050 (`9d73a77`). This branch did not merge main or copy its backend/schema changes.
- T031-T038 foundation/demo acceptance passed; T032-T038 checked with implementation/evidence in this checkpoint. T063-T068 remain unchecked, with exact dependencies in `docs/INTEGRATION_STATUS.md`.
- Vite: http://localhost:5173/; interactive simulated crew/supervisor app, 55 map/list points, reporting/review/instruction flow and exact-site research advisory.
- 21 focused frontend tests, lint/TypeScript/build and 1440/390/320 browser workflows passed. Current-main source-export backend suite: 282 passed, one existing dependency deprecation. See `docs/frontend-acceptance.json`.
- Actual health 200; protected site reads directly and via Vite proxy return 401. No real signed-in site data, report persistence, Auth0 tenant login or Gemini response was verified.
- Local Auth0/Tiger Data settings and missing alert/report/notice/Gemini routes block real integration. No production deployment, bypass, model retraining or ML contract changes.

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
- Live writes/AI disabled until routes exist. T050 optional compact field displayed if supplied; 2.1 panel is exact-site demo only, with null local probabilities and explicit unknown hazards.
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
- Rudra: implement/test alert acknowledgement, report/photo/review and notice confirmation/instruction routes; review T050 frontend optional mirror and Leaflet frontend dependency; keep scores/alerts isolated.
- Braydin: configure real tenant/roles/audience, Tiger Data/seed assignments, durable photo storage and Gemini endpoints/fallbacks. No secrets in Git.
- Cache: next integration is T063 when real configuration is available, then T064-T068 after actual server prerequisites. No remaining authorized live acceptance can be completed with mock credentials alone.
- 2026-10-17 UTC: T031 owner transfer/check-off in `140d118` updates AGENTS/tasks/context. This checkpoint changes only T032-T038 boxes after their checks and updates the context/coordination docs; no adjacent owner tasks changed.
- Commit/PR publication references are recorded below after pushing. Rudra coordinates review/merge; no automatic merge.
