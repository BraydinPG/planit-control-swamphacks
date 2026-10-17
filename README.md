# planit-control-swamphacks

Swamphacks 2026 Official Repository

React + TypeScript UI, built with Vite and Tailwind CSS. API routes, auth checks, scoring, alerts, and Gemini calls run in a separate FastAPI app under `backend/app/`.

## Layout

| Path | Contents | Owner |
|---|---|---|
| `frontend/` | Vite + React + TypeScript + Tailwind UI | Nick (`src/pages`, `src/components`, `src/styles`, `src/api`), Braydin (`src/auth`) |
| `backend/app/` | FastAPI app and every API route | Rudra (except `backend/app/security/`, owned by Braydin) |
| `backend/tests/` | Backend tests | Rudra |
| `ml/` | Model training, prediction, evaluation | Cache |
| `auth/` | Auth0 setup notes | Braydin |

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

