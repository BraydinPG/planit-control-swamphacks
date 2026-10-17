# Frontend integration status

Backend availability update (2026-10-17, T054): this checkout now includes T053 report
creation, T054 confirmation/absent-report review and T054A supervisor instruction send.
See `T054_IMPLEMENTATION.md` and `T054A_IMPLEMENTATION.md` for routes, permissions,
receipts, Gemini draft/manual fallback and verification. T055 also refreshes the reporting
site's score atomically after present-report confirmation; see `T055_IMPLEMENTATION.md`.
Frontend report capabilities
and real end-to-end acceptance remain pending. The
frontend verification record below predates these backend additions.

Verified 2026-10-17. Cache now owns remaining frontend implementation; Nick retains prior attribution. PR #16 and #17 merged during this run (`806676e` and `7021ce2`). Delivery moved to new branch `feature/cache-frontend-workflows`, targeting main `723a5b8`, which includes Rudra's T050 (`9d73a77`) and newly merged T048 (`944471f`, PR #18). Reviewed main was incorporated without conflicts in `dc35458`; no Cache-authored backend/schema changes. No merge of this delivery is authorized.

Review: [PR #19](https://github.com/BraydinPG/planit-control-swamphacks/pull/19), open against main, implementation head `8834867`. This handoff is reviewable and pushed; no deployed production integration is claimed.

## Task acceptance

Task IDs and original done criteria are preserved in `tasks.md`. Ownership of the authorized T031-T038/T063-T068 chain changed to Cache. Prerequisites T003/T006/T007/T030 were checked before implementation; each dependent foundation task below passed in order. T031's first checkpoint is `140d118`; `3fbd98f` checks T032-T038 with the code and evidence.

| Task | Exact done check | Verified evidence | Completion |
| --- | --- | --- | --- |
| T031 | Observed, stale, simulated, unavailable distinct without color alone | All six canonical source-state labels; null/legacy score tests | Checked |
| T032 | Main action appears without scrolling on a phone | Inspect/ack link above bottom nav at 320x740 and 390x844; site/status/update/notice/instruction browser flow | Checked |
| T033 | Fixtures show active, reset, cleared | Ack/reload, additional-strike window reset, explicit server-cleared payload; expiry remains active | Checked |
| T034 | Submission does not require typed text | Browser submits a photo/present/category report with coordinates and empty note; validation tests | Checked |
| T035 | Occupied location above empty and team name visible | 55-location ranking (50 exact EIA IDs + 5 simulated); team-first DOM assertion, map popup/list navigation, filters, factor text | Checked |
| T036 | Supervisor can review fixture report | Pending -> confirmed review, relevant notice confirmation, edited instruction delivery back to crew; raw score/alert invariance | Checked |
| T037 | Generated and fallback text look distinct | Prerecorded Gemini vs deterministic fallback named headings; evidence, window, unknowns; briefing and explanation browser actions | Checked |
| T038 | Checklist passes or remaining issues become separate tasks | All 10 destinations at 3 sizes, no overflow, named/labeled controls, >=44px primary/zoom controls, keyboard skip/Tab visible focus, text states | Checked for foundation/demo scope; live recheck remains T068 |
| T063 | Live API and fixtures render same views | Shared views/HTTP mocked; T041/T042 checked, but no authenticated real site data retrieved | **Unchecked**: real Auth0/Tiger Data configuration |
| T064 | Acknowledgement updates shared state | T048 is now checked/merged; enabled HTTP all-state listing/ack, shared refetch, server clock estimate and mocked token POST pass; no real authenticated request | **Unchecked**: Auth0/Tiger Data acceptance |
| T065 | Full report lifecycle works in UI | Complete demo lifecycle; no real photo/report/notice writes | **Unchecked**: T053/T054/T054A |
| T066 | Both roles see correct screens | Existing provider/guard imports, mocked crew/supervisor/transitions/denials pass | **Unchecked**: T025/T026 acceptance and real tenant accounts/tokens |
| T067 | Success/failure states work | Fixture Gemini/fallback/evidence; prepared HTTP calls disabled | **Unchecked**: T057-T060 routes/credentials |
| T068 | No P0 usability issue after real API recheck | Demo foundation checklist passes | **Unchecked**: T063-T067 real integration |

No Rudra/Braydin task was checked off. No T070 clean-application setup, T072 deployed permissions or whole-app demo acceptance is claimed.

## Actual live versus simulated behavior

| Capability | Verified real behavior | Demonstration / limitation |
| --- | --- | --- |
| FastAPI health | `/health` 200, `{"status":"ok"}` | Server now runs the current checkout after incorporating main `723a5b8` |
| Site auth boundary | Direct `/api/sites` and Vite-proxied `/api/sites` return 401 `Sign in required` | No authenticated successful real site query; 55 demo sites render through same views |
| Auth0 | Existing modules/token validation in source and backend tests | No local tenant values or real login; mocked-provider tests do not prove real roles |
| Site list/detail | Protected routes exist on main | No configured Tiger Data; live failures stay visible, never fixtures |
| Alert/list/ack | T048 routes and persistence tests inherited unchanged from main; unauthenticated read returns 401 | Enabled frontend bearer-token all-state list/ack, mocked provider/HTTP workflow passes; real authenticated persistence still unverified |
| Reports/photo/review/notices | Missing persistence/routes | Simulated reports/review/instructions persist locally; photos memory-only |
| T050 compact ML | Main schema/detail publication verified | Optional field displayed if supplied; real activated response not retrieved |
| Comprehensive 2.1 | No approved authenticated endpoint | Two validated exact-site public replay exports, unchanged ML/contract; local hazard probabilities null |
| Gemini | Server interface/contracts exist, routes not implemented | Prerecorded canonical Gemini and deterministic fallback; no browser API key/request |
| Map | Geographic Leaflet points/pan/zoom/list work offline | Optional online OSM tiles need network; reference coordinates do not establish local conditions |

The existing model output is a conditional recorded-event research advisory, never event onset or safety. No ML behavior was modified or predictive evaluation rerun. Existing model/gating limitations remain in `ml/HAZARD_INTEGRATION.md`, `ml/WORKER_PREVIEW.md` and `ml/EVALUATION.md`. No score/alert mutation or clearance can follow from it.

## Reproducible checks and owner actions

Run commands in [frontend/INTEGRATION.md](../frontend/INTEGRATION.md). `docs/frontend-acceptance.json` records the browser run, 23 focused tests, lint/build and merged-checkout backend suite (297 passed, one pre-existing Starlette/httpx deprecation). Earlier pre-merge branch and isolated main-export checks passed 266 and 282 respectively. Reviewed main is now incorporated; its code remains unchanged by Cache. Existing local Python needed its declared PyJWT dependency installed. No new backend dependency/manifest was changed. ML behavior is untouched, so no expensive model refit/backtest was run.

T038 checklist passed: touch targets, keyboard flow/visible focus, labels/announcements, readable non-color states, 320/390/1440 layouts and all demo destinations. This is focused prototype acceptance, not full screen-reader/WCAG certification. Live-state checks are already tracked by T068; no duplicate tasks were added.

Clean frontend reproduction: committed export `4a9e44f` contains frontend files only, without local `.env`, `node_modules`, ML artifacts or Python. `npm ci` and production build pass; the full demo browser lifecycle also passes against its static preview using `--production`, with no backend requests/exceptions and no bundled mock-auth harness. This verifies the frontend demo's provisioning, not the whole application's T070 or a production deployment.

**Rudra:** retain `/api/sites` and detail authorization; review the enabled T048 client, and publish/test T053 report creation and multipart photo, T054 review, T054A recipient/confirming-supervisor/instruction routes. Use unchanged canonical fixtures as requests/responses. Assert crew cannot read unassigned sites, review reports or send instructions; only the confirming notified supervisor may send. Provide server persistence/reload tests and deterministic alert isolation. The frontend now imports the canonical T050 type inherited from main. Enable report/hazard/AI capabilities separately only when their routes pass owner tests, then run T063-T065 real acceptance. Alert acknowledgement is already enabled for T048; it remains an authenticated operation, not a fixture fallback. Comprehensive 2.1 still needs separate approved route/schema work; do not silently invent it.

**Braydin:** provide local/public Auth0 SPA settings, configured audience/claims and crew/supervisor accounts, matching backend validation and assigned-site/organization seed data; no secrets in Git. Configure Tiger Data and durable Vultr photo storage with the owners. Complete T025/T026 verification and T057-T060 Gemini endpoints/fallbacks, radius/suggestion confirmation semantics. Instructions remain human-approved. Re-run mocked and actual login/logout/expired-token/role transition tests; do not enable a bypass to close T066.

**Cache:** the next integration to unblock is T063 after those credentials and seed prerequisites are available; the shared view/client is ready. Then verify the real lifecycle and T068 without checking tasks from fixtures. Review/publish with Rudra; no merge/deployment authorization is implied. **Nick:** prior work remains preserved; no parallel remaining implementation is assigned. **Claude:** styling boundaries and regression commands are in `FRONTEND_REDESIGN_HANDOFF.md`.
