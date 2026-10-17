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

Aim for 15–60 minutes per task. Split larger tasks before coding. Respect the default path ownership in `AGENTS.md`; explicit project-level authorization may permit focused cross-owner changes. Preserve unrelated work. Rudra coordinates shared schemas, manifests, deployment configuration, and integration. Braydin owns Tiger Data migrations.

## Owners

- Rudra: backend routes, API contracts, alert rules, scoring, Gemini endpoints, integration, deployment, README.
- Cache: `ml/`, model training, features, prediction, evaluation.
- Braydin: `backend/app/security/`, `backend/app/db/**`, `backend/app/ingestion/**`, database migrations, EIA-860M site import, live data feeds, `frontend/src/auth/`, `auth/SETUP.md`.
- Nick: `frontend/src/pages/`, `frontend/src/components/`, `frontend/src/styles/`, `frontend/src/api/`.

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
- `POST /api/sites/{id}/briefings`
- `POST /api/sites/{id}/explanations`

## Phase 0: Kickoff and shared setup

- [ ] **T001 | Rudra | Confirm the stack.** Use React + TypeScript with Vite and Tailwind CSS for the UI, FastAPI for every API route, Tiger Data for the database, Auth0 for identity, and Vultr for hosting and photo storage, as required in `spec.md`. Auth0, Tiger Data, and Vultr are sponsors for tracks. Done when all members agree on that stack and run commands.
- [ ] **T002 | All | Read the project docs.** Read `spec.md` and `AGENTS.md`. Done when each person confirms owned paths and project scope.
- [x] **T003 | Rudra | Create the minimal repo skeleton.** Add frontend, FastAPI backend, model, auth, and test folders. Done when a placeholder Vite frontend and a FastAPI `GET /health` route run locally.
- [x] **T004 | Rudra | Add `.env.example`.** List Tiger Data, Auth0, Gemini, and Vultr Object Storage variable names and descriptions, with no secrets. Done when a new member can identify required configuration.
- [ ] **T005 | Rudra | Add quality commands.** Document existing formatter, linter, and test commands. Done when each command runs locally.
- [x] **T006 | Rudra | Publish API schemas.** Define organization, team, site, observation, alert, score, report, hazard notice, briefing, and explanation types. A site includes its assigned team. A report includes whether the hazard is present. A hazard notice includes the radius and keeps the instruction empty until a supervisor sends it. Done when Nick can build without guessing field names.
- [ ] **T007 | Rudra | Add API fixtures.** Create sample JSON matching T006, including stale, simulated, and unavailable states. Done when fixtures validate against the schemas.
- [ ] **T008 | All | Create separate branches.** Use `feature/rudra-api`, `feature/cache-ml`, `feature/braydin-auth0`, and `feature/nick-ui`. Done when each member confirms their branch.

## Phase 1: Parallel foundation work

Rudra's API-dependent lanes start after T006 and T007. Cache may start the independent ML lane using ML-owned fixtures and schema; backend integration waits for the approved contract. Nick may use fixture data until API routes are ready.

### Rudra: backend foundation

- [ ] **T009 | Rudra | Add API health route.** Implement FastAPI `GET /health` in `backend/app/`. Needs T003. Done when local startup and the health check pass.

### Braydin: Tiger Data setup

- [ ] **T010 | Braydin | Configure the Tiger Data connection.** Read `DATABASE_URL` from the environment and require `sslmode=require` for Tiger Cloud. Needs T004 and T006. Done when the backend starts with documented settings.
- [ ] **T011 | Braydin | Define database models.** Add Organization, Team, Site, Observation, Alert, HazardPrediction, HazardScore, CrewReport, HazardNotice, Acknowledgement, Briefing, and AuditEvent. A crew member belongs to one team. A team is assigned to one location. A supervisor belongs to one organization. Needs T006. Done when models import successfully.
- [ ] **T012 | Braydin | Add database initialization.** Create migrations or a schema setup command on Tiger Data. Enable TimescaleDB and convert `Observation`, `Alert`, and `AuditEvent` into hypertables. Needs T011. Done when a clean database initializes from scratch.
- [ ] **T013 | Braydin | Add a seed command.** Provide one runnable command. Leave demo scenario contents for Rudra. Needs T012. Done when the command runs against a clean database.

### Cache: AI/ML

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

- [ ] **T024 | Braydin | Document Auth0 setup.** Add tenant, callback, logout, audience, role, permission, and environment-variable instructions to `auth/SETUP.md`. Needs T004 and T006. Done when another member can configure the tenant from the guide.
- [ ] **T025 | Braydin | Implement frontend auth provider.** Export `AuthProvider` and `useAuth()` with user, role, loading, login, logout, and token access. Needs T006. Done when an isolated page can sign in and read the role.
- [ ] **T026 | Braydin | Add frontend role guard.** Export `RequireRole` or the agreed equivalent. Needs T025. Done when the wrong role sees an access state.
- [ ] **T027 | Braydin | Implement backend token validation.** Add reusable FastAPI security dependencies. Needs T024. Done when missing, invalid, expired, and valid tokens return expected results.
- [ ] **T028 | Braydin | Add permission helpers.** Support crew and supervisor actions in `AGENTS.md`. Needs T027. Done when tests reject crew access to supervisor-only actions.
- [ ] **T029 | Braydin | Document demo account setup.** Explain how to test both roles without committing credentials. Needs T024 and T025. Done when setup steps are clear.

### Nick: frontend and UI/UX

- [ ] **T030 | Nick | Create responsive app shell.** Add navigation and fixture mode. Style it with Tailwind utility classes. Needs T003 and T007. Done when app renders on phone and desktop sizes.
- [ ] **T031 | Nick | Create score and status components.** Show risk score, factors, freshness, and source. Needs T006 and T007. Done when observed, stale, simulated, and unavailable states are distinct without color alone.
- [ ] **T032 | Nick | Build crew home screen.** Show site, status, alert, immediate action, update time, and a “potential {hazard}” notice with no instructions. After a supervisor sends an instruction, show that text. Needs T030 and T031. Done when the main action appears without scrolling on a phone.
- [ ] **T033 | Nick | Build alert detail.** Show trigger, evidence, distance, acknowledgement, and countdown. Needs T032. Done when fixtures show active, reset, and cleared states.
- [ ] **T034 | Nick | Build hazard report form.** Add photo, category (including broken electrical pole or downed line, on-site fire, wildlife, flooding, and other), coordinates, a required present-or-absent choice, optional note, and confirmation. Needs T030. Done when submission does not require typed text.
- [ ] **T035 | Nick | Build supervisor location list.** Show the full map and every location with its assigned team, alerts, scores, and top factors. Place locations that have a team above locations that do not. Needs T030 and T031. Done when an occupied location appears above an empty one and the team name is visible.
- [ ] **T036 | Nick | Build site detail and report review.** Show observations, timestamps, source, reports, and review status. Needs T031 and T035. Done when a supervisor can review a fixture report.
- [ ] **T037 | Nick | Build briefing and explanation panels.** Show recommendations, evidence, unknowns, and fallback state. Needs T007 and T031. Done when generated and fallback text look distinct.
- [ ] **T038 | Nick | Check accessibility and responsive behavior.** Test touch targets, keyboard flow, focus, labels, and risk information without color. Needs T032–T037. Done when checklist passes or remaining issues become separate tasks.

## Phase 2: Real sites, data, scores, and alerts

- [ ] **T039 | Braydin | Inspect EIA-860M data.** Record source date, fields, and import mapping. Needs T013. Done when coordinate fields are verified.
- [ ] **T040 | Braydin | Import 50+ sites.** Validate IDs, coordinates, and duplicates. Label locations as representative power plants, not verified construction sites. Needs T039 and T012. Done when 50 valid locations are in the database.
- [ ] **T041 | Rudra | Implement `GET /api/sites`.** Return every location with its assigned team, matching T006. Sort locations with a team first, then by risk. Needs T040 and T006. Done when response validates.
- [ ] **T042 | Rudra | Implement `GET /api/sites/{id}`.** Return observations, score factors, reports, and freshness. Needs T041. Done when valid IDs return detail and unknown IDs return 404.
- [ ] **T043 | Braydin | Add the NWS weather and forecast feed (P0).** Use `api.weather.gov` point lookup, hourly forecast, and latest station observation in `backend/app/ingestion/`. Send a `User-Agent`. Normalize results into Observation records through the ingestion interface in `AGENTS.md`. Needs T012. Done when one site receives timestamped observed and forecast readings.
- [ ] **T043A | Braydin | Add the NWS flood alerts feed (P0).** Fetch active Flood Warning, Flash Flood Warning, and Flood Watch alerts for each site point. Normalize them into `flood_alert` Observations. Needs T043. Done when a fixture alert produces an Observation and a failed fetch is marked unavailable, not "no flood."
- [ ] **T044 | Braydin | Add caching and stale state for every feed.** Preserve each feed's last successful readings, track freshness per feed, and mark stale and unavailable states. Needs T043. Done when failed refreshes cannot appear current and one failed feed does not mark the others stale.
- [ ] **T045 | Braydin | Define lightning event input and replay fixture (P0).** Normalize strike location and time. Expose `submit_strike()` from the ingestion interface. Label replayed strikes simulated. Needs T012. Done when tests can submit a strike without a live feed.
- [ ] **T045A | Braydin | Add a live lightning feed (P1, best effort).** Try NOAA GOES GLM lightning data on AWS Open Data. Fall back to the replay fixture and label it simulated. Needs T045 and T044. Done when live strikes arrive as Observations, or the fallback is documented and labeled.
- [ ] **T045B | Braydin | Add the hurricane feed (P1).** Use NHC active storms (`CurrentStorms.json`) and NWS Hurricane and Tropical Storm Warning and Watch alerts. Normalize them into `hurricane` Observations. Needs T044. Done when a fixture storm produces an Observation with source and time, and a failed fetch is marked unavailable.
- [ ] **T045C | Braydin | Add the earthquake feed (P1).** Use the USGS earthquake GeoJSON summary feed. Normalize magnitude, location, and time into `earthquake` Observations. Needs T044. Done when a fixture event produces an Observation and a failed fetch is marked unavailable.
- [ ] **T045D | Braydin | Add the USGS flood gauge feed (P1).** Use USGS Water Services instantaneous readings for gauges near sites. Normalize them into `flood_gauge` Observations. Needs T044. Done when a fixture gauge reading produces an Observation and NWS flood alerts remain the fallback.
- [ ] **T046 | Rudra | Implement the 10-mile trigger.** Create stop-work alert for qualifying strikes. Needs T045. Done when tests cover inside, outside, and boundary distance.
- [ ] **T047 | Rudra | Implement 30-minute resettable timer.** Base clear time on latest qualifying strike. Needs T046. Done when a second strike resets the timer and 30 strike-free minutes clear it.
- [ ] **T048 | Rudra | Implement alert listing and acknowledgement.** Persist alert status, user, and acknowledgement time. Needs T046, T047, and T027. Done when state persists across requests.
- [ ] **T049 | Rudra | Add prototype heat and flood factors.** Use Braydin's weather, forecast, and flood Observations and document configurable thresholds. Needs T043, T043A, and T044. Done when factors include source, time, and prototype label.
- [ ] **T049A | Rudra | Add prototype hurricane and earthquake rules (P1).** A hurricane warning covering the site or an NHC storm within a configurable distance, and a USGS event at or above a configurable magnitude within a configurable distance, each create a potential-hazard notice and a score factor. Use the default radii in `spec.md`. Needs T045B, T045C, and T053. Done when fixture Observations inside and outside the settings produce the expected notices and factors, and every setting is labeled prototype.
- [ ] **T050 | Rudra | Add optional active-event outlook integration.** Import `predict_active_event()` only after the backend event/as-of contract is approved; expose a compact separate field, not a score factor. Needs T022 and the approved event-context contract. Done when unavailable output leaves existing routes and deterministic alerts unchanged.
- [ ] **T051 | Rudra | Calculate final 0–10 score.** Combine current deterministic factors and confirmed reports; exclude conditional persistence unless score semantics are separately approved. Document weights and missing-data handling. Needs T049. Done when response includes factor contributions and tests pass.

## Phase 3: Reports, Gemini, and permissions

- [ ] **T052 | Rudra | Configure photo storage.** Use Vultr Object Storage, with a private local directory for development. Add size and type limits. Needs T012. Done when invalid uploads are rejected.
- [ ] **T053 | Rudra | Implement report creation and potential notices.** Store organization, team, reporter, category, whether the hazard is present, coordinates, photo, optional note, time, and pending status. A source detection or a present report asks Gemini for a radius and sends “potential {hazard}” with no instructions to teams and supervisors inside it. If Gemini is unresponsive or the radius is invalid, use that category’s labeled default from `spec.md`. Needs T052, T027, and T056. Done when the report persists and recipients inside the radius are notified.
- [ ] **T054 | Rudra | Implement hazard confirmation.** Any supervisor who received the potential notice can confirm it. The reporting organization’s supervisor still reviews a report that no hazard is present. Record reviewer and time. Needs T053 and T028. Done when crew is denied, a supervisor outside the notice is denied, and an absent report stays with its own organization.
- [ ] **T054A | Rudra | Send the supervisor’s instruction.** After confirmation, ask Gemini for one concise instruction. Let the confirming supervisor edit it, then send that text to every team inside the stored radius. Needs T054 and T056. Done when the potential notice contains no instruction and teams receive the supervisor’s final text.
- [ ] **T055 | Rudra | Add confirmed reports to scores.** Count only confirmed reports that the hazard is present. Exclude pending, rejected, and confirmed-absent reports. Needs T051 and T054. Done when only those confirmed reports affect the score.
- [ ] **T056 | Rudra | Configure Gemini client.** Keep key server-side and define timeouts. Needs T004. Done when missing key returns a controlled unavailable state.
- [ ] **T057 | Rudra | Implement briefing endpoint.** Use forecast, score factors, alerts, confirmed reports, timestamps, and unknowns. Validate structured output and evidence IDs. Needs T042, T051, and T056. Done when material claims cite supplied evidence.
- [ ] **T058 | Rudra | Add deterministic briefing fallback.** Generate a template when Gemini fails or returns invalid output. Needs T057. Done when briefing remains available without Gemini.
- [ ] **T059 | Rudra | Implement score explanation endpoint.** Explain the existing score without changing score or alert state. Needs T051 and T056. Done when evidence maps to supplied factors.
- [ ] **T060 | Rudra | Implement report enrichment.** Ask Gemini to suggest category and visible evidence. Require human review. Needs T053 and T056. Done when suggestions cannot change score before confirmation.
- [ ] **T061 | Rudra | Add Gemini evaluation cases.** Test grounding, schema, unknown handling, radius validation, instruction review, and unsupported safety claims. Needs T057, T059, T060, and T054A. Done when results and limitations are documented.
- [ ] **T062 | Braydin + Rudra | Verify API permissions.** Test crew, supervisor, no token, and invalid token on protected routes. Needs T028 and protected routes. Done when policy matches `spec.md`.

## Phase 4: Frontend integration

- [ ] **T063 | Nick | Connect site list and detail APIs.** Keep fixture mode. Needs T041 and T042. Done when live API and fixtures render the same views.
- [ ] **T064 | Nick | Connect alert state and acknowledgement.** Preserve countdown across reloads. Needs T048. Done when acknowledgement updates shared state.
- [ ] **T065 | Nick | Connect report creation and review.** Upload the photo, record whether the hazard is present, show the potential notice without instructions, let a notified supervisor edit the suggested instruction, and show the sent instruction to teams inside the radius. Needs T053, T054, and T054A. Done when the full report lifecycle works in the UI.
- [ ] **T066 | Nick | Connect Auth0 exports.** Import Braydin’s provider and role guard. Do not edit auth files. Needs T025 and T026. Done when both roles see the correct screens.
- [ ] **T067 | Nick | Connect Gemini features.** Call briefing, explanation, and enrichment endpoints. Show loading, fallback, evidence, and review states. Needs T057–T060. Done when success and failure states work.
- [ ] **T068 | Nick | Recheck mobile and accessibility.** Test real API states, phone width, and keyboard flow. Needs T063–T067. Done when no P0 usability issue remains.

## Phase 5: Validate and rehearse

- [ ] **T069 | Rudra | Seed the demo scenario.** Add a labeled Everglades-style site, weather, confirmed wildlife report, and lightning replay. Needs T040, T048, and T055. Done when one command restores the same demo.
- [ ] **T070 | All | Test clean setup.** Follow repo instructions from a clean checkout. Needs T009–T068. Done when another teammate can start frontend and backend without undocumented steps.
- [x] **T071 | Cache | Verify active-event model reproducibility.** Run training/backtest or document fixture-only status. Needs T021–T023. Done when outputs match evaluation and safety-scope documentation.
- [x] **T071A | Cache | Verify takeover and preserve prior work.** Audit branch/remotes/processes, verify archive/artifact hashes, and secure pending source. Done: original files preserved, obsolete job identity verified before stopping; see `ml/TAKEOVER_REPORT.md`.
- [x] **T071B | Cache | Correct boundary leakage and default selection.** Purge complete episodes crossing fit/selection cutoffs and compare matched populations. Done: v2 full backtest and cache-only weather comparison rerun; KM remains default and all outlooks are production-ineligible.
- [x] **T071C | Cache | Provision and verify the backend adapter.** Pin dependencies/archive revisions, regenerate the model, verify hashes, and test inference from the backend working directory. Done: clean environment produced byte-identical artifact; 81 ML and one health test passed. Live route integration remains T050.
- [x] **T071D | Cache | Measure bounded runtime.** Profile stages, compare preserved curve scoring, and measure 1/4/8/12 workers. Done: parity verified, one worker retained; results and interference limits recorded in `ml/reports/purged_v2/benchmark.json`.
- [ ] **T072 | Braydin | Verify role boundaries.** Test UI guards and direct API requests. Needs T062 and T066. Done when prohibited crew requests fail server-side.
- [ ] **T073 | Rudra + Braydin | Test alert timing and feed failures.** Cover trigger, reset, expiry, and an unavailable state for each built feed (weather, forecast, flood, lightning, hurricane, earthquake). Confirm a feed outage never clears an alert. Needs T046–T048 and T044. Done when tests pass and UI labels replay/unavailable states.
- [ ] **T074 | All | Test AI and model failures.** Test missing Gemini key, timeout, invalid output, missing evidence, and model fallback. Needs T023 and T061. Done when fallbacks work and AI cannot clear alerts or alter scores.
- [ ] **T075 | All | Rehearse the 3–5 minute demo.** Use the sequence in `spec.md` without manual database edits. Needs T069–T074. Done when the team completes the flow and logs blockers.
- [ ] **T076 | Rudra | Freeze features and fix critical defects.** Fix acceptance failures and demo-breaking bugs only. Needs T075. Done when main runs and no P0 defect remains.

## Phase 6: Documentation and deployment

- [ ] **T077 | Rudra | Complete public README.** Document setup, architecture, data sources, model evaluation and limits, Gemini safeguards, Auth0 setup, Tiger Data, Vultr, the sponsor tracks, and demo. Needs T021, T024, T061, and T070. Done when a new developer can run the app.
- [ ] **T078 | Rudra | Record the Vultr deployment.** Host the FastAPI app and frontend on Vultr. Keep the database on Tiger Data and identity on Auth0. Needs T001. Done when build commands and required env variables are recorded.
- [ ] **T079 | Rudra | Prepare deployment config.** Add health checks, build settings, migrations, allowed origins, and secret names. Needs T078. Done when config validates locally.
- [ ] **T080 | Rudra | Deploy the backend to Vultr.** Configure secrets in Vultr, run Tiger Data migrations, and seed data. Needs T076 and T079. Done when health and sites endpoints succeed.
- [ ] **T081 | Braydin | Configure Auth0 for deployed URLs.** Add exact callbacks, logout URLs, and allowed origins. Needs T080. Done when both demo roles sign in.
- [ ] **T082 | Nick | Deploy the frontend on Vultr.** Set the backend URL and public Auth0 configuration. Needs T080 and T081. Done when the deployed frontend reaches the backend.
- [ ] **T083 | Rudra | Verify deployed security and CORS.** Test role access, allowed origins, and secret exposure. Needs T081 and T082. Done when authorized requests work and unauthorized requests fail.
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
T039–T045D: sites and live feeds (Braydin, backend/app/ingestion/)
T046–T062: alerts, rules, scoring, reports, Gemini, permissions (Rudra; reads Braydin's Observations)
                ↓
T063–T068: frontend integration
                ↓
T069–T076: validation, rehearsal, feature freeze
                ↓
T077–T086: documentation, deployment, submission
