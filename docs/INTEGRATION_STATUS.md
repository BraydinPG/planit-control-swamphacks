# Frontend integration status

Verified 2026-10-17. Current branch `feature/cache-stored-briefings-report-lifecycle` stacks on open PR #24 head `6a2fc4d`; merged reviewed main `70c20ff` in `9dcd278`. PR #26 merged as `9809db4`, adding T054/T054A/T055. Braydin's T058A and Auth0 changes are inherited unchanged. This current section supersedes prior missing-route statements; historical phase-4 measurements remain in phase4-integration-verification.json.

## Authorized sequence and task evidence

| Task | Prerequisites and acceptance | State |
| --- | --- | --- |
| T067A | T058A checked. Stored site and organization GETs, 404 empty, 401/403/503 errors, malformed DTO/window rejection, Gemini/template labels, no fixture fallback, keyboard/phone/desktop. 44 Node, 65 focused backend/fixture/mirror checks; lint/TS/build and full browser pass. | Complete after exact check |
| T065 | T053/T054/T054A now checked. Existing frontend form/client will be connected to reviewed routes; actual complete report lifecycle under real roles, persistence and delivery is required. | Unchecked pending actual acceptance |
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

Braydin's upstream isolated real sign-in is owner evidence. Cache's prior redacted local check found no private configuration and invalid bearer returned 503; those results are historical. The next diagnostic must inspect current configuration and running/source route drift. No real-account or database success is claimed from source availability.

## Owner handoffs

Braydin continues private Auth0/Tiger Data/membership/Gemini/storage work without Cache duplicating it. Supply approved configuration privately; no tokens in logs/source. Rudra reviews the client contract and coordinates merges; PR #26 implementation details remain in T054_IMPLEMENTATION.md, T054A_IMPLEMENTATION.md and T055_IMPLEMENTATION.md. Canonical private photo retrieval remains an owner gap; the UI shows only a reference, never fetches an arbitrary photo URL.

Run and real acceptance checklist: frontend/LIVE_INTEGRATION.md. Visual work remains separately authorized; module boundaries are in FRONTEND_REDESIGN_HANDOFF.md.
