# Deploying FORESITE on Vultr

One Vultr server runs everything: Caddy serves the built frontend and HTTPS, and proxies
`/api/*` and `/health` to the FastAPI backend (uvicorn, systemd). The database stays on
Tiger Data and identity on Auth0. Crew photos go to Vultr Object Storage.

| Piece | Where |
|---|---|
| Server | Vultr Cloud Compute `foresite`, Atlanta, shared CPU, 2 vCPU / 4 GB, Ubuntu 24.04 |
| Firewall | Vultr group `foresite-web` (22, 80, 443) plus ufw on the server |
| Address | `https://foresiteoperations.org` and `www.` (GoDaddy A/CNAME records, set up by Cache); `https://64-177-53-1.sslip.io` stays as a backup |
| Photos | Vultr Object Storage `foresite-photos` (Atlanta), private bucket `foresite-photos` |
| Backend | `/srv/foresite/app`, venv `/srv/foresite/venv` (Python 3.14 via uv), unit `foresite-api` |
| Frontend | `/srv/foresite/frontend` (Vite build, live API, same origin) |
| Secrets | `/srv/foresite/app/backend/.env`, mode 600, owned by `foresite`. Never committed. |

## Server `.env`

Start from `backend/.env.example` and fill every value. Production differences:

- `CORS_ALLOWED_ORIGINS=https://<site address>` (the browser calls the same origin, so CORS is
  normally unused)
- `DEV_AUTH_BYPASS=false`
- `FEED_REFRESH_ENABLED=true` and `BRIEFING_SCHEDULE_ENABLED=true` **on this server only**.
  Every laptop sharing the Tiger database sets both to `false`.
- `PHOTO_LOCAL_DIR=/srv/foresite/photos`
- `USGS_HTTP_CONNECTIONS=4`, `FLOOD_GAUGE_BATCH_DEGREES=1`, `FEED_ROUND_BUDGET_SECONDS=900`: USGS
  takes about 9 s per box, and with the defaults the gauge feed hit the 480 s round budget
  with about two thirds of sites unfetched. Still well inside the 60-minute stale window.
- `VULTR_OBJECT_STORAGE_ENDPOINT`, `_ACCESS_KEY`, `_SECRET_KEY`, `_BUCKET` from the Object
  Storage subscription (`vultr-cli object-storage get <id>`).

Write it over SSH without printing it, then `chmod 600` and `chown foresite:foresite`.

## First-time setup

```bash
ssh root@SERVER 'bash -s' < deploy/setup.sh       # Caddy, uv + Python 3.14, user, ufw 80/443
scp deploy/foresite-api.service root@SERVER:/etc/systemd/system/
scp deploy/Caddyfile root@SERVER:/etc/caddy/Caddyfile
ssh root@SERVER 'mkdir -p /etc/systemd/system/caddy.service.d &&
  printf "[Service]\nEnvironment=\"SITE_ADDRESS=64-177-53-1.sslip.io\"\n" > /etc/systemd/system/caddy.service.d/site.conf &&
  systemctl daemon-reload && systemctl enable foresite-api && systemctl restart caddy'
```

## Automatic deploys (GitHub Actions)

Every push to `main` runs `.github/workflows/deploy.yml`: backend tests and lint, the
frontend type check and tests, then `deploy/deploy.sh` and a live check of `/health` and
`/api/sites` (401). Teammates only merge to `main`; nobody needs server access.

- Watch a deploy: GitHub → Actions → Deploy. Rerun or deploy by hand: "Run workflow".
- A failing test stops the deploy. If the new version fails its health check on the server,
  `deploy.sh` rolls back to the previous version.
- Secrets: `DEPLOY_HOST`, `DEPLOY_SSH_KEY` (a key used only by Actions,
  `github-actions-deploy@foresite` in the server's `authorized_keys`), `DEPLOY_KNOWN_HOSTS`.
  Variables: `VITE_AUTH0_DOMAIN`, `VITE_AUTH0_CLIENT_ID`, `VITE_AUTH0_AUDIENCE` (public).
- CI doesn't have the gitignored model artifact, so the server keeps the one it has. Ship a
  new model from a laptop with `deploy/deploy.sh`.
- Revoke: delete the `github-actions-deploy@foresite` line from `/root/.ssh/authorized_keys`
  and the `DEPLOY_SSH_KEY` secret.

## Deploy a commit by hand

From a clean checkout with `backend/.env`-independent `frontend/.env.local` (public Auth0 SPA
values) and the provisioned model in `ml/artifacts/provisioned_v2`:

```bash
deploy/deploy.sh root@SERVER
```

It builds the frontend, ships `HEAD` with `git archive` plus the gitignored model artifact,
keeps the server `.env`, installs requirements pinned by `deploy/constraints.txt`, applies
missing database columns (`python -m app.db.init`), and restarts the API. The previous version stays in `app.prev` / `frontend.prev`.

**Roll back:** `ssh root@SERVER 'cd /srv/foresite && mv app app.bad && mv app.prev app && mv frontend frontend.bad && mv frontend.prev frontend && systemctl restart foresite-api'`

## Add a custom domain

1. DNS: an A record for the subdomain pointing to the server IP (GoDaddy → DNS → Add record).
2. Add it to `SITE_ADDRESS`, comma-separated, e.g.
   `SITE_ADDRESS=64-177-53-1.sslip.io, app.example.com`, then `systemctl daemon-reload &&
   systemctl restart caddy`. Caddy gets the certificate on its own.
3. Add `https://app.example.com` to the server `CORS_ALLOWED_ORIGINS` and to Auth0 (below),
   then `systemctl restart foresite-api`.

## Auth0 (T081)

Auth0 dashboard → Applications → the SPA → Settings → Application URIs. Keep the localhost
entries and add, for each site address:

- Allowed Callback URLs: `https://<address>`
- Allowed Logout URLs: `https://<address>`
- Allowed Web Origins: `https://<address>`

## Operate

```bash
ssh root@SERVER 'journalctl -u foresite-api -f'      # backend log (feed rounds, briefings)
ssh root@SERVER 'systemctl status foresite-api caddy'
```

## Demo sites stay current

Live feeds skip demo sites (`location_type="demo_site"`). Beside the feed loop, the server
slides every demo site forward in time every `FEED_REFRESH_SECONDS` (`app/demo/freshen.py`):
readings, lightning timers, notices, confirmations, crew reports and acknowledgements all
move by the same amount, so the pages read as just seeded ("strike 6 min ago", stop-work
still counting down, never "Stale"), and scores stay the same. Real sites are never touched.
It runs with the feed loop, so only where `FEED_REFRESH_ENABLED=true`.

- Seed or reset the demo from a laptop:
  `cd backend && PYTHONPATH=.. .venv/bin/python -m app.demo anomalies`. Reseeding clears the
  anomaly sites' briefings until the next 6 PM run.
- Slide once by hand: `python -m app.demo freshen`.
- Log lines: `demo_freshened` (sites moved, minutes) and `demo_freshen_failed` (one site rolled
  back; the live feed round is unaffected).

## Tear down after the hackathon

Destroy the instance and the Object Storage subscription in Vultr (stopped servers still
bill), delete the Vultr API key, and remove the deployed URLs from Auth0.
