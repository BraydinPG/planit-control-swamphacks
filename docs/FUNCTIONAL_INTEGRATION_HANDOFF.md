# Codex / Claude integration handoff

Verified 2026-10-17 against main `ebd6d92` (PR #29 merged). Functional branch:
`feature/cache-functional-acceptance`, separate worktree `C:/Users/cache/planit-control-functional`.
Claude's primary checkout and running frontend were left untouched. No unmerged parent dependency.

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
