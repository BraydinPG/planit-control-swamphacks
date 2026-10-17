# PlanIT Control Task Backlog

Read `spec.md`, `AGENTS.md`, and `tasks.md` before starting. Use task IDs to sequence and record implementation. An explicit user-approved scope may include a focused chain of dependent tasks; preserve per-task acceptance checks and completion states.

## Instructions for the coding LLM

For each task:

1. Choose an unchecked task or explicitly approved task sequence; distinguish blocking prerequisites from integration-only dependencies.
2. Inspect the relevant files and preserve existing work.
3. Implement only within the approved scope.
4. Run each task's done check and relevant tests.
5. Check each box only after its done check passes.
6. Report changed files, checks run, and blockers. Leave blocked tasks unchecked.

Aim for 15–60 minutes per task. Split larger tasks before coding. Respect the default path ownership in `AGENTS.md`; explicit project-level authorization may permit focused cross-owner changes. Preserve unrelated work. Rudra coordinates shared schemas, manifests, alert rules, and scoring. Braydin owns Tiger Data migrations, Gemini endpoints, and Vultr deployment.

## Owners

- Rudra: backend routes except Gemini, API contracts, NWS feeds and the shared feed cache in `backend/app/ingestion/`, photo storage in `backend/app/storage/`, alert rules, storing and serving scores (the risk algorithm itself is Cache's, T051A), report and notice persistence, README.
- Cache: `ml/`, model training, features, prediction, evaluation, and the 0–10 site risk algorithm (`backend/app/rules/score.py` and the score weights in `backend/app/rules/settings.py`, T051A).
- Braydin: `backend/app/security/`, `backend/app/db/**`, `backend/app/ingestion/**` except Rudra's NWS and cache files, `backend/app/gemini/**`, database migrations, EIA-860M site import, lightning, hurricane, earthquake, and flood-gauge feeds, Gemini endpoints, Vultr deployment, `frontend/src/auth/`, `auth/SETUP.md`.
- Cache (formerly Nick): remaining frontend implementation/integration in `frontend/src/pages/`, `frontend/src/components/`, `frontend/src/styles/`, `frontend/src/api/`. Nick retains attribution for prior contributions; separate future Claude redesign requires authorization. Auth0 internals remain Braydin-owned.
- Nick: T054, T054A, and T055 (hazard confirmation, supervisor instructions, confirmed reports in the score). This backend work lives in Rudra's report, notice, and scoring files under `backend/app/`; Rudra reviews it and owns the API contract. Nick also still deploys the frontend (T082).

## Shared contracts

Rudra publishes schemas before parallel work begins. Nick uses fixtures until APIs are ready.

Cache implements `predict_site(features)` returning hazard probabilities, model score component, factor contributions, confidence, model version, and data quality. Rudra combines this result with current hazard factors and confirmed crew reports to calculate the final score.

Routes:
- `GET /api/sites`
- `GET /api/sites/{id}`
- `GET /api/alerts`
- `POST /api/alerts/{id}/acknowledge`
- `POST /api/reports`
- `GET /api/reports`
- `POST /api/reports/{id}/review`
- `POST /api/hazards/{id}/confirm`
- `POST /api/hazards/{id}/instruction`
- `GET /api/sites/{id}/briefing`
- `GET /api/briefings`

## Phase 0: Kickoff and shared setup

- [x] **T001 | Rudra | Confirm the stack.** Use React + TypeScript with Vite and Tailwind CSS for the UI, FastAPI for every API route, Tiger Data for the database, Auth0 for identity, and Vultr for hosting and photo storage, as required in `spec.md`. Auth0, Tiger Data, and Vultr are sponsors for tracks. Done when all members agree on that stack and run commands.
- [x] **T002 | All | Read the project docs.** Read `spec.md` and `AGENTS.md`. Done when each person confirms owned paths and project scope.
- [x] **T003 | Rudra | Create the minimal repo skeleton.** Add frontend, FastAPI backend, model, auth, and test folders. Done when a placeholder Vite frontend and a FastAPI `GET /health` route run locally.
- [x] **T004 | Rudra | Add `.env.example`.** List Tiger Data, Auth0, Gemini, and Vultr Object Storage variable names and descriptions, with no secrets. Done when a new member can identify required configuration.
- [x] **T005 | Rudra | Add quality commands.** Document existing formatter, linter, and test commands. Done when each command runs locally.
- [x] **T006 | Rudra | Publish API schemas.** Define organization, team, site, observation, alert, score, report, hazard notice, briefing, and explanation types. A site includes its assigned team. A report includes whether the hazard is present. A hazard notice includes the radius and keeps the instruction empty until a supervisor sends it. Done when Nick can build without guessing field names.
- [x] **T007 | Rudra | Add API fixtures.** Create sample JSON matching T006, including stale, simulated, and unavailable states. Done when fixtures validate against the schemas.
- [ ] **T008 | All | Create separate branches.** Use `feature/rudra-api`, `feature/cache-ml`, `feature/braydin-auth0`, and `feature/nick-ui`. Done when each member confirms their branch.

## Phase 1: Parallel foundation work

Rudra's API-dependent lanes start after T006 and T007. Cache may start the independent ML lane using ML-owned fixtures and schema; backend integration waits for the approved contract. Nick may use fixture data until API routes are ready.

### Rudra: backend foundation

- [x] **T009 | Rudra | Add API health route.** Implement FastAPI `GET /health` in `backend/app/`. Needs T003. Done when local startup and the health check pass.

### Braydin: Tiger Data setup

- [x] **T010 | Braydin | Configure the Tiger Data connection.** Read `DATABASE_URL` from the environment and require `sslmode=require` for Tiger Cloud. Needs T004 and T006. Done when the backend starts with documented settings.
- [x] **T011 | Braydin | Define database models.** Add Organization, Team, Site, Observation, Alert, HazardPrediction, HazardScore, CrewReport, HazardNotice, Acknowledgement, Briefing, and AuditEvent. A crew member belongs to one team. A team is assigned to one location. A supervisor belongs to one organization. Needs T006. Done when models import successfully.
- [x] **T012 | Braydin | Add database initialization.** Create migrations or a schema setup command on Tiger Data. Enable TimescaleDB and convert `Observation`, `Alert`, and `AuditEvent` into hypertables. Needs T011. Done when a clean database initializes from scratch.
- [x] **T013 | Braydin | Add a seed command.** Provide one runnable command. Leave demo scenario contents for Rudra. Needs T012. Done when the command runs against a clean database.

### Cache: AI/ML

- [x] **T087 | Cache | Independent worker-outlook developer preview (non-production).** Generate one offline, worker-readable read-only preview of existing comprehensive event-plus-site outlooks for real EIA reference sites and clearly labeled replayed disaster contexts. Invoke the existing ML callable and typed 2.1.0 contract; reuse approved site identities, real captured observations where available, and explicit unknowns. Include at least one meaningful Flood and one High Wind example and a negative/missing-evidence example; provide a one-command reproducible local run. Needs T022, T023, and TML-H03. Done when the preview renders in a browser or terminal without starting an unauthenticated API, every output validates, a clean checkout can reproduce or gracefully report missing artifacts, safety boundaries are tested, and integration instructions are documented. This does not finish T050, T063, or the whole application demo.

Worker advisory continuation (Cache-owned, explicit user authorization; independent of production integration):

Comprehensive hazard follow-up (new branch after PR #9 merged):
- [x] **TML-H01 | Cache | Audit natural and cascading worksite hazards.** 146-entry typed registry, all 54 raw NOAA labels, FEMA 18-group crosswalk, official pointers and distinct maturity/sign-off states.
- [x] **TML-H02 | Cache | Strengthen official evidence and unknown hazards.** 64 source receipts, 50 NWS point queries, strict native alerts, opt-in 2.1 schema/report contracts and explicit cascading unknowns; no production writes.
- [x] **TML-H03 | Cache | Verify comprehensive offline rehearsal.** 31 adversarial scenarios, 50 reconciled backend EIA identities, coverage/missingness/performance; fresh-environment full suite 361 passed with frontend/backend checks.
- [x] **TML-H04 | Cache | Publish tested owner handoffs.** Context, source/verification reports, three canonical 2.1 examples and copy-ready owner handoffs published in PR #12; review comment posted. PR remains open, with teammate features and all research/safety gates preserved.

- [x] **TML-W01 | Cache | Verify merged ancestry and shared project memory.** PR #4/#6 merge ancestry verified, new branch from `20af37d`, `PROJECT_CONTEXT.md` created with the AGENTS read-first/update pointer.
- [x] **TML-W02 | Cache | Census all NOAA types and stage official sources.** 349,030 rows / 54 verbatim types; versioned typed source catalog, per-family reporting groups and limitations, real EIA/NWS/CO-OPS/USGS/NDBC/SWPC snapshots, explicit not-retrieved sources.
- [x] **TML-W03 | Cache | Build source/time/space gates and Layer B.** Typed provenance, availability/issue checks, geography, units/QC, conservative gauge/track handling, reviewed crew evidence, matched derived heat index, descriptive source forecasts; no learned local probability claim.
- [x] **TML-W04 | Cache | Compose and demonstrate both layers.** `build_worker_outlook`, schema 2.0.0, real-weather/hypothetical-event Flood and High Wind scenarios, missing/mismatch, compound and quake cases; unchanged scores/alerts/timers.
- [x] **TML-W05 | Cache | Verify isolated setup, artifact identity and offline research.** Fresh environment full suite, existing artifact hashes/references without refitting, schema examples, offline MC consistency/sensitivity and measured one-worker latency; no new predictive backtest claim.
- [x] **TML-W06 | Cache | Prepare exact owner handoff.** Canonical request/response JSON, source catalog, runnable demo, integration proposal, display/Gemini limits and remaining feed dependencies documented; production integration remains Rudra/Nick/Braydin-owned.

Multi-disaster continuation (explicitly authorized Cache scope; separate from team feature branches):

- [x] **TML-EXP01 | Cache | Inventory all 15 requested NOAA types.** Done: 349,030 source rows audited with original types, episode/region/year counts, point/invalid/missingness exclusions, and pinned checksums in `ml/COVERAGE.md` and reports.
- [x] **TML-EXP02 | Cache | Add official specialized-source adapters.** Done: observed heat/wind station parsing, NHC storm tracks and issued advisory probe, bounded NIFC/FIRMS investigation, and USGS gage-height probe; fixture tests distinguish missing/censored data from resolution/containment.
- [x] **TML-EXP03 | Cache | Evaluate separate conditional targets.** Done: seven new NOAA fits and observed heat fit with fixed chronological grouped holdouts, baseline comparisons, reliability/duration/support/bootstrap results, and unchanged predeclared gates. Five research targets qualify; three failed types remain disabled. NHC trend is explicitly offline/post-analysis.
- [x] **TML-EXP04 | Cache | Extend inference and compatibility.** Done: contract 1.1 dispatch, type/hash-specific model cache, target/local evidence checks, compact metadata and variable horizons; no onset/score/alert mutation. Existing shared ModelOutput accepts new dictionaries in focused backend tests.
- [x] **TML-EXP05 | Cache | Verify reproducibility and performance.** Done: all eight duration artifacts rebuilt byte-for-byte separately without holdout reruns; Flood reference predictions preserved; serial timings and selected-distribution internal Monte Carlo recorded.
- [x] **TML-EXP06 | Cache | Publish research evidence and handoff.** Done: runnable provisioning, per-target historical examples, coverage/evaluation/method notes, source limitations, and Rudra integration instructions in `ml/MULTIDISASTER.md`; focused ML/backend checks pass. Team review is required before merging or operational product exposure.

These tasks are independent of Rudra's site/API fixtures. Use ML-owned event fixtures first; backend integration remains a separate, opt-in dependency. Never predict event onset or interpret recorded event resolution as site clearance.

- [x] **T014 | Cache | Define active-event input/output contract.** Define `predict_active_event(event_context)` and the safe `predict_site()` compatibility adapter. No T006 prerequisite. Done when schema tests cover active, inactive, invalid, simulated, and unavailable cases.
- [x] **T015 | Cache | Validate as-of features and evidence.** Enforce feature allowlists, UTC timestamps, stale/missing flags, and no future-valid observations. Needs T014. Done when leakage and invalid-input tests pass.
- [x] **T016 | Cache | Create labeled synthetic fixtures.** Include event groups, active snapshots, censoring, and no-event compatibility inputs. Needs T014. Done when tests run offline and fixture-only claims are explicit.
- [x] **T017 | Cache | Implement conditional survival baseline.** Estimate persistence/resolution conditional on event age using training groups only. Needs T016. Done when survival is monotonic, age-conditioned, and sparse support returns unavailable.
- [x] **T018 | Cache | Acquire and normalize historical event data.** Add bounded, retrying NOAA Storm Events retrieval with provenance and schema checks. Needs T016. Done when a small real archive subset is verified or a concrete network/data blocker is recorded.
- [x] **T019 | Cache | Build leakage-safe event snapshots.** Create active-event snapshots and recorded-end/censoring labels; keep episode groups intact. Needs T015 and T018. Done when future fields cannot become predictors and snapshots are reproducible.
- [x] **T020 | Cache | Fit conditional outcome model.** Train an interpretable discrete-time survival model only if real support justifies it; preserve baseline fallback. Needs T017 and T019. Done when artifact/features/version are reproducible or support limitations are explicit.
- [x] **T021 | Cache | Backtest by event chronology.** Hold out complete episode/storm groups and report Brier/calibration, duration errors and interval coverage where defined. Needs T020. Done when `ml/EVALUATION.md` reports actual results or clearly states historical validation was not completed.
- [x] **T022 | Cache | Implement production inference.** Load validated artifacts offline and return deterministic `predict_active_event()` results. Keep `predict_site()` keys but do not fabricate onset probabilities or an approved score contribution. Needs T014 and T020. Done when fresh-process import and JSON-safety tests pass.
- [x] **T023 | Cache | Add offline Monte Carlo and fallbacks.** Test conditional draws, monotonic event state, unresolved tail, seeded reproducibility, and explicit unavailable behavior. Needs T017 and T022. Done when simulation checks pass and docs state Monte Carlo is not independent validation.

### Braydin: Auth0

- [x] **T024 | Braydin | Document Auth0 setup.** Add tenant, callback, logout, audience, role, permission, and environment-variable instructions to `auth/SETUP.md`. Needs T004 and T006. Done when another member can configure the tenant from the guide.
- [x] **T025 | Braydin | Implement frontend auth provider.** Export `AuthProvider` and `useAuth()` with user, role, loading, login, logout, and token access. Needs T006. Done when an isolated page can sign in and read the role.
- [x] **T026 | Braydin | Add frontend role guard.** Export `RequireRole` or the agreed equivalent. Needs T025. Done when the wrong role sees an access state.
- [x] **T027 | Braydin | Implement backend token validation.** Add reusable FastAPI security dependencies. Needs T024. Done when missing, invalid, expired, and valid tokens return expected results.
- [x] **T028 | Braydin | Add permission helpers.** Support crew and supervisor actions in `AGENTS.md`. Needs T027. Done when tests reject crew access to supervisor-only actions.
- [x] **T029 | Braydin | Document demo account setup.** Explain how to test both roles without committing credentials. Needs T024 and T025. Done when setup steps are clear.

### Cache: frontend and UI/UX (ownership transferred from Nick)

- [x] **T030 | Nick | Create responsive app shell.** Add navigation and fixture mode. Style it with Tailwind utility classes. Needs T003 and T007. Done when app renders on phone and desktop sizes.
- [x] **T031 | Cache | Create score and status components.** Show risk score, factors, freshness, and source. Needs T006 and T007. Done when observed, stale, simulated, and unavailable states are distinct without color alone.
- [x] **T032 | Cache | Build crew home screen.** Show site, status, alert, immediate action, update time, and a “potential {hazard}” notice with no instructions. After a supervisor sends an instruction, show that text. Needs T030 and T031. Done when the main action appears without scrolling on a phone.
- [x] **T033 | Cache | Build alert detail.** Show trigger, evidence, distance, acknowledgement, and countdown. Needs T032. Done when fixtures show active, reset, and cleared states.
- [x] **T034 | Cache | Build hazard report form.** Add photo, category (including broken electrical pole or downed line, on-site fire, wildlife, flooding, and other), coordinates, a required present-or-absent choice, optional note, and confirmation. Needs T030. Done when submission does not require typed text.
- [x] **T035 | Cache | Build supervisor location list.** Show the full map and every location with its assigned team, alerts, scores, and top factors. Place locations that have a team above locations that do not. Needs T030 and T031. Done when an occupied location appears above an empty one and the team name is visible.
- [x] **T036 | Cache | Build site detail and report review.** Show observations, timestamps, source, reports, and review status. Needs T031 and T035. Done when a supervisor can review a fixture report.
- [x] **T037 | Cache | Build briefing panel.** Show recommendations, evidence, unknowns, and fallback state. Needs T007 and T031. Done when generated and fallback text look distinct.
- [x] **T038 | Cache | Check accessibility and responsive behavior.** Test touch targets, keyboard flow, focus, labels, and risk information without color. Needs T032–T037. Done when checklist passes or remaining issues become separate tasks.

## Phase 2: Real sites, data, scores, and alerts

- [x] **T039 | Braydin | Inspect EIA-860M data.** Record source date, fields, and import mapping. Needs T013. Done when coordinate fields are verified.
- [x] **T040 | Braydin | Import 50+ sites.** Validate IDs, coordinates, and duplicates. Label locations as representative power plants, not verified construction sites. Needs T039 and T012. Done when 50 valid locations are in the database.
- [x] **T041 | Rudra | Implement `GET /api/sites`.** Return every location with its assigned team, matching T006. Sort locations with a team first, then by risk. Needs T040 and T006. Done when response validates.
- [x] **T042 | Rudra | Implement `GET /api/sites/{id}`.** Return observations, score factors, reports, and freshness. Needs T041. Done when valid IDs return detail and unknown IDs return 404.
- [x] **T043 | Rudra | Add the NWS weather and forecast feed (P0).** Use `api.weather.gov` point lookup, hourly forecast, and latest station observation in `backend/app/ingestion/`. Send a `User-Agent`. Normalize results into Observation records through the ingestion interface in `AGENTS.md`. Needs T012. Done when one site receives timestamped observed and forecast readings.
- [x] **T043A | Rudra | Add the NWS flood alerts feed (P0).** Fetch active Flood Warning, Flash Flood Warning, and Flood Watch alerts for each site point. Normalize them into `flood_alert` Observations. Needs T043. Done when a fixture alert produces an Observation and a failed fetch is marked unavailable, not "no flood."
- [x] **T044 | Rudra | Add caching and stale state for every feed.** Preserve each feed's last successful readings, track freshness per feed, and mark stale and unavailable states. Needs T043. Done when failed refreshes cannot appear current and one failed feed does not mark the others stale.
- [x] **T045 | Braydin | Define lightning event input and replay fixture (P0).** Normalize strike location and time. Expose `submit_strike()` from the ingestion interface. Label replayed strikes simulated. Needs T012. Done when tests can submit a strike without a live feed.
- [x] **T045A | Braydin | Add a live lightning feed (P1, best effort).** Try NOAA GOES GLM lightning data on AWS Open Data. Fall back to the replay fixture and label it simulated. Wrap the fetch in `FeedCache` (see `AGENTS.md`, "Adding a feed adapter"). Needs T045 and T044. Done when live strikes arrive as Observations, or the fallback is documented and labeled.
- [x] **T045B | Braydin | Add the hurricane feed (P1).** Use NHC active storms (`CurrentStorms.json`) and NWS Hurricane and Tropical Storm Warning and Watch alerts. Normalize them into `hurricane` Observations. Wrap the fetch in `FeedCache` (see `AGENTS.md`, "Adding a feed adapter"). Needs T044. Done when a fixture storm produces an Observation with source and time, and a failed fetch is marked unavailable.
- [x] **T045C | Braydin | Add the earthquake feed (P1).** Use the USGS earthquake GeoJSON summary feed. Normalize magnitude, location, and time into `earthquake` Observations. Wrap the fetch in `FeedCache` (see `AGENTS.md`, "Adding a feed adapter"). Needs T044. Done when a fixture event produces an Observation and a failed fetch is marked unavailable.
- [x] **T045D | Braydin | Add the USGS flood gauge feed (P1).** Use USGS Water Services instantaneous readings for gauges near sites. Normalize them into `flood_gauge` Observations. Wrap the fetch in `FeedCache` (see `AGENTS.md`, "Adding a feed adapter"). Needs T044. Done when a fixture gauge reading produces an Observation and NWS flood alerts remain the fallback.
- [x] **T046 | Rudra | Implement the 10-mile trigger.** Create stop-work alert for qualifying strikes. Needs T045. Done when tests cover inside, outside, and boundary distance.
- [x] **T047 | Rudra | Implement 30-minute resettable timer.** Base clear time on latest qualifying strike. Needs T046. Done when a second strike resets the timer and 30 strike-free minutes clear it.
- [x] **T048 | Rudra | Implement alert listing and acknowledgement.** Persist alert status, user, and acknowledgement time. Needs T046, T047, and T027. Done when state persists across requests.
- [x] **T049 | Rudra | Add prototype heat and flood factors.** Use Braydin's weather, forecast, and flood Observations and document configurable thresholds. Needs T043, T043A, and T044. Done when factors include source, time, and prototype label.
- [x] **T049A | Rudra | Add prototype hurricane and earthquake rules (P1).** A hurricane warning covering the site or an NHC storm within a configurable distance, and a USGS event at or above a configurable magnitude within a configurable distance, each create a potential-hazard notice and a score factor. Use the default radii in `spec.md`. Needs T045B, T045C, and T053. Done when fixture Observations inside and outside the settings produce the expected notices and factors, and every setting is labeled prototype. Done: rules and factors in `backend/app/rules/regional.py`, notices in `backend/app/services/feed_notices.py`, tests in `backend/tests/test_regional_rules.py`. `compute_score` now takes an optional `site` keyword, which the NHC storm distance needs. Nothing calls `send_feed_notices` on a schedule yet; see T049B.
- [x] **T049B | Rudra | Add the feed refresh loop.** On a schedule, for every site: fetch each feed adapter, store the returned Observations, evaluate the lightning rule (T048), send source-detected potential notices (`send_feed_notices`, T049A), and rescore (`score_site`, T051). One feed failing must not stop the others. Start it from the FastAPI lifespan behind a setting that is off in tests. Needs T043, T043A, T044, T045–T045D, T048, T049A, and T051. Done when one refresh stores readings for every site, a fixture hurricane or earthquake sends one notice, and a repeat refresh sends none. Done: `backend/app/services/refresh.py` (`refresh_all`, background `run_forever`, one-shot `python -m app.services.refresh`), started from the lifespan only when `FEED_REFRESH_ENABLED=true` (default off). It scores from the readings just fetched via the new optional `observations` argument to `score_site`; other callers are unchanged. Tests: `backend/tests/test_refresh.py`.
- [x] **T050 | Rudra | Add optional active-event outlook integration.** Import `predict_active_event()` only after the backend event/as-of contract is approved; expose a compact separate field, not a score factor. Needs T022 and the approved event-context contract. Done when unavailable output leaves existing routes and deterministic alerts unchanged.
- [x] **T051 | Rudra | Calculate final 0–10 score.** Combine current deterministic factors and confirmed reports; exclude conditional persistence unless score semantics are separately approved. Document weights and missing-data handling. Needs T049. Done when response includes factor contributions and tests pass.
- [ ] **T051A | Cache | Own the 0–10 site risk algorithm.** Assigned 2026-10-17 by Braydin. Cache owns the deterministic weighted algorithm that turns current hazard factors and confirmed reports into each site's 0–10 score and risk level (low, moderate, high, critical): `backend/app/rules/score.py` and the score weights in `backend/app/rules/settings.py`. Start from Rudra's T051 implementation there; keep the `HazardScore` and `FactorContribution` contract and `services/scoring.py` call unless Rudra publishes a change. Rules: weight factors by risk with documented, labeled prototype weights and bands; no ML or Gemini output in the score (score explanations were removed, so the weighted factor breakdown is the only explanation); stale or unavailable inputs never count as low risk and must lower `data_completeness`; never clear or suppress alerts. The 6 PM briefings (T058A) use this risk level. Add hurricane and earthquake factors when T049A lands. Needs T051. Done when the algorithm, its weights, bands, and missing-data handling are documented in the module and covered by tests.

## Phase 3: Reports, Gemini, and permissions

- [x] **T052 | Rudra | Configure photo storage.** Use Vultr Object Storage, with a private local directory for development. Add size and type limits. Needs T012. Done when invalid uploads are rejected.
- [x] **T053 | Rudra | Implement report creation and potential notices.** Store organization, team, reporter, category, whether the hazard is present, coordinates, photo, optional note, time, and pending status. Call Braydin’s Gemini radius function. Send “potential {hazard}” with no instructions to teams and supervisors inside the returned radius. If that function reports Gemini unresponsive or an invalid radius, use that category’s labeled default from `spec.md`. Needs T052, T027, and T056. Done when the report persists and recipients inside the radius are notified.
- [x] **T054 | Nick | Implement hazard confirmation.** Any supervisor who received the potential notice can confirm it. The reporting organization’s supervisor still reviews a report that no hazard is present. Record reviewer and time. Needs T053 and T028. Done when crew is denied, a supervisor outside the notice is denied, and an absent report stays with its own organization. Verified: receipt-scoped confirmation, organization-scoped review/site-detail privacy, atomic first confirmer and audit rollback; backend 363 passed, 2 optional ML checks skipped; Ruff lint/format pass. See `docs/T054_IMPLEMENTATION.md`. Subsequent T054A/T055 acceptance is recorded below.
- [x] **T054A | Nick | Send the supervisor’s instruction.** After confirmation, call Braydin’s Gemini instruction function. Let the confirming supervisor edit the suggestion, then send that text to every team inside the stored radius. Needs T054 and T056. Done when the potential notice contains no instruction and teams receive the supervisor’s final text. Verified: structured Gemini draft/manual fallback, confirmer-only atomic send, current-team stored-radius delivery, private drafts, rollback and concurrent-send tests; 73 focused / 393 backend tests passed, 2 optional ML checks skipped; Ruff lint/format pass. See `docs/T054A_IMPLEMENTATION.md` for Braydin/Rudra/Cache handoffs. Live Gemini and frontend acceptance remain separate.
- [x] **T055 | Nick | Add confirmed reports to scores.** Count only confirmed reports that the hazard is present. Exclude pending, rejected, and confirmed-absent reports. Needs T051 and T054. Preserve T049A's compute_score site keyword and T049B's current observations input. Done when only those confirmed reports affect the score. Verified: atomic confirmation/score persistence, full eligible-report query beyond UI limit, same-time/concurrent refresh ordering, exclusions and rollback; full backend 409 passed, zero skipped, Ruff lint/format pass. See `docs/T055_IMPLEMENTATION.md`; no live deployment/frontend acceptance claimed.
- [x] **T056 | Rudra | Configure Gemini client.** Keep key server-side and define timeouts. Needs T004. Done when missing key returns a controlled unavailable state.
- [ ] **T057 | Braydin | Implement Gemini endpoints.** In `backend/app/gemini/`, add the briefing, report enrichment, notice radius, and confirmed-instruction calls. Register that router from `backend/app/main.py` without changing Rudra’s other routes. Validate structured output and evidence IDs. Needs T042, T051, and T056. Done when a briefing cites supplied evidence and the radius and instruction functions are importable by Rudra’s report routes.
- [x] **T058 | Braydin | Add deterministic briefing fallback.** Generate a template when Gemini fails or returns invalid output. Needs T057. Done when briefing remains available without Gemini.
- [x] **T058A | Braydin | Generate briefings at 6 PM site-local time.** For every site with an assigned team whose organization has a supervisor, generate and store one next-day briefing (07:00–19:00 local) at 6 PM in the site's time zone, from the NWS point lookup. Serve the latest with `GET /api/sites/{id}/briefing` and, for crew and supervisors with `read:org_briefings`, `GET /api/briefings`. No manual generation route. Needs T057 and T058. Done when a site past 6 PM local gets exactly one briefing for the next day, a site before 6 PM gets none, a site whose organization has no supervisor gets none, and both routes follow the role policy.
- [x] ~~**T059 | Braydin | Implement score explanation endpoint.**~~ Removed from scope 2026-10-17 by Braydin: Gemini does not explain or interpret the hazard score. The score is a deterministic weighted algorithm, and the factor breakdown is its explanation. The route, `Explanation` schema, fixtures, and `request:explanations` permission were deleted.
- [ ] **T060 | Braydin | Implement report enrichment.** Ask Gemini to suggest category and visible evidence. Require human review. Needs T053 and T056. Done when suggestions cannot change score before confirmation.
- [ ] **T061 | Braydin | Add Gemini evaluation cases.** Test grounding, schema, unknown handling, radius validation, instruction review, and unsupported safety claims. Needs T057, T059, T060, and T054A. Done when results and limitations are documented.
- [ ] **T062 | Braydin + Rudra | Verify API permissions.** Test crew, supervisor, no token, and invalid token on protected routes. Needs T028 and protected routes. Done when policy matches `spec.md`.

## Phase 4: Frontend integration

- [ ] **T063 | Cache | Connect site list and detail APIs.** Keep fixture mode. Needs T041 and T042. Done when live API and fixtures render the same views.
- [ ] **T064 | Cache | Connect alert state and acknowledgement.** Preserve countdown across reloads. Needs T048. Done when acknowledgement updates shared state.
- [ ] **T065 | Cache | Connect report creation and review.** Upload the photo, record whether the hazard is present, show the potential notice without instructions, let a notified supervisor edit the suggested instruction, and show the sent instruction to teams inside the radius. Needs T053, T054, and T054A. Done when the full report lifecycle works in the UI.
- [ ] **T066 | Cache | Connect Auth0 exports.** Import Braydin’s provider and role guard. Do not edit auth files. Needs T025 and T026. Done when both roles see the correct screens.
- [ ] **T067 | Cache | Connect Gemini features.** Call briefing and enrichment endpoints. Show loading, fallback, evidence, and review states. Needs T057–T060. Done when success and failure states work.
- [x] **T067A | Cache | Remove score explanations and manual briefing requests from the frontend.** Added 2026-10-17 by Braydin after two scope decisions: Gemini no longer explains the hazard score (the weighted factor breakdown is the explanation), and briefings are generated automatically at 6 PM site-local time, never on request. Remove the "Request score explanation" button and panel, `explanation()` from `api/contracts.ts`, `api/http-client.ts`, and `demo/client.ts`, and the matching `scripts/check-shell.mjs` steps. Replace "Request next-day briefing" with a read-only view of the latest stored briefing: `GET /api/sites/{id}/briefing` (team sites in the caller's organization) and, for crew and supervisors with `read:org_briefings`, `GET /api/briefings`. On 404, show "No briefing yet. Briefings are generated at 6 PM site-local time." Show `generated_by` (Gemini or template) and the forecast window. Keep fixture mode on `briefings.json`. Then delete the leftover `Explanation` and `BriefingRequest` interfaces from `frontend/src/types/api.ts` (marked for removal) and `frontend/src/fixtures/explanations.json`, and update `frontend/INTEGRATION.md` and `docs/INTEGRATION_STATUS.md`. Needs T058A. Done when TypeScript, lint, build, the frontend tests, and the shell check pass, and no frontend code references explanations or a briefing POST.
- [ ] **T068 | Cache | Recheck mobile and accessibility.** Test real API states, phone width, and keyboard flow. Needs T063–T067. Done when no P0 usability issue remains.

## Phase 5: Validate and rehearse

- [ ] **T069 | Rudra | Seed the demo scenario.** Add a labeled Everglades-style site, weather, confirmed wildlife report, lightning replay, and a pre-generated next-day briefing (as the 6 PM schedule would produce it). Needs T040, T048, and T055. Done when one command restores the same demo.
- [ ] **T070 | All | Test clean setup.** Follow repo instructions from a clean checkout. Needs T009–T068. Done when another teammate can start frontend and backend without undocumented steps.
- [x] **T071 | Cache | Verify active-event model reproducibility.** Run training/backtest or document fixture-only status. Needs T021–T023. Done when outputs match evaluation and safety-scope documentation.
- [x] **T071A | Cache | Verify takeover and preserve prior work.** Audit branch/remotes/processes, verify archive/artifact hashes, and secure pending source. Done: original files preserved, obsolete job identity verified before stopping; see `ml/TAKEOVER_REPORT.md`.
- [x] **T071B | Cache | Correct boundary leakage and default selection.** Purge complete episodes crossing fit/selection cutoffs and compare matched populations. Done: v2 full backtest and cache-only weather comparison rerun; KM remains default and all outlooks are production-ineligible.
- [x] **T071C | Cache | Provision and verify the backend adapter.** Pin dependencies/archive revisions, regenerate the model, verify hashes, and test inference from the backend working directory and published T006 schemas. Done: clean environment produced byte-identical artifact; 81 ML and 42 backend/schema/mirror/integration checks passed. Live route integration remains T050.
- [x] **T071D | Cache | Measure bounded runtime.** Profile stages, compare preserved curve scoring, and measure 1/4/8/12 workers. Done: parity verified, one worker retained; results and interference limits recorded in `ml/reports/purged_v2/benchmark.json`.
- [x] **T071E | Cache | Deliver reviewed source and handoff.** Preserve team changes, push `feature/cache-ml`, and open a review PR without merging. Done: draft PR #4 at `https://github.com/BraydinPG/planit-control-swamphacks/pull/4`; Rudra integration checklist is in `ml/INTEGRATION.md`.
- [ ] **T072 | Braydin | Verify role boundaries.** Test UI guards and direct API requests. Needs T062 and T066. Done when prohibited crew requests fail server-side.
- [x] **T073 | Rudra + Braydin | Test alert timing and feed failures.** Cover trigger, reset, expiry, and an unavailable state for each built feed (weather, forecast, flood, lightning, hurricane, earthquake). Confirm a feed outage never clears an alert. Needs T046–T048 and T044. Done when tests pass and UI labels replay/unavailable states. Done: `backend/tests/test_feed_failures.py` runs all six feeds through a real `FeedCache` and `refresh_all`: each outage reads stale then unavailable, never "none"; no outage clears or shortens a lightning alert; 10.0-mile boundary, reset, and exact 30-minute clear. Braydin's adapters are covered by these tests and his own adapter tests; no adapter changes were needed. Fixed: an unavailable lightning feed was labeled "stale" in the score. UI: `frontend/src/components/data/Status.tsx` labels simulated, stale, and unavailable in text.
- [ ] **T074 | All | Test AI and model failures.** Test missing Gemini key, timeout, invalid output, missing evidence, and model fallback. Needs T023 and T061. Done when fallbacks work and AI cannot clear alerts or alter scores.
- [ ] **T075 | All | Rehearse the 3–5 minute demo.** Use the sequence in `spec.md` without manual database edits. Needs T069–T074. Done when the team completes the flow and logs blockers.
- [ ] **T076 | Rudra | Freeze features and fix critical defects.** Fix acceptance failures and demo-breaking bugs only. Needs T075. Done when main runs and no P0 defect remains. Pre-rehearsal sweep (2026-10-17): backend 505 tests, frontend build/lint/39 tests pass on main `f3a65a7`. Fixed: rescoring from stored history (report confirmation) counted expired alerts and older fetches; `score_site` now keeps each feed's latest fetch (`current_readings`). Stays open until T075 runs.

## Phase 6: Documentation and deployment

- [ ] **T077 | Rudra | Complete public README.** Document setup, architecture, data sources, model evaluation and limits, Gemini safeguards, Auth0 setup, Tiger Data, Vultr, the sponsor tracks, and demo. Needs T021, T024, T061, and T070. Done when a new developer can run the app.
- [ ] **T078 | Braydin | Record the Vultr deployment.** Host the FastAPI app and frontend on Vultr. Keep the database on Tiger Data and identity on Auth0. Needs T001. Done when build commands and required env variables are recorded.
- [ ] **T079 | Braydin | Prepare deployment config.** Add health checks, build settings, migrations, allowed origins, and secret names. Needs T078. Done when config validates locally.
- [ ] **T080 | Braydin | Deploy the backend to Vultr.** Configure secrets in Vultr, run Tiger Data migrations, and seed data. Needs T076 and T079. Done when health and sites endpoints succeed.
- [ ] **T081 | Braydin | Configure Auth0 for deployed URLs.** Add exact callbacks, logout URLs, and allowed origins. Needs T080. Done when both demo roles sign in.
- [ ] **T082 | Nick | Deploy the frontend on Vultr.** Set the backend URL and public Auth0 configuration. Needs T080 and T081. Done when the deployed frontend reaches the backend.
- [ ] **T083 | Braydin | Verify deployed security and CORS.** Test role access, allowed origins, and secret exposure. Needs T081 and T082. Done when authorized requests work and unauthorized requests fail.
- [ ] **T084 | All | Run deployed acceptance checks.** Test sites, scores, alerts, reports, Gemini, fallbacks, and Auth0. Needs T083. Done when P0 checks pass on deployment.
- [ ] **T085 | Rudra | Finish Devpost submission.** Add repo/deployed links, track mapping, data and model disclosure, screenshots, and limitations. Needs T077 and T084. Done when claims match the implementation.
- [ ] **T086 | All | Prepare a demo fallback.** Record the full demo or create a stable local replay. Label simulated data. Needs T075. Done when backup demo is ready.

## Dependency order

```text
T001–T008: kickoff, repo, contracts
  ├── T009: API health route
  ├── T010–T013: Tiger Data setup
  ├── T014–T023: model lane
  ├── T024–T029: Auth0 lane
  └── T030–T038: frontend lane
                ↓
T039–T040, T045–T045D: sites and non-NWS feeds (Braydin, backend/app/ingestion/)
T043–T044: NWS feeds and FeedCache (Rudra, backend/app/ingestion/)
T046–T055: alerts, rules, scoring, reports, permissions (Rudra; calls Braydin's Gemini functions)
T049B: feed refresh loop (Rudra; ties feeds, lightning rule, feed notices, and scoring together)
T056–T061: Gemini endpoints (Braydin, backend/app/gemini/)
                ↓
T063–T068: frontend integration
                ↓
T069–T076: validation, rehearsal, feature freeze
                ↓
T077, T085: README and Devpost (Rudra)
T078–T083: Vultr deployment (Braydin; Nick deploys the frontend in T082)
