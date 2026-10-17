# planit-control-swamphacks

Swamphacks 2026 Official Repository

React + TypeScript UI, built with Vite and Tailwind CSS. API routes, auth checks, scoring, alerts, and Gemini calls run in a separate FastAPI app under `backend/app/`. Auth0 is the identity provider. Tiger Data is the application database. Vultr hosts the app and stores crew photos. Auth0, Tiger Data, and Vultr are sponsors for tracks. Many organizations share one deployment. A supervisor manages every team in one organization. The supervisor list shows every location and its assigned team, with occupied locations first. A detected hazard, or a crew member marking one present, sends “potential {hazard}” with no instructions to teams and supervisors inside a radius chosen by Gemini. If Gemini is unresponsive, the notice uses that category’s default radius. Any notified supervisor can confirm it, edit Gemini’s suggested instruction, and send that instruction to the teams inside the radius. The reporting organization’s supervisor still decides when a crew member reports that no hazard is present.

## Layout

| Path | Contents | Owner |
|---|---|---|
| `frontend/` | Vite + React + TypeScript + Tailwind UI | Nick (`src/pages`, `src/components`, `src/styles`, `src/api`), Braydin (`src/auth`) |
| `frontend/src/types/api.ts` | TypeScript mirror of the API schemas | Rudra |
| `frontend/src/fixtures/` | Mock API responses for fixture mode (generated) | Rudra |
| `backend/app/` | FastAPI app and every API route | Rudra (except `backend/app/security/`, `backend/app/db/`, `backend/app/ingestion/`, and `backend/app/gemini/`, owned by Braydin) |
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

