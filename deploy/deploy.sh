#!/usr/bin/env bash
# Ship the current commit to the server (T080, T082). Run from the repo root:
#   deploy/deploy.sh root@SERVER
# GitHub Actions runs it on every push to main (.github/workflows/deploy.yml). The public
# Auth0 SPA values come from frontend/.env.local on a laptop, or VITE_AUTH0_* in CI.
# Secrets travel over SSH only. Nothing here prints them.
set -euo pipefail
# Keep macOS file metadata out of the tarballs.
export COPYFILE_DISABLE=1
SERVER="${1:?usage: deploy/deploy.sh root@SERVER}"
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "Commit or stash changes first; the deploy ships HEAD." >&2
  exit 1
fi

for name in VITE_AUTH0_DOMAIN VITE_AUTH0_CLIENT_ID VITE_AUTH0_AUDIENCE; do
  if [ -z "${!name:-}" ] && ! grep -qE "^${name}=.+" frontend/.env.local 2>/dev/null; then
    echo "$name is not set; the deployed site couldn't sign anyone in." >&2
    exit 1
  fi
done

echo "Building the frontend (live API, same origin)..."
(cd frontend && VITE_API_BASE_URL= VITE_USE_FIXTURES=false npm run build >/dev/null)

echo "Shipping $(git rev-parse --short HEAD)..."
ssh "$SERVER" 'rm -rf /srv/foresite/app.next && mkdir -p /srv/foresite/app.next'
git archive --format=tar HEAD | ssh "$SERVER" 'tar -x -C /srv/foresite/app.next'
# The model artifact (ml/artifacts/provisioned_v2) is gitignored. A laptop that has it ships
# it; otherwise (CI) the server keeps the one it already has.
if [ -f ml/artifacts/provisioned_v2/active_event.joblib ]; then
  tar -c -C "$ROOT" ml/artifacts/provisioned_v2 | ssh "$SERVER" 'tar -x -C /srv/foresite/app.next'
fi
tar -c -C "$ROOT/frontend/dist" . | ssh "$SERVER" 'rm -rf /srv/foresite/frontend.next && mkdir -p /srv/foresite/frontend.next && tar -x -C /srv/foresite/frontend.next'

ssh "$SERVER" 'bash -s' <<'REMOTE'
set -euo pipefail
cd /srv/foresite
# Keep the server's .env and, when this deploy didn't ship one, its model artifact.
[ -f app/backend/.env ] && cp -p app/backend/.env app.next/backend/.env
if [ ! -d app.next/ml/artifacts/provisioned_v2 ] && [ -d app/ml/artifacts/provisioned_v2 ]; then
  mkdir -p app.next/ml/artifacts
  cp -rp app/ml/artifacts/provisioned_v2 app.next/ml/artifacts/provisioned_v2
fi
if [ ! -f app.next/ml/artifacts/provisioned_v2/active_event.joblib ]; then
  echo "The model artifact is missing; deploy once from a laptop that has ml/artifacts." >&2
  exit 1
fi
rm -rf app.prev frontend.prev
[ -d app ] && mv app app.prev
[ -d frontend ] && mv frontend frontend.prev
mv app.next app
mv frontend.next frontend
chown -R foresite:foresite /srv/foresite
chmod 711 /srv/foresite
chmod -R a+rX /srv/foresite/frontend
chmod 600 app/backend/.env
UV_PYTHON_INSTALL_DIR=/srv/foresite/python VIRTUAL_ENV=/srv/foresite/venv \
  uv pip install --quiet -r app/backend/requirements.txt -c app/deploy/constraints.txt
# Apply missing tables, columns and hypertables to Tiger before the new code starts. It only
# adds what's missing, so it's safe to run on every deploy.
(cd app/backend && sudo -u foresite env PYTHONPATH=.. /srv/foresite/venv/bin/python -m app.db.init)
systemctl restart foresite-api

# Roll back on its own if the new version doesn't come up healthy.
for _ in $(seq 1 30); do
  curl -fsS -m 3 http://127.0.0.1:8000/health >/dev/null 2>&1 && break
  sleep 2
done
if ! curl -fsS -m 3 http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "New version failed its health check; rolling back." >&2
  journalctl -u foresite-api --no-pager -n 30 >&2
  rm -rf app.bad frontend.bad
  mv app app.bad && mv app.prev app
  mv frontend frontend.bad && mv frontend.prev frontend
  systemctl restart foresite-api
  exit 1
fi
echo "deployed; previous version kept in app.prev and frontend.prev"
REMOTE
