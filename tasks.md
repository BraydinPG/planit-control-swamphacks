# PlanIT Control Task Backlog

Read `spec.md` and `AGENTS.md` before starting. Complete one task per LLM run. Do not ask an LLM to build the whole project at once.

## Instructions for the coding LLM

For each task:

1. Choose one unchecked task with completed prerequisites.
2. Inspect the relevant files and preserve existing work.
3. Implement only that task. Do not start the next task.
4. Run its done check and relevant tests.
5. Check the box only after the done check passes.
6. Report changed files, checks run, and blockers. Leave blocked tasks unchecked.

Aim for 15–60 minutes per task. Split larger tasks before coding. Follow path ownership in `AGENTS.md`. Do not edit another member’s files. Rudra owns shared schemas, migrations, manifests, deployment configuration, and integration.

## Owners

- Rudra: backend, site data, API contracts, alerts, Gemini endpoints, integration, deployment, README.
- Cache: `ml/`, model training, features, prediction, evaluation.
- Braydin: `backend/app/security/`, `frontend/src/auth/`, `auth/SETUP.md`.
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
- `POST /api/sites/{id}/briefings`
- `POST /api/sites/{id}/explanations`

## Phase 0: Kickoff and shared setup

- [ ] **T001 | Rudra | Confirm the stack.** Use React + TypeScript with Vite and Tailwind CSS for the UI, and FastAPI for every API route, as required in `spec.md`. Done when all members agree on that stack and run commands.
- [ ] **T002 | All | Read the project docs.** Read `spec.md` and `AGENTS.md`. Done when each person confirms owned paths and project scope.
- [x] **T003 | Rudra | Create the minimal repo skeleton.** Add frontend, FastAPI backend, model, auth, and test folders. Done when a placeholder Vite frontend and a FastAPI `GET /health` route run locally.
- [ ] **T004 | Rudra | Add `.env.example`.** List required variable names and descriptions, with no secrets. Done when a new member can identify required configuration.
- [ ] **T005 | Rudra | Add quality commands.** Document existing formatter, linter, and test commands. Done when each command runs locally.
- [ ] **T006 | Rudra | Publish API schemas.** Define site, observation, alert, score, report, briefing, and explanation types. Done when Nick can build without guessing field names.
- [ ] **T007 | Rudra | Add API fixtures.** Create sample JSON matching T006, including stale, simulated, and unavailable states. Done when fixtures validate against the schemas.
- [ ] **T008 | All | Create separate branches.** Use `feature/rudra-api`, `feature/cache-ml`, `feature/braydin-auth0`, and `feature/nick-ui`. Done when each member confirms their branch.

## Phase 1: Parallel foundation work

Start these lanes after T006 and T007. Use mock data or stubs when a dependency is unfinished.

### Rudra: backend foundation

- [ ] **T009 | Rudra | Add API health route.** Implement FastAPI `GET /health` in `backend/app/`. Needs T003. Done when local startup and the health check pass.
- [ ] **T010 | Rudra | Configure database connection.** Read settings from environment variables. Needs T004. Done when the backend starts with documented local settings.
- [ ] **T011 | Rudra | Define database models.** Add Site, Observation, Alert, HazardPrediction, HazardScore, CrewReport, Acknowledgement, Briefing, and AuditEvent. Needs T006. Done when models import successfully.
- [ ] **T012 | Rudra | Add database initialization.** Create migrations or a schema setup command. Needs T011. Done when a clean database initializes from scratch.
- [ ] **T013 | Rudra | Add a small seed command.** Seed development sites and observations. Needs T012. Done when one command creates repeatable fixtures.

### Cache: AI/ML

- [ ] **T014 | Cache | Define model input and output types.** Match the shared `predict_site()` contract. Needs T006. Done when tests validate required fields and ranges.
- [ ] **T015 | Cache | Validate features and missing values.** Add type checks and data-quality flags. Needs T014. Done when missing data never silently becomes zero risk.
- [ ] **T016 | Cache | Create a small training fixture.** Label synthetic data clearly. Needs T014. Done when training code runs without backend data.
- [ ] **T017 | Cache | Add a baseline predictor.** Create a simple comparison model. Needs T016. Done when baseline and trained model use the same fixture.
- [ ] **T018 | Cache | Add historical data loader.** Load weather or hazard-event data from a local file or documented script. Needs T016. Done when expected columns are validated and bad rows are reported.
- [ ] **T019 | Cache | Join data to site-time windows.** Document geographic radius, time window, labels, and negative sampling. Needs T018. Done when a repeatable training table is produced.
- [ ] **T020 | Cache | Train the first model.** Predict weather-related hazard likelihood for the next 24 hours. Needs T019. Done when a local model artifact is produced or a specific data blocker is documented.
- [ ] **T021 | Cache | Evaluate the model.** Use a chronological holdout and baseline comparison. Report precision, recall, PR-AUC where supported, and Brier score if feasible. Needs T020. Done when `ml/EVALUATION.md` documents data, metrics, and limitations.
- [ ] **T022 | Cache | Implement `predict_site()`.** Return probabilities, score component, factors, confidence, version, and data quality. Needs T014 and T020. Done when tests cover valid input.
- [ ] **T023 | Cache | Add model fallback.** Handle missing artifact or required features. Needs T022. Done when fallback is labeled and does not imply low risk.

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
- [ ] **T032 | Nick | Build crew home screen.** Show site, status, alert, immediate action, and update time. Needs T030 and T031. Done when the main action appears without scrolling on a phone.
- [ ] **T033 | Nick | Build alert detail.** Show trigger, evidence, distance, acknowledgement, and countdown. Needs T032. Done when fixtures show active, reset, and cleared states.
- [ ] **T034 | Nick | Build hazard report form.** Add photo, category, pin, optional note, and confirmation. Needs T030. Done when submission does not require typed text.
- [ ] **T035 | Nick | Build supervisor ranking.** Show ranked sites, map, alerts, scores, and top factors. Needs T030 and T031. Done when the top three sites are visible at a glance.
- [ ] **T036 | Nick | Build site detail and report review.** Show observations, timestamps, source, reports, and review status. Needs T031 and T035. Done when a supervisor can review a fixture report.
- [ ] **T037 | Nick | Build briefing and explanation panels.** Show recommendations, evidence, unknowns, and fallback state. Needs T007 and T031. Done when generated and fallback text look distinct.
- [ ] **T038 | Nick | Check accessibility and responsive behavior.** Test touch targets, keyboard flow, focus, labels, and risk information without color. Needs T032–T037. Done when checklist passes or remaining issues become separate tasks.

## Phase 2: Real sites, data, scores, and alerts

- [ ] **T039 | Rudra | Inspect EIA-860M data.** Record source date, fields, and import mapping. Needs T013. Done when coordinate fields are verified.
- [ ] **T040 | Rudra | Import 50+ sites.** Validate IDs, coordinates, and duplicates. Label locations as representative power plants, not verified construction sites. Needs T039 and T012. Done when 50 valid locations are in the database.
- [ ] **T041 | Rudra | Implement `GET /api/sites`.** Return site summaries matching T006. Needs T040 and T006. Done when response validates.
- [ ] **T042 | Rudra | Implement `GET /api/sites/{id}`.** Return observations, score factors, reports, and freshness. Needs T041. Done when valid IDs return detail and unknown IDs return 404.
- [ ] **T043 | Rudra | Add one weather/forecast feed.** Normalize results into Observation records. Needs T012. Done when one site receives timestamped readings.
- [ ] **T044 | Rudra | Add caching and stale state.** Preserve last successful readings and mark old data stale. Needs T043. Done when failed refreshes cannot appear current.
- [ ] **T045 | Rudra | Define lightning event input and replay fixture.** Normalize strike location and time. Needs T012. Done when tests can submit a strike without a live feed.
- [ ] **T046 | Rudra | Implement the 10-mile trigger.** Create stop-work alert for qualifying strikes. Needs T045. Done when tests cover inside, outside, and boundary distance.
- [ ] **T047 | Rudra | Implement 30-minute resettable timer.** Base clear time on latest qualifying strike. Needs T046. Done when a second strike resets the timer and 30 strike-free minutes clear it.
- [ ] **T048 | Rudra | Implement alert listing and acknowledgement.** Persist alert status, user, and acknowledgement time. Needs T046, T047, and T027. Done when state persists across requests.
- [ ] **T049 | Rudra | Add prototype heat and flood factors.** Use available data and document configurable thresholds. Needs T043 and T044. Done when factors include source, time, and prototype label.
- [ ] **T050 | Rudra | Connect Cache’s model.** Import `predict_site()` behind a backend adapter. Needs T022. Done when site data includes model version, confidence, and data quality.
- [ ] **T051 | Rudra | Calculate final 0–10 score.** Combine model output, current factors, and confirmed reports. Document weights and missing-data handling. Needs T049 and T050. Done when response includes factor contributions and tests pass.

## Phase 3: Reports, Gemini, and permissions

- [ ] **T052 | Rudra | Configure photo storage.** Choose local development storage or the configured object store. Add size and type limits. Needs T012. Done when invalid uploads are rejected.
- [ ] **T053 | Rudra | Implement report creation.** Store reporter, category, coordinates, photo, optional note, time, and pending status. Needs T052 and T027. Done when report persists and appears in site detail.
- [ ] **T054 | Rudra | Implement supervisor report review.** Confirm or reject reports and record reviewer/time. Needs T053 and T028. Done when crew is denied and review persists.
- [ ] **T055 | Rudra | Add confirmed reports to scores.** Exclude pending and rejected reports. Needs T051 and T054. Done when only confirmed reports affect the score.
- [ ] **T056 | Rudra | Configure Gemini client.** Keep key server-side and define timeouts. Needs T004. Done when missing key returns a controlled unavailable state.
- [ ] **T057 | Rudra | Implement briefing endpoint.** Use forecast, score factors, alerts, confirmed reports, timestamps, and unknowns. Validate structured output and evidence IDs. Needs T042, T051, and T056. Done when material claims cite supplied evidence.
- [ ] **T058 | Rudra | Add deterministic briefing fallback.** Generate a template when Gemini fails or returns invalid output. Needs T057. Done when briefing remains available without Gemini.
- [ ] **T059 | Rudra | Implement score explanation endpoint.** Explain the existing score without changing score or alert state. Needs T051 and T056. Done when evidence maps to supplied factors.
- [ ] **T060 | Rudra | Implement report enrichment.** Ask Gemini to suggest category and visible evidence. Require human review. Needs T053 and T056. Done when suggestions cannot change score before confirmation.
- [ ] **T061 | Rudra | Add Gemini evaluation cases.** Test grounding, schema, unknown handling, and unsupported safety claims. Needs T057, T059, and T060. Done when results and limitations are documented.
- [ ] **T062 | Braydin + Rudra | Verify API permissions.** Test crew, supervisor, no token, and invalid token on protected routes. Needs T028 and protected routes. Done when policy matches `spec.md`.

## Phase 4: Frontend integration

- [ ] **T063 | Nick | Connect site list and detail APIs.** Keep fixture mode. Needs T041 and T042. Done when live API and fixtures render the same views.
- [ ] **T064 | Nick | Connect alert state and acknowledgement.** Preserve countdown across reloads. Needs T048. Done when acknowledgement updates shared state.
- [ ] **T065 | Nick | Connect report creation and review.** Upload photo and pin, show pending state, then show review result. Needs T053 and T054. Done when full report lifecycle works in UI.
- [ ] **T066 | Nick | Connect Auth0 exports.** Import Braydin’s provider and role guard. Do not edit auth files. Needs T025 and T026. Done when both roles see the correct screens.
- [ ] **T067 | Nick | Connect Gemini features.** Call briefing, explanation, and enrichment endpoints. Show loading, fallback, evidence, and review states. Needs T057–T060. Done when success and failure states work.
- [ ] **T068 | Nick | Recheck mobile and accessibility.** Test real API states, phone width, and keyboard flow. Needs T063–T067. Done when no P0 usability issue remains.

## Phase 5: Validate and rehearse

- [ ] **T069 | Rudra | Seed the demo scenario.** Add a labeled Everglades-style site, weather, confirmed wildlife report, and lightning replay. Needs T040, T048, and T055. Done when one command restores the same demo.
- [ ] **T070 | All | Test clean setup.** Follow repo instructions from a clean checkout. Needs T009–T068. Done when another teammate can start frontend and backend without undocumented steps.
- [ ] **T071 | Cache | Verify model reproducibility.** Run training and evaluation or document fixture fallback. Needs T021–T023. Done when results match the documentation.
- [ ] **T072 | Braydin | Verify role boundaries.** Test UI guards and direct API requests. Needs T062 and T066. Done when prohibited crew requests fail server-side.
- [ ] **T073 | Rudra | Test alert timing and feed failures.** Cover trigger, reset, expiry, and unavailable feed. Needs T046–T048. Done when tests pass and UI labels replay/unavailable states.
- [ ] **T074 | All | Test AI and model failures.** Test missing Gemini key, timeout, invalid output, missing evidence, and model fallback. Needs T023 and T061. Done when fallbacks work and AI cannot clear alerts or alter scores.
- [ ] **T075 | All | Rehearse the 3–5 minute demo.** Use the sequence in `spec.md` without manual database edits. Needs T069–T074. Done when the team completes the flow and logs blockers.
- [ ] **T076 | Rudra | Freeze features and fix critical defects.** Fix acceptance failures and demo-breaking bugs only. Needs T075. Done when main runs and no P0 defect remains.

## Phase 6: Documentation and deployment

- [ ] **T077 | Rudra | Complete public README.** Document setup, architecture, data sources, model evaluation and limits, Gemini safeguards, Auth0 setup, and demo. Needs T021, T024, T061, and T070. Done when a new developer can run the app.
- [ ] **T078 | Rudra | Choose deployment target.** Use existing team hosting or choose compatible frontend, backend, and database hosts. Needs T001. Done when build commands and required env variables are recorded.
- [ ] **T079 | Rudra | Prepare deployment config.** Add health checks, build settings, migrations, allowed origins, and secret names. Needs T078. Done when config validates locally.
- [ ] **T080 | Rudra | Deploy backend to test environment.** Configure secrets in host settings, run migrations, and seed data. Needs T076 and T079. Done when health and sites endpoints succeed.
- [ ] **T081 | Braydin | Configure Auth0 for deployed URLs.** Add exact callbacks, logout URLs, and allowed origins. Needs T080. Done when both demo roles sign in.
- [ ] **T082 | Nick | Deploy frontend.** Set backend URL and public Auth0 configuration. Needs T080 and T081. Done when deployed frontend reaches the backend.
- [ ] **T083 | Rudra | Verify deployed security and CORS.** Test role access, allowed origins, and secret exposure. Needs T081 and T082. Done when authorized requests work and unauthorized requests fail.
- [ ] **T084 | All | Run deployed acceptance checks.** Test sites, scores, alerts, reports, Gemini, fallbacks, and Auth0. Needs T083. Done when P0 checks pass on deployment.
- [ ] **T085 | Rudra | Finish Devpost submission.** Add repo/deployed links, track mapping, data and model disclosure, screenshots, and limitations. Needs T077 and T084. Done when claims match the implementation.
- [ ] **T086 | All | Prepare a demo fallback.** Record the full demo or create a stable local replay. Label simulated data. Needs T075. Done when backup demo is ready.

## Dependency order

```text
T001–T008: kickoff, repo, contracts
  ├── T009–T013: backend foundation
  ├── T014–T023: model lane
  ├── T024–T029: Auth0 lane
  └── T030–T038: frontend lane
                ↓
T039–T062: sites, data, scoring, alerts, reports, Gemini, permissions
                ↓
T063–T068: frontend integration
                ↓
T069–T076: validation, rehearsal, feature freeze
                ↓
T077–T086: documentation, deployment, submission