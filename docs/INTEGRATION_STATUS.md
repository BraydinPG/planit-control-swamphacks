# Frontend integration status

Verified 2026-10-17. Cache now owns remaining frontend implementation; Nick retains prior attribution. Branch `feature/cache-functional-frontend` stacks on PR #16 head `84e3936`, targeting `feature/cache-t030-app-shell`. PR #16 was open at preflight; no merge or approval is claimed. Main `2e79cb6` separately contains T050 (`9d73a77`). Do not duplicate the parent diff against main; Rudra retargets after the parent merges.

## Task acceptance

Task IDs and original done criteria are preserved in `tasks.md`. Ownership of the authorized T031-T038/T063-T068 chain changed to Cache. Prerequisites T003/T006/T007/T030 were checked before implementation; each dependent foundation task below passed in order. T031's first checkpoint is `140d118`; the following implementation commit checks T032-T038 with the code and evidence.

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
| T064 | Acknowledgement updates shared state | Demo persistence and prepared client pass; live T048/ack route absent | **Unchecked** |
| T065 | Full report lifecycle works in UI | Complete demo lifecycle; no real photo/report/notice writes | **Unchecked**: T053/T054/T054A |
| T066 | Both roles see correct screens | Existing provider/guard imports, mocked crew/supervisor/transitions/denials pass | **Unchecked**: T025/T026 acceptance and real tenant accounts/tokens |
| T067 | Success/failure states work | Fixture Gemini/fallback/evidence; prepared HTTP calls disabled | **Unchecked**: T057-T060 routes/credentials |
| T068 | No P0 usability issue after real API recheck | Demo foundation checklist passes | **Unchecked**: T063-T067 real integration |

No Rudra/Braydin task was checked off. No T070 clean-application setup, T072 deployed permissions or whole-app demo acceptance is claimed.

## Actual live versus simulated behavior

| Capability | Verified real behavior | Demonstration / limitation |
| --- | --- | --- |
| FastAPI health | `/health` 200, `{"status":"ok"}` | Server is current-main source export, not this older stacked backend |
| Site auth boundary | Direct `/api/sites` and Vite-proxied `/api/sites` return 401 `Sign in required` | No authenticated successful real site query; 55 demo sites render through same views |
| Auth0 | Existing modules/token validation in source and backend tests | No local tenant values or real login; mocked-provider tests do not prove real roles |
| Site list/detail | Protected routes exist on main | No configured Tiger Data; live failures stay visible, never fixtures |
| Alert/list/ack | Missing route implementation | Browser-only simulated ack/reset/explicit cleared payload; no independent clearance rule |
| Reports/photo/review/notices | Missing persistence/routes | Simulated reports/review/instructions persist locally; photos memory-only |
| T050 compact ML | Main schema/detail publication verified | Optional field displayed if supplied; real activated response not retrieved |
| Comprehensive 2.1 | No approved authenticated endpoint | Two validated exact-site public replay exports, unchanged ML/contract; local hazard probabilities null |
| Gemini | Server interface/contracts exist, routes not implemented | Prerecorded canonical Gemini and deterministic fallback; no browser API key/request |
| Map | Geographic Leaflet points/pan/zoom/list work offline | Optional online OSM tiles need network; reference coordinates do not establish local conditions |

The existing model output is a conditional recorded-event research advisory, never event onset or safety. No ML behavior was modified or predictive evaluation rerun. Existing model/gating limitations remain in `ml/HAZARD_INTEGRATION.md`, `ml/WORKER_PREVIEW.md` and `ml/EVALUATION.md`. No score/alert mutation or clearance can follow from it.

## Reproducible checks and owner actions

Run commands in [frontend/INTEGRATION.md](../frontend/INTEGRATION.md). `docs/frontend-acceptance.json` records the browser run, 21 focused tests, lint/build and current-main backend suite (282 passed, one pre-existing Starlette/httpx deprecation). Backend tests ran from an isolated Git source export at `2e79cb6` using existing requirements; they do not merge that main into this stacked branch. Existing local Python needed its declared PyJWT dependency installed. No new backend dependency/manifest was changed. ML behavior is untouched, so no expensive model refit/backtest was run.

T038 checklist passed: touch targets, keyboard flow/visible focus, labels/announcements, readable non-color states, 320/390/1440 layouts and all demo destinations. This is focused prototype acceptance, not full screen-reader/WCAG certification. Live-state checks are already tracked by T068; no duplicate tasks were added.

**Rudra:** retain `/api/sites` and detail authorization; publish/test T048 alert state/ack, T053 report creation and multipart photo, T054 review, T054A recipient/confirming-supervisor/instruction routes. Use unchanged canonical fixtures as requests/responses. Assert crew cannot read unassigned sites, review reports or send instructions; only the confirming notified supervisor may send. Provide server persistence/reload tests and deterministic alert isolation. Review the optional T050 frontend type against main. Only then enable the appropriate live capability (currently `HttpClient.writesAvailable=false`) and run T063-T065 real acceptance. Comprehensive 2.1 still needs separate approved route/schema work; do not silently invent it.

**Braydin:** provide local/public Auth0 SPA settings, configured audience/claims and crew/supervisor accounts, matching backend validation and assigned-site/organization seed data; no secrets in Git. Configure Tiger Data and durable Vultr photo storage with the owners. Complete T025/T026 verification and T057-T060 Gemini endpoints/fallbacks, radius/suggestion confirmation semantics. Instructions remain human-approved. Re-run mocked and actual login/logout/expired-token/role transition tests; do not enable a bypass to close T066.

**Cache:** the next integration to unblock is T063 after those credentials and seed prerequisites are available; the shared view/client is ready. Then verify the real lifecycle and T068 without checking tasks from fixtures. Review/publish with Rudra; no merge/deployment authorization is implied. **Nick:** prior work remains preserved; no parallel remaining implementation is assigned. **Claude:** styling boundaries and regression commands are in `FRONTEND_REDESIGN_HANDOFF.md`.
