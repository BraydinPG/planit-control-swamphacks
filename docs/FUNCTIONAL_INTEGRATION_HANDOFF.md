# Codex / Claude integration handoff

## T034A location controller — 2026-10-17

Fresh functional branch `feature/cache-report-device-location` from main `681582b` (PR #33 merged). Cache adds `application/report-location.ts` and `useReportLocation.ts`, focused Node tests and a test-only browser harness using the existing shell runner. No page/component/style/App/auth/client/DTO/backend edit. `useReportLocation(reportOpen ? site : null, client.mode)` returns immediate coordinates/source/accuracy/status/message plus `setPin(lat,lon)`; site fallback is approximate, late fixes cannot overwrite a manual pin, and close clears state. Demo requests no real GPS and the logic writes no storage or network. Existing Client/hooks stay compatible.

**Claude:** consume this interface only after Rudra/Braydin publish T053A. Exact field/edit/loading/submission instructions and privacy requirements: [REPORT_LOCATION_INTEGRATION.md](REPORT_LOCATION_INTEGRATION.md). **Rudra:** canonical source/accuracy/returned distance, route, TS mirror, fixtures and contract tests. **Braydin:** idempotent migration/persistence; exclude GPS from T060 photo analysis. Current ReportForm and transport remain unchanged; T034A/T053A stay unchecked. 90 Node,105 focused backend,linter/TS,both builds and synthetic hook/existing browser lifecycle pass; no actual GPS/Auth0/Tiger acceptance. Claude retains all visual ownership and no UI coordination edit is assumed.

## Current scoring verification — 2026-10-17

PR #31 merged `07a459d`; functional branch `feature/cache-scoring-integration` is based on that main with no unmerged parent. Maintainers subsequently merged visual PR #32 as `176cf36`; feature-branch merge `3b8dfe2` incorporates it without any manual visual edit, with every visual file equal to main. Primary checkout remains untouched. Current full checklist/evidence: [SITE_SCORING_INTEGRATION.md](SITE_SCORING_INTEGRATION.md). This run changes API validation, diagnostic/tests and shared docs; one backend **test** joins existing adapters/refresh/persistence/API/report paths. No backend production, auth, schema, fixture, ML or presentation changes.

Stable Client/hooks/DTOs: unchanged. `validateSiteDetail` now rejects a headline/nested stored-score disagreement on value, band, version, completeness or time, and a scored detail missing its breakdown. Equivalent timezone timestamps/null-unscored pass. This compares server values, never computes scores or authority. Existing mock response versions/unscored fields corrected. API errors remain typed502 with existing error UI/no fixture fallback.

Actual configuration/database/account acceptance remains blocked. Controlled NWS -> DB-test/API -> report confirmation yields2.1/3/4/7 and held7 under outage/completeness0. Actual test response snapshots pass16 browser value comparisons, while two no-evidence display cases correctly expose the pending warning defect. Standard browser mocks pass1440/390/320; Python648,Node70,lint/TS,both builds,Ruff pass, including repeated frontend/browser checks after the incoming main redesign (API553.81kB warning). **Claude:** explicit incomplete-index warning/RiskBadge handling; **Rudra:** ranking/evidence-status and current-main orchestration/T069; **Braydin:** approved Auth0/Tiger settings/memberships and briefing qualification. tasks.md unchanged; T063-T068 pending. No task completion from mocks.

## Previous functional checkpoint (historical)

Verified 2026-10-17 against main `ebd6d92` (PR #29 merged). Functional branch:
`feature/cache-functional-acceptance`, separate worktree `C:/Users/cache/planit-control-functional`.
Claude's primary checkout and running frontend were left untouched. No unmerged parent dependency.
Review: [PR #30](https://github.com/BraydinPG/planit-control-swamphacks/pull/30), open against main at publication; API commit `b7c8dc4`, diagnostics/handoff `11806fa`.

| Owner | Paths / coordination |
| --- | --- |
| Codex / Cache | `frontend/src/api/**`, `application/**`, `demo/**`, functional `scripts/**` and `tests/**`. This change touches API/diagnostics/tests only. |
| Claude | `src/pages/**`, `src/components/**`, `src/styles/**`, `src/index.css`, visual assets and responsive layout. No changes here by Codex. |
| Shared: coordinate first | `App.tsx`, shell navigation/DOM contracts, manifests/locks, Vite configuration, integration docs and context. No composition/configuration/dependency edit in this change. |
| Rudra / Braydin | Rudra's canonical `types/api.ts`, generated fixtures, backend routes/scoring; Braydin's `src/auth/**`, security, database, provider configuration and deployment. Read-only consumption here. |

## Stable component interfaces

- Continue using `Client` from `api/contracts.ts`: existing method names/arguments and canonical DTOs are unchanged. `acknowledge(id)` now explicitly returns `Promise<Alert>` instead of `unknown`; show success only after that promise resolves, then refresh shared state.
- `sites()`, `site(id)`, `alerts()` and acknowledgement now reject malformed/coerced values, duplicate list IDs, unrelated nested site evidence, invalid source timestamps and invalid acknowledgement responses with `ApiError(502)`. Null score/time/distance stays null. This is validation, never authorization or a new scoring/alert engine.
- New reusable functions in `api/live-read-validation.ts`: `validateSiteSummary(value)`, `validateSiteDetail(value, id)`, `validateAlert(value, optionalId)`, `validateUniqueRows(value, validator)`. Existing components obtain this automatically through HttpClient; do not duplicate parsing in JSX.
- `useApplication()` (`client`, `persona`, `principalId`, `revision`, `refresh`), `useResource(key, load)`, `useClock()` and `useRoute()` remain unchanged. No competing hook/state implementation was added.
- Existing `AuthProvider`, `RequireRole`, `useAuth()` remain Braydin's exports. Consume their subject/role/token in live mode; fixture persona is never authorization. CLI metadata checks now match existing case-insensitive roles; FastAPI still validates signatures/permissions.
- Preserve prior report/notice behavior: absent report review vs present notice confirmation; optional unsent suggestion/manual field; confirmer-only explicit 1-500-character send; stable notice ID keys preserve draft edits. Potential notices have no instruction. Never calculate recipients/score or clear alerts in React.
- Preserve stored site/organization briefing GETs, 404 scheduled empty state, Gemini/template labels, evidence/unknowns/window/time. Enrichment remains an owner blocker: no guessed endpoint was introduced.

No component migration or visual change is required. Claude can redesign the existing views against these interfaces. Coordinate changes to labels/selectors used by `scripts/check-shell.mjs`; keep the same behavioral checks.

## Authenticated demo, not employee accounts

Cache clarified that the existing Auth0 crew/supervisor test aliases are the intended accounts. Do not create real-user accounts, store profiles, or populate employee data. A provider-authenticated demo using labeled Tiger Data fixtures is different from the browser's isolated mock transport. This run created neither accounts nor database rows. Any required demo subject-to-team/organization membership linkage remains Braydin/Rudra's existing setup responsibility; no bypass or policy change is proposed.

Current local blocker: no approved DATABASE_URL, Auth0 SPA/backend settings or token session is available in either checked location. Tenant roles/test accounts can exist independently; their existence is not disputed. Membership contents remain unknown. T063-T068 stay unchecked; T068 also waits for the redesigned UI.

## Checks and owner actions

- 68 Node checks (56 prior + 6 read/ack contracts + 6 acceptance regressions), 521 Python checks (511 backend + 10 probe), lint/TypeScript and fixture/API-mode builds pass. Existing Starlette warning; API-mode bundle warns at 531 kB. No presentation refactor to address that warning.
- Full installed-browser regression on `http://localhost:5176/`: 1440/390/320, existing demo and mocked HTTP report/alert/briefing flows pass, no browser exceptions or real backend mutations. Primary `5173` is untouched; `5176` is a separate development instance of the same app, not an Auth0 callback configuration change.
- Actual readiness: all 11 source/running operations match; ten anonymous/development-header denials return 401. Invalid bearer is 503 with unconfigured local Auth0; not successful signature validation. Exit 2 remains appropriate.
- Diagnostics now gate account-token use on **every published anonymous denial**, check crew notice confirm/send denial, read stored briefings through the same HttpClient, and compare full acknowledgement identity/time across fresh clients. They never generate briefings or create reports automatically.
- To inspect existing approved private settings without copying them, use `--configuration-root <approved-project-root>` on `check-live-integration.mjs` or `run-live-account-check.py`. Schemas/imports remain this worktree; only existing environment settings are read. No token in argv/env/output; the private wrapper still uses hidden prompts and stdin.
- Braydin/Rudra: finish the existing demo configuration/membership handoff; do not provision employee identities for these checks. Then use `frontend/LIVE_INTEGRATION.md` for actual Auth0 demo-role reads, explicit simulated-test-alert acknowledgement/read-back, and the full UI report lifecycle. CLI token checks never substitute for browser login/reload proof.

Exact commands, results and changed files: `docs/functional-integration-verification.json`. Review PR/commits are recorded in PROJECT_CONTEXT and CROSS_SCOPE_CHANGES after publication. No task checkbox changed by this run.
