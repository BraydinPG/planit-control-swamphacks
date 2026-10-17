# Frontend integration status

Verified 2026-10-17. PR #24 merged as `f3a65a7` and T067A PR #27 merged as `1eed70e` by maintainers during this run. T065 continues on `feature/cache-report-lifecycle-integration` from reviewed main `dcd9fc5` (PR #28 scoring-history fix), targeting main with no duplicated parent diff. PR #26 (`9809db4`) and Braydin's T058A/Auth0 updates are inherited unchanged.

Review: [PR #29](https://github.com/BraydinPG/planit-control-swamphacks/pull/29), implementation `60ce280`, open against main. No merge or real acceptance claimed.

## Authorized sequence and task evidence

| Task | Prerequisites and acceptance | State |
| --- | --- | --- |
| T067A | T058A checked. Stored site and organization GETs, 404 empty, 401/403/503 errors, malformed DTO/window rejection, Gemini/template labels, no fixture fallback, keyboard/phone/desktop. 44 Node, 65 focused backend/fixture/mirror checks; lint/TS/build and full browser pass. | Checked; commit `2e4cfb7`, merged PR #27 |
| T065 | T053/T054/T054A now checked. Create/list, absent review, present notice confirmation, returned draft/manual editor and explicit instruction send now wired and validated. Shared reads refresh; competing-owner/error states preserve authority. Demo and mocked HTTP pass; actual complete roles/persistence/delivery remain blocked. | Unchecked pending actual acceptance |
| T063 | Shared fixture/live views exist; actual authorized site reads in application still require private setup/role memberships. | Unchecked |
| T064 | HTTP ack and shared refresh mock-tested; actual persisted ack/reload required. | Unchecked |
| T066 | Braydin verified isolated Auth0 sign-in (T025/T026 checked); Cache must verify actual application roles and scope. | Unchecked |
| T067 | Stored briefing retrieval implemented by T067A. Enrichment/provider acceptance is separate. | Unchecked |
| T068 | Fixture/mock phone/keyboard regressions pass; complete real-service checks still required. | Unchecked |

## Source contracts

- GET /api/sites, GET /api/sites/{id}, GET /api/alerts, POST /api/alerts/{id}/acknowledge.
- POST /api/reports (canonical multipart; photo required for present, optional for absent), GET /api/reports.
- POST /api/reports/{id}/review: absent report, reporting organization's supervisor.
- POST /api/hazards/{id}/confirm: notified supervisor; HazardConfirmResponse contains authoritative notice and optional draft.
- POST /api/hazards/{id}/instruction: confirming supervisor; explicit final text of 1?500 characters; returns HazardNotice. Backend owns radius, recipients and scoring.
- GET /api/sites/{id}/briefing and GET /api/briefings: stored results, backend's 6 PM site-local schedule. No frontend generation action/timer. Site 404 is the exact no-briefing message; organization list requires read:org_briefings. Briefing source remains Gemini or deterministic template.

T067A removes the obsolete generated-score panel/client/types/fixture with explicit user and task authorization. Canonical backend counterparts were already removed. Deterministic factors/source/time/prototype labels remain visible. No backend, auth, database, ML, manifest/lock or deployment change authored.

## Real versus simulated evidence

The full demo remains isolated in planit:frontend-demo:v1; photos memory-only, archived fixtures labeled, EIA plants are reference points. Mocked HTTP verifies browser/request behavior, not actual Auth0/persistence. No frontend recomputes scores, authorizes work, selects real notice recipients, or clears alerts.

Current redacted readiness: all 11 required operations match the running FastAPI after safely restarting only Cache's known developer process. Five existing and five new-route anonymous/development-header denials return 401. Invalid bearer returns 503 because local Auth0 settings are missing, not a signature-validation success. Local DATABASE_URL, Auth0 backend/SPA, Gemini and storage settings remain missing. Database contents and membership linkage remain unknown; no real authenticated report/write/delivery was performed. Readiness exits 2; DEV_AUTH_BYPASS=false, feed refresh and briefing scheduler disabled on this diagnostic process. Braydin's isolated real sign-in is separate owner evidence.

T065 frontend checks: 56 Node tests and 518 backend/probe tests (511+7), lint/TypeScript/build; clean npm ci/build without environment/ML artifacts passes. Detailed final browser status and resolved race/test issues are recorded in `t065-verification.json`. Canonical mirrors remain unchanged by T065; T067A removed only the two authorized obsolete types and fixture. No backend/auth/DB/ML/manifest/lockfile edits authored.

Present and absent reports use different routes. A returned confirmation initializes the unsent instruction draft; empty manual fallback and a 500-character final text are supported. Refreshing the same notice preserves typed edits. Another confirmer produces a clear state and no send editor. Site/report views read backend state after mutations; the UI does not recompute scores or recipients. Private photos are not rendered from arbitrary API URLs.

## Owner handoffs

Braydin continues private Auth0/Tiger Data/membership/Gemini/storage work without Cache duplicating it. Supply approved configuration privately; no tokens in logs/source. Rudra reviews the client contract and coordinates merges; PR #26 implementation details remain in T054_IMPLEMENTATION.md, T054A_IMPLEMENTATION.md and T055_IMPLEMENTATION.md. Canonical private photo retrieval remains an owner gap; the UI shows only a reference, never fetches an arbitrary photo URL.

Run and real acceptance checklist: frontend/LIVE_INTEGRATION.md. Visual work remains separately authorized; module boundaries are in FRONTEND_REDESIGN_HANDOFF.md.
