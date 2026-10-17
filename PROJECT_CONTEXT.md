# PlanIT Control: shared project context

Read this verified index first, then `AGENTS.md`, `spec.md`, `tasks.md` and relevant source. Keep this short; detailed evidence belongs in the linked guides.

## Last verified: 2026-10-17
- Explicit user transfer: Cache owns remaining frontend implementation/integration, formerly Nick. Prior attribution and T030 remain preserved. Claude's later visual redesign requires separate authorization.
- Branch `feature/cache-frontend-workflows`, targeting main `723a5b8`. PR #16 (T030) and #17 (`140d118`, ownership/T031) merged during this run; the new branch preserves them and incorporates reviewed main via `dc35458`. T032-T038 implementation: `3fbd98f`.
- Rudra completed T049A: prototype hurricane/earthquake rules in `backend/app/rules/regional.py` (score factors, P1, outside data completeness) and feed-detected "potential {hazard}" notices in `backend/app/services/feed_notices.py` (default radius 50/25 mi, one notice per event, fresh readings only). `compute_score` takes an optional `site`. Tests: `backend/tests/test_regional_rules.py`; full backend suite 378 passed.
- Rudra published T050 (`9d73a77`) and T048 (`944471f`, PR #18). Their canonical backend/fixtures/types were inherited from main unchanged, with no Cache-authored backend/API diff.
- T031-T038 foundation/demo acceptance passed; T032-T038 checked with implementation/evidence in this checkpoint. T063-T068 remain unchecked, with exact dependencies in `docs/INTEGRATION_STATUS.md`.
- Vite: http://localhost:5173/; interactive simulated crew/supervisor app, 55 map/list points, reporting/review/instruction flow and exact-site research advisory.
- 23 focused frontend tests, lint/TypeScript/build and 1440/390/320 browser workflows passed. Current merged branch backend suite: 297 passed, one existing dependency deprecation. Earlier branch/export checks were 266/282 passed. See `docs/frontend-acceptance.json`.
- Clean committed frontend export `4a9e44f`: npm ci/build and full static-bundle demo browser acceptance pass without local env/Python/ML artifacts. No whole-app/deployment acceptance claimed.
- Actual health 200; protected site reads directly and via Vite proxy return 401. No real signed-in site data, report persistence, Auth0 tenant login or Gemini response was verified.
- Local Auth0/Tiger Data settings and missing report/notice/Gemini routes block real integration. Published alert listing/acknowledgement is connected and mock-tested. No production deployment, bypass, model retraining or ML contract changes.
- Score explanations removed from scope 2026-10-17 (Braydin): Gemini never explains or interprets the hazard score. The 0–10 score is a deterministic weighted algorithm and its factor breakdown is the explanation. Deleted: `POST /api/sites/{id}/explanations`, the Python `Explanation` schema and fixture generator entry, `request:explanations` permission, and T059. The TS `Explanation` type and `explanations.json` stay, marked for removal, until Cache's frontend drops them (T067A); T037/T057/T067 now cover briefings and enrichment only.
- Briefings are scheduled, never on request (2026-10-17, Braydin): generated at 6 PM site-local time for team sites whose organization has a supervisor, stored, and read via `GET /api/sites/{id}/briefing` and `GET /api/briefings` (crew and supervisors with `read:org_briefings`). `POST .../briefings`, the Python `BriefingRequest`, and `generate:briefings` are gone (now `read:org_briefings`); the TS `BriefingRequest` goes with T067A. Risk level comes from the computed score. The demo uses a pre-generated briefing (T069). New `sites.timezone` column applied to Tiger.
- Auth0 tenant `dev-qwsm71sgsbiajl7x.us.auth0.com` configured via the Auth0 MCP (SPA, API `https://api.planit-control` with 8 permissions, deployed roles Action). Roles (crew 4 permissions, supervisor 8), the Action in the post-login flow, and one demo user per role are set up in the dashboard; real sign-in verified for both roles on `auth-check.html` (T024–T026, T029). Role names match case-insensitively. Demo users still need `memberships` rows for site data (T069).

## Ownership and safety
- Cache: `ml/**` plus remaining frontend composition/data access/pages/components/styles/tests and integration preparation under this explicit transfer. Also the 0–10 site risk algorithm (`backend/app/rules/score.py` and the score weights in `backend/app/rules/settings.py`), assigned by Braydin 2026-10-17 as T051A: deterministic, weighted by risk, no ML or Gemini input.
- Rudra: canonical API/types/fixtures, backend routes, deterministic alerts, storing/serving scores, and shared coordination.
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
- Rudra: T044A, store feed readings on a schedule (nothing saves feed readings yet, so scores and briefings see no live data). Also review T048 client and implement/test report/photo/review and notice confirmation/instruction routes; retain canonical T050 and review Leaflet frontend dependency; keep scores/alerts isolated.
- Braydin: configure real tenant/roles/audience, Tiger Data/seed assignments, durable photo storage and Gemini endpoints/fallbacks. No secrets in Git.
- Cache: T051A, the site risk algorithm, and T067A, removing score explanations and manual briefing requests from the frontend (see `tasks.md`). Next integration is T063 when real configuration is available, then T064-T068 after actual server prerequisites. No remaining authorized live acceptance can be completed with mock credentials alone.
- 2026-10-17 UTC: T031 owner transfer/check-off in `140d118` updates AGENTS/tasks/context. `3fbd98f` changes only T032-T038 boxes after their checks and updates the context/coordination docs; no adjacent owner tasks changed.
- Published review PR [#19](https://github.com/BraydinPG/planit-control-swamphacks/pull/19), open against main, implementation head `8834867`. Earlier delivery commits: `3fbd98f`, reviewed-main incorporation `dc35458`, T048 client `4a9e44f`. Metadata-only follow-up records this publication. Rudra coordinates review/merge; no automatic merge or deployment.
