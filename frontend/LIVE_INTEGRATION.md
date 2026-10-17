# Real application acceptance (T063-T068)

This guide tests the existing application, Auth0 provider and FastAPI client. It does not create accounts, a database, a server, sample operational records or a second authentication implementation. Keep the working demo available while the owners configure real services. No phase-4 task is completed by the diagnostics alone.

## Current verified boundary

PR #24 merged as `f3a65a7`, and T067A PR #27 merged as `1eed70e` during this run (external maintainer actions). T065 now uses `feature/cache-report-lifecycle-integration` from reviewed main `dcd9fc5` (PR #28); it does not duplicate either parent PR. T053/T054/T054A/T055 and T058A GET routes are present in source and the running service. Cache authored no backend/auth/database change.

Stored site and organization briefings are read-only. A site 404 means "No briefing yet. Briefings are generated at 6 PM site-local time." No browser timer or mutation generates a briefing. Canonical Gemini and template fixture results remain visibly archived/simulated. Site factors provide the deterministic score breakdown.

Braydin verified isolated Auth0 sign-in on main; that is owner evidence, not Cache's authenticated application/persistence acceptance. Database memberships and this application's real workflow still require verification. Do not overwrite private configuration or duplicate provisioning.

## T065 implementation and remaining real proof

Live HTTP capabilities for create/list, absent review, notice confirmation and instruction send are enabled. Published paths use the canonical request/response types. `api/validate.ts` rejects malformed or mismatched report/notice/confirmation responses. A potential notice cannot carry instructions or confirmation ownership. The editor initializes from the confirmed server notice and stays empty when no suggestion exists; sending is a deliberate action with a 500-character limit. Only the confirming Auth0 subject can see the send UI; the backend still authorizes every call. Present report review controls are removed and link to the site's notices instead.

All successful mutations refresh shared API reads. No pending/absent/rejected client action computes a score or clears an alert. Permission/conflict failures refresh current server state without claiming ownership. Network/timeout outcomes are explicit and never retry automatically or switch to demo data. Use Refresh server state / Refresh reports before repeating an uncertain operation. Private photo retrieval remains an owner gap; live present upload still uses the canonical multipart form.

The browser harness and 12 HTTP lifecycle unit tests are **mock only**. They test photo/presence rules, pending/no instruction, absent review, returned draft/manual fallback, editing, deliberate send, crew read-back/reload, malformed replies, permissions and races. Browser fixtures persist in a separate test-only session namespace; no real user/token/photo or backend request is used. Production build excludes this test entry. Demo behavior remains independently isolated in its existing namespace.

Actual readiness: all 11 operations match source/running OpenAPI after restarting only our known local server. Ten anonymous/development-header denial probes pass (five prior plus five new routes); invalid bearer remains 503 because local Auth0 is unconfigured. Readiness exits 2. Local DATABASE_URL and Auth0 SPA/backend values are missing, so database contents/memberships and real authenticated persistence remain unknown. Braydin's isolated tenant sign-in verification is separate owner evidence. T065 stays unchecked until the full actual UI lifecycle is proven.

For an authorized real test: crew submits a nonprivate test photo/pin/present report and an absent report; reload pending state; own-organization supervisor reviews absent; notified supervisor confirms present; inspect unsent draft or empty manual field, edit/send, then reload from the assigned crew account and confirm backend delivery. Verify direct forbidden requests with crew/unrelated supervisor and a competing confirmer. Inspect the server-provided score after confirmation, and confirm pending/absent/rejected reports and instruction sends never alter deterministic alerts. Keep DEV_AUTH_BYPASS=false; do not use the browser test harness for this proof. No extra report-write automation is added to the private account checker.

## Configure and start the existing services

Use [auth/SETUP.md](../auth/SETUP.md) and the existing environment templates. Never put credentials, account identifiers or tokens in Git/chat or a `VITE_` value. Only the existing public Auth0 SPA values belong in frontend configuration.

- **Braydin:** configure `backend/.env` with the real Tiger Data `DATABASE_URL` and required TLS, `AUTH0_DOMAIN`, `AUTH0_AUDIENCE`, and `DEV_AUTH_BYPASS=false`. Configure the Auth0 SPA/client callback/logout origins, RBAC and roles Action. Supply crew/supervisor accounts privately, link their actual Auth0 subjects to organizations/teams/sites, and verify T025/T026. `app.db.seed` creates schema but intentionally inserts no demo scenario rows; it does not provision the memberships needed here. Run the existing initializer/import/seed procedures as owner, not from the diagnostic.
- **Frontend local settings:** set `VITE_USE_FIXTURES=false`, the matching public `VITE_AUTH0_DOMAIN`, `VITE_AUTH0_CLIENT_ID`, `VITE_AUTH0_AUDIENCE`, empty `VITE_API_BASE_URL` for the existing proxy, and empty `VITE_DEV_AUTH_ROLE`. Restart Vite after changes. Do not enable a bypass for real acceptance.
- **Backend startup:** use the existing installed backend Python requirements and start from `backend/`. Once a populated private `.env` exists, explicitly load it so `DATABASE_URL` reaches the process:

```powershell
cd backend
$env:DEV_AUTH_BYPASS = 'false'
python -m uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8000
```

The Auth0 settings class reads `.env`; the database connection reads process environment. Running without `--env-file` or equivalent exported variables can therefore leave database configuration unavailable even when a file exists. Do not start with the template's placeholder URL. Health 200 is liveness, not database readiness. This run restarted only its own known local FastAPI process after incorporating main; no other job was stopped.

Start the existing frontend as documented in [INTEGRATION.md](INTEGRATION.md), with Node 24 and `npm ci`. Its Vite `/api` proxy targets FastAPI:8000. No alternative database or identity provider is permitted. Absolute API URLs require owner CORS configuration; this diagnostic deliberately targets loopback application services.

Latest main also publishes the T049B feed-refresh loop, off by default. For local diagnostic acceptance keep FEED_REFRESH_ENABLED=false. After actual database/provider setup, the ingestion owner can deliberately configure NWS_USER_AGENT and the existing refresh settings to collect observations. This inspector never starts that loop or fetches feeds; source timestamps and stale/unavailable labels remain authoritative.

## One-command redacted readiness

From repository root, with Node 24 on PATH and a backend Python environment containing the existing requirements:

```powershell
node frontend/scripts/check-live-integration.mjs --python backend/.venv/Scripts/python.exe --check-database
```

Use `backend/.venv/bin/python` on Unix, or pass the absolute path to your existing backend environment. The verification in this workspace used `ml/.venv/hazard_clean_check/Scripts/python.exe`; that ignored environment is not required by a clean checkout. No ML artifact or training is needed.

The report records configuration presence/placeholder flags and domain/audience matches, never values; fixture/live mode; unsafe public credential variable names; health/OpenAPI/proxy behavior; published versus missing endpoints; source-versus-running-server drift; actual unauthenticated/development-header/invalid-token responses. It uses Vite's environment loader and the existing backend settings, not a second configuration source. Environment inspection cannot prove what an already running process loaded; restart after changing settings.

`--check-database` is optional and read-only: a remote PostgreSQL connection with bounded connect/statement timeouts, transaction read-only mode, required tables, aggregate counts, formatted EIA IDs/in-range coordinates, linked crew/supervisor memberships, and the three existing Timescale hypertables. It never initializes, seeds, migrates or changes rows. Missing/placeholder URLs and local databases are blocked; SQLite is never accepted. Provider-account provenance still needs owner confirmation; the count is not a new authoritative EIA reconciliation. Without a usable URL the result is unknown/blocked, not zero sites.

Exit **2** means phase-4 acceptance remains incomplete (including required real browser checks); exit **1** means a failed check/input. In this run the expected result is exit 2: the existing five denial checks pass (five additional current-route denial probes are recorded separately), while Auth0/database/account acceptance remains blocked. A 503 for an invalid token with unconfigured Auth0 is not proof that signatures or expiry were validated. No task checkbox changes automatically.

## Private real-account API check

After owner configuration, sign in normally through the existing Auth0 application using both accounts. Use access tokens from your own sessions (the protected request's Authorization header can be inspected locally); do not use ID tokens, mint test tokens, or paste credentials into shared tools. A private interactive wrapper keeps token entry hidden and pipes it directly to the checker:

```powershell
python frontend/scripts/run-live-account-check.py
```

Use the backend Python environment; Node 24 must be on PATH or pass `--node` with its executable path. The wrapper refuses a noninteractive/echoed prompt. It does not save tokens, put them in argv/environment, authenticate a different identity, or print subjects/response bodies. Programmatic private secret-manager piping can use `--tokens-stdin` on the Node checker with keys `crew`, `supervisor`, and optional `alert_id`; do not commit such JSON.

The runner uses the application's existing `HttpClient`, inspects expected access-token metadata, and relies on the real backend for signature/permission validation. It requires actual anonymous, invalid-token and development-header rejection before sending account tokens. It reads both roles' authorized sites/detail/alerts/reports, verifies crew cannot read another existing supervisor-visible site, and tests crew review denial only after that route is published. Missing routes/404 are blocked, not permission proof. Canonical backend Pydantic models validate returned DTOs; actual responses and canonical fixtures render through the same existing ScorePanel/Factors/Observations components. No private payload/HTML is saved.

No real report is created by this runner. Acknowledgement is off by default. For a deliberately selected **active simulated test alert** already stored for the real crew, use:

```powershell
python frontend/scripts/run-live-account-check.py --acknowledge
```

The extra prompt requests that specific alert ID. The write requires real role reads, permission checks and read-only remote database/seed readiness. It refuses cleared, operational, unrelated or unknown alerts and never auto-selects an alert. Fresh crew and supervisor HTTP clients must independently read back the same server acknowledgement/time; a successful POST echo alone fails. This can verify genuine database-backed replay behavior; it does not turn a replay into an actual lightning incident or clear an alert.

## Required real browser evidence before checking tasks

| Task | Verify with actual services; retain private evidence outside Git |
| --- | --- |
| T063 | Sign in, get 200 authorized site list/detail, and inspect the same view components used in demo. Supervisor sees the actual seeded monitored locations; crew sees only its assignment. Confirm source/freshness/null states and no demo substitution on errors. |
| T064 | Use the real seeded simulated alert, acknowledge in the UI, reload, and confirm the same backend acknowledgement. Observe server-provided countdown/state; local zero never clears it. Independent API read-back supplements this browser check. |
| T066 | Owner verifies T025/T026 first. Real crew and supervisor login/logout, roles/screens and session transitions; direct unrelated-site request denied server-side. Missing/expired/invalid token and prohibited operations must have actual outcomes, not mocked-provider assertions. |
| T065 | With the merged T054/T054A routes, use the existing real report form: present/photo and absent cases, pending state, potential notice without instruction, notified supervisor confirmation/edit/send and team delivery. Private local photo storage is development-only; deployed Vultr configuration stays owner work. |
| T067 | Verify stored site/organization briefing GETs, template labels, source references, enrichment suggestion and human review. No Gemini secret or direct request in browser. |
| T068 | Re-run phone/desktop, keyboard/focus and failure states with those actual API/session paths. Demo checks remain regression evidence only. |

The checker explicitly leaves browser sign-in/reload acceptance unverified. Do not check T063-T068 merely because API reads or this harness pass. Keep AI advisory output separate from deterministic score/alert authority and work authorization. Reported electrical/structural/access hazards require confirmed field evidence; simulated or missing data cannot mean safe conditions.

Focused checks from repository root (backend Python active):

```powershell
python -m pytest frontend/tests/test_integration_probe.py backend/tests -q
python -m ruff check frontend/scripts/probe-integration.py frontend/scripts/run-live-account-check.py frontend/tests/test_integration_probe.py
cd frontend
node --test --test-concurrency=1 tests/status.test.mjs tests/data.test.mjs tests/integration.test.mjs tests/briefings.test.mjs tests/lifecycle.test.mjs
npm run lint
npm run build
node scripts/check-shell.mjs http://localhost:5173/
```

Runner orchestration unit tests use explicitly labeled mock transports and read-only fake query objects. Existing backend role/persistence tests also use their normal fixtures. They are not real Auth0/Tiger Data acceptance. Current measured results and blockers are in `docs/t065-verification.json`; prior phase-4 history is in `docs/phase4-integration-verification.json` and `docs/INTEGRATION_STATUS.md`.
