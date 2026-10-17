# Frontend run and integration guide

Cache owns this implementation following the user's 2026-10-17 transfer from Nick. T030's layout/navigation is retained. This is one React/Vite/Tailwind application using one shared client interface; no API server or authentication implementation was added.

## Run the interactive demo

Install Node 24, then from repository root:

```powershell
cd frontend
npm ci
npm run dev -- --host localhost --port 5173 --strictPort
```

Open http://localhost:5173/. No Python setup, ignored ML model artifact, API credential or database is needed for this frontend demo. If a previous `.env.local` sets `VITE_USE_FIXTURES=false`, set it to `true` and restart Vite. Unset/`true` means demo; `false` means Auth0/API; any other value displays a configuration error. Production builds also default to explicitly labeled demo unless configured. Demo JSON is public bundled material, never a location for private records or secrets.

1. **Crew:** open Overview, inspect the active alert, record a simulated acknowledgement, and reload to see persistence. In Alerts, replay another server strike or an explicitly cleared payload. Countdown expiry alone never clears an alert.
2. Open Reports. Choose category and present/absent; coordinates start at the reference site and are editable. Add an optional JPEG/PNG/WebP (maximum 5 MB); leave the note empty and submit. The new report is pending, and a present report creates a potential notice with no instructions.
3. **Supervisor:** switch workspace; open the map/list, use filters, and open the Everglades simulated site. Review the new report's classification, confirm its relevant potential notice, write/edit an instruction and send it. Switch back to Crew to see that approved instruction. These operations change only the isolated browser demo.
4. Open Briefings for the Everglades simulated site. Request the prerecorded Gemini example, then select the deterministic fallback checkbox and request again. Review evidence, time window and unknowns. These canonical historical texts are not regenerated after demo mutations and are not current employer instructions.
5. In supervisor locations, **Flood advisory replay** opens `eia860m-FL-59611`; **Wind advisory replay** opens `eia860m-AZ-68414`. Inspect the 2.1 research event persistence, duration, accepted/rejected site evidence, source times and explicit unverified worker hazards. Other sites report no supported outlook; they never borrow these probabilities.

Demo state is stored only in `planit:frontend-demo:v1`. Reset demo restores this namespace without deleting Auth0 or unrelated storage. Photos are object URLs in memory and disappear on reload; the report does not claim durable photo storage. Corrupt/oversized saved demo data resets locally; blocked/full storage reports that mutations are memory-only. Never use real private photos or personal information in this public demonstration.

## Data and map provenance

- Five canonical simulated sites, alerts, reports, notices, briefings and explanations are read unchanged from Rudra's generated `src/fixtures/*.json` using `src/types/api.ts`.
- Fifty EIA reference plants use the reconciled `eia860m-{state}-{plant_id}` identities and coordinates from the existing ML/backend-selector export. They are not verified active worksites and have null scores/timestamps and no supplied live observations. Demo organization/team assignments apply to the canonical simulated examples, not all reference plants.
- `src/demo/generated/references.json` and `advisories.json` are committed exports of approved ML fixtures. Rebuild only after checking source changes, from repository root with the documented ML Python environment:

```powershell
python frontend/scripts/export-demo-sources.py
```

The exporter checks existing source hashes and validates both comprehensive 2.1 responses. It does not collect new data, run Python in the browser, retrain or require model weights. Event activations are hypothetical/replays; individual environmental source captures retain their original method/time provenance. The underlying package previously qualified local environmental readings at only 2/50 sites and official notices at 10/50; this UI does not imply full live coverage.

The map uses [Leaflet](https://leafletjs.com/examples/quick-start/) with actual geographic coordinates, an offline graticule and equivalent linked location list. Pan, zoom and point popups work offline. An explicit checkbox enables the online OpenStreetMap basemap, with attribution and a tile-failure message; network is required. Follow the [OSM tile policy](https://operations.osmfoundation.org/policies/tiles/): no offline tile downloading/prefetch, preserve attribution and normal browser caching. Default demo acceptance makes no tile requests.

Legacy canonical fixture scores containing a `model` factor are withheld and excluded from demonstration ranking; raw JSON remains unchanged. The frontend does not recalculate scores. Approved server scores in real mode are supplied by Rudra. Unknown scores, timestamps and unsupported local hazard probabilities remain unknown/null.

## Real Auth0/API mode

Phase-4 current setup, redacted readiness command, private real-account checker and per-task browser criteria: [LIVE_INTEGRATION.md](LIVE_INTEGRATION.md). PR #19 is now merged; the continuation incorporates main `9ba1b7c` and T053 report list/create. The earlier foundation validation below remains historical evidence.

Set the existing public values in `frontend/.env.local` using `auth/SETUP.md`, then restart Vite:

```dotenv
VITE_USE_FIXTURES=false
VITE_API_BASE_URL=
VITE_AUTH0_DOMAIN=<public tenant domain>
VITE_AUTH0_CLIENT_ID=<public SPA client id>
VITE_AUTH0_AUDIENCE=<matching backend API audience>
VITE_DEV_AUTH_ROLE=
```

Configure the actual Auth0 application callback/logout URLs for localhost:5173 as Braydin documents. The application imports `AuthProvider`, `RequireRole` and `useAuth()` from `src/auth/`. It only accepts real `auth0` mode, rejects development bypass roles and obtains a bearer token per request. No crew/supervisor preview selector exists in live mode. Session subject/role transitions remount application state; frontend URL changes cannot grant a different role or site assignment. The backend must independently authorize every request.

An empty API base uses same-origin `/api`. Vite proxies it to the existing FastAPI at `127.0.0.1:8000`; start that backend using its own documented environment. An absolute API base requires owner-configured CORS. Production hosting must route `/api` to FastAPI; Vite's development proxy is not deployment configuration. HTTP is allowed only for loopback; remote APIs require HTTPS. No tokens are stored by the demo client and no redirects or fake development-role headers are sent.

The shared `HttpClient` supports published canonical request types and routes, multipart `ReportCreate` with `photo`, review/confirmation/instruction bodies, briefing/explanation and the separately published optional T050 `event_outlook`. Verified main `9ba1b7c` publishes site reads, T048 alert listing/acknowledgement and T053 report listing/create. The client requests `state=all`, enables acknowledgement only for active alerts, and refreshes shared views after the server responds. Response Date headers correct the display clock estimate; an elapsed countdown still cannot change server state. `capabilities.reports` now enables published list/create. Separate `.reviewReports`, `.hazards` and `.ai` remain false until review/confirmation/instruction/Gemini routes are published and tested. Live present reports require a photo; absent reports do not. Enable each deliberately after owner review. There is no automatic POST retry.

`401`, `403`, `404`, `409`, `422`, `503`, invalid JSON, token acquisition failure, request timeout and network failure have explicit UI outcomes. Live failure never switches to fixtures. Missing Auth0 settings show the existing provider's unconfigured sign-in state. Missing Tiger Data configuration remains a service blocker, not permission for a local database or bypass. Live lists/details share the same view components as demos; authenticated successful real data is not yet verified locally.

Main's T050 compact field was published in `9d73a77`. PR #16/#17 merged during implementation, so this follow-on branch targets main and incorporates it without altering Rudra's canonical schemas/fixtures/type mirror. `src/api/contracts.ts` now reuses the canonical `SiteDetail` directly. Comprehensive 2.1 is demo-only: no approved authenticated live endpoint exists. Rudra must publish one before it is connected; no guessed endpoint was added.

## Checks and module boundaries

From `frontend/`, with Vite running for the browser check:

```powershell
npm run lint
npm run build
node --test --test-concurrency=1 tests/status.test.mjs tests/data.test.mjs tests/integration.test.mjs
node scripts/check-shell.mjs http://localhost:5173/
```

Build includes TypeScript. The focused suite now has 39 tests (23 foundation and 16 integration-orchestration tests); the latter are labeled mock transport tests, not real Auth0/Tiger Data acceptance. Browser acceptance uses Node 24's built-in WebSocket and installed headless Edge/Chromium, with isolated profiles, temporary loopback configuration-test servers and screenshots under ignored `.shell-check/`. Set `SHELL_BROWSER` to an installed Chromium path when not using Windows Edge. It leaves the original Vite server running. `tests/browser.html` is a mocked-provider/HTTP test entry and is not a production build input or Auth0 verification.

For the built demo, run `npm run preview -- --host localhost --port 5174 --strictPort` in a second terminal after building, then `node scripts/check-shell.mjs http://localhost:5174/ --production`. This exercises the same demo lifecycle against static production assets and verifies that the mocked auth harness is absent; compile-time mode/provider tests run only against the development server. A fresh committed frontend export at `4a9e44f`, with no `.env`, cache, Python or model artifacts copied, passed `npm ci`, build and this full production-bundle browser check. The existing Auth0 dependency's postinstall allowScripts warning did not prevent installation/build; npm reported zero known vulnerabilities at that check.

The browser run exercises crew and supervisor lifecycles, 55 points, three viewports, all ten destinations, >=44px primary controls, keyboard skip/visible focus, source labels, API failures and no silent samples. These tests do not certify WCAG compliance, actual worker safety, server persistence or real tenant roles. See `docs/frontend-acceptance.json` and `docs/INTEGRATION_STATUS.md` for exact results and unchecked integration tasks.

Data access lives in `src/api/`; simulated persistence in `src/demo/`; session/composition and async resource lifecycle in `src/application/`; reusable display in `src/components/data/`; navigation in `components/shell/`; page composition in `pages/ConnectedPages.tsx`. The [redesign handoff](../docs/FRONTEND_REDESIGN_HANDOFF.md) describes safe visual changes.
