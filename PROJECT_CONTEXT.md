# PlanIT Control: shared project context

Read this index first, then AGENTS.md, spec.md, tasks.md and relevant source. Verify facts in code; detailed historical results remain in owner guides and Git history.

## Current frontend checkpoint - 2026-10-17
- Authorized sequence: Cache T067A, then T065; no backend/auth/database/ML changes in this run.
- Current branch `feature/cache-report-lifecycle-integration` from reviewed main `dcd9fc5` (PR #28 scoring-history fix; initial base `1eed70e`). Maintainers merged PR #24 (`f3a65a7`) and our verified T067A checkpoint `2e4cfb7` as PR #27 (`1eed70e`) during this run; remaining T065 PR targets main. No PR merges performed by Cache.
- T067A replaces obsolete generated-score prose and manual generation actions with stored GETs: `/api/sites/{id}/briefing` and `/api/briefings`. Site 404 is a scheduled-generation empty state. Canonical obsolete TS types/fixture removal explicitly authorized; no other API fields changed.
- Frontend `StoredBriefings.tsx` shows site/organization, window, hazards, actions, evidence, unknowns, Gemini/template source and creation time. Fixtures are archived/read-only; no browser scheduler. Score factors remain.
- T067A acceptance: 44 Node tests, 65 focused backend/fixture/mirror checks, lint/TypeScript/build and installed Edge browser checks at 1440/390/320 widths pass. Source has no retired calls. These are frontend/mock/contract checks, not real account persistence.
- T065 wired: create/list; absent review; present notice confirmation with validated server response; unsent suggested/manual draft, explicit 1-500-character confirmer send; shared state refresh. Stable notice keys preserve edits during GET refresh; conflicts refresh ownership. No React scoring/recipient selection or automatic send/retry.
- T065 remains unchecked: full real roles/persistence/delivery is blocked by missing local private configuration/memberships. T063/T064/T066/T067/T068 unchanged. Current checks: 56 Node and 518 backend/probe (511+7), lint/TS/build and clean npm ci/build pass; final browser evidence in docs/t065-verification.json.
- Actual running/source OpenAPI now match all 11 operations. Ten anonymous/dev-header checks return 401; invalid bearer 503 (Auth0 unavailable). DATABASE_URL/Auth0 SPA/backend/Gemini/storage settings missing locally; no real DB write or authenticated delivery verified. Diagnostic process bypass/feed refresh/briefing schedule stay off.
- Website: http://localhost:5173/ (explicit demo). Run `cd frontend; npm ci; npm run dev -- --host localhost --port 5173 --strictPort`. Node 24, no ML artifacts needed.

## Verified upstream / owner boundaries
- Cache owns frontend implementation/integration (formerly Nick), `ml/**`; T051A is separately assigned but outside this run. Nick retains attribution and T054/T054A/T055 backend completion; Rudra owns canonical contracts/review/merges, deterministic alerts and score persistence. Braydin owns Auth0, Tiger Data, ingestion/Gemini, memberships and deployment.
- PR #19 merged `64cf632`. PR #24 adds reusable redacted readiness/private account tooling; initial implementation `ff35b7b`, validated prior source `483bcd1` (39 Node/432 Python). No local real persistence was proven there.
- Nick PR #26: receipt-scoped confirmation/atomic first confirmer; absent review scoped to reporting organization; confirmer-only draft/send; current-team stored-radius receipts; pending/absent/rejected excluded from score. Score persistence retains per-site lock, complete eligible reports and rollback. Focused owner records: `docs/T054_IMPLEMENTATION.md`, `T054A_IMPLEMENTATION.md`, `T055_IMPLEMENTATION.md` (post-main backend 487 pass).
- Rudra T049A/T049B/T073: regional prototype factors, source notices/receipts, optional off-by-default feed refresh, outage regression tests; no feed outage or AI clears lightning state. `compute_score(site=...)` and refresh observation inputs preserved.
- Braydin T058A: backend generates one next-day 07:00-19:00 site-local briefing after 18:00 for eligible team sites with an organization supervisor; stored GET reads. `sites.timezone` applied to Tiger per owner note. No manual generation API.
- Braydin `7a2a886`: tenant/SPA/API `https://api.planit-control`, deployed roles Action, crew/supervisor permissions and isolated real sign-in verified; role matching case-insensitive. Actual demo subject memberships still need T069. No private credentials in this index.

## Architecture / integration
- `App.tsx` mode composition; `application/*` session and shared refresh; `api/contracts.ts`/`http-client.ts` canonical client; `demo/client.ts` isolated simulated persistence. `ConnectedPages.tsx` shared views; `components/data/*` reusable display. Auth exports stay in Braydin's `src/auth/**`.
- VITE_USE_FIXTURES=false requires real Auth0, bearer-only API, no preview role selector or fixture fallback. Vite proxies /api to existing FastAPI:8000; production routing is separate owner work. DEV_AUTH_BYPASS remains false for real acceptance.
- Demo: 55 points including 50 reconciled EIA reference plants, not active jobs; photos memory-only. Unknown scores stay null. No React score engine; deterministic alert state stays authoritative.
- Guides: `frontend/INTEGRATION.md`, `frontend/LIVE_INTEGRATION.md`, `docs/INTEGRATION_STATUS.md`, `docs/CROSS_SCOPE_CHANGES.md`, `docs/FRONTEND_REDESIGN_HANDOFF.md`.
- Diagnostics: `node frontend/scripts/check-live-integration.mjs --python <backend Python> --check-database`; optional read-only DB/private token checks; never auto-completes tasks.

## Existing ML package (unchanged)
- Primary `ml.predict.predict_active_event`; safe compatibility adapter; `ml/dispatch.py` type/hash dispatch. Combined `ml/worker/combined.py` (2.0) and `comprehensive.py` (2.1). Full 2.1 live endpoint remains owner-gated; exact-site demo exports only.
- Six research duration targets: Flood, Flash Flood, High Wind, Heavy Rain, Winter Storm, observed Heat Index Exceedance. Strong Wind/Ice Storm/Heavy Snow disabled; trend/intensity unsupported without labels. 349,030 NOAA rows/54 verbatim labels, grouped chronology, inspected 2025 holdout, baseline/artifact exclusions preserved.
- `ml/hazard_registry.json`, HAZARD_COVERAGE_AUDIT.md, SOURCE_INVENTORY_DIFF.md, source_catalog.json, EVALUATION.md, METHODOLOGY.md and MULTIDISASTER.md hold source/maturity/statistical limitations.
- 31-scenario/50-site rehearsal and T087 preview already implemented. Prior qualified local environmental coverage 2/50 and notices 10/50. Handoffs/provisioning: ml/HAZARD_INTEGRATION.md, WORKER_OUTLOOK.md, WORKER_PREVIEW.md, INTEGRATION.md.
- No onset, injury probability, site clearance or score contribution from research ML. Monte Carlo stays offline consistency/sensitivity; no fresh predictive validation in this run.

## Shared-file log / next owners
- 2026-10-17: T067A changes tasks.md only after its exact checks; context and integration/redesign/cross-scope guides record the authorized mirror/fixture removal and stored briefing behavior. T067A commit `2e4cfb7` merged in PR #27. T065 commit/PR recorded in CROSS_SCOPE_CHANGES.
- Cache next: actual T065 end-to-end acceptance after approved private configuration and memberships; independently actionable next task T051A has checked T051 prerequisite, for a separate authorized run. Braydin continues provisioning independently; Rudra reviews interfaces/coordinates merge. No production deployment/merge is authorized.
- Scope decisions (Braydin, 2026-10-17): Gemini never explains or interprets the hazard score; the weighted factor breakdown is the explanation (T059 removed, T051A is Cache's deterministic algorithm). Briefings are scheduled only; crew and supervisors with `read:org_briefings` read their organization's briefings.
- Rudra next: T069 demo seed, including demo-account `memberships`, teams, and a pre-generated briefing; set `FEED_REFRESH_ENABLED=true` wherever live scores and briefings are needed (off by default).
- Braydin next: T069 memberships with Rudra, the Gemini notice-radius, instruction, and enrichment calls (T057, T060), and Vultr deployment. No secrets in Git.
