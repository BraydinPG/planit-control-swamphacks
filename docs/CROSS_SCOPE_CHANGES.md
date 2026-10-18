## Alert, report and header maintenance - 2026-10-17

Explicit user request authorizes focused frontend integration on
`feature/alert-report-header-fixes`. Changes cover alert timer presentation,
pre-submission photo removal, report status copy and the live header. Header logo
changes were reverted at the user's follow-up request; original logo markup and
behavior are preserved. Acknowledgement button changes were also reverted at the
user's request; original acknowledgement behavior is preserved.
`application/LiveApplication.tsx` calls the existing logout function; no Auth0 internals,
API contracts, backend alert decisions or stored photos are changed. Expired live
windows stay active until updated server state arrives. Demo controls and simulated
labels are preserved. Browser acceptance uses the existing isolated mock harness.

## Official FORESITE logo (Cache for Rudra and Braydin) - 2026-10-17

Explicit user authorization permits narrow visual identity integration, including
app-owned auth presentation. Branch `feature/cache-official-foresite-logo` starts
from main `991c52f`, preserving merged branding, feeds, photos, reports and deployment
work. No deployment files or another worktree/process were changed.

- `frontend/public/foresite-logo.png`: unmodified approved 2172×724 transparent PNG.
  New `foresite-{logo-full,wordmark,cyclone,favicon-16,favicon-32,apple-touch-icon,
  icon-192,social}.png`, multi-size `foresite-favicon.ico` and
  `foresite-brand-assets.json`: extracted approved pixels, dimensions and hashes.
- `frontend/scripts/prepare-brand-assets.py`: optional reproducible Pillow 13 extraction;
  no production dependency/lockfile change. No drawing/redesign/vector-wrapper claim.
- `frontend/src/components/shell/Brand.tsx` (new): shared full/compact/icon rendering,
  intrinsic dimensions, aspect ratio/alt/contrast and cache version.
  `AppShell.tsx`: logo placement in existing navigation/header/footer, bounded sizing
  and hidden empty mobile breadcrumb. `Icon.tsx`: existing Logo export delegates to
  the cyclone; operational icons unchanged.
- `frontend/src/auth/RequireRole.tsx`: add logo to existing access/loading panels and
  optional presentation-only showBrand prop. `AuthCheckPage.tsx`: one full logo and
  omit duplicates in embedded examples. Guard conditions, login/logout/token flow,
  roles and provider configuration unchanged. Braydin reviews these presentation edits.
- `frontend/index.html`, `auth-check.html`: cyclone favicon/touch refs, main social
  imagery, exact FORESITE title retained. Old planit-mark asset remains for compatibility
  but is no longer referenced by current frontend source/entrypoints.
- Existing `frontend/scripts/check-shell.mjs`: assert image decode/source/aspect/alt,
  actual 16/32/180/social assets, tablet viewport and light/dark DPR2 sign-in captures.
- Docs: new `docs/OFFICIAL_LOGO.md` and public simulated screenshots/contact sheet in
  `docs/branding/`; current logo section in `docs/REBRANDING.md`; concise context/log.

Final checks: frontend lint, TypeScript, **171 tests**, live/demo production builds,
asset regeneration/hash/alpha/ICO checks pass. Dev Edge smoke passes all 11 destinations
at 1440/768/390/320, preserving six outlooks, 6.1/10, report/photo/confirmation/instruction,
alerts, teams and briefings, with no browser exceptions or real backend requests.
First browser attempt found 5177 absent; a new explicit demo was started from this
checkout (PID 25276), no existing server stopped. Built-demo Edge suite also passes
all eleven destinations/four widths, assets and lifecycle; no browser exceptions or
real API calls. Temporary 5182 preview closed; public simulated screenshots committed.
Backend suite not rerun: no backend changes. Existing live bundle-size warning remains.

Rudra reviews placement; Braydin reviews app-owned auth presentation and separately
coordinates external Universal Login imagery. Vultr owner performs the normal frontend
release with committed assets; no backend/migration/config/secret/DNS/workflow changes.
No task check-off, real-account acceptance, automatic merge or deployment.

Published [PR53](https://github.com/BraydinPG/planit-control-swamphacks/pull/53),
**Integrate Official FORESITE Logo and Branding Assets**, open against main;
tested implementation `4508e9d`, base `991c52f`. Later main `6aa528b` contains
deployment-only work with no overlap; no deployment files edited in this PR.

## Feed refresh optimization (Cache for Braydin and Rudra) - 2026-10-17 23:12 UTC

Explicit task-specific user authorization permits focused ingestion/refresh edits.
Branch `feature/cache-feed-refresh-performance`, baseline `11c62b6`; latest fetched
main `cdba4c3` changes only UI hover styling, incorporated by `e0120fb` after
implementation checkpoint `ffff712`. No teammate
worktree/server changes. T043/T043A/T044/T045B/C/D/T049B/T073 remain historically
completed; no new task checkbox or live-service acceptance claim.

Every cross-owner modification in this run:

- `backend/app/ingestion/http.py` (new): pooled HTTP, host limits/pacing, bounded
  response/retry/time budgets, Retry-After/cancellation and redacted status diagnostics.
- `backend/app/ingestion/runtime.py` (new): immutable worker snapshots, bounded ordered
  I/O, round single-flight, cancellation and retrieval/phase/region metrics.
- `backend/app/ingestion/alert_matching.py` (new): conservative active CAP/geometry,
  holes and exact-zone matching, with uncertain geometry delegated to point queries.
- `backend/app/ingestion/nws.py`: client lifecycle, coordinate-keyed expiring metadata,
  negative TTL only for explicit coverage errors, safe origin/pagination and shared
  regional alerts. `json_client.py`: pooled transport and typed invalid-response logs.
- `backend/app/ingestion/cache.py`: coordinate-safe fallback keys, bounded multi-site
  fetching and structured per-site final states; original observation times retained.
- `backend/app/ingestion/nws_weather.py`: bounded fetches and station metadata reuse.
  `nws_alerts.py`: bounded fetches and source-qualified shared alerts.
- `backend/app/ingestion/hurricanes.py`: bounded site matching/shared NWS notices;
  original NHC single fetch preserved. `earthquakes.py`: preserve structured failure
  identity while retaining one shared summary fetch.
- `backend/app/ingestion/flood_gauges.py`: bounded geographic/region batch queries,
  outward boxes, per-site nearest gauges and original gauge/time provenance; reject
  nonfinite/wrong-unit/future/no-data measurements. No site flood-depth inference.
- `backend/app/ingestion/settings.py`: additive conservative workers/HTTP/cache/batch
  options; no shared environment-template changes.
- `backend/app/services/refresh.py`: immutable snapshots, serial unchanged upserts,
  rule/notice/score calls, explicit missing subresults and coverage/processing metrics;
  cancellation propagation, redacted one-shot preflight/report CLI and scheduler guard.
- `backend/scripts/benchmark_refresh.py` (new): offline 256-site mocked benchmark,
  original/optimized source hashes, observation/score equivalence and paced option.
- `backend/tests/test_feed_http.py`, `test_feed_optimization.py` (new): 42 offline
  cases for transport, statuses, retry budgets, caches, spatial association, batching,
  final-state logs, isolated failures, no zero/false clearance and serial persistence.
  Existing `test_nws_alerts.py` and `test_hurricanes.py` assert the intentional combined
  alert query while retaining output assertions.
- Shared docs: `PROJECT_CONTEXT.md` index and this log; new
  `docs/FEED_REFRESH_PERFORMANCE.md` plus `feed-refresh-{baseline,optimized,paced}.json`
  provide operator commands, measured results, coverage and source/migration limits.

Checks: **923 backend tests pass**, including scoring/alerts/GLM/schema mirror; Ruff
lint and **153-file** formatting pass. Final tests reject external socket connections
(Windows asyncio internal loopback allowed). Synthetic before/after **21.05/4.44 s**,
requests **1,794/578**, paced **152.96 s**; all 256 sites, 4,352 readings, matching
observation and score hashes. Serial DB processing measured 1.11/2.22 s; no database
performance improvement claimed. Detailed per-feed coverage in the guide/reports.

Local ignored FEED_REFRESH_ENABLED stays false; no DATABASE_URL/NWS_USER_AGENT ready.
No real refresh, shared DB write, account/configuration provisioning or automatic job
was run. Frontend, canonical schemas, alert rules, scoring weights, ML, Gemini and
security modules are untouched. Existing servers retain PIDs 77984/22668/65924.

**Braydin review:** provider limits/cache/batching, actual regional error diagnosis,
legacy USGS degradation/retirement and separately approved modern API key/migration.
**Rudra review:** snapshot/serial ORM ordering, per-source unavailable placeholders,
coverage versus fully processed counts and unchanged deterministic authority.
An owner-approved single live round remains required before claiming the reported
20-minute production problem is resolved. PR publication/commit reference follows
in this log; no merge by Cache.

Published [PR50](https://github.com/BraydinPG/planit-control-swamphacks/pull/50),
**Optimize Feed Refresh Performance and Reliability**, open against main.
Implementation `ffff712`, reviewed-main merge `e0120fb`, handoff `68ca740`.
No Codex merge or background job enablement; live acceptance remains pending.
## FORESITE application rebrand (Cache for Rudra and Braydin) - 2026-10-17

Explicit user authorization covers application-wide brand text and current docs.
Branch `feature/cache-foresite-rebrand` begins at main `ea6dcfa`; open PR50 remains
independent and preserved. Another teammate's active Vultr work is untouched.

- **Rudra/frontend:** `components/shell/AppShell.tsx` wordmark/header/footer/ARIA and
  exact document title; `index.html` and `auth-check.html` metadata; existing
  `public/planit-mark.svg` title only (no geometry); `index.css` comment and
  `types/api.ts` documentation only. No page layout/class/style behavior changed.
- **Braydin/auth:** `auth/{AuthCheckPage,RequireRole}.tsx` display strings and
  `auth/{context,roles,index}.ts` comments only; `backend/app/security/{roles,
  dependencies}.py` documentation and the human-readable 403 message only.
  Role/audience/claim/client/tenant/callback/guard/token logic remains unchanged.
- **Rudra/backend:** `app/main.py` docstring/FastAPI title; `app/outlook/events.py`
  fallback source/vintage labels; `app/schemas/{__init__,common,species}.py`
  descriptions only. No schema field or endpoint changes.
- **Braydin/species:** `app/species/service.py` retrieval note. Existing offline
  canonical generator regenerates `frontend/src/fixtures/species-context.json`;
  only that note differs, all other generated fixtures are byte-unchanged.
- **Cache/ML:** `ml/__init__.py` docstring, `event_outlook_preview.py` and
  `worker_preview.py` display titles, `worker/impacts.py` derived publisher label,
  `ml/EVENT_OUTLOOKS.md` product wording. No algorithm, model name/hash/artifact,
  gate, ID, probability, time or statistical claim changed. Local previews refreshed.
- **Shared docs:** README product title/intro; AGENTS/spec/tasks/context product
  titles (task checkboxes/ownership unchanged); frontend/SHELL, auth/SETUP and
  docs/SPECIES_CONTEXT demo wording. Both `.env.example` files change comments only;
  no configuration values changed. New `docs/REBRANDING.md` records all intentional
  compatibility names, historical exceptions and the deployment/hosted-login handoff.
- **Browser tests:** existing `frontend/scripts/check-shell.mjs` adds exact
  FORESITE title/metadata and no-old-visible/accessible-name assertions across
  eleven destinations, plus missing-role wording. No new test framework/server.

Checks: **168 frontend, 881 backend and 297 ML tests pass**, frontend lint/TypeScript
and live/demo builds, backend Ruff lint/147-file format. Installed Edge development
and built-demo suites pass at 1440/390/320, retaining six cards, 6.1/10, alerts,
report/photo/confirmation/instruction, teams and briefings; zero browser exceptions
or real backend calls. Screenshots inspected. ML previews validate 16 cases and 150
outputs/50 sites without network. Existing Starlette/bundle warnings remain.
PowerShell required npm.cmd instead of blocked npm.ps1; policy was not changed.
Ignored environment fingerprints unchanged; no secrets, deployment files, schemas,
routes, model artifacts or private data added. Existing servers retained; temporary
built-preview server closed. Detailed evidence/commands: `docs/REBRANDING.md`.

**Rudra:** review text/metadata only; preserve independent PR50 context notes when
merging. **Braydin/deployment:** normal frontend/backend build/release; independently
inspect the external Auth0 login display name and coordinate its FORESITE branding,
preserving all technical settings. No Vultr, tenant, DNS, secret or workflow edits.
No tasks checked off and no real Auth0/Tiger/deployed acceptance claim. PR/commit
publication reference follows; no automatic merge.

Published [PR51](https://github.com/BraydinPG/planit-control-swamphacks/pull/51),
**Rebrand PlanIT Control to FORESITE**, open against main; implementation `e4f5555`,
base `ea6dcfa`. No merge, hosting/tenant update or live acceptance by Cache.

## Application-wide UI readability (Cache for Rudra) — 2026-10-17 22:23 UTC

Explicit user authorization expands this run to frontend copy, typography and
presentation across Crew and Supervisor. Initial base `5045790`, branch
`feature/cache-ui-readability-polish`, existing isolated functional checkout.
No edits to another checkout or another owner's running server.

- `frontend/src/presentation/display.ts`, new `components/data/Details.tsx`:
  controlled display labels, local timezone formatting, unit notation and native
  accessible disclosures. Identifiers/contracts and authored prose stay intact.
- `App.tsx`, `application/LiveApplication.tsx`, `components/shell/AppShell.tsx`,
  `index.css`, `pages/{ConnectedPages,WorkspaceOverview}.tsx`: shorter navigation,
  consistent capitalization, readable layout, demo details, clearer reporting,
  location/error states and a link to all active alerts on Crew overview.
- `components/data/{Status,EventOutlooks,AlertCard,NoticeCard,Duration,Advisory,
  ReportAnalysis,StoredBriefings,SpeciesPanel,TeamRoster,SupervisorOverview,
  attention,Interaction,SiteMap}`: summaries before evidence; visible alert and
  approved instruction authority; original crew/Gemini/supervisor prose retained.
  “Watch window” replaces countdown wording that suggested automatic clearance.
- Existing frontend tests/browser runner updated for intentional copy; new
  `tests/display.test.mjs` verifies formatting, disclosure and safety wording.
  Integration unit Vite watcher disabled to avoid scanning browser profiles.
- No scoring, ML, alert rule/timer, permission, API/schema, database, Gemini-prompt
  or private-configuration edits. No fixture regeneration or task check-off.

Checkpoint checks: 164 frontend tests; lint, TypeScript/production build; 85
backend fixture/outlook/score/lightning tests; Edge demo/mock browser checks at
1440/390/320. Final upstream integration and recheck follow in this branch.
Rudra reviews the UI; backend-authored wording questions and screen audit are in
`docs/UI_READABILITY.md`. T063–T068 live acceptance remains separate.

Final verification, 2026-10-17 22:30 UTC: incorporated upstream `e2092dc` in
`42dbd18`, after implementation checkpoint `9863599`. Resolved the three UI
conflicts by retaining organization renaming/Add Team placement, recorded Gemini
species attribution and all six report categories. PR diff against this main has
**no backend, ML, Auth0, API/schema, fixture, task or manifest changes**.
All **166 frontend and 881 backend tests** pass; lint, TypeScript, both live-mode
and simulated production builds pass. Development demo/mock and built-demo Edge
suites pass all eleven destinations, long content, stale/missing data, multiple
alerts and expanded evidence at 1440/390/320; zero browser exceptions or actual
backend requests. Simulated organization rename/team/code actions pass. The
existing Starlette deprecation and default/live bundle-size warning remain.
Nine ignored environment/artifact files are hash-unchanged. Demo remains at
http://localhost:5177/; no teammate server was restarted. Review: Rudra for UI,
Braydin/Rudra for the unchanged backend-authored wording noted in the guide.

Published [PR47](https://github.com/BraydinPG/planit-control-swamphacks/pull/47),
open against main, verified UI commit `a5a06cd`; no Codex merge. This publication
note changes only the shared context/log; the implementation checks above stand.

## Canonical demo scores and prediction failure handling (Cache) — 2026-10-17

Explicit user authorization: fix the obsolete fixture score and both reproduced
prediction bugs, regenerate canonical fixtures, test and publish a review PR.
Branch `feature/cache-demo-score-prediction-fixes` started at main `0a0d5c8` and
incorporated reviewed main `3272930`; no unmerged dependency. Team/species and the
new supervisor Overview are preserved; both concurrent change-log entries retained.

- **Rudra review:** `backend/scripts/generate_fixtures.py` uses `compute_score` with
  declared default weights and T069's simulated weather inputs. Generated sites,
  site-detail and briefings JSON agree on **6.1/10 high, rules-0.2**, no ML factor,
  and 0 current live completeness. Breakdown: 3 lightning + 1.11 heat + 1 Flood Watch
  + 1 confirmed moderate wildlife, rounded by the approved algorithm. Other synthetic
  sites also use the scorer.
- **Rudra review:** `backend/app/outlook/events.py` contains per-card conversion
  failures and missing/duplicate results. Valid siblings, site response, score and
  alerts survive. `frontend/src/api/live-read-validation.ts` checks nested forecast
  shapes, source/time/coordinate/probability fields before rendering. Archived cards
  retain original EIA associations only as explicitly simulated reference replays.
- Existing fixture/outlook/client/read/briefing tests and
  `frontend/scripts/check-shell.mjs` cover the regressions. The browser runner
  recreates obsolete saved data in its own profile, uses **Reset demo**, verifies
  reload and retains a synthetic Auth0 storage sentinel. It checks 6.1, incomplete
  evidence and six cards at 1440/390/320; no browser exceptions/backend requests.
  After incorporating main's new supervisor Overview, restrict the map assertion
  to Worksites: Overview deliberately has no map. No presentation component edit.
- `backend/tests/score_scenarios.py` and its checked evaluation JSON update the
  changed fixture comparison/wording; 35 fixed algorithm scenarios and weights are
  unchanged. `docs/SITE_RISK_SCORING.md` documents the corrected fixture and reset.
- No presentation component/style, schema/type mirror, model, weight, alert rule,
  authorization, private configuration, migration/seed or teammate checkout change.
  No task checkbox changed; live T050A/T063–T068 acceptance remains separate.

Checks on incorporated main: 874 backend tests, backend Ruff and format checks of
145 files pass. Before incorporating main, the combined run
also passed 297 ML and 10 diagnostic tests; its old evaluation-fixture comparison
failed, was regenerated, and passed in the subsequent full backend run. Six existing
model hash/load/reference checks and 16 offline preview cases pass. All 155 frontend
tests, oxlint, TypeScript, production build and Edge demo/mock checks pass.
Existing Starlette deprecation and Vite
bundle-size warnings remain. Real-service setup is outside this simulated bug fix.

## Team onboarding, supervisor Overview, and supervisor UI cleanup (Braydin) — 2026-10-17

Explicit user requests (Braydin): join codes (`XXXX-XXXX`, 7 days); supervisors see exactly who is on each team; the supervisor UI should follow Rudra's design but be functional, logical and free of bloat, covering spec.md and tasks.md. Rudra now owns all frontend/UI (Cache's ownership update), so every change below is focused and listed for his review.

- **Backend.** New `app/api/teams.py` (Rudra's route area) and `app/schemas/teams.py`; registered in `app/main.py`.
  - `app/security/dependencies.py`: name and email profile claims; only crew fall back to role permissions when the list is empty.
  - `app/db`: `JoinCode` table and membership `email`, `display_name`, `joined_at` (applied to Tiger).
- **Robustness.** `app/services/refresh.py` commits after reading sites, so its ~20-minute fetch no longer holds locks. `app/db/init.py` alters only missing columns and hypertables, with a 15 s lock timeout. Before this, a migration queued live API requests behind the refresh transaction.
- **Frontend (Rudra's).** `types/api.ts` mirror, plus `api/contracts.ts`, `api/http-client.ts`, `api/validate.ts`, and `demo/client.ts` (simulated roster and codes).
  - `components/shell/AppShell.tsx` and `Icon.tsx`: a supervisor-only Team tab with a "team" icon; the phone nav uses 6 columns for supervisors.
  - New `components/data/TeamRoster.tsx` (Team page; "Join your team" for crew with no team), `SupervisorOverview.tsx` and `attention.ts`.
  - `pages/ConnectedPages.tsx`:
    - The supervisor Overview is now "Needs your attention" (active alerts, potential notices to confirm, absent reports to review, team sites) plus the three highest-risk sites. Worksites keeps the map, list and filters.
    - Developer and fixture wording removed (`site-…` IDs on rows, "sample/reference", "supplied", raw factor IDs).
    - Reports and Briefings pickers list team sites only.
  - `components/data/AlertCard.tsx`: plain titles ("Flood alert active"), "Status · Simulated replay", empty distance and window fields hidden, evidence shown by label, pluralized acknowledgements.
- **Team management** (user request: a supervisor runs more than one team): `POST /api/teams`, `PATCH`/`DELETE /api/teams/{id}` (one team per site; only empty teams with no reports are removed); `TeamCreate`/`TeamUpdate` schemas and TS mirror; client and demo methods; Add team and Manage team on the Team tab.
- **`scripts/check-shell.mjs`**: the supervisor Overview waits for "Needs your attention", and the map and list checks run on Worksites ("55 locations"). It still stops earlier, on main's existing crew 320 px layout issue.

Checks: 800+ backend and 121 frontend tests, Ruff, oxlint, `tsc -b`, and build clean. The demo-mode supervisor tabs were re-read in headless Chrome.
## Access mat A-D condition (T034B, Rudra; cross-scope into Braydin's DB/Gemini and Cache's form) — 2026-10-17

Explicit user request (Rudra): for access mat deterioration, step 2 of the report form asks "What is the condition?" with A-D instead of present/absent; other categories unchanged. User decisions: A = hazard absent, B-D = hazard present; no Unsure choice.

- **Rudra (owned):** `MatCondition` enum and `mat_condition` on `ReportCreate` (required for access mats only, must match `hazard_present`) and `CrewReport`; `POST /api/reports` form field; `create_report`; site report serializer; TS mirror; fixtures regenerated; spec route row; T034B status.
- **Braydin (review requested):** `crew_reports.mat_condition` column in `db/models.py` plus an idempotent `ADDED_COLUMNS` entry in `db/init.py` (run `python -m app.db.init` against Tiger Data once); `gemini/report_analysis.py` adds the crew's grade as `crew:mat_condition` evidence (no rubric, so Gemini still must not assign a grade).
- **Cache (review requested):** `ReportForm` step 2 for access mats, grade chip on `ReportCard`, `validateReport`, submit echo check, demo client rule, `tests/mock-service.ts`.

Checks: 887 backend tests (new validation, grade-A/no-notice and Gemini-evidence cases) and 170 frontend tests; ruff, oxlint, `tsc -b`, both builds; browser check of the form and a submitted grade-C demo report.

## Site species context (Rudra; cross-scope into Braydin's Gemini and Cache's frontend) — 2026-10-17

Explicit user request (Rudra): a read-only, site-aware species guide for team sites using the USFWS IPaC Location API, USFWS critical habitat boundaries on the existing map, and the existing Gemini client. Guide: [SPECIES_CONTEXT.md](SPECIES_CONTEXT.md).

- **Rudra (owned):** new route `GET /api/sites/{id}/species` (`backend/app/api/species.py`, registered in `main.py`), schemas `backend/app/schemas/species.py` + TS mirror, `backend/app/species/**`, fixture generator (`species-context.json`), `.env.example`, AGENTS.md/spec.md route lists. No database models or migrations.
- **Braydin (review requested):** new `backend/app/gemini/species.py` only. It uses the existing `GeminiClient.generate_structured` and changes no other Gemini file. Please review the grounding rules and confirm the IPaC source/provenance notes.
- **Cache (review requested):** new `frontend/src/components/data/SpeciesPanel.tsx` and `frontend/tests/species.test.mjs`. Focused edits: `Client.species()` in `api/contracts.ts`, `api/http-client.ts`, `api/validate.ts`, `demo/client.ts`; optional `habitat` overlay prop in `components/data/SiteMap.tsx` (no change when omitted); one `SpeciesSection` line in `pages/ConnectedPages.tsx`. Formatted with the existing prettier style.
- **Safety lead (open):** curated encounter guidance in `backend/app/species/guidance.py` is `pending_review` until signed off.
- Score, alerts, report review and clearance are untouched; a test compares site detail, list, alerts and row counts before and after species reads.

Checks: 782 backend tests (47 new), ruff check/format; 118 frontend tests (9 new), oxlint, `tsc -b`, fixture- and API-mode builds; browser check at 1510 px and 390 px with no console errors.

## Live feeds on, demo site frozen, faster refresh (Braydin) — 2026-10-17

Explicit user decision (Braydin): live data for every real site, one frozen scripted demo site.

- `app/services/refresh.py` (Rudra's):
  - `refresh_all` skips `location_type="demo_site"` (`DEMO_LOCATION_TYPE`), so live feeds never overwrite the T069 scenario. `app/demo/scenario.py` uses the constant, and its docstring says so.
  - Each site's readings are written in one `INSERT … ON CONFLICT (id, observed_at) DO UPDATE` (`store_observations`) instead of one `session.merge` per reading. Against Tiger, saving went from ~7 sites/min (a full round of ~40 readings per site took ~35 min to save) to ~0.2 s per site.
  - `python -m app.services.refresh` now loads `backend/.env` (it failed with "DATABASE_URL is not set").
- `tests/conftest.py`: tests force `FEED_REFRESH_ENABLED=false` and `BRIEFING_SCHEDULE_ENABLED=false`, so starting the app in a test never reaches live feeds or Tiger. `test_loop_is_off_by_default` checks the code default instead of the developer's `.env`.
- `tests/test_refresh.py`: the demo site is never refreshed; one upsert stores a batch and keeps the last duplicate.

Measured on a live round: the fetch phase is ~20 min for 256 sites. NWS weather and alerts are ~1 s per site; USGS flood gauges are the slowest, with occasional 503 responses. The NWS contact is set through `NWS_USER_AGENT` in each machine's uncommitted `.env`.
## Multi-event ML integration handoff (Cache) - 2026-10-17

Explicit user assignment: reuse existing qualified event models and build a typed
multi-event preview in `ml/**`; propose API/component inputs without changing
Rudra's contracts or Claude's UI. Branch `feature/cache-multi-event-outlooks`,
started at main `ca99e64`; reviewed main `a7759c9` incorporated as `7c30618`
after maintainers merged Rudra PR #38 and the report/map update. No unmerged dependency.

- New ML adapter/schema, bounded official-product parsers, checksummed NHC/USGS
  captures, verified local artifact reuse, 16-case static preview and tests.
- Shared edit: `PROJECT_CONTEXT.md` gains this verified navigation/handoff entry;
  this log records ownership. `tasks.md` and all teammate implementation files
  are unchanged. Exact inputs, schemas, examples and acceptance proposals for
  Rudra/Claude are in `ml/EVENT_OUTLOOKS.md` and `ml/fixtures/event_outlooks/`.
- Final verification on updated main: 51 focused checks; ML/backend 1,024; 109 frontend
  tests, lint/TypeScript/build pass. Offline browser at1440/390 renders16 cases/18
  cards without external requests/exceptions. Clean tracked-source export with
  existing pinned dependencies degrades honestly without artifacts, then restores
  all six via verified local reuse and matches four canonical responses.
- PR #39 is open against main (no dependency); implementation `9a77360`, hardening
  `ef35343`, reviewed-main integration `7c30618`; final evidence:
  `ml/reports/event_outlooks_verification.json`. No merge into main. The log
  resolution retains the full incoming owner log; no teammate implementation edit.
- No authenticated production integration, event activation feed, score/alert
  change or newly validated local probability. T050A remains pending with Rudra;
  source publication/retrieval and hypothetical activation are separately labeled.

## Report form and map cleanup (Braydin, for Cache/Rudra UI) — 2026-10-17

Explicit user requests (Braydin):
- **Report step 2:** the present/absent `<select>` became two large radio choices styled like the category step. The select's selected colors (`bg-stop text-white`) conflicted with the shared `field` class (`bg-surface text-ink`), so a choice rendered as white on white.
- **Location (T034A):** no latitude/longitude by default. One status line ("Using your current location · Accurate to about 12 m", "Finding your location…", "Using the site's location (approximate)" with the reason). The fields appear only after "Enter a different spot", or while pinning or fixing an invalid point.
- **Map (`components/data/SiteMap.tsx`):**
  - The OpenStreetMap basemap loads by default, and there is no opt-in toggle.
  - Offline (`navigator.onLine` false), or when no tile loads, the map section is hidden and the location list remains. It returns on reconnect.
- **`scripts/check-shell.mjs`:** clicks the presence radios instead of setting the select.

Checks: 104 frontend tests, oxlint, `tsc -b`, and build clean.

## Report location, analysis panel, and duration on screen (T034A, T036A, T036B; Braydin for Cache) — 2026-10-17

Explicit user authorization (Braydin): complete Cache's T034A, T036A, and T036B in Cache's frontend files, matching Rudra's redesign theme (existing tokens, `card`/`kicker`/`chip`/`field`, `RiskShape`, existing icons; no new colors).

- `frontend/src/pages/ConnectedPages.tsx`:
  - `ReportForm` wires `useReportLocation` (T034A) and is now exported for tests.
  - `ReportCard` places `ReportAnalysis` beside the report and shows the location source and distance.
  - Notices receive the site's `event_outlook`.
  - Formatted with the file's existing single-quote, no-semicolon style.
- New: `components/data/ReportAnalysis.tsx`, `components/data/Duration.tsx`, `components/data/duration-text.ts`.
- `components/data/NoticeCard.tsx` gains an optional `outlook` prop; `components/data/Advisory.tsx` replaces the raw JSON outlook with the plain sentence.
- Tests: `frontend/tests/report-analysis.test.mjs` (panel states, duration sentence, form location); `frontend/tests/data.test.mjs` expects the new advisory wording.

Also (user-authorized dependency change): `backend/requirements.txt` adds Cache's model packages (`joblib`, `numpy`, `scikit-learn`, same ranges as `ml/requirements.txt`). Without them the backend could not import `ml`, so every live duration estimate was "unavailable". After installing, provision the model once from the repo root: `python -m ml.provision --download` (writes the git-ignored `ml/artifacts/provisioned_v2/`). Run the backend with `PYTHONPATH=..` from `backend/`.

Checks: 103 frontend tests, oxlint, `tsc -b`, and build clean. Cache's `scripts/check-shell.mjs` run in headless Chrome renders all three features with no browser errors. It then fails "Crew primary action below viewport at 320" at the same pixel position on unmodified main, so that existing layout issue is Rudra's redesign, not these changes.

## Briefing index and hazard points (T058C, Braydin) — 2026-10-17

Explicit user decision (Braydin): briefings show the site's 0–10 index and each hazard's points, both from Cache's deterministic score; Gemini's per-hazard level word is removed.

- Rudra's `app/schemas/briefings.py`: `Briefing.risk_score` and `data_completeness` (nullable); `BriefingHazard.points` replaces `risk_level`. `frontend/src/types/api.ts`, `scripts/generate_fixtures.py`, and regenerated `briefings.json` mirror it.
- Cache's `frontend/src/api/validate.ts` (`validateBriefing`) and `frontend/src/components/data/StoredBriefings.tsx` (headline "Site hazard index: x / 10 · level", "+n pts" or "not in score" per hazard, "Not enough current data to score" at 0% completeness; old briefings without an index still show the level).
- Braydin's own: `app/gemini/briefings.py`, `app/db/models.py`, `app/db/init.py` (two `briefings` columns, applied to Tiger). Score factor evidence ids stay `factor:{site}:{factor}`, with a suffix only when two factors share a name (one per confirmed report).

Checks: 701 backend tests, 97 frontend tests, Ruff, oxlint, `tsc -b`, and build clean; one live Gemini briefing verified.

## Gemini calls, report analysis, and report location (Braydin) — 2026-10-17

Explicit user authorization (Braydin): finish the Gemini tasks end to end, including focused edits in Rudra's and Cache's files, with this log for review. T057, T058B, T053A, and T060 are done; T061 waits on a live run.

Rudra's files:
- `app/schemas/reports.py` and `app/schemas/__init__.py`: new `LocationSource`, `AnalysisVerdict`, `AnalysisPoint`. `ReportEnrichment` is replaced by the supports/contradicts analysis (`status`, `verdict`, `summary`, `supporting`, `contradicting`, `also_visible`, `suggested_category`, `severity_suggestion`, `confidence`, `unknowns`, `evidence`, `unavailable_reason`, `needs_review`, `generated_by`, `analyzed_at`). `CrewReport` gains `location_source`, `location_accuracy_m`, `site_distance_miles`; `ReportCreate` gains `location_source` (default `site`) and `location_accuracy_m` (device only).
- `app/api/reports.py`: new form fields, a background task for `run_report_analysis`, and `include_context=False` on the 422 detail. Without it, a model-validator error crashed the response instead of returning 422.
- `app/services/reports.py`: `create_report` takes keyword-only `location_source`/`location_accuracy_m` and stores the site distance. Positional callers are unchanged.
- `app/api/sites.py`: `_notices` → `load_notices`, `_event_outlook` → `event_outlook_for` (public, reused by briefings and instructions); `report_schema` returns the location fields.
- `app/api/hazards.py`, `app/services/instructions.py`: the confirm route passes the outlook service, and `draft_instruction` offers the expected duration to the suggestion.
- `app/outlook/context.py`, `app/outlook/service.py`: site annotations widened from `SiteSummary` to `SiteLike` (id, lat, lon). No behavior change.
- `app/config.py` and `.env.example`: `GEMINI_THINKING_LEVEL` (default `low`); recommended model `gemini-3.5-flash-lite` (the free tier allows `gemini-3.8-flash` only 20 requests a day), timeout 20.
- `frontend/src/types/api.ts`, `scripts/generate_fixtures.py`, regenerated `reports.json`/`site-detail.json`: the mirror of the above; fixtures cover supports, inconclusive, and unavailable analyses.

Cache's files:
- `frontend/src/api/validate.ts`: validates the new analysis and location fields (it would otherwise reject every live report).
- `frontend/src/pages/ConnectedPages.tsx`: the old suggestion block now shows the verdict in words and "Photo analysis unavailable". T036A builds the full side panel.
- `frontend/src/demo/client.ts`, `frontend/tests/mock-service.ts`: report objects carry the location fields.

New shared test file: `backend/tests/conftest.py` blanks `GEMINI_API_KEY`, so no test can reach the real API from a developer's `.env`.

Checks: 694 backend tests (2 optional ML skips), Ruff and format clean; 95 frontend tests, oxlint, `tsc -b`, and build clean. Live: radius and instruction verified on `gemini-3.8-flash` until its 20-a-day free quota ran out (429); then all 16 text cases of `scripts/gemini_eval.py` answered and passed on `gemini-3.5-flash-lite`.

## Clean setup / T070 preparation — 2026-10-17 13:03 UTC

Explicit user scope: audit and reproduce frontend/backend startup without changing Claude's visuals or owner infrastructure. Separate `feature/cache-clean-setup` from main `681582be17315444f5ed9785c15f0fb37e8c09eb`; PR #34 was open at `8869e16` at startup and was not rewritten. No unmerged parent dependency or geolocation implementation copied. Identical `watch:null` helper change exists in both PRs; preserve it once when merging.

Upstream update: maintainers merged PR #34 at2026-10-17T12:52:20Z as `a7e2e720d11612a829bba467b1cb938ce05c6801`, discovered at final fetch. Verified checkpoint `447f5ca` is preserved; reviewed main is incorporated into this feature. Only PROJECT_CONTEXT/INTEGRATION_STATUS insertions conflicted; both histories retained, all incoming source preserved. The identical helper change combines once. Final source checks against this main:90 Node,lint/TypeScript,both builds, actual dev restart plus merged synthetic location hook and production preview pass. Final dev2026-10-17T13:03:32.058Z/preview2026-10-17T13:03:30.781Z: zero browser exceptions/API requests at all three widths. Backend/ML/dependency files are unchanged between681582b and this main, so clean637+10 Python/2 optional skips remain applicable. No main merge by Codex, and no form/contract/task completion added.

Two implementation files only: `frontend/vite.config.ts` excludes generated `.shell-check/` from watchers after a clean Vite restart reproduced EBUSY on locked Edge Cookies/Sessions; `frontend/scripts/check-shell.mjs` disables unnecessary watching on fixed-source helper servers, records completed stages on failure, and adds optional bounded interactive `--restart-check`. The checker never stops a server. It preserves the same isolated browser while an operator restarts their own process, then checks exact persisted demo JSON plus rendered report, supervisor confirmation, approved crew instruction, navigation and stored briefing. No new harness/server/dependency/seed or product behavior.

Verification uses a tracked-main archive with the two owned edits applied, a fresh `npm.cmd ci` and Python3.12.10 venv without system site packages, copied .env/model files or installed modules. `pip check` clean; 71 Node tests,637 backend tests/2 expected optional ML skips,10 probe tests,Ruff/117-file formatting,lint/TypeScript and fixture/API builds pass. Node24.22.0/npm11.19.1; lockfile unchanged. Existing Starlette deprecation/API554.37kB chunk/npm browser-tabs-lock postinstall warnings recorded; no script approval or dependency changes. Final dev browser2026-10-17T12:57:48.211Z includes real restart, production preview2026-10-17T12:58:20.615Z passes; both1440/390/320, zero browser exceptions/backend requests. No EBUSY after exclusion with active test profile. Initial test-edit lint warning/copy path corrected before verification; no existing acceptance assertion weakened.

Fresh actual FastAPI starts on8052 with no credentials and background jobs/bypass off, then with a health-only `.env` derived from the existing template. Health200 and anonymous site401; no DB/provider/account writes. Existing default proxy on5177->8000 returns401 JSON; not claimed to target isolated8052. Pre-existing5173 PID22668 (primary old checkout),5176 PID64004 (functional) and8000 PID65924 were preserved. Only this run's snapshot dev process was restarted; temporary test processes are shut down after verification. A Python worker may retain older imports, Vite serves its own checkout and preview serves old dist unless rebuilt; guide provides ownership-aware troubleshooting.

Shared documentation: PROJECT_CONTEXT, frontend/INTEGRATION, INTEGRATION_STATUS, this log; new WINDOWS_QUICKSTART and redacted clean-setup-verification.json. **No tasks.md change**: T070 requires pending tasks/actual services and another teammate's reproduction; real Auth0/Tiger memberships/T069 and enrichment/location/photo-analysis/live acceptance remain owner work. No pages/components/styles/App/auth/API/schema/backend/DB/migration/ML/manifest/lock/deployment edits. Rudra handoff: link guide from README/T077 and supply T069/contract readiness; Braydin: approved private settings/memberships; Claude: no interface or layout change required. Publication refs follow below.

Published [PR #35](https://github.com/BraydinPG/planit-control-swamphacks/pull/35), open against main. Implementation checkpoint `447f5ca`, reviewed-main feature merge `167ac4b`, finalized evidence `8c636fd`. Publication-only follow-up records refs in this log/context/evidence; no task completion, main merge or production activation. Owned test servers5177/5178/8052 are stopped; original5173 PID22668,5176 PID64004 and8000 PID65924 still listen. Claude's primary checkout remains clean/unchanged.

## Site-scoring integration verification — 2026-10-17 11:34 UTC

Explicit user scope: verify existing ingestion -> scoring -> persistence -> API -> UI -> confirmed report, fix functional defects without touching Claude's visual files or Rudra/Braydin production modules. PR #31 merged `07a459d`. Separate `feature/cache-scoring-integration` from that main; no unmerged parent. Reviewed Claude `feature/rudra-ui` `ac5861c` without merging/editing it; primary checkout/server preserved.

Changes: `frontend/src/api/live-read-validation.ts` rejects inconsistent headline/nested persisted-score value/band/version/completeness/time and scored detail without breakdown; `frontend/tests/live-read.test.mjs` covers it; `tests/mock-service.ts` fixes test-only inconsistent version/unscored responses. Existing diagnostic `scripts/check-live-integration.mjs` renders full factors and flags the actual component's missing incomplete-evidence warning using the existing T051A zero-evidence fixture; text gate in `scripts/integration/acceptance.mjs`, regression in `tests/integration.test.mjs`. No Client, hook, canonical DTO or auth export changes.

`backend/tests/test_site_scoring_workflow.py` is test-only explicitly authorized integration verification: existing NWS MockTransport/adapters/cache -> refresh/T051A -> in-memory test persistence/protected API -> test signed crew/supervisor permissions -> report confirmation -> outage. Stored/list/detail/full and top factors/ranking match across seven stages (2.1/3/3/4/4/7/7). This closes the cross-stage test gap without another engine, API, identity provider, application DB, seed, live feed or production write. Test snapshots export only to pytest temp for optional inspection, never JWTs.

Current results: 648 Python (638 backend+10 probe),70 Node,Ruff,changed-Python format,lint/TS,fixture/API builds pass. API553.81kB chunk warning after incoming main redesign and existing Starlette TestClient deprecation remain. Existing Edge mock/demo at1440/390/320 passes. One-off local inspection of seven actual test API snapshots through production HttpClient and mock-auth browser yields16 value comparisons at1440/390, zero exceptions; two additional no-evidence warning cases fail as documented. Helper/screenshots ignored, not a new shipped harness. Initial new-test issues were registering a synchronous Node test before top-level Vite awaits, an incorrect forecast-HI expectation and an existing helper's dict return; corrected before final checks. npm.ps1 was blocked by local policy; npm.cmd succeeded without policy changes.

Actual diagnostic: approved primary root lacks Auth0 SPA/backend/DATABASE_URL; DB state unknown, feeds off and NWS user-agent missing, T069 source seed empty. Actual health/OpenAPI200,11 routes,ten anonymous/dev-header401 and proxy401; invalid bearer503 remains blocked. No private account, DB connection/write or seed attempted, DEV_AUTH_BYPASS staysfalse. Diagnostic now exits1 on the known incomplete-score UI failure in addition to service blockers. Main/redesign ScorePanel need Claude's warning; Rudra owns ranking/status proposal and running-main/refresh/T069; Braydin owns private setup/membership/briefing qualification.

Shared updates: PROJECT_CONTEXT, INTEGRATION_STATUS, FUNCTIONAL_INTEGRATION_HANDOFF, FRONTEND_REDESIGN_HANDOFF, this log; new SITE_SCORING_INTEGRATION guide and redacted verification JSON. tasks.md is unchanged, T063-T068 unchecked. No component/page/style/App.tsx/auth/schema/fixture/algorithm/backend-production/DB/migration/manifest/lock/deployment changes. Implementation `b7d12934f6f646b1f4be0c57c02eb0cc73aa0d0f`; [PR #33](https://github.com/BraydinPG/planit-control-swamphacks/pull/33) open against main. Publication-only follow-up records these refs; no merge or operational enablement authorized/performed.

2026-10-17 11:41 UTC upstream update: maintainers merged visual PR #32 as `176cf36`. Cache integrated that reviewed main into the feature branch (`3b8dfe2`) without conflicts or manual visual edits. `git diff origin/main -- frontend/src/{pages,components,styles} frontend/src/index.css` is empty. Repeated70 Node/lint/TS/fixture+API builds and standard Edge1440/390/320 pass; actual controlled API snapshots again yield16 value matches/two known warning failures with zero browser exceptions. Backend/contract/algorithm source is unchanged from the verified648-test run. Primary checkout/server untouched. This supersedes earlier unmerged-redesign inspection status; no Codex merge into main.

## T051A deterministic scoring - 2026-10-17 11:16 UTC

Cache's explicit task-specific authorization assigns `backend/app/rules/score.py` and score weights in `backend/app/rules/settings.py`. Separate `feature/cache-site-risk-scoring` branch in the functional worktree, base merged PR #30 `1b1b0c3`; reviewed later main `ee923c3` only updates README. Primary/Claude checkout, server and uncommitted work untouched. No unmerged parent PR.

Code: rules-0.2 preserves compute_score/HazardScore/FactorContribution and default weights/bands. Adds trusted source/site/as-of/validity/unit qualification, matched heat-input provenance, cache-age checks, replay excluded from live completeness, current-feed coverage independent of active alert authority, report ID/shared-notice dedup and a labeled 3-point budget per reviewed category. All independent capped reports remain visible. No report expiry, injury probabilities, ML/Gemini term, timer change or clearance. Source-name checks are not authentication.

Tests: new `backend/tests/score_scenarios.py`, `test_site_risk_algorithm.py`, `test_site_risk_persistence.py`; focused fixture corrections in `test_score.py` (units/source identities, distinct cap-test IDs, replay completeness) and one canonical successful-none marker in `test_refresh.py`. No acceptance was weakened: old replay-as-live expectation intentionally corrected. 35 reproducible synthetic cases, two reconciled EIA reference comparisons and five canonical examples saved to `docs/site-risk-scoring-evaluation.json`. `docs/SITE_RISK_SCORING.md` specifies formula, limits and exact owner proposals.

Acceptance: initial 73 focused tests passed. Final `python -m pytest backend/tests -q`: **637 passed**, zero skipped, 11.15s, sole existing Starlette TestClient deprecation warning. `python -m ruff check backend` and format check for seven changed Python files pass. Includes canonical schemas/fixtures, stored site routes, refresh/alert transitions, history/previous score, concurrent confirmation/rollback and 18:00 briefing risk-level tests. A fresh subprocess blocks ML/Gemini imports with Gemini key absent. No new frontend/ML/browser build was needed; contracts/UI unchanged. These are offline/in-memory integration checks, not Auth0/Tiger Data/provider acceptance. Intermediate failures were stricter fixture assumptions, lint lengths/import, absent EIA IDs in illustrative frontend fixtures, and a new test's composite DB-key lookup; corrected before final acceptance.

Shared edits: only T051A `[ ]` becomes `[x]` in tasks.md, exact original text and all other bytes preserved; PROJECT_CONTEXT updated in the implementation commit. No other checkboxes changed. No production service, canonical schema, route, persistence, DB/migration, auth, ingestion, Gemini, ML, frontend, manifest/lockfile or deployment file edited.

Handoffs: **Rudra** reviews category cap and the mandatory numeric score's inability to express insufficient evidence, source coverage/ranking and explicit rescore orchestration outside refresh. **Braydin** reviews briefing unknowns/provenance and a future qualified report-resolution lifecycle. **Claude** keeps visual ownership; render existing states/completeness with incomplete index warnings and archived-fixture labels. Existing 7.6 display example is illustrative; recomputation is 5.0, not claimed live parity. Full proposal/acceptance details are in SITE_RISK_SCORING.md; no owner feature was implemented on their behalf. Implementation `e29baccd97d2a11758d80766dad8164753a0642a`; [PR #31](https://github.com/BraydinPG/planit-control-swamphacks/pull/31) is open against main for Rudra review. This documentation follow-up records publication refs; no merge authorized or performed.

## Functional diagnostics / Claude coordination - 2026-10-17

Published [PR #30](https://github.com/BraydinPG/planit-control-swamphacks/pull/30) against main; source checkpoints `b7c8dc4` and `11806fa`. Open at publication, no Codex merge. This follow-up records exact refs; no implementation/task state changes.

User authorization: Codex handles API/state/Auth0 consumption/diagnostics/tests; Claude actively owns visual files. User clarified existing Auth0 crew/supervisor test aliases are the demo accounts; do not create real-user/employee records. No identities, profiles or DB rows were created. Auth0-backed demo acceptance remains separate from isolated mocks.

Separate branch/worktree `feature/cache-functional-acceptance` / `C:/Users/cache/planit-control-functional`, from merged PR #29 main `ebd6d92`. API checkpoint `b7c8dc4` is preserved below. No unmerged parent dependency; primary checkout/server and teammate jobs/configuration are untouched. Full path ownership and stable component interfaces: FUNCTIONAL_INTEGRATION_HANDOFF.md.

Diagnostic changes: `frontend/scripts/check-live-integration.mjs` (explicit read-only configuration-root), `scripts/integration/acceptance.mjs` (gate every published anonymous denial before tokens; role casing, stored reads, crew notice denial and complete ack read-back), `scripts/probe-integration.py` (canonical Briefing validation; external settings without copying/code import changes), `scripts/run-live-account-check.py` (forward settings-root; hidden stdin tokens unchanged), `tests/integration.test.mjs` and `tests/test_integration_probe.py` (six/three new regression checks). API/test changes are the prior checkpoint's exact paths. No JSX/presentation/composition/auth/canonical fixtures/types/backend/ML/manifest/lockfile edits.

Shared docs: PROJECT_CONTEXT, INTEGRATION_STATUS, this log, FRONTEND_REDESIGN_HANDOFF, new FUNCTIONAL_INTEGRATION_HANDOFF and functional-integration-verification.json, frontend/INTEGRATION and LIVE_INTEGRATION. Task.md is unchanged. Documentation distinguishes actual provider-authenticated demo data from mocks and preserves existing owner work.

Checks: 68 Node, 521 Python (511 backend+10 probe), lint/TypeScript, fixture/API-mode builds, Ruff and existing installed Edge workflows at 1440/390/320 pass. API build warns for 531kB chunk; no conflicting layout/code-splitting change attempted. Initial new tests exposed a fixture assumption and the backend loader's source-fixed .env path; corrected test setup and explicit-root handling, with final checks passing. Actual local readiness: all11 operations match, ten anonymous/dev-header denials401, invalid bearer503, no Auth0 demo session or DB connection; exit2. Exact commands/results/files are in the machine record.

Rudra/Braydin: use existing demo setup and private session/configuration handoff; no employee accounts are needed. Claude: no component migration required; retain Client/hook interfaces, server-owned alert state, explicit instruction approval and stable notice IDs. Shared type/composition/config changes require coordination. Final implementation commit and review PR follow this verified checkpoint; no merge authorized/performed by Codex.

## Functional API validation checkpoint - 2026-10-17

User explicitly authorized Codex API/state/diagnostics/tests while Claude owns presentation. Separate worktree/branch from merged PR #29 main `ebd6d92`; primary checkout/server untouched. This checkpoint changes only `frontend/src/api/{contracts,http-client,live-read-validation}.ts`, new `frontend/tests/live-read.test.mjs`, context and this record. Canonical types/fixtures remain read-only; no pages/components/styles/auth/backend/ML/manifests/locks.

Site/alert DTOs, coordinates/nulls/source times/IDs and acknowledgement response now validated. Client method arguments unchanged; acknowledgement return is typed Alert. Six focused read/ack regressions pass; existing suite and current combined diagnostics were verified together (68 Node /521 Python; lint/build/browser pass). Final diagnostic and full coordination evidence follows in the next focused commit. No task checkbox changed; Auth0 test identities, not employee records, are intended for actual demo acceptance.

## T065 frontend lifecycle integration - 2026-10-17

Published implementation `60ce28082e5bf18822f758bec4f4b1686d3dc794`: [PR #29](https://github.com/BraydinPG/planit-control-swamphacks/pull/29), open against main at publication. This metadata-only follow-up records exact refs; source validation and T065 unchecked state are unchanged. Rudra/Braydin should use the owner handoff below.

Authorized scope: frontend wiring/tests and shared progress docs, using merged T053/T054/T054A/T055 and T058A contracts. No backend/auth/database/ML/deployment/manifest/lockfile change. T065 remains unchecked because actual authenticated persistence/delivery is not available locally. T063/T064/T066/T067/T068 unchanged.

Git update: maintainers merged PR #24 as `f3a65a7` and the pushed T067A checkpoint `2e4cfb7` in PR #27 as `1eed70e` while this run continued. Cache performed no main merge or force push. Preserved all work and fast-forwarded the new `feature/cache-report-lifecycle-integration` to reviewed main `1eed70e`; then fast-forwarded reviewed PR #28 main `dcd9fc5` (score-history regression fix) without touching its backend or T076 task note. Final review targets main without duplicated parent changes.

Changed code paths:
- `frontend/src/api/contracts.ts`: typed HazardConfirmResponse/HazardNotice returns; existing canonical types imported.
- `frontend/src/api/http-client.ts`: published review/notice capabilities, canonical multipart/report/review/confirmation/instruction validation; general conflict and unknown timeout outcomes, no retries.
- `frontend/src/api/validate.ts`: report/notice shape, ID/context/state and confirmation consistency checks; no inferred ownership or instruction on a potential notice.
- `frontend/src/components/data/Interaction.tsx`: synchronous in-flight guard; permission/conflict/malformed mutation responses refresh shared state.
- `frontend/src/components/data/NoticeCard.tsx`: returned server notice/draft, manual fallback, confirmer-only editor, explicit final 500-character send, foreign-owner state; stable notice identity preserves edits while GETs refresh.
- `frontend/src/pages/ConnectedPages.tsx`: absent-only review actions, present report site-notice link, stable notice keys, upload in-flight state, honest live photo-reference message and manual server refresh.
- `frontend/src/demo/client.ts`: separate absent review/present notice confirmation, matching report confirmation, duplicate conflicts; no simulated score recalculation.
- `frontend/tests/{data.test.mjs,lifecycle.test.mjs,browser-harness.tsx,mock-service.ts}` and `frontend/scripts/check-shell.mjs`: reuse fixtures in isolated mocked HTTP tests, 12 new lifecycle tests and browser UI flow; fixtures in test session storage, no real credentials/API access.

Shared docs: PROJECT_CONTEXT, INTEGRATION_STATUS, CROSS_SCOPE_CHANGES, FRONTEND_REDESIGN_HANDOFF, frontend/INTEGRATION, frontend/LIVE_INTEGRATION and docs/t065-verification.json. No T065 task.md change. T067A task checkbox already merged.

Verification: 56 Node tests, 518 backend/probe checks (511+7), lint/TS/build and isolated npm ci/build pass. Full final browser acceptance passes at 1440/390/320, including complete mock lifecycle and reload; evidence is in t065-verification.json. Early browser runs exposed a confirmation-refresh editor reset; fixed stable parent/child keys and retained server response. Another browser assertion expected raw 8.25 while the existing UI correctly rounds to 8.3; assertion corrected. These failed runs are not counted as acceptance.

Actual local readiness: restarted only owned FastAPI PID 64044 via its known session; intermediate known process 69228 has DEV_AUTH_BYPASS=false, FEED_REFRESH_ENABLED=false, BRIEFING_SCHEDULE_ENABLED=false. All 11 operations present without source/running drift. Five old and five additional route denial checks pass 401; invalid bearer503 remains blocked. DATABASE_URL/Auth0 settings missing; no actual account persistence, photos, instructions or Gemini-provider response verified. Final known developer process is PID 65924 after incorporating PR #28; it has the same disabled flags. No teammate process/configuration or long job was changed.

Owner handoff: Rudra reviews canonical route/response use and coordinates merge. Braydin continues independent private Auth0/Tiger Data/membership/storage/Gemini setup; use LIVE_INTEGRATION's real report lifecycle checklist afterwards. Private photo retrieval remains unconnected; UI never follows arbitrary photo URLs. Separate redesign should preserve state, evidence, roles, explicit approval and error behavior.

## T067A / T065 continuation - 2026-10-17

Explicit user authorization: complete T067A first, then wire T065 without duplicating Braydin's provisioning. Branch `feature/cache-stored-briefings-report-lifecycle` stacks on PR #24 head `6a2fc4d`; reviewed main `70c20ff` incorporated in `9dcd278`, preserving merged PR #26 and Auth0/Gemini changes. Detailed teammate evidence remains linked in PROJECT_CONTEXT and owner guides.

T067A changed paths: `frontend/src/api/{contracts,http-client,validate}.ts`, `src/demo/client.ts`, `src/pages/ConnectedPages.tsx`, new `src/components/data/StoredBriefings.tsx`, `scripts/integration/acceptance.mjs`, `scripts/check-shell.mjs`, `tests/{briefings,data,status}.test.mjs`, `tests/browser-harness.tsx`; removed only explicitly authorized obsolete interfaces in `src/types/api.ts` and `src/fixtures/explanations.json`. No unrelated canonical fixtures edited. Unit SSR caches isolated to prevent browser profile/file watcher conflicts; verified test time improved from 48 to 5 seconds.

Shared docs: `tasks.md` exact T067A box only, `PROJECT_CONTEXT.md`, this log, `docs/INTEGRATION_STATUS.md`, `docs/FRONTEND_REDESIGN_HANDOFF.md`, `frontend/INTEGRATION.md`, `frontend/LIVE_INTEGRATION.md`. Before: removed-feature request buttons/POSTs and fallback-generation checkbox. After: read-only site/organization stored GETs, exact scheduled 404 empty, validated window/context/source, retained deterministic score factors. No generation scheduler in browser.

T067A verification: lint/TypeScript/build, 44 Node checks, 65 focused backend fixture/briefing/TS-mirror checks; full installed Edge browser at 1440/390/320, stored success/404/401/403/503/invalid responses, Gemini/template labels, GET-only requests and keyboard checks pass. Actual role/persistence is separate; T065 stays unchecked without it. Backend/auth/database/ML/manifests/locks remain unchanged by Cache. Rudra should review contract compatibility; Braydin should use the current GET-only UI. Implementation commit follows this entry; PR metadata follows publication.

Historical records below retain their original as-of facts; current status is INTEGRATION_STATUS.

# Cross-scope changes

### 2026-10-17 - Access mat deterioration category

Explicit user request to add timber access mat deterioration as a report category.
Focused coordinated edits span Rudra's report enum, services, TypeScript mirror and
spec; Cache's form, analysis labels, validation and demo client; and Braydin's Gemini
category labels, radius reference and prompt. The additive value is
`access_mat_deterioration`; the prototype fallback radius is 1 mile. Existing string
DB columns and generated fixtures remain compatible. Crew stage notes stay unchanged
by Gemini. Structured A-D grading is tracked separately as T034B, not claimed complete.

## T034A device-location preparation — 2026-10-17 12:30 UTC

Explicit Cache assignment: implement report geolocation functionality under application/tests, preserving Claude's visual files and Rudra/Braydin's unpublished T053A contract. PR #33 is merged (`a54b87e`); isolated `feature/cache-report-device-location` starts at latest main `681582be17315444f5ed9785c15f0fb37e8c09eb`, no unmerged dependency. Primary checkout/server left untouched.

New `frontend/src/application/report-location.ts` and `useReportLocation.ts` implement one-shot/permission-based live acquisition, approximate site fallback while pending/failed, finite coordinate/accuracy checks,8-second timeout,pin priority,site/session reset,close cleanup and ignored late callbacks. Demo never requests private GPS; neither module writes storage or sends network/Gemini requests. A retained old form handler cannot restart acquisition after close or change a reopened session. No new fields sent to existing report transport; **ReportForm remains unchanged** because T053A source/accuracy/backend distance are absent. T034A/T053A and all other task states remain unchanged.

New19 Node cases and test-only React StrictMode/browser harness extend the existing Edge checker, without an alternate app/API/dependency. All90 Node and105 report/upload/schema/fixture/mirror backend tests pass; lint/TypeScript/fixture+API builds pass. Existing Starlette deprecation and API554.37kB chunk warning retained. Existing application regression at1440/390/320 and synthetic hook pass with no browser exceptions/backend calls. Final repeated browser timing and commit/PR are recorded below after verification/publication. A broad string assertion accidentally matched an unrelated fixture coordinate and the initial backend test path was wrong; corrected to report identity/actual test file before final checks. Test-only render lint warnings fixed; no existing test weakened.

Shared changes: this log, PROJECT_CONTEXT, INTEGRATION_STATUS, functional/redesign handoffs and new REPORT_LOCATION_INTEGRATION guide, to keep Claude/Rudra/Braydin aware of ready logic and exact contract/form blockers. No tasks.md/page/component/style/App/backend/DB/migration/auth/contract/fixture/ML/manifest/lock/deployment edit. No actual GPS, authenticated DB write, identity provisioning, or operational task completion claimed.

Final verification 2026-10-17T12:33:25.849Z: all browser stages pass, including closed/reopened-session protection; zero browser exceptions/backend requests. Existing automated no-note/no-GPS simulated form takes91ms. Two intervening runs exceeded the existing30-second cold helper-server limit before completing config checks. Disabling unnecessary file watching in fixed-source helper servers gives final false/invalid-mode startup23.404/10.614s; assertions/deadline unchanged. New failure JSON includes completed stages, and hook checks run before config startup to distinguish failures. No source/form behavior changes from this harness adjustment.

Published implementation `cc7b86b99c2327b6459cad6bebd1828c172c5f4a` as [PR #34](https://github.com/BraydinPG/planit-control-swamphacks/pull/34), open against main. Publication-only follow-up updates this log, PROJECT_CONTEXT and REPORT_LOCATION_INTEGRATION with exact refs. No task check-off, main merge, real location collection, or production activation performed. Claude/Rudra/Braydin owner handoff remains the next dependency.

## Phase 4 integration preparation - 2026-10-17

Cache implements under the user's explicit frontend/ML and phase-4 authorization. Starting checkout was clean at `8af5b9d`, PR #19 initially open, so this work began on a separate stacked branch. #19 merged during execution (`64cf632`), followed by Rudra's T052/T053 publication. Branch `feature/cache-live-integration-checks` fast-forwarded to reviewed main `9ba1b7c` without conflicts or loss of untracked work and now targets main. Nick's new backend T054/T054A/T055 ownership was preserved. No owner backend/auth/contract work was copied or rewritten.

Before: tested demo and prepared live site/alert calls, no reproducible live-readiness/real-account acceptance command. After: redacted diagnostics, bounded read-only database checks, real-token optional existing-client orchestration, canonical DTO/shared component checks, safe independent acknowledgement read-back and precise blocked outcomes. Newly published T053 report list/create is enabled separately from still-disabled review/instruction/AI; real present reports require a photo. No real login, DB connection or write was performed because configuration is unavailable.

Exact scoped paths:

| Files | Reason / contract / owner coordination |
| --- | --- |
| `frontend/scripts/check-live-integration.mjs`, `frontend/scripts/integration/acceptance.mjs` | Actual readiness/OpenAPI/proxy/denial checks, optional real role reads using existing HttpClient, source drift, no secret reports or invented live completion. |
| `frontend/scripts/probe-integration.py`, `frontend/scripts/run-live-account-check.py` | Existing backend settings/schema reuse, explicit read-only remote DB counts and hidden private stdin token bridge; no initialization, alternative database or identity provider. |
| `frontend/src/api/contracts.ts`, `frontend/src/api/http-client.ts`, `frontend/src/demo/client.ts`, `frontend/src/components/data/Interaction.tsx`, `frontend/src/pages/ConnectedPages.tsx` | Narrow T053 create/list capability versus disabled review; live photo-required semantics match Rudra's published multipart contract. Existing demo, canonical JSON, auth internals and ML behavior preserved. |
| `frontend/tests/integration.test.mjs`, `frontend/tests/test_integration_probe.py`, `frontend/tests/data.test.mjs`, `frontend/tests/browser-harness.tsx` | 16 new orchestration / 7 probe safety checks plus existing regression tests and updated capabilities; mocks explicitly distinguished from real acceptance. |
| `frontend/scripts/check-shell.mjs` | Mocked live photo requirement, isolated temporary Vite caches, measured cold-start allowance and network diagnostics; all existing content/accessibility assertions retained. |
| `frontend/LIVE_INTEGRATION.md`, `frontend/INTEGRATION.md`, `docs/INTEGRATION_STATUS.md`, `docs/phase4-integration-verification.json`, `PROJECT_CONTEXT.md`, `docs/CROSS_SCOPE_CHANGES.md` | Copyable actual setup/check commands, per-task proof/blockers, exact file/test/branch references and current owner handoffs. |

Tests: 39 frontend Node checks; 432 backend/probe Python checks (425+7), lint/TypeScript/build/Ruff and full desktop/phone browser workflows. Actual HTTP: health/OpenAPI 200; five anonymous/development-header denials 401; invalid token 503 with unconfigured Auth0. Redacted checker correctly exits 2 as blocked. No checkbox changed by Cache; T063-T068 remain unchecked. No backend/auth canonical types/fixtures, migrations, manifests/locks, deployment or ML source change relative to the reviewed main base. Exact file list and failed/resolved cold-start check are in phase4 verification JSON.

Owner actions: Braydin supplies Auth0/Tiger Data/account-membership configuration and Gemini/storage provisioning; Rudra reviews the T053 client and coordinates Nick's T054/T054A/T055 routes. Private photo retrieval and full live lifecycle remain unverified. Publication: [PR #24](https://github.com/BraydinPG/planit-control-swamphacks/pull/24), open against main, initial implementation `ff35b7b`. Later reviewed main `4e94c52` added T049A/T049B and `9b395f0` added T073 and conflicted only in PROJECT_CONTEXT; resolved by retaining both current phase-4 facts and Rudra's verified notes, then reran compatibility. No merge of this PR or deployment is authorized.

Final validated source: `483bcd1`; reviewed-main incorporation commits `d93fb3e` and `483bcd1` preserve every owner note. PR #24 was verified open and mergeable at that head; final metadata records the exact source. No task checkbox was changed by Cache.

The records below describe earlier checkpoints; this phase-4 section supersedes their old branch, PR-open and missing-T053 statements.


Current delivery update (2026-10-17): PR #16 and the T031 checkpoint PR #17 merged during this run. Delivery is now `feature/cache-frontend-workflows` against main `723a5b8`; T032-T038 implementation `3fbd98f`, reviewed-main incorporation `dc35458`. Rudra's newly merged T048 is connected with an acknowledgement capability; report/hazard/AI routes remain unavailable. The canonical T050 type is inherited directly. Earlier branch/status statements below record their original checkpoints.

Publication: [PR #19](https://github.com/BraydinPG/planit-control-swamphacks/pull/19), open/ready against main, implementation head `8834867`, with `4a9e44f` T048 integration and clean-export identity. This metadata follow-up records the exact review URL; no merge, reviewer acceptance, deployment or actual authenticated workflow is claimed. Shared-file changes are for Cache's authorized tasks; Rudra/Braydin should use the explicit owner actions in INTEGRATION_STATUS.

## Full frontend transfer — 2026-10-17

The user explicitly transferred Nick's remaining frontend responsibilities to Cache and authorized the dependent T031-T038/T063-T068 chain. Prior contributions and PR #16 remain attributed and preserved. Cache owns frontend implementation/integration; Rudra retains canonical backend/API ownership and Braydin retains Auth0 internals, Gemini, database and deployment. Claude's future redesign requires a separate authorization.

Branch `feature/cache-functional-frontend` stacks on PR #16 head `84e3936`; PR #16 was verified open. No later frontend branch/open PR was found. Main `2e79cb6` includes the separately merged T050 compact advisory; live endpoint/credential gaps are recorded in INTEGRATION_STATUS. `AGENTS.md` and remaining named task owners are updated without changing task IDs/acceptance or prior completion attribution.

Planned scoped changes: frontend data access/demo store, reusable UI, pages, application composition, tests, run/redesign guides and task/context evidence. A Leaflet map dependency in the frontend manifest/lockfile is necessary for T035's geospatial map; this is a focused shared-file change under the explicit project authorization, for Rudra review. No backend/auth internals/Gemini/database/ML contract edit is planned. Every completed task must carry its passing checks; live integration remains unchecked until its actual prerequisites and acceptance pass.

First verified milestone: T031 source-state/score/observation components in `frontend/src/components/data/Status.tsx`, checked by `frontend/tests/status.test.mjs` (three passed), frontend lint/build. All six canonical source states have text labels; null scores are not zero/low risk; legacy ML score components are withheld without payload mutation. `AGENTS.md`, `tasks.md` (remaining named owner transfer and T031 checkbox), `PROJECT_CONTEXT.md`, this log and `docs/INTEGRATION_STATUS.md` record authorization and scope. `frontend/package.json`/lockfile add only Leaflet 1.9.4 and matching type definitions for the forthcoming map; no backend/auth/ML contract change. Cache implements; Nick remains attributed for prior work. This checkpoint is the first commit of the stacked follow-on branch.

## T032-T038 functional frontend delivery — 2026-10-17 UTC

Cache implements under the explicit full frontend transfer, formerly Nick-owned. Before: T030 navigation plus isolated reference context. After: shared demo/HTTP view architecture with interactive crew and supervisor workflows, 55-point geographic map/list, canonical report/review/notices, existing-provider Auth0 integration, exact-site research advisory and explicit failure states. No real production report/write or authenticated session is simulated in live mode. T031 checkpoint: `140d118`. This verified implementation checks only T032-T038; T063-T068 remain unchecked because real dependencies are unavailable. PR publication references are appended after push.

Exact changed paths in this milestone (all paths relative to repository root):

| Files | Reason, contract/dependency, handoff |
| --- | --- |
| `frontend/src/App.tsx`, `frontend/src/components/shell/AppShell.tsx` | Compose the existing shell with shared demo/provider-backed real modes; preserve navigation and prior attribution. No independent Auth0 implementation. |
| `frontend/src/api/contracts.ts`, `frontend/src/api/http-client.ts` | One client interface, canonical T050 SiteDetail and typed HTTP/multipart requests; T048 all-state list/acknowledgement, server Date display-clock estimate, disabled missing report/hazard/AI services, explicit errors/token timeout, no demo fallback. Rudra reviews capabilities after actual routes exist. |
| `frontend/src/application/context.tsx`, `frontend/src/application/Provider.tsx`, `frontend/src/application/LiveApplication.tsx` | Existing Braydin provider/guard/token exports, role/subject session lifecycle, async resource cancellation, source refresh. Auth internals untouched; mocked roles are test-only. |
| `frontend/src/demo/client.ts`, `frontend/src/demo/generated/references.json`, `frontend/src/demo/generated/advisories.json` | Isolated localStorage namespace and memory-only photos; canonical fixture-derived demo state; 50 verified EIA IDs and two validated ML 2.1 replay exports. No active job/live incident assertion or model modification. |
| `frontend/src/pages/ConnectedPages.tsx` | T032-T037 shared crew/site/alert/report/review/map/briefing pages. Present/absent mandatory, note optional; confirmation/instruction isolated from score/alert authority. |
| `frontend/src/components/data/AlertCard.tsx`, `NoticeCard.tsx`, `Interaction.tsx`, `SiteMap.tsx`, `Advisory.tsx` | Reusable display/actions, authoritative countdown display, potential/confirmed semantics, geographic map, provenance/unknown research output. |
| `frontend/src/components/data/Status.tsx`, `frontend/tests/status.test.mjs` | Formatting of the prior T031 implementation/tests only; original source-state/null/legacy score behavior retained. |
| `frontend/src/styles/map.css` | Vendor zoom overrides >=44px and focus treatment; no second styling framework. |
| `frontend/scripts/export-demo-sources.py` | Offline checksum/schema validation and reproducible approved public exports; no retrieval/refit. |
| `frontend/tests/data.test.mjs`, `frontend/tests/browser.html`, `frontend/tests/browser-harness.tsx`, `frontend/scripts/check-shell.mjs` | 23 unit/component checks and complete browser workflows, mocked existing provider/HTTP; not real Auth0 proof. Test HTML excluded from production build inputs. |
| `frontend/vite.config.ts`, `frontend/.env.example` | Same-origin development /api proxy to existing FastAPI:8000; public configuration documentation, explicit bypass rejection. Production routing stays owner-controlled. |
| `frontend/SHELL.md`, `frontend/INTEGRATION.md`, `docs/INTEGRATION_STATUS.md`, `docs/FRONTEND_REDESIGN_HANDOFF.md`, `docs/frontend-acceptance.json` | Run/fixture/live/blocked matrix, task acceptance, exact tests and modular visual handoff. |
| `AGENTS.md`, `tasks.md`, `PROJECT_CONTEXT.md`, `docs/CROSS_SCOPE_CHANGES.md` | Accurate ownership/coordination, only verified T032-T038 boxes, short shared memory and this authorization/file log. No adjacent task acceptance changed. |

The preceding checkpoint also changed `frontend/package.json` and `frontend/package-lock.json` for Leaflet 1.9.4 / @types/leaflet 1.9.21; this focused frontend dependency is explicitly recorded for Rudra review. Root manifests/locks, `frontend/src/auth/**`, `frontend/src/types/api.ts`, Rudra's generated `src/fixtures/*.json`, backend routes/security/DB/Gemini, deployment and ML source/contracts/artifacts remain unchanged.

Final acceptance: 23 focused tests; lint and TypeScript/production build; installed headless Edge at 1440x1000/390x844/320x740; all ten destinations, map/list identity, team-first ordering, ack/reload/reset/explicit cleared payload, photo report without note, human review/confirm/send and crew instruction delivery; Gemini/fallback and exact-site ML advisory; missing/invalid config and mocked 200/401/403/503 plus T048 ack POST, keyboard/focus/44px controls. Merged-checkout backend tests: 297 passed, one pre-existing dependency warning. `docs/frontend-acceptance.json` records results; ignored screenshots were inspected. No ML behavior changed, so no retraining/backtest or scientific validation claim.

Required owner work: Rudra reviews the connected T048 client and implements remaining protected report/notice persistence/routes; Braydin supplies true tenant/configuration, Tiger Data/assigned-site seeds, photo storage and server Gemini routes. Exact task IDs/acceptance and requests are in `docs/INTEGRATION_STATUS.md`. Nick's prior work is preserved; future Claude work can restyle presentation while keeping data/session/permission semantics and tests. Publishing this review PR does not authorize merge or deployment.

The older T030 section below is a historical record of its original scope; the full transfer/delivery above supersedes its next-owner and unavailable-page statements.

Reproduction checkpoint: `4a9e44f` records the T048 integration/current-main reconciliation. A clean committed frontend-only export passed npm ci/build and full production-bundle demo browser acceptance. The browser driver adds an explicit `--production` mode to skip development-only provider/configuration tests and verify the test harness is absent. No local settings, model artifacts or dependencies were copied into that export. `docs/frontend-acceptance.json` contains the exact final changed-file list and both development/production browser records.

## T030 — Cache assisting Nick, 2026-10-17

Authorization: the user explicitly assigned T030 to Cache and stated, “Nick has given Cache permission to assist with frontend development.” Nick remains the owner and reviewer; this is not evidence that Nick has accepted the resulting PR. No merge is authorized without review.

Preflight: clean `feature/cache-worker-preview` checkout; fetched all remotes; current main `3dd52cc` includes merged PR #14 and Braydin's Auth0 implementation. No published Nick branch or open PR was returned by the remote/API checks, and no uncommitted frontend edits existed. Unpublished work on another machine is not observable here. New isolated branch: `feature/cache-t030-app-shell`, based on that main, preserving all published teammate changes.

T030 was unchecked. T003 and T007 are checked; the exact done criterion is “app renders on phone and desktop sizes.” Only T030 may be checked in this change. T031–T038 and T063 remain separate work.

Changed paths and handoff:

| Path | Change / owner handoff |
| --- | --- |
| `frontend/src/App.tsx` | Replaces starter content with one `AppShell` mount. Nick owns future application composition. |
| `frontend/index.html` | Removes starter root layout/dark styling, sets application metadata. No build/server configuration change. |
| `frontend/public/planit-mark.svg` | Small matching utility-grid favicon; leaves starter assets and the independent auth page untouched. |
| `frontend/src/components/shell/AppShell.tsx` | Desktop sidebar, phone bottom navigation, preview workspace selection, hash destinations, skip navigation, explicit connection states. Nick can replace destination content as each tracked page lands. |
| `frontend/src/components/shell/Icon.tsx` | Small shared SVG shell icon set; existing React/Tailwind only. |
| `frontend/src/pages/WorkspaceOverview.tsx` | Read-only reference context using existing simulated fixtures; no list/map, operational score, timer, report or briefing implementation. |
| `frontend/src/api/shell-fixtures.ts` | Bundled, typed fixture context and explicit default/false/invalid modes; no HTTP requests, tokens, writes or authentication bypass. Replace only through T063's reviewed client work. |
| `frontend/scripts/check-shell.mjs` | Reproducible installed-browser acceptance, isolated profiles/temporary test Vite servers; no new npm dependencies. |
| `frontend/.gitignore` | Ignores browser acceptance output/profile directory `.shell-check/`. |
| `frontend/SHELL.md` | Commands, fixture configuration, limits, testing and exact next owner task. |
| `docs/t030-acceptance.json` | Recorded browser/lint/build acceptance evidence. |
| `tasks.md` | Only T030 checkbox, after phone/desktop acceptance; all other task text/state preserved. |
| `PROJECT_CONTEXT.md` | Factual T030 index, current main/auth/PR state, entrypoint and review reference. |
| `docs/CROSS_SCOPE_CHANGES.md` | This authorization, file-by-file coordination and handoff record. |

Preserved without edits: `frontend/src/auth/**`, `frontend/src/types/api.ts`, generated fixture JSON, manifests/lockfiles, backend routes/security/schemas/database, ML code and contracts. `npm ci` installed main's declared dependencies; the lockfile did not change. No development auth role or backend bypass was enabled. No new test/format dependency was added to the project.

Verification: `npm run lint`, `npm run build`, and `node scripts/check-shell.mjs http://localhost:5173/`. Browser acceptance passed 1440×1000, 390×844 and 320×740; all ten preview destinations at each size, no horizontal overflow, >=44px navigation targets, reload/back/keyboard skip navigation, null-score wording and fixture-off/invalid states. No browser exceptions or backend API requests. Desktop/phone screenshots were visually inspected. Generated screenshots stay ignored; summary is in `docs/t030-acceptance.json`. A first browser test wait was corrected to ignore CSS uppercase text transformation; final assertions pass.

Limits: the app shell remains a demonstration. Preview workspace selection grants no permission. The reference site is a simulated fixture, not EIA/live work. Existing legacy onset/score examples are not shown. Account and live data remain unconnected to the shell, even though Braydin's independent auth modules now exist on main. Other page destinations show honest connection states, not working alert/report workflows.

Next owner work: **Nick T031**, prerequisites T006/T007 checked. T032 then needs T030 and T031. Rudra's T050 and API integration remain separate; Braydin's Auth0 module requires T066 wiring before the application can claim an authenticated session. Review the main fixture score wording with Rudra before any future scoring display; do not change or approve ML semantics through this shell.

Implementation checkpoint: `9d94f75e78b33c1a73d31ed2d35e02138ecf5785`. Review PR: [#16](https://github.com/BraydinPG/planit-control-swamphacks/pull/16), open against `main`; review requested from verified Nick handle `n1ckbown`. No acceptance by Nick or merge is claimed. Rudra coordinates merge after review.

## 2026-10-17 — Rudra frontend visual redesign (branch `feature/rudra-ui`)

Explicit user authorization: Rudra takes over frontend visual polish. This is a visual-only pass; Codex continues functional integration. Design references were Rudra's supplied crew/supervisor mockups and landing-page brand language (Archivo, JetBrains Mono, ink/bone/signal palette, mono kickers, distinct data-state marks).

| Path | Change |
|---|---|
| `frontend/src/index.css`, `frontend/src/styles/map.css` | Theme tokens per workspace (`data-theme` crew = dark, supervisor = light), fonts, focus rings, skeleton, reduced motion. |
| `frontend/src/components/shell/{AppShell,Icon}.tsx` | Sidebar/header/bottom-nav restyle and new icons. Routing, props, skip link, nav labels and heading focus unchanged. |
| `frontend/src/components/data/*` | Restyled cards; new `Risk.tsx` (shape + word risk badges, score bar). All safety copy, roles, labels and client calls kept. |
| `frontend/src/pages/ConnectedPages.tsx` | Markup/classes only: crew home order, two-column site detail, supervisor stat row and ranked table, report category tiles. Same state, handlers, required/disabled rules and strings. |

Not edited: `auth/**`, `api/**`, `application/**`, `demo/**`, `types/**`, fixtures, `App.tsx`, `LiveApplication.tsx`, manifests/lockfiles, backend, ML. No new dependencies.

Verification: `npm run build`, `npm run lint` (clean), the four `node --test` suites (44/44), and `node scripts/check-shell.mjs` at 1440×1000, 390×844 and 320×740 (pass, no browser exceptions, no backend requests). Risk is never color-only: every level has a shape and a word.

### 2026-10-17 — follow-up: crew phone layout, dark supervisor, location suggestions

- The crew workspace keeps its phone layout at every screen size: a centered phone-width column, no sidebar and the bottom navigation always visible. Page layouts now use container queries (`@container` on `<main>`), so they respond to the content column rather than the viewport.
- The supervisor workspace now uses the same dark tokens as the crew workspace. Leaflet controls, popups and marker outlines are themed for dark surfaces.
- "Search locations" (`components/data/LocationSearch.tsx`) is an ARIA combobox. With an empty box it suggests the first ranked locations; typing ranks matches by name, then team, then site ID, and still filters the map and list. Arrow keys plus Enter, or a click, open the chosen location.
- Restored the repo's single-quote, no-semicolon formatting in three files that the previous merge commit reformatted.

### 2026-10-17 — second polish pass (guided by the garden-skills web-design skill, "Redesign · Preserve")

- **Scoring display issue from FRONTEND_REDESIGN_HANDOFF.md is addressed (presentation only).** New `components/data/evidence.ts` classifies a supplied score by `data_completeness`: none (0%), partial, or full. Nothing is recalculated and DTOs are unchanged; the backend number and band always stay visible.
  - No evidence: ScorePanel headline reads "Unknown" with "Server value x / 10 · band", a dashed bar and an explicit note that the number is not a low or safe reading. RiskBadge reads "Unknown: no evidence"; ranked list, search suggestions and map (grey fill) match.
  - Partial: the band is kept and qualified ("Low · incomplete"), the bar is hatched, a note gives the reported percentage, and map markers get a dashed outline.
  - Stale or replayed inputs add a "Includes stale or simulated (replay) inputs" line. Null and legacy-withheld handling is unchanged.
- Large field buttons now actually render 72px/large text (important modifiers; the base size was winning). Crew home puts Report/View briefing directly after the alert and no longer repeats the site name.
- Removed left-border accent callouts; observations are one divided list instead of a card per reading; alert detail hides the ring when the server supplies no countdown and colors it by alert tone; active stop-work gets a beacon ring.
- Supervisor: "sites with active alerts" and "assigned team" stats double as filter toggles (`aria-pressed`); filter bar is sticky on wide layouts (map isolated under it); alerting rows are tinted; map popup link fixed for the dark theme.
- Motion tokens (one easing, three durations): button press feedback, page entry fade, stop-work beacon. All disabled under `prefers-reduced-motion`. Report form shows a local photo preview thumbnail (object URL revoked on change/unmount).

Verification: build, lint (clean), 90/90 Node tests, `check-shell.mjs` pass with no browser exceptions; before/after screenshots at 390 and 1440.

### 2026-10-17 — Apple Human Interface style (approved mockup), light theme

Rudra approved an Apple-style mockup and chose its light theme for both workspaces (this replaces the earlier dark supervisor request).

- `index.css` tokens: grouped grey background `#F2F2F7`, white surfaces, hairline `#D2D2D7`, ink `#1D1D1F`, system blue accent `#0071E3`, darkened system risk colours (stop `#D70015`, warning `#C93400`) so white text passes 4.5:1. System font stack (San Francisco on Apple devices); the Google Fonts import is removed. `kicker` is now an iOS grouped-list header, new `chip` utility for status pills, expo-out motion easing.
- Primary buttons are system blue; secondary are grey fills; cards are borderless white on the grouped background. Translucent header, sidebar and tab bar; tab bar marks the current tab with blue and bold text (plus `aria-current`); the preview workspace switch is a segmented control.
- **Behavior-visible change:** the crew alert detail no longer lists evidence IDs (Rudra's request). Trigger, distance, rule, source and the acknowledgement warning remain; supervisors still see the evidence list. No data, API or check changed.
- All strings, roles, shapes-plus-words, null/unknown/incomplete handling and 44/72px targets are unchanged.

Verification: build, lint (clean), 95/95 Node tests, `check-shell.mjs` pass with no browser exceptions; phone and desktop screenshots reviewed.

### 2026-10-17 — Rudra: score display integration (rules-0.2)

Explicit user request to make the Site Hazard Index display and update correctly. Focused
edits outside Rudra's default paths: `backend/app/gemini/briefings.py` (Braydin: stale
factors keep their points in briefing hazards; incomplete-evidence unknowns) and
`frontend/src/api/contracts.ts` (Codex: `sortSites` completeness tie-break matching the
backend). Presentation helper `frontend/src/components/data/evidence.ts` and the site
factor breakdown in `ConnectedPages.tsx` (Claude's redesign files). No schema, contract,
weight or scorer change. Details: SITE_SCORING_INTEGRATION.md.

### 2026-10-17 — Rudra/Claude: T050A multi-event outlooks (contract published)

Explicit request to connect Cache's PR #39 adapter to the site API and UI. Additive contract
`SiteDetail.event_outlooks` + `EvidenceKind.event_start` (docs/EVENT_OUTLOOKS_API.md); the
singular `event_outlook` is kept. Focused edits outside Rudra's paths: frontend
`live-read-validation.ts` (Codex: tolerant card checks), `demo/client.ts` and
`tests/mock-service.ts` (default `event_outlooks: []`), new `EventOutlooks.tsx` and its
placement on site detail (Claude). No `ml/**`, score, alert, auth or DB-schema change; notice
evidence is existing JSON. Cache/Codex: please review the contract before live testing.

### 2026-10-18 — Braydin: report photo retrieval (deployment finding)

Supervisors on the deployed site saw "private photo retrieval is not connected" on every report: reports stored a private photo key, but no route returned the image. Added with the user's authorization, touching Rudra's paths:

- `backend/app/api/reports.py`: `GET /api/reports/{id}/photo` streams the photo through the backend. Visibility matches `GET /api/reports` (crew: their team's sites; supervisor: their organization). A report the caller can't see, a report without a photo, and an object missing from storage are all 404s. `Cache-Control: private`.
- `frontend/src/api/{contracts,http-client}.ts`: optional `reportPhoto(id)` fetches the photo as a blob with the session token, since an `<img>` can't send one.
- `frontend/src/pages/ConnectedPages.tsx`: `StoredPhoto` shows the image, or "This photo isn't in storage."
- Tests: `backend/tests/test_reports_api.py` (visibility, 401, missing object), `frontend/tests/team.test.mjs` (authorized blob request).

The seven reports created before deployment have photo keys whose files were stored on teammates' laptops, so they show "This photo isn't in storage." New photos go to the private `foresite-photos` bucket.
