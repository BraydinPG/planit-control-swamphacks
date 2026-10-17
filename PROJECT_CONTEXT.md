# PlanIT Control: shared project context

## Last verified
- UTC: 2026-10-17 05:28:05; update this file with each relevant checkpoint.
- Working branch: `feature/cache-combined-disaster-outlooks`.
- Base: `origin/main` at `20af37d858d3961f5a250aadb9ce94a23e710fed`.
- GitHub PR #4: merged 2026-10-17, merge `cf9d3bb`; already an ancestor of main.
- GitHub PR #6: merged 2026-10-17, merge `20af37d`; source head `28b89cf`.
- Both merge states verified through GitHub API and local ancestry, not assumed.
- Python: `ml/.venv/Scripts/python.exe`, 3.14.5; pinned ML dependencies exist.
- Prior PR #6 reported 176 tests passing; this checkpoint has not rerun them.
- New combined worker outlook is being implemented, not yet verified at this checkpoint.

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
- Existing Observation lacks a complete issue/availability/vintage/coverage contract.
- Do not invent those missing fields from a fetched timestamp.
- `ml/predict.py`: `predict_active_event`, legacy `predict_site` adapter.
- `ml/backend_adapter.py`: cached `ActiveEventPredictor`, including `predict_for_site`.
- `ml/dispatch.py`: per-type registry and checksum guard for expansion models.
- `ml/contracts.py`, `ml/schemas.py`: existing active-event contract 1.1.
- `ml/train.py`, `features.py`, `backtest.py`: shared duration core, grouped cutoffs.
- `ml/monte_carlo.py`: offline sampling; production inference does not import it.
- Combined site-impact schema/callable is absent at this initial checkpoint.
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
- All-category `ml/DISASTER_COVERAGE.md` and source catalog are pending this push.

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
| Other hazards | No verified combined site implementation yet | Inventory required |

## Existing runnable entry points
```powershell
./ml/setup.ps1 -ProvisionModel
python -m ml.provision_expansion --download
python -m ml.smoke
python -m pytest ml/tests backend/tests -q
```
- Use the ML environment; install backend requirements for combined backend tests.
- Backend-working-directory import requires repository root in PYTHONPATH.
- Existing canonical examples: `ml/reports/multidisaster/examples.json`.
- Existing reproducibility evidence: `ml/reports/multidisaster/reproducibility.json`.
- New demo command/combined JSON fixtures will be added and verified in this push.

## Verified limits and current dependencies
- No real 50+ EIA site import is verified on main; frontend fixtures are mock data.
- Existing duration artifacts are present locally; verify hashes before reuse.
- NOAA episode groups are reporting clusters, not proven independent disasters.
- 2025 holdouts were inspected; do not tune on them or call them fresh tests.
- Unidentified duration quantiles remain null; three disabled models stay disabled.
- Station proximity alone does not establish site exposure or basin relevance.
- Backend must authorize site access and supply confirmed event and source evidence.
- New operational-vintage feeds and site association are not yet integrated.

## Next actions and handoff
1. Cache: complete all-category catalog, evidence gates and two-layer offline demo.
2. Rudra/Braydin: supply authorized site/event and issued evidence with true timestamps.
3. Nick: display method, spatial limitations, unknowns and research labels separately.
- Paste to a new agent: Read PROJECT_CONTEXT.md, then AGENTS.md and the relevant
  `ml/INTEGRATION.md`, `ml/MULTIDISASTER.md`, and contract code before editing.
  Preserve current contracts and safety limits; use the versioned example output.

## Decision log
- 2026-10-17: PR #4/#6 ancestry verified; branch from merged main, no duplicate merge.
- 2026-10-17: preserve existing duration fits; prioritize evidence-only site conditions.
- Update this file in the same commit as model/contract/source/handoff/test changes.
- Reconcile teammate edits; keep deep details in ML docs, not a transcript here.
