# Frontend run and integration guide

Current split: Codex/Cache owns functionality; Claude is actively redesigning pages/components/styles. See docs/FUNCTIONAL_INTEGRATION_HANDOFF.md before changing shared interfaces. Nick's earlier attribution is preserved. T030's layout/navigation is retained. This is one React/Vite/Tailwind application using one shared client interface; no API server or authentication implementation was added.

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
3. **Supervisor:** switch workspace; open the map/list, use filters, and open the Everglades simulated site. Review an absent report, or confirm a present report's relevant potential notice, write/edit an instruction and send it. Switch back to Crew to see that approved instruction. These operations change only the isolated browser demo.
4. Open Briefings: the latest stored site fixture loads automatically. Choose Organization briefings to inspect the archived Gemini and template examples. Review evidence, forecast window and unknowns. These texts are read-only, not regenerated after demo mutations, and are not current employer instructions.
5. In supervisor locations, **Flood advisory replay** opens `eia860m-FL-59611`; **Wind advisory replay** opens `eia860m-AZ-68414`. Inspect the 2.1 research event persistence, duration, accepted/rejected site evidence, source times and explicit unverified worker hazards. Other sites report no supported outlook; they never borrow these probabilities.

Demo state is stored only in `planit:frontend-demo:v1`. Reset demo restores this namespace without deleting Auth0 or unrelated storage. Photos are object URLs in memory and disappear on reload; the report does not claim durable photo storage. Corrupt/oversized saved demo data resets locally; blocked/full storage reports that mutations are memory-only. Never use real private photos or personal information in this public demonstration.

## Data and map provenance

- Five canonical simulated sites, alerts, reports, notices and briefings are read unchanged from Rudra's generated `src/fixtures/*.json` using `src/types/api.ts`.
- Fifty EIA reference plants use the reconciled `eia860m-{state}-{plant_id}` identities and coordinates from the existing ML/backend-selector export. They are not verified active worksites and have null scores/timestamps and no supplied live observations. Demo organization/team assignments apply to the canonical simulated examples, not all reference plants.
- `src/demo/generated/references.json` and `advisories.json` are committed exports of approved ML fixtures. Rebuild only after checking source changes, from repository root with the documented ML Python environment:

```powershell
python frontend/scripts/export-demo-sources.py
```

The exporter checks existing source hashes and validates both comprehensive 2.1 responses. It does not collect new data, run Python in the browser, retrain or require model weights. Event activations are hypothetical/replays; individual environmental source captures retain their original method/time provenance. The underlying package previously qualified local environmental readings at only 2/50 sites and official notices at 10/50; this UI does not imply full live coverage.

The map uses [Leaflet](https://leafletjs.com/examples/quick-start/) with actual geographic coordinates, an offline graticule and equivalent linked location list. Pan, zoom and point popups work offline. An explicit checkbox enables the online OpenStreetMap basemap, with attribution and a tile-failure message; network is required. Follow the [OSM tile policy](https://operations.osmfoundation.org/policies/tiles/): no offline tile downloading/prefetch, preserve attribution and normal browser caching. Default demo acceptance makes no tile requests.

Legacy canonical fixture scores containing a `model` factor are withheld and excluded from demonstration ranking; raw JSON remains unchanged. The frontend does not recalculate scores. Approved server scores in real mode are supplied by Rudra. Unknown scores, timestamps and unsupported local hazard probabilities remain unknown/null.

## Real Auth0/API mode

Current setup, redacted readiness command and real-account criteria: [LIVE_INTEGRATION.md](LIVE_INTEGRATION.md). PR #24 and T067A PR #27 merged during this run; T065 continues from reviewed main `dcd9fc5` on `feature/cache-report-lifecycle-integration`. Earlier foundation records remain historical.

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

The shared `HttpClient` uses canonical multipart `ReportCreate` and published response types. Stored briefings are read with `GET /api/sites/{id}/briefing` and `GET /api/briefings`. Site 404 is an empty scheduled-briefing state; other errors stay errors. There is no browser scheduler or generation action. `StoredBriefings.tsx` separates display from transport and labels Gemini versus deterministic template results. The deterministic factor breakdown remains in site detail.

T065 enables the reviewed report lifecycle capabilities. A present report needs a photo in real mode and stays pending until its notice is confirmed; its report card links to the site notices. An absent report uses the reporting-organization supervisor review route. Confirmation validates `HazardConfirmResponse`, reads the returned notice and shows an unsent server draft or empty manual field. Only the confirming session sees the editor; FastAPI enforces actual authority. Send explicitly accepts/edits 1-500 nonblank characters and validates the returned `HazardNotice`. Shared refresh reloads sites, reports and notices; no score is computed in React. Refreshing the same notice preserves the edited draft. Conflicts refresh ownership, and no operation is automatically retried. A timeout has an unknown outcome: refresh before resubmitting.

Demo confirmation now marks its matching present report confirmed; the absent review route refuses present reports. Duplicate review/confirmation/send conflicts are explicit. Demo scores remain static fixture payloads, not a new score implementation. The isolated mocked HTTP tests additionally supply a changed server score and persisted fixture delivery to verify the shared views; they are not real backend acceptance. Private photo retrieval is still unconnected; photos are never fetched from an arbitrary returned URL.

`401`, `403`, `404`, `409`, `422`, `503`, invalid JSON, token acquisition failure, request timeout and network failure have explicit UI outcomes. Live failure never switches to fixtures. Missing Auth0 settings show the existing provider's unconfigured sign-in state. Missing Tiger Data configuration remains a service blocker, not permission for a local database or bypass. Live lists/details share the same view components as demos; authenticated successful real data is not yet verified locally.

Main's T050 compact field was published in `9d73a77`. PR #16/#17 merged during implementation, so this follow-on branch targets main and incorporates it without altering Rudra's canonical schemas/fixtures/type mirror. `src/api/contracts.ts` now reuses the canonical `SiteDetail` directly. Comprehensive 2.1 is demo-only: no approved authenticated live endpoint exists. Rudra must publish one before it is connected; no guessed endpoint was added.

## Checks and module boundaries

From `frontend/`, with Vite running for the browser check:

```powershell
npm run lint
npm run build
node --test --test-concurrency=1 tests/status.test.mjs tests/data.test.mjs tests/integration.test.mjs tests/briefings.test.mjs tests/lifecycle.test.mjs tests/live-read.test.mjs
node scripts/check-shell.mjs http://localhost:5173/
```

Build includes TypeScript. The combined suite has 68 focused checks (56 prior plus 12 read/ack and diagnostic regressions); the latter are labeled mock transport tests, not real Auth0/Tiger Data acceptance. Browser acceptance uses Node 24's built-in WebSocket and installed headless Edge/Chromium, with isolated profiles, temporary loopback configuration-test servers and screenshots under ignored `.shell-check/`. Set `SHELL_BROWSER` to an installed Chromium path when not using Windows Edge. It leaves the original Vite server running. `tests/browser.html` is a mocked-provider/HTTP test entry and is not a production build input or Auth0 verification.

For the built demo, run `npm run preview -- --host localhost --port 5174 --strictPort` in a second terminal after building, then `node scripts/check-shell.mjs http://localhost:5174/ --production`. This exercises the same demo lifecycle against static production assets and verifies that the mocked auth harness is absent; compile-time mode/provider tests run only against the development server. A fresh committed frontend export at `4a9e44f`, with no `.env`, cache, Python or model artifacts copied, passed `npm ci`, build and this full production-bundle browser check. The existing Auth0 dependency's postinstall allowScripts warning did not prevent installation/build; npm reported zero known vulnerabilities at that check.

The browser run exercises crew and supervisor lifecycles, 55 points, three viewports, all ten destinations, >=44px primary controls, keyboard skip/visible focus, source labels, API failures and no silent samples. These tests do not certify WCAG compliance, actual worker safety, server persistence or real tenant roles. See `docs/frontend-acceptance.json` and `docs/INTEGRATION_STATUS.md` for exact results and unchecked integration tasks.

Data access lives in `src/api/`; simulated persistence in `src/demo/`; session/composition and async resource lifecycle in `src/application/`; reusable display in `src/components/data/`; navigation in `components/shell/`; page composition in `pages/ConnectedPages.tsx`. The [redesign handoff](../docs/FRONTEND_REDESIGN_HANDOFF.md) describes safe visual changes.
