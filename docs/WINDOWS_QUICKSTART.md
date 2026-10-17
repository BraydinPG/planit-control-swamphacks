# Windows PowerShell quick start

Use a regular PowerShell terminal. Tested with Node 24.22.0/npm 11.19.1, Python 3.12.10,
and installed Microsoft Edge. The repository requires Node 24 for its browser checker
and Python 3.11+ for the backend; the commands below select installed Python 3.12.
No activation script or execution-policy change is needed. Use `npm.cmd`, not `npm.ps1`.

For a **new checkout** (skip cloning if you already have one):

```powershell
git clone https://github.com/BraydinPG/planit-control-swamphacks.git
Set-Location planit-control-swamphacks
git status --short --branch
git log -1 --oneline
node --version
npm.cmd --version
py --list-paths
```

Install the required runtimes before continuing if those commands are unavailable;
open a new terminal after installing them. No ignored environment/model directory
from Cache's computer is required. [Verified results](clean-setup-verification.json).

## 1. Frontend demonstration — no services or credentials

From the repository root:

```powershell
Set-Location frontend
npm.cmd ci
$env:VITE_USE_FIXTURES = 'true'
$env:VITE_DEV_AUTH_ROLE = ''
npm.cmd run dev -- --host localhost --port 5173 --strictPort
```

Open **http://localhost:5173/** and check the **Simulated demo** banner. This process
variable overrides an older `.env.local` live-mode setting without rewriting it.
Auth0, Tiger Data, Gemini, Python, ML artifacts and online map tiles are unnecessary.
Keep this terminal open. Stop only your own server with Ctrl+C. If 5173 belongs to
another checkout, leave it running and explicitly use 5177 instead; use that same URL
in the browser/checker. Alternative ports here are for the **demo**, not new Auth0 callbacks.

Exercise the existing application:

1. Crew → Reports: select present/absent, leave the note blank, submit a simulated
   report. A photo is optional in the demo; use only a nonprivate test image.
2. Supervisor → Everglades site: confirm the matching potential notice, enter/edit
   the instruction, and explicitly send it. An absent report has its own review action.
3. Return to Crew: inspect the approved instruction. Open Briefings for the archived
   site/organization Gemini/template examples. Nothing is generated live.
4. Restart your Vite server on the **same host and port**, reload, and inspect the same
   report/confirmation/instruction. State lives only in `planit:frontend-demo:v1` in
   that browser origin. Photos are memory-only and disappear on reload. Reset demo
   resets only that namespace. No real backend persistence or work authorization is implied.

For a production-bundle demonstration, in another terminal at `frontend/`:

```powershell
$env:VITE_USE_FIXTURES = 'true'
npm.cmd run build
npm.cmd run preview -- --host localhost --port 5178 --strictPort
```

Open http://localhost:5178/. **Build first:** preview serves the existing `dist/` and
does not recompile changed code or environment values. Setting fixture mode only when
starting preview cannot change a bundle previously built in live mode. Preview is a
local build check, not deployment configuration.

## 2. Backend dependencies and tests — no credentials

In a new terminal, from the repository root:

```powershell
Set-Location backend
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
& .\.venv\Scripts\python.exe -m pip check
& .\.venv\Scripts\python.exe -m pytest -q -rs
& .\.venv\Scripts\python.exe -m ruff check .
& .\.venv\Scripts\python.exe -m ruff format --check .
```

Run tests before adding private configuration; tests use their existing isolated
fixtures, not Tiger Data or real providers. Clean backend-only result: **637 passed,
2 optional ML skips**, one existing Starlette TestClient/httpx deprecation warning.
The skips name `ml/requirements-lock.txt`; leave the optional research dependencies
out for this demo. Model-unavailable behavior is tested separately. No training,
archive downloads, seed command or alternative application database is needed.

## 3. Optional FastAPI liveness without a database

In that **health-only** `backend/` terminal:

```powershell
$env:DATABASE_URL = ''
$env:AUTH0_DOMAIN = ''
$env:AUTH0_AUDIENCE = ''
$env:DEV_AUTH_BYPASS = 'false'
$env:FEED_REFRESH_ENABLED = 'false'
$env:BRIEFING_SCHEDULE_ENABLED = 'false'
$env:LIGHTNING_LIVE_ENABLED = 'false'
$env:GEMINI_API_KEY = ''
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

From another terminal: `Invoke-RestMethod http://127.0.0.1:8000/health` returns
`status: ok`. Anonymous `/api/sites` returns 401. This verifies process liveness and
protected routes, **not** database readiness. If 8000 is already owned, leave it alone;
use 8052 for this isolated health check and change the health URL accordingly. The
frontend development proxy still targets 8000.

## 4. Configured application — owner prerequisites remain

Use a **new terminal** for real integration so the empty health-only environment
variables above cannot override a populated `.env`. Follow [auth setup](../auth/SETUP.md)
and [live integration](../frontend/LIVE_INTEGRATION.md). Rudra/Braydin provide the
initialized Tiger Data database, existing demo-account memberships/teams/sites,
approved Auth0 SPA/API roles and configuration, T069 scenario and applicable provider/storage settings.
Do not start data workflows with the template's placeholder database URL.

Once the owners have supplied your private `backend/.env`, from `backend/`:

```powershell
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8000
```

`--env-file` matters: database configuration reads process environment, while several
settings classes read `.env` themselves. The empty/nonsecret health-only configuration
was also verified using this exact env-file startup path. Never print or commit that
file. Keep `DEV_AUTH_BYPASS=false`. Enable background jobs only when their owners have
configured the real database/feeds; health 200 alone is insufficient.

Live frontend uses `VITE_USE_FIXTURES=false`, the owner's public Auth0 SPA values,
empty `VITE_DEV_AUTH_ROLE`, and empty `VITE_API_BASE_URL`. Restart Vite after changing
settings. Empty API base uses same-origin `/api`; **Vite dev proxies to 127.0.0.1:8000**.
An anonymous request to `http://localhost:5173/api/sites` should return401 JSON, not
Vite HTML or fixtures. An absolute API URL requires owner-configured backend CORS.
Production hosting needs its own `/api` reverse proxy; do not assume the dev server
configures deployment. Failed live requests never fall back to demo data.

## Checks and restart acceptance

At `frontend/`, with your demo Vite server running:

```powershell
node --test tests/*.test.mjs
npm.cmd run lint
node node_modules/typescript/bin/tsc -b
npm.cmd run build
node scripts/check-shell.mjs http://localhost:5173/ --restart-check
```

The existing installed-Edge runner checks 1440/390/320 widths and the report lifecycle.
At `RESTART CHECK`, restart **your** demo server in its own terminal, on the same port,
then press Enter in the checker terminal. It never kills a server. It verifies the
exact stored demo state and rendered report/confirmation/instruction/briefing afterward;
the prompt has a five-minute bound. For another installed Chromium executable, set
`SHELL_BROWSER` to its path. Results/screenshots are ignored in `frontend/.shell-check/`.
For the freshly built preview use `node scripts/check-shell.mjs http://localhost:5178/ --production`.

## Troubleshooting

| Symptom | Check / action |
| --- | --- |
| `npm` missing or unsupported runtime | Install Node 24; reopen PowerShell and verify `node --version`. Use `npm.cmd ci` in `frontend/`. |
| Execution policy blocks npm/activation | Use `npm.cmd` and the explicit `.venv\Scripts\python.exe` above; do not change policy. |
| Old design, stale routes or wrong mode | Check the URL/port, terminal working directory and `git log -1`. Vite serves that checkout; a running Python worker keeps imported code until restarted. Rebuild before preview. |
| Port already used | `Get-NetTCPConnection -State Listen -LocalPort 5173,5176,8000` identifies PIDs; `Get-Process -Id <PID>` shows start time/name. Stop only a process you own, preferably via its terminal. No bulk Node/Python termination. |
| Browser state vanished after restart | Keep the exact origin (localhost differs from 127.0.0.1, and ports differ). Avoid private browsing; blocked storage reports memory-only changes. |
| `EBUSY` watching Edge cookies/profile files | Update to the startup-reliability change: Vite excludes `.shell-check/`; fixed-source checker helpers disable watching. Never delete an active profile or another agent's output. |
| Preview shows sign-in after setting demo mode | Set `VITE_USE_FIXTURES=true` **before build**, build again, then restart preview. |
| Backend health 200 but data unavailable | Health is liveness. Check owner-provided Auth0/Tiger settings, env-file loading, membership/seed and real role acceptance. Do not enable bypasses or seed a substitute database. |
| Windows blocks SQLAlchemy's optional compiled module | Use the existing [Smart App Control instructions](../README.md#windows-smart-app-control); do not disable platform security. This was not needed in the clean Python 3.12 run. |

T070 stays unchecked: another teammate must reproduce setup and the remaining real-service
prerequisites/acceptance must pass. Current pending prerequisite IDs and exact results
are in [the verification record](clean-setup-verification.json). T053A and PR #34's
form integration are separate owner work; this guide does not implement them.
