#!/usr/bin/env bash
# Ship the current commit to the server (T080, T082). Run from the repo root on a laptop
# that has backend/.env and frontend/.env.local:
#   deploy/deploy.sh root@SERVER
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

echo "Building the frontend (live API, same origin)..."
(cd frontend && VITE_API_BASE_URL= VITE_USE_FIXTURES=false npm run build >/dev/null)

echo "Shipping $(git rev-parse --short HEAD)..."
ssh "$SERVER" 'rm -rf /srv/foresite/app.next && mkdir -p /srv/foresite/app.next'
git archive --format=tar HEAD | ssh "$SERVER" 'tar -x -C /srv/foresite/app.next'
# The gitignored model artifact (ml/artifacts/provisioned_v2) goes with the code.
tar -c -C "$ROOT" ml/artifacts/provisioned_v2 | ssh "$SERVER" 'tar -x -C /srv/foresite/app.next'
tar -c -C "$ROOT/frontend/dist" . | ssh "$SERVER" 'rm -rf /srv/foresite/frontend.next && mkdir -p /srv/foresite/frontend.next && tar -x -C /srv/foresite/frontend.next'

ssh "$SERVER" 'bash -s' <<'REMOTE'
set -euo pipefail
cd /srv/foresite
# Keep the server's .env across deploys.
[ -f app/backend/.env ] && cp -p app/backend/.env app.next/backend/.env
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
systemctl restart foresite-api
echo "deployed; previous version kept in app.prev and frontend.prev"
REMOTE
