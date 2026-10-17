# Real application acceptance (T063-T068)

This guide tests the existing application, Auth0 provider and FastAPI client. It does not create accounts, a database, a server, sample operational records or a second authentication implementation. Keep the working demo available while the owners configure real services. No phase-4 task is completed by the diagnostics alone.

## Current verified boundary

PR #19 merged as `64cf632`. This phase-4 branch incorporates reviewed main `9b395f0` (initial phase-4 base `9ba1b7c`), including T052 photo storage and T053 report list/create. Site and alert reads/acknowledgement plus report reads/create are published. Report review, hazard confirmation/instruction and Gemini endpoints remain absent at this checkpoint. Nick now owns T054/T054A/T055 under Rudra's contract review; Braydin owns Auth0, database/seed linkage, Gemini and Vultr provisioning. Read current tasks/ownership before editing.

The frontend enables report creation/listing separately from review. In real mode a present report requires a photo; absent reports do not. The existing multipart client sends canonical fields and lets the server enforce team/organization scope and validate image bytes. Review/instruction/AI actions stay unavailable until their routes exist. No actual report was submitted during this run; real credentials/database are still missing. The frontend offers JPEG/PNG/WebP; the new backend additionally supports HEIC. Private photo retrieval still needs its authorized owner integration.

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

Exit **2** means phase-4 acceptance remains incomplete (including required real browser checks); exit **1** means a failed check/input. In this run the expected result is exit 2: five actual 401 denial checks pass, while Auth0/database/account acceptance remains blocked. A 503 for an invalid token with unconfigured Auth0 is not proof that signatures or expiry were validated. No task checkbox changes automatically.

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
| T065 | After Nick's T054/T054A routes land, use the existing real report form: present/photo and absent cases, pending state, potential notice without instruction, notified supervisor confirmation/edit/send and team delivery. Private local photo storage is development-only; deployed Vultr configuration stays owner work. |
| T067 | After Braydin publishes T057-T060, verify generated/fallback briefing, explanation, source references, enrichment suggestion and human review. No Gemini secret or direct request in browser. |
| T068 | Re-run phone/desktop, keyboard/focus and failure states with those actual API/session paths. Demo checks remain regression evidence only. |

The checker explicitly leaves browser sign-in/reload acceptance unverified. Do not check T063-T068 merely because API reads or this harness pass. Keep AI advisory output separate from deterministic score/alert authority and work authorization. Reported electrical/structural/access hazards require confirmed field evidence; simulated or missing data cannot mean safe conditions.

Focused checks from repository root (backend Python active):

```powershell
python -m pytest frontend/tests/test_integration_probe.py backend/tests -q
python -m ruff check frontend/scripts/probe-integration.py frontend/scripts/run-live-account-check.py frontend/tests/test_integration_probe.py
cd frontend
node --test --test-concurrency=1 tests/status.test.mjs tests/data.test.mjs tests/integration.test.mjs
npm run lint
npm run build
node scripts/check-shell.mjs http://localhost:5173/
```

Runner orchestration unit tests use explicitly labeled mock transports and read-only fake query objects. Existing backend role/persistence tests also use their normal fixtures. They are not real Auth0/Tiger Data acceptance. Current measured results and blockers are in `docs/phase4-integration-verification.json` and `docs/INTEGRATION_STATUS.md`.
