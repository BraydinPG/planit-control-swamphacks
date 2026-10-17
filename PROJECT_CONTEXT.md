# PlanIT Control: shared project context

## Last verified
- UTC verification: 2026-10-17 08:43:07 UTC; current task T030 only, Cache assisting Nick with explicit user authorization.
- Branch: `feature/cache-t030-app-shell`, based on main `3dd52cc`; no uncommitted frontend work or published Nick branch/open PR found at startup.
- PR #14 is merged in that main; prior PR #4/#6/#9/#12 remain merged. No stacked dependency.
- Main now includes Braydin's Auth0 modules and site-route guards; tenant/live token behavior not verified in T030.
- T030 replaces the Vite starter with the responsive React/TypeScript/Tailwind application shell.
- Exact entrypoint: `frontend/src/App.tsx` -> `components/shell/AppShell.tsx`; fixture overview in `pages/WorkspaceOverview.tsx`.
- Run: `cd frontend; npm ci; npm run dev`; current printed URL http://localhost:5173/ (developer server left running).
- Fixture mode defaults on when unset; `VITE_USE_FIXTURES=false` or invalid input shows unavailable, never silent sample/live fallback.
- Existing generated SiteSummary/SiteDetail fixtures used for reference context; all sample data explicitly simulated, not EIA/live jobs.
- Crew/supervisor preview navigation grants no permissions. Auth0/API integration, site list/detail, score components and alert/report workflows remain separate.
- Browser acceptance: 1440x1000, 390x844, 320x740; ten crew/supervisor destinations per size, no horizontal overflow, >=44px nav targets.
- Reload/back/keyboard skip link, null-score text, false/invalid fixture states passed; zero browser exceptions and backend API requests.
- `npm run lint`, `npm run build`, browser acceptance and visual desktop/phone inspection pass; details in `docs/t030-acceptance.json`.
- Visible Edge launch was blocked by automatic approval review; headless browser rendering succeeded. No security workaround enabled.
- Only T030 checkbox changed after its done criterion passed; T031/T032/T063 and every other state preserved.
- No auth/backend/shared type/fixture JSON/ML/manifest/lockfile edits; no new project dependencies.
- Cross-scope authorization, all changed paths and Nick handoff: `docs/CROSS_SCOPE_CHANGES.md`; fixture commands/limits: `frontend/SHELL.md`.
- Implementation commit/review PR: T030 checkpoint in this branch, pending publication for Nick review; no merge authorized.
- Existing offline ML preview remains `python -m ml.worker_preview` (T087); combined 2.1.0 callable/contracts unchanged.
- Prior ML source snapshot: 2026-10-17T07:18:48.564672Z, 50 sites/150 replay outputs; environmental evidence 2/50, notices 10/50.
- Next unblocked task: Nick T031 (T006/T007 checked), before T032 crew home. T063 remains a later integration task.

## Mission and boundaries
- Layer A: conditional evolution of an already confirmed event, never event onset.
- Existing NOAA targets concern recorded intervals, not physical worksite clearance.
- Layer B: site-associated observed/issued environmental evidence; no injury model.
- Combined outlook must distinguish observed, issued forecast, research, and unknown.
- Monte Carlo stays offline: arithmetic/sensitivity checks, never proof of accuracy.
- All ML remains research only and operationally ineligible.
- Never clear/suppress warnings, authorize access/work, change alerts or final scores.
- Lightning within 10 miles and resettable 30-minute timer remain deterministic.
- Missing measurements are unknown, never zero risk.
- Do not infer downed lines, energized water, wildlife, damage or access from weather.
- Crew hazard classifications require human confirmation.
- EIA plants are representative monitored locations, not verified construction sites.

## Ownership
- Cache: `ml/**`, datasets, evaluation, advisory contracts and offline demos.
- Current T030 authorization permits Cache to assist Nick in the frontend, plus cross-scope docs, context and the exact T030 checkbox. No auth/API/ML contract changes authorized.
- Rudra: API contracts/routes, deterministic alerts/scoring, root README; see AGENTS.
- Nick: frontend pages/components/styles/API client; preserve his files.
- Braydin: auth, database/ingestion, Gemini, Vultr deployment per current AGENTS.
- T030 permits the shell frontend changes only; preserve routes, migrations, auth modules, API types and shared manifests.
- Propose integration through fixtures/tests/handoff; do not merge into main yourself.
- Read current `AGENTS.md`, `spec.md`, `tasks.md` for the authoritative ownership map.

## Architecture already implemented
- Frontend: React/TypeScript + Vite + Tailwind. Backend: FastAPI only.
- `backend/app/schemas/`: canonical API; `frontend/src/types/api.ts`: mirror.
- `backend/app/schemas/observations.py`: current reading/location/time shape.
- `backend/app/schemas/sites.py`: SiteSummary and SiteDetail.
- Existing backend Observation lacks the full issue/availability/vintage/coverage contract.
- Main site routes include Auth0/assigned-site guard code; real tenant/token behavior is not verified by this shell.
- Main includes Tiger Data models/schema setup and Braydin's EIA importer; deployed DB state unverified here.
- Do not invent those missing fields from a fetched timestamp.
- `ml/predict.py`: `predict_active_event`, legacy `predict_site` adapter.
- `ml/backend_adapter.py`: cached `ActiveEventPredictor`, including `predict_for_site`.
- `ml/dispatch.py`: per-type registry and checksum guard for expansion models.
- `ml/contracts.py`, `ml/schemas.py`: existing active-event contract 1.1.
- `ml/train.py`, `features.py`, `backtest.py`: shared duration core, grouped cutoffs.
- `ml/monte_carlo.py`: offline sampling; production inference does not import it.
- `ml/worker/schema.py`: WorkerOutlookRequest/WorkerOutlook, combined contract 2.0.0.
- `ml/worker/comprehensive.py`: build_comprehensive_outlook; opt-in 2.1, 2.0 callable unchanged.
- `ml/worker/comprehensive_schema.py`: ComprehensiveRequest/Outlook; explicit to_legacy adapter.
- `ml/hazard_registry.json`, `ml/HAZARD_COVERAGE_AUDIT.md`: per-hazard maturity and sign-off.
- `ml/hazard_rehearsal.py`: disconnected scenarios + 50-site acceptance, models provisioned separately.
- `ml/HAZARD_INTEGRATION.md`: 2.1 migration and exact Rudra/Nick/Braydin handoffs.
- Request has no trust-policy/principal field; caller-owned policy authenticates nobody.
- `ml/worker/combined.py`: build_worker_outlook, build_for_backend_site, explanation_context.
- `ml/worker/evidence.py`, `spatial.py`, `impacts.py`: as-of/unit/geometry gates and Layer B.
- Site condition probabilities/confidence are null; no learned site target is validated.
- Derived heat index links matched eligible inputs; not a direct measurement or WBGT.
- Unknown/future artifact fit policy fails closed; earlier replay cannot use later fit.
- No ML route or frontend outlook integration was added by PR #6.

## Source index and provenance
- `ml/COVERAGE.md`: 15-type NOAA inventory from PR #6.
- `ml/reports/source_manifest.json`: five pinned NOAA 2021–2025 archives.
- `ml/reports/multidisaster/coverage.json`: counts, regions, exclusions, hashes.
- `ml/reports/multidisaster/registry.json`: model eligibility, targets and hashes.
- `ml/reports/multidisaster/station_coverage.json`: three observed station histories.
- `ml/reports/multidisaster/hurdat_coverage.json`: post-analysis and advisory receipts.
- Wildfire/gauge investigation receipts are in the same reports directory.
- Raw data, artifacts, environments and private inputs remain gitignored.
- HURDAT2/NOAA final records/ERA5 do not establish historical operational availability.
- ISD-Lite archived measurements lack original issue/acquisition vintages.
- `ml/DISASTER_COVERAGE.md`, `ml/source_catalog.json`: all 54 raw types / staged sources.
- `ml/reports/worker_outlook/noaa_census.json`: all 349,030 rows, family reporting groups.
- `ml/reports/worker_outlook/feed_snapshot.json`: 18 cached responses, hashes and gaps.
- Real NWS/CO-OPS/USGS/NDBC/SWPC captures; CO-OPS humidity unavailable.
- `ml/fixtures/worker_outlook/`: normalized real exports, EIA locations, typed examples/schemas.
- Real environment is paired with hypothetical event contexts; compound warning/quake are fixtures.
- `ml/fixtures/hazard_coverage/`: backend-selector export, 64 receipts, schemas and three 2.1 examples.
- `ml/reports/hazard_coverage/`: per-site source coverage, 31 scenario results and real performance.
- New real ShakeMap is an automatic Pakistan model; zero US-site grid coverage, uncertainty absent.
- Normalized fixture hashes use UTF-8/LF; original HTTP hashes retain exact source bytes.

## Current readiness
| Family | Verified prior implementation | Limit |
|---|---|---|
| Flood | Preserved KM duration research | Regional record, not local water depth |
| Flash Flood | Research duration dispatch | Positive continuous interval, age >=1h |
| High Wind | Research duration dispatch | Regional wind record, not site gust |
| Heavy Rain | Research duration dispatch | Recorded interval, not rainfall depth |
| Winter Storm | Research duration dispatch | No local ice/load prediction |
| Heat Index Exceedance | Three-station research replay | 90F prototype threshold, no work/rest rule |
| Strong Wind | Trained, disabled | Failed calibration gate |
| Ice Storm | Trained, disabled | Sparse groups/classes and calibration |
| Heavy Snow | Trained, disabled | Failed calibration gate |
| Hurricane | Offline wind-change experiment | Post-analysis, no live dispatch |
| Thunderstorm Wind | Ingested | Point reports do not label storm lifetime |
| Wildfire | Perimeter/FIRMS investigation | No containment/progression model |
| USGS water level | 97 historical measurements | No validated basin/site relationship |
| Site wind/heat/rain | Real observed/issued evidence, matching gates | No learned local probability or worker exposure claim |
| Earthquake | 20 catalog events; synthetic local demo | No local shaking/structural estimate |
| Coastal/buoy/SWPC | Real probes, source/QC/association checks | No inundation/outage prediction |
| AirNow/FIRMS | Fixture-tested only | Credentials/archive data not acquired; AQS identified only |
| Other NOAA hazards | All 54 raw types inventoried | No added predictive dispatch |
| Terrain/tsunami/volcano feeds | Sources identified | No issued-vintage/local-label acquisition |

## Existing runnable entry points
```powershell
./ml/setup.ps1 -ProvisionModel
python -m ml.provision_expansion --download
python -m ml.smoke
python -m ml.demo_worker_outlook --require-models
python -m ml.worker_research
python -m ml.hazard_rehearsal --require-models
python -m pytest ml/tests backend/tests -q
```
- Use the ML environment; install backend requirements for combined backend tests.
- Backend-working-directory import requires repository root in PYTHONPATH.
- Existing canonical examples: `ml/reports/multidisaster/examples.json`.
- Existing reproducibility evidence: `ml/reports/multidisaster/reproducibility.json`.
- New examples: `ml/fixtures/worker_outlook/flood_request.json`, `flood_outlook.json`.
- Second example: `wind_request.json`, `wind_outlook.json`; schemas in the same folder.
- Demo uses real weather + explicitly hypothetical activation, never a real-event claim.
- `ml/WORKER_OUTLOOK.md`: complete setup, evidence semantics, limits and commands.
- `ml/reports/worker_outlook/validation.json`: exact checks and counts.

## Verified limits and current dependencies
- EIA August 2026: 28,379 generator rows, 14,700 valid unique plant locations, 50 exported.
- This is a research fixture set, not a backend database import or verified worksites.
- Braydin's separate EIA importer uses `eia860m-{state}-{plant_id}` IDs; do not assume ML fixture IDs match.
- Existing duration artifacts were hash/reference verified in the fresh environment.
- NOAA episode groups are reporting clusters, not proven independent disasters.
- 2025 holdouts were inspected; do not tune on them or call them fresh tests.
- Unidentified duration quantiles remain null; three disabled models stay disabled.
- Station proximity alone does not establish site exposure or basin relevance.
- Backend must authorize site access and supply confirmed event and source evidence.
- Captured source products prove availability at capture, not earlier historical vintages.
- Production ingestion/auth/routes/UI are not wired to this new library.
- In 2.1, electrical/structural/chemical/wildlife/access dangers stay explicit unknowns without trusted review.
- Default report trust is deny; fixture role/site checks are not production token validation.
- Five offline scenarios pass; current warm composition is about 1–2ms, one worker.
- Offline MC: 20,000 draws each for Flood/High Wind, plus 12 policy-sensitivity cases.
- No new learned target, joint probability or historical ML backtest was introduced.
- New cold/warm/batch/validation and traced-allocation measurements are in hazard acceptance.json.

## Next actions and handoff
- Next unblocked tracked task: Nick T031 (T006/T007 checked); T030 shell does not complete scores/status components or T063.
1. Rudra: review opt-in FastAPI wiring after assigned-site authorization; keep controls separate.
2. Braydin: supply true event confirmation, source timestamps/versions, auth and basin evidence.
3. Nick: display method/window/source, derived/demo badges and unknowns; no clearance countdown.
- Prefer the opt-in 2.1 examples/schemas and HAZARD_INTEGRATION; 2.0 consumers use to_legacy explicitly.
- Paste to a new agent: Read PROJECT_CONTEXT.md, then AGENTS.md and the relevant
  `ml/INTEGRATION.md`, `ml/MULTIDISASTER.md`, and contract code before editing.
  Preserve current contracts and safety limits. Use `ml/fixtures/worker_outlook/flood_outlook.json`
  and the worker 2.0.0 schema; legacy 1.1 duration calls remain intact.

## Decision log
- 2026-10-17: PR #4/#6 ancestry verified; branch from merged main, no duplicate merge.
- 2026-10-17: preserve existing duration fits; prioritize evidence-only site conditions.
- 2026-10-17: all-category census and two-layer research slice verified; site ML not forced.
- 2026-10-17: 256 checks passed on base `7950971`; feature pushed and PR #9 opened for review.
- 2026-10-17: PR #9 merged; new 2.1 hazard package passes 361 checks and clean-export fallback/provisioned replay; PR #12 was then open; merge reverified in the T087 checkpoint above.
- Update this file in the same commit as model/contract/source/handoff/test changes.
- Reconcile teammate edits; keep deep details in ML docs, not a transcript here.

- 2026-10-17 08:20:44 UTC: T087 changes `tasks.md` (one new Cache task/check-off) and this index for accurate coordination; code/tests/docs stay in `ml/`. Rudra, Nick and Braydin should read WORKER_PREVIEW. Evidence and candidate export identity: `ml/preview_verification.json`; implementation `555ce0a`, PR #14 (open for Rudra review).

- 2026-10-17 08:43:07 UTC: T030 cross-scope shell accepted on desktop/phones; only its checkbox changed. Nick reviews the scoped PR; `docs/CROSS_SCOPE_CHANGES.md` records authorization, files and checks.
