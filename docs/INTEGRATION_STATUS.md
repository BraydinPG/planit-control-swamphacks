# Frontend integration status

## T034A location preparation — 2026-10-17

PR #33 is merged. Separate functional branch `feature/cache-report-device-location` starts at main `681582b`; no unmerged dependency or Claude visual edit. [REPORT_LOCATION_INTEGRATION.md](REPORT_LOCATION_INTEGRATION.md) contains the new hook/controller interface, privacy behavior, exact T053A owner actions and final form acceptance checklist. T034 is checked; T034A/T053A remain unchecked. Published report types/route/persistence lack location source/accuracy/backend distance, so existing ReportForm and HttpClient remain unchanged. No metadata persistence or actual device/form integration claimed.

One-shot live location has an immediate approximate site fallback, validated accuracy,8-second deadline, manual pin priority, site/session reset and close cleanup. Demo avoids requesting real GPS because existing demo reports persist in localStorage; the new logic has no storage/network/Gemini calls. 90 Node tests (19 new),105 backend report/upload/schema/fixture/mirror tests, lint/TypeScript, fixture/API builds and installed Edge desktop/phone/mock lifecycle plus synthetic StrictMode hook pass. Existing Starlette and API554.37kB bundle warnings remain. Browser results/timing and publication refs are in the report-location guide and CROSS_SCOPE_CHANGES. No task checkbox changed and no real Auth0/Tiger/GPS acceptance attempted.

## Site-scoring verification — 2026-10-17 11:34 UTC

T051A/PR #31 merged `07a459d`. Separate `feature/cache-scoring-integration` worktree branch, no unmerged parent; Claude's primary/`feature/rudra-ui` visual changes preserved. See [SITE_SCORING_INTEGRATION.md](SITE_SCORING_INTEGRATION.md) and [redacted evidence](site-scoring-integration-verification.json) for the current pipeline results, precise owner actions and reproducible acceptance commands.

Controlled complete backend path passes: canned NWS JSON -> actual adapters/cache/refresh -> stored rules-0.2 score -> crew/supervisor API -> human confirmation -> updated score. Indices 2.1 ->3 ->4 ->7; failed feed holds active alert/7 while completeness becomes0. Existing in-memory test DB and fake JWT/JWKS identities only. Actual test responses render unchanged through production HttpClient/browser (16 comparisons at two widths); two additional no-evidence warning cases fail. Client now rejects internally contradictory score metadata; no algorithm, route, canonical contract or presentation edit.

Actual local readiness remains blocked: Auth0 SPA/backend and DATABASE_URL missing, DB membership/contents unknown, refresh off/NWS user-agent missing, T069 source seed still empty. Health/OpenAPI200, all11 operations, ten anonymous/dev-header401 denials and proxy401 verified; invalid bearer503 is not real signature-validation proof. No real login, source collection, DB connection or authenticated mutation performed. Current runner exits1 for its newly detected **incomplete-score display failure**, in addition to configuration blockers: ScorePanel shows0/low at0% without an explicit warning next to it. Claude/Rudra handoffs are actionable; no UI/contract changes forced.

Checks: **648 Python (638+10)**, **70 Node**, Ruff, lint/TS, fixture and API builds pass; API chunk553.81kB warning retained after incorporating maintainer-merged PR #32/main176cf36 as feature merge3b8dfe2; repeated frontend/browser checks pass and visual paths exactly equal main. Existing Edge demo/mock checks pass1440/390/320, no exceptions. T063–T068 stay unchecked; tasks.md unchanged. This improves independent verification, not live integration completion.

## Previous functional checkpoint (historical)

Verified 2026-10-17. PR #29 is merged as `ebd6d92`; Codex functional changes now use separate worktree `C:/Users/cache/planit-control-functional`, branch `feature/cache-functional-acceptance`. Claude actively owns presentation in the primary checkout. No unmerged prerequisite PR at startup; no visual files touched. Current path/interface handoff: FUNCTIONAL_INTEGRATION_HANDOFF.md.

Cache clarified that existing Auth0 crew/supervisor test aliases are intended for the demo. No employee/real-user records, profiles, accounts or database rows were created by Codex. Actual Auth0-backed demo behavior can satisfy integration; isolated mocked authentication cannot prove it. Local approved environment settings/sessions are still missing in both checked roots. Tenant/account existence is not inferred from missing local files; demo membership linkage remains owner setup.

Current functional changes: canonical site/alert/nested evidence validation, typed acknowledgement response, all-published-route anonymous gate before account tokens, case-insensitive role metadata matching existing auth exports, crew notice denial checks, stored site/org briefing reads, full acknowledgement identity/time read-back, and read-only cross-worktree configuration selection. Source/imports stay in this worktree; private settings are never copied. No API/auth/backend/schema/fixture/dependency changes.

Current checks: **68 Node**, **521 backend/probe** (511+10), lint/TypeScript, fixture/API-mode builds, Ruff and existing browser demo/mock workflows at 1440/390/320 pass. Actual ten anonymous/development-header denials return401; invalid token503 remains unverified; all11 source/running routes match, no drift. No authenticated demo mutation performed; readiness exits2. API-mode build has a chunk-size warning (531kB); no visual/composition refactor attempted. Exact evidence: functional-integration-verification.json. Historical T065 evidence remains in t065-verification.json.

T063-T068 remain unchecked. T063 needs actual Auth0 demo site reads; T064 needs persisted demo ack/browser reload; T066 needs actual demo-role UI/API permissions; T065 needs actual full report lifecycle; T067 still lacks enrichment; T068 waits for those flows and live accessibility on the now-integrated redesign. No task checkbox changed in this run.

Review: [PR #30](https://github.com/BraydinPG/planit-control-swamphacks/pull/30), source checkpoints `b7c8dc4` / `11806fa`, open against main at publication.

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
