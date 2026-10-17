# planit-control-swamphacks

Swamphacks 2026 Official Repository

React + TypeScript UI, built with Vite and Tailwind CSS. API routes, auth checks, scoring, alerts, and Gemini calls run in a separate FastAPI app under `backend/app/`. Auth0 is the identity provider. Tiger Data is the application database. Vultr hosts the app and stores crew photos. Auth0, Tiger Data, and Vultr are sponsors for tracks. Many organizations share one deployment. A supervisor manages every team in one organization. The supervisor list shows every location and its assigned team, with occupied locations first. A detected hazard, or a crew member marking one present, sends “potential {hazard}” with no instructions to teams and supervisors inside a radius chosen by Gemini. If Gemini is unresponsive, the notice uses that category’s default radius. Any notified supervisor can confirm it, edit Gemini’s suggested instruction, and send that instruction to the teams inside the radius. The reporting organization’s supervisor still decides when a crew member reports that no hazard is present.

## Layout

| Path | Contents | Owner |
|---|---|---|
| `frontend/` | Vite + React + TypeScript + Tailwind UI | Nick (`src/pages`, `src/components`, `src/styles`, `src/api`), Braydin (`src/auth`) |
| `frontend/src/types/api.ts` | TypeScript mirror of the API schemas | Rudra |
| `frontend/src/fixtures/` | Mock API responses for fixture mode (generated) | Rudra |
| `backend/app/` | FastAPI app and every API route | Rudra (except `backend/app/security/`, `backend/app/db/`, and `backend/app/gemini/`, owned by Braydin) |
| `backend/app/ingestion/` | Live-feed adapters | Split by file: Rudra (NWS weather, forecast, flood alerts, shared `FeedCache`), Braydin (lightning, hurricane, earthquake, flood gauges) |
| Vultr deployment files | Hosting, backend deploy, and photo storage config | Braydin |
| `backend/app/schemas/` | Canonical Pydantic API schemas | Rudra |
| `backend/tests/` | Backend tests | Rudra |
| `ml/` | Model training, prediction, evaluation | Cache |
| `auth/` | Auth0 setup notes | Braydin |

## Configuration

Copy the templates and fill in values. Each variable is commented with its purpose and owner. Never commit the filled-in files.

- `backend/.env.example` → `backend/.env`: Tiger Data, Auth0, Gemini, Vultr Object Storage, live feeds, CORS.
- `frontend/.env.example` → `frontend/.env.local`: API URL, fixture mode, public Auth0 SPA values.

## Frontend

```bash
cd frontend
npm install
npm run dev
npm run build
npm run lint
```

## Backend

Requires Python 3.11+.

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
pytest
```

Health check: `GET http://localhost:8000/health` returns `{"status": "ok"}`.

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

| Feed | Module | Source | Status |
|---|---|---|---|
| Weather and hourly forecast | `nws_weather.py` | NWS `api.weather.gov`: point lookup, latest station observation, hourly forecast | Built (T043) |
| Flood alerts | `nws_alerts.py` | NWS active alerts: Flood Warning, Flash Flood Warning, Flood Watch | Built (T043A) |
| Lightning, hurricanes, earthquakes, flood gauges | Braydin's adapters | See `spec.md` section 5 | Planned (T045–T045D) |

Freshness (`cache.py`, T044): each feed keeps its own cache of the last successful readings per site.

- A failed refresh returns those readings marked `stale`.
- Readings older than `FEED_STALE_AFTER_MINUTES` (default 60) are `stale`.
- After `FEED_UNAVAILABLE_AFTER_MINUTES` (default 360), or when nothing was ever fetched, the feed reports `unavailable`.
- A stale or unavailable feed is never shown as current, and it never clears an alert.

Configuration: set `NWS_USER_AGENT` in `backend/.env`. NWS requires an identifying User-Agent, and without one the NWS feeds report `unavailable`.

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

## Quality checks

Run these before opening a pull request. All must pass.

| Area | Command (run from) | What it does |
|---|---|---|
| Backend lint | `ruff check .` (`backend/`) | Lint with Ruff (pyflakes, pycodestyle, import order, bugbear, pyupgrade) |
| Backend format | `ruff format --check .` (`backend/`) | Check formatting. Run `ruff format .` to fix. |
| Backend tests | `pytest` (`backend/`) | Unit tests, including contract and TS-mirror checks |
| Frontend lint | `npm run lint` (`frontend/`) | Lint with oxlint |
| Frontend type check and build | `npm run build` (`frontend/`) | `tsc -b` type check, then Vite production build |

Ruff and pytest settings live in `backend/pyproject.toml`. The frontend has no separate formatter configured.

