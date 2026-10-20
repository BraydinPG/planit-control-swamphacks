# FORESITE

FORESITE: utility field operations for crews and supervisors. SwampHacks 2026 official repository.

**Live site:** https://foresiteoperations.org. Select **Explore Live Demo** on the landing page to view the demo worksites as a crew member or a supervisor, read-only, with no sign-in.

The product is now **FORESITE**. Repository/package names and deployed service
identifiers remain compatible; see [branding and deployment handoff](docs/REBRANDING.md).

## What it does

FORESITE watches public hazard feeds around utility worksites, raises stop-work alerts, scores each site's risk from 0 to 10, and connects crew reports to supervisors who make the final call.

- **Live hazard feeds.** NWS weather, forecasts, flood alerts and severe storms; NOAA GOES lightning; NHC and NWS hurricane alerts; USGS earthquakes and flood gauges. Every reading shows its source, its time, and whether it is stale or unavailable.
- **Deterministic alerts.** Lightning within 10 miles triggers stop-work with a 30-minute all-clear countdown that resets with each new strike. Tornado, hurricane, flash flood, earthquake and other warnings are ranked by danger tier. Rules control alerts; no AI output can clear one.
- **Site risk score.** A weighted 0–10 score from current hazards and confirmed crew reports, shown as its factor breakdown. Missing data lowers completeness and never reads as low risk. See [docs/SITE_RISK_SCORING.md](docs/SITE_RISK_SCORING.md).
- **Crew reports reviewed by a supervisor.** A crew member reports a hazard such as a downed line, fire, wildlife, flooding or a damaged access mat, with an optional photo, and says whether it is present. Nothing is sent until the organization's supervisor accepts the report. Accepting one marked present sends "potential {hazard}" to every organization inside a radius chosen by Gemini, or the category's default radius when Gemini is unavailable. Gemini drafts an instruction, which the supervisor edits or sends as is. Each notified organization confirms the hazard for itself and instructs only its own teams.
- **Organizations and teams.** Anyone can create an organization and becomes its owner. The owner's supervisor code makes one person the organization's supervisor and grants the Auth0 Supervisor role. The supervisor claims sites, creates teams and join codes, and crew join a team with a code.
- **Briefings.** At 6 PM site-local time, Gemini writes a briefing for the next workday at every team site, citing the supplied evidence and stating unknowns.
- **Event outlooks.** For a confirmed event, a historical model estimates in plain words how much longer it is likely to last. It is labeled as an estimate and is never an all-clear.
- **Pages update on their own.** Signed-in pages refresh every 30 seconds and when you return to the tab.

## Stack

React + TypeScript UI built with Vite and Tailwind CSS. API routes, auth checks, scoring, alerts and Gemini calls run in a FastAPI app under `backend/app/`. Auth0 is the identity provider, Tiger Data (Postgres with TimescaleDB) is the database, and Vultr hosts the app and stores crew photos. Gemini and scikit-learn complete the stack. Auth0, Tiger Data and Vultr are sponsors for tracks.

## AI and model safeguards

- **Gemini only suggests.** It analyzes reports, drafts instructions, picks notice radiuses and writes briefings. Its output is validated against schemas, labeled, and falls back safely: the default radius, a manual instruction, or a template briefing. A supervisor approves every classification and instruction. Gemini never declares work safe, clears an alert or changes a score. See [docs/GEMINI_EVALUATION.md](docs/GEMINI_EVALUATION.md).
- **The model is conditional and kept out of the score.** It only estimates how a confirmed active event will play out. It does not predict event onset or worksite safety, and it is excluded from the score. Training, chronological backtests, calibration and limitations are in [ml/EVALUATION.md](ml/EVALUATION.md), [ml/METHODOLOGY.md](ml/METHODOLOGY.md) and [ml/MULTIDISASTER_EVALUATION.md](ml/MULTIDISASTER_EVALUATION.md). To run it, see [ml/QUICKSTART.md](ml/QUICKSTART.md).

## Layout

| Path | Contents | Owner |
|---|---|---|
| `frontend/` | Vite + React + TypeScript + Tailwind UI | Nick, with contributions from Rudra (Braydin owns `src/auth/`) |
| `frontend/public/` | Public website: landing, Platform, Data and About pages | Cache |
| `frontend/src/types/api.ts` | TypeScript mirror of the API schemas | Rudra |
| `frontend/src/fixtures/` | Mock API responses for fixture mode (generated) | Rudra |
| `backend/app/` | FastAPI app and every API route | Rudra |
| `backend/app/security/`, `db/`, `gemini/`, `ingestion/` | Auth0 checks, Tiger Data models, Gemini services, live-feed adapters | Braydin |
| `backend/app/rules/score.py`, `rules/settings.py` | The 0–10 risk algorithm and its weights | Cache |
| `backend/app/schemas/` | Canonical Pydantic API schemas | Rudra |
| `ml/` | Model training, prediction, evaluation | Cache |
| `auth/` | Auth0 setup notes | Braydin |
| `deploy/`, `.github/workflows/deploy.yml` | Vultr deployment | Braydin |

Ownership details and the shared contracts are in [AGENTS.md](AGENTS.md); the product spec is [spec.md](spec.md).

## Configuration

Copy the templates and fill in values. Each variable is commented with its purpose and owner. Never commit the filled-in files.

- `backend/.env.example` → `backend/.env`: Tiger Data, Auth0, Gemini, Vultr Object Storage, live feeds, CORS.
- `frontend/.env.example` → `frontend/.env.local`: API URL, fixture mode, public Auth0 SPA values.

Auth0 tenant setup (roles, callback URLs, the role-manager app the organization flow needs, demo accounts) is in [auth/SETUP.md](auth/SETUP.md).

## Frontend

```bash
cd frontend
npm install
npm run dev
npm run build
npm run lint
```

With `VITE_USE_FIXTURES=true` the app runs on mock data with no backend or sign-in.

## Backend

Requires Python 3.11+.

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
python -m app.db.init
uvicorn app.main:app --reload --env-file .env --port 8000
pytest
```

`--env-file .env` loads `backend/.env` (copied from `backend/.env.example`). Without it, `DATABASE_URL` is not set and data routes answer 503. `python -m app.db.init` creates the tables and hypertables and adds new columns; it is safe to run again.

Health check: `GET http://localhost:8000/health` returns `{"status": "ok"}`.

### Demo data

From `backend/`:

| Command | What it does |
|---|---|
| `python -m app.demo seed` | Remove the previous demo rows and restore the demo scenario |
| `python -m app.demo anomalies` | Add one demo site per anomaly type and restore the Everglades wildlife demo |
| `python -m app.demo freshen` | Slide the demo sites' times to now (the deployed server does this every round) |
| `python -m app.demo strike 1` | Replay one lightning step at the demo site; step 2 resets the countdown |
| `python -m app.demo briefing-test` | Set up the organization that checks the 6 PM briefing schedule |

Demo sites say "(demo)" in their name. The read-only guest view is enabled only on the deployed server (`DEMO_GUEST_ENABLED`).

### Windows Smart App Control

If `pytest` or `uvicorn` fails with `An Application Control policy has blocked this file` for a `sqlalchemy\...\_*_cy*.pyd` file, Smart App Control is blocking SQLAlchemy's optional compiled speedups. Smart App Control has no per-file allow list, so reinstall SQLAlchemy as pure Python instead of turning it off:

```powershell
cd backend
$env:DISABLE_SQLALCHEMY_CEXT = "1"
.venv\Scripts\python -m pip install --force-reinstall --no-deps --no-binary sqlalchemy "sqlalchemy>=2.0"
```

This changes only your local virtual environment. To see which file was blocked, open Event Viewer and go to Applications and Services Logs > Microsoft > Windows > CodeIntegrity > Operational.

### Live data feeds

`backend/app/ingestion/` turns public hazard feeds into `Observation` records. Every adapter exposes `fetch(sites, now) -> list[Observation]`.

| Feed | Module | Source |
|---|---|---|
| Weather and hourly forecast | `nws_weather.py` | NWS `api.weather.gov`: latest station observation, hourly forecast |
| Flood alerts | `nws_alerts.py` | NWS active Flood Warning, Flash Flood Warning, Flood Watch |
| Tornado and severe thunderstorm | `severe_storms.py` | NWS warnings and watches for the site |
| Lightning | `lightning.py`, `glm.py` | NOAA GOES GLM (live, `LIGHTNING_LIVE_ENABLED`); labeled replay fixture otherwise |
| Hurricanes | `hurricanes.py` | NHC active storms and NWS tropical warnings/watches |
| Earthquakes | `earthquakes.py` | USGS earthquake feed |
| Flood gauges | `flood_gauges.py` | USGS water services gage height and streamflow |
| Site locations | `eia860m.py` | EIA-860M power plant locations (representative worksites) |

Freshness (`cache.py`): each feed keeps its own cache of the last successful readings per site.

- A failed refresh returns those readings marked `stale`.
- Readings older than `FEED_STALE_AFTER_MINUTES` (default 60) are `stale`.
- After `FEED_UNAVAILABLE_AFTER_MINUTES` (default 360), or when nothing was ever fetched, the feed reports `unavailable`.
- A stale or unavailable feed is never shown as current, and it never clears an alert.

Configuration: set `NWS_USER_AGENT` in `backend/.env`. NWS requires an identifying User-Agent, and without one the NWS feeds report `unavailable`. Only one backend refreshes feeds and writes briefings (`FEED_REFRESH_ENABLED`, `BRIEFING_SCHEDULE_ENABLED`); laptops sharing the database leave both `false`.

Manual check against live NWS data, from `backend/`:

```bash
python -c "from datetime import UTC, datetime; from types import SimpleNamespace as S; from app.ingestion import nws_weather; [print(o.hazard_type, o.label, o.value, o.unit, o.data_state) for o in nws_weather.fetch([S(id='demo', lat=25.76, lon=-80.49)], datetime.now(UTC))]"
```

Adding a feed: follow `AGENTS.md`, "Ingestion interface", then "Adding a feed adapter." Tests use canned responses through `httpx.MockTransport` (see `backend/tests/nws_fakes.py`) and never call the network.

### Fixtures

`frontend/src/fixtures/*.json` holds mock API responses for frontend fixture mode. They cover stale, simulated, and unavailable data, a lightning alert after a timer reset, pending, confirmed, and absent reports, and Gemini and fallback briefings. They are generated from the Pydantic schemas, so edit `backend/scripts/generate_fixtures.py` and regenerate instead of editing the JSON:

```bash
cd backend
python -m scripts.generate_fixtures
```

`pytest` fails if the JSON is out of date or no longer validates.

## Deployment

Pushing to `main` deploys automatically: GitHub Actions (`.github/workflows/deploy.yml`) runs the backend tests and lint and the frontend type check and tests, then `deploy/deploy.sh` updates the Vultr server and runs `python -m app.db.init`. One server runs Caddy (HTTPS and the built frontend) in front of the FastAPI backend; the database stays on Tiger Data and identity on Auth0. Server setup and every production setting are in [deploy/README.md](deploy/README.md).

## Quality checks

Run these before opening a pull request. All must pass.

| Area | Command (run from) | What it does |
|---|---|---|
| Backend lint | `ruff check .` (`backend/`) | Lint with Ruff (pyflakes, pycodestyle, import order, bugbear, pyupgrade) |
| Backend format | `ruff format --check .` (`backend/`) | Check formatting. Run `ruff format .` to fix. |
| Backend tests | `pytest` (`backend/`) | Unit tests, including contract and TS-mirror checks |
| Frontend lint | `npm run lint` (`frontend/`) | Lint with oxlint |
| Frontend type check and build | `npm run build` (`frontend/`) | `tsc -b` type check, then Vite production build |
| Frontend tests | `node --test --test-concurrency=1 tests/*.test.mjs` (`frontend/`) | Unit tests for the API client, validation and workflows |
| App browser check | `node scripts/check-shell.mjs http://localhost:5179/` (`frontend/`) | Crew and supervisor workflows, polling and layout at several widths, against `VITE_USE_FIXTURES=true npx vite --port 5179` |
| Public pages check | `node scripts/check-public-pages.mjs http://localhost:5179/ --fixtures` (`frontend/`) | Landing, Platform, Data and About pages, with and without JavaScript |

The browser checks drive a local Chrome or Edge; set `SHELL_BROWSER` to its path. Ruff and pytest settings live in `backend/pyproject.toml`. The frontend has no separate formatter configured.
