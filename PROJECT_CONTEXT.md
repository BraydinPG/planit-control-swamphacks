# PlanIT Control: shared project context

## Last verified
- UTC verification: 2026-10-17 06:40:52; update with each relevant checkpoint.
- Working branch: `feature/cache-combined-disaster-outlooks`.
- Base: `origin/main` at `2bf48e9`; teammate API/DB commits preserved by clean rebase.
- Verified implementation: `5aa49a0`; context/verification follow-up commits may follow.
- GitHub PR #4: merged 2026-10-17, merge `cf9d3bb`; already an ancestor of main.
- GitHub PR #6: merged 2026-10-17, merge `20af37d`; source head `28b89cf`.
- Both merge states verified through GitHub API and local ancestry, not assumed.
- Python: `ml/.venv/Scripts/python.exe`, 3.14.5; pinned ML dependencies exist.
- Fresh isolated environment: 252 ML/backend tests passed, including 62 new worker checks.
- Backend lint/format, new Python lint/format, frontend lint/typecheck/build passed.
- Existing nine duration artifacts/reference predictions verified without refitting.
- New PR is pending publication at this checkpoint; do not merge into main.

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
- This task explicitly authorizes root `PROJECT_CONTEXT.md` and a short AGENTS pointer.
- Rudra: API contracts/routes, deterministic alerts/scoring, root README; see AGENTS.
- Nick: frontend pages/components/styles/API client; preserve his files.
- Braydin: auth, database/ingestion, Gemini, Vultr deployment per current AGENTS.
- Do not change routes, migrations, auth, frontend screens or shared manifests here.
- Propose integration through fixtures/tests/handoff; do not merge into main yourself.
- Read current `AGENTS.md`, `spec.md`, `tasks.md` for the authoritative ownership map.

## Architecture already implemented
- Frontend: React/TypeScript + Vite + Tailwind. Backend: FastAPI only.
- `backend/app/schemas/`: canonical API; `frontend/src/types/api.ts`: mirror.
- `backend/app/schemas/observations.py`: current reading/location/time shape.
- `backend/app/schemas/sites.py`: SiteSummary and SiteDetail.
- Existing backend Observation lacks the full issue/availability/vintage/coverage contract.
- Main now includes Tiger Data models/schema setup and an empty seed; no EIA import yet.
- Do not invent those missing fields from a fetched timestamp.
- `ml/predict.py`: `predict_active_event`, legacy `predict_site` adapter.
- `ml/backend_adapter.py`: cached `ActiveEventPredictor`, including `predict_for_site`.
- `ml/dispatch.py`: per-type registry and checksum guard for expansion models.
- `ml/contracts.py`, `ml/schemas.py`: existing active-event contract 1.1.
- `ml/train.py`, `features.py`, `backtest.py`: shared duration core, grouped cutoffs.
- `ml/monte_carlo.py`: offline sampling; production inference does not import it.
- `ml/worker/schema.py`: WorkerOutlookRequest/WorkerOutlook, combined contract 2.0.0.
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
- Existing duration artifacts were hash/reference verified in the fresh environment.
- NOAA episode groups are reporting clusters, not proven independent disasters.
- 2025 holdouts were inspected; do not tune on them or call them fresh tests.
- Unidentified duration quantiles remain null; three disabled models stay disabled.
- Station proximity alone does not establish site exposure or basin relevance.
- Backend must authorize site access and supply confirmed event and source evidence.
- Captured source products prove availability at capture, not earlier historical vintages.
- Production ingestion/auth/routes/UI are not wired to this new library.
- Five offline scenarios pass; current warm composition is about 1–2ms, one worker.
- Offline MC: 20,000 draws each for Flood/High Wind, plus 12 policy-sensitivity cases.
- No new learned target, joint probability or historical ML backtest was introduced.

## Next actions and handoff
1. Rudra: review opt-in FastAPI wiring after assigned-site authorization; keep controls separate.
2. Braydin: supply true event confirmation, source timestamps/versions, auth and basin evidence.
3. Nick: display method/window/source, derived/demo badges and unknowns; no clearance countdown.
- Paste to a new agent: Read PROJECT_CONTEXT.md, then AGENTS.md and the relevant
  `ml/INTEGRATION.md`, `ml/MULTIDISASTER.md`, and contract code before editing.
  Preserve current contracts and safety limits. Use `ml/fixtures/worker_outlook/flood_outlook.json`
  and the worker 2.0.0 schema; legacy 1.1 duration calls remain intact.

## Decision log
- 2026-10-17: PR #4/#6 ancestry verified; branch from merged main, no duplicate merge.
- 2026-10-17: preserve existing duration fits; prioritize evidence-only site conditions.
- 2026-10-17: all-category census and two-layer research slice verified; site ML not forced.
- Update this file in the same commit as model/contract/source/handoff/test changes.
- Reconcile teammate edits; keep deep details in ML docs, not a transcript here.
