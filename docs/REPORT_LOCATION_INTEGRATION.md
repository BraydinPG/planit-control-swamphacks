# T034A report location: implementation and remaining integration

Verified 2026-10-17. Branch `feature/cache-report-device-location` starts at merged main
`681582be17315444f5ed9785c15f0fb37e8c09eb`. PR #33 is merged (`a54b87e`); no unmerged
parent dependency. Work is isolated in `C:/Users/cache/planit-control-functional`.
Implementation `cc7b86b99c2327b6459cad6bebd1828c172c5f4a` is published in
[PR #34](https://github.com/BraydinPG/planit-control-swamphacks/pull/34), open for review;
no automatic merge or operational activation.

**T034A remains unchecked.** T034 is checked; T053A is unchecked and not published in
`backend/app/schemas/reports.py`, `frontend/src/types/api.ts`, or report persistence.
The new hook/controller are tested but intentionally **not connected to ReportForm**.
Current reports still use the existing canonical latitude/longitude-only transport.
No new metadata is sent, discarded, or claimed persisted. Claude's form/layout/styles,
Rudra's schemas/routes/fixtures, Braydin's database/auth, and all task states are untouched.

## Ready for Claude

```tsx
import { useReportLocation } from '../application/useReportLocation'

// In ReportForm, or a controller mounted only for that workflow:
const reportLocation = useReportLocation(reportOpen ? site : null, client.mode)
const point = reportLocation.location
// Display reportLocation.message in an accessible status area.
// point is immediately the site's approximate location, even while locating.
// Manual inputs: valueAsNumber, NOT Number('') (which incorrectly becomes zero).
// reportLocation.setPin(latInput.valueAsNumber, lonInput.valueAsNumber)
```

The site input is the canonical `{id, lat, lon}` subset of SiteSummary. Pass `null`
outside the report. The existing `<ReportForm key={site.id}>` can remain; the hook also
handles changes without remounting. Keep typed coordinate drafts separate from accepted
coordinates so empty/invalid edits are visible. Call `setPin` on every edit with both
values, using `NaN` for an unfinished field. A valid pin clears device accuracy and
invalidates pending GPS. An invalid edit also invalidates GPS and returns `false` with
`location=null`; do not silently submit the previous point. After correcting the fields,
the source becomes `pin`. Re-selecting a site resets the point; late old-site callbacks
and retained old-session handlers cannot change the new report.

| State | Coordinates / presentation | Submission once T053A exists |
| --- | --- | --- |
| `closed` | No location retained | No report action |
| `locating` | Site coordinates, **approximate**, accuracy unknown | Immediately eligible; never wait for GPS |
| `device` | Device coordinates and reported accuracy in meters | Source `device`; accuracy is an estimate, not proof of hazard/location validity |
| `site` | Site coordinates, **approximate**, accuracy unknown; reason displayed | Source `site`; accuracy null |
| `pin` | Worker-adjusted coordinates; device accuracy cleared | Source `pin`; accuracy null |
| `unavailable` | No valid coordinates; invalid site or unfinished/invalid pin | Require valid coordinates, not a GPS fix or note |

Live mode performs one browser `getCurrentPosition` request per opening/site change,
with `enableHighAccuracy=true`, `maximumAge=0` and an 8-second timeout. The controller
also enforces its own deadline when the permission prompt stays unanswered. Denied,
unsupported, unavailable, timeout, provider exception, invalid coordinates or invalid
accuracy all keep the approximate site fallback. Finite latitude/longitude must be within
[-90,90]/[-180,180]; finite accuracy must be >=0. There is no invented accuracy cutoff.
React StrictMode's discarded effect does not issue a duplicate request.

Closing/unmounting clears the timer and all controller coordinates; callbacks are ignored.
The browser API cannot cancel an already outstanding one-shot acquisition/prompt; this
code does not use its eventual result after close. There is no watch, retry loop,
background service, storage, logging, fetch, photo analysis, or Gemini call in this logic.
Deployment needs the browser's normal secure-context/location permissions; no permission
or authentication bypass is added.

**Demo privacy:** `mode='demo'` never requests real device coordinates and explicitly
labels the fixture site fallback. The current DemoClient persists submitted reports in
its existing localStorage namespace, so do not wire real GPS into that client. The
location hook itself never writes storage, including manual points. If a future demo
collects personal/manual real positions, keep the report session in memory rather than
passing them to the persistent demo client. Synthetic device cases exist only in test
providers; they are not actual employee locations or authenticated integration evidence.

## Rudra / Braydin T053A gate

Rudra publishes `location_source` (`device|site|pin`) and optional
`location_accuracy_m` on ReportCreate, CrewReport, the multipart route, TS mirror, and
generated fixtures; also publish the backend-computed site-distance field and unit.
Braydin supplies the idempotent database column migration/persistence. Do not compute
site distance in this hook or guess its future field name/unit. Preserve compatible
legacy requests and validate contradictory metadata according to the owner contract.

Only after that publication, map one **immutable snapshot** at submit time:

```text
point.lat       -> lat
point.lon       -> lon
point.source    -> location_source
point.accuracyM -> location_accuracy_m (null for site/pin; no invented precision)
```

Extend the existing HttpClient/validateReport against those published types; validate
the returned coordinates/source/accuracy and backend-computed distance. Do not coerce a
device point into a legacy latitude/longitude-only request. Extend DemoClient/mock
fixtures only against the published contract. These are owner handoffs, not new API
definitions. No transport change is part of this PR. Never send report GPS to Gemini's
photo-analysis input; preserve T060's explicit exclusion.

Claude then connects the hook to existing ReportForm opening/loading, coordinate fields,
accuracy/source/status display and final submission while preserving layout, optional
note, present/absent choice and the live present-hazard photo requirement. Disable submit
only for ordinary field/upload/submission failures or `point=null`, never `locating`.
Take a snapshot before awaiting token/upload work so later GPS cannot change that request.
Keep server permissions, human review, deterministic alerts and scores independent.

## Reproduce checks

From repository root, with documented Node 24/frontend dependencies and backend test
environment already provisioned (no models, GPS credentials or real accounts needed):

```powershell
Set-Location frontend
node --test tests/*.test.mjs
npm.cmd run lint
node node_modules/typescript/bin/tsc -b
npm.cmd run build
# In a separate terminal, existing Vite instance or:
npm.cmd run dev -- --host localhost --port 5176 --strictPort
# From frontend/, while Vite runs:
node scripts/check-shell.mjs http://localhost:5176/
```

The existing installed Edge/CDP runner includes the **test-only** `/tests/location.html`
hook harness and the unchanged application report/ack/review/notice/briefing flows at
1440/390/320 widths. The harness intercepts geolocation with synthetic positions before
mounting the hook; it never requests real permission or submits a report. Test entry
files are not production build inputs. Results/screenshots are ignored under
`frontend/.shell-check/`. The new runner also measures the existing automated no-note,
no-GPS simulated form against 30 seconds; this is not T034A backend/form acceptance.

Backend compatibility from repository root:

```powershell
python -m pytest backend/tests/test_reports_api.py backend/tests/test_photo_storage.py backend/tests/test_fixtures.py backend/tests/test_ts_mirror.py backend/tests/test_schemas.py -q
```

Verified: 90 Node tests (19 new location cases), 105 backend compatibility tests, lint,
TypeScript and fixture/API production builds pass. Existing Starlette TestClient/httpx
deprecation and API554.37kB chunk warnings remain. Final Edge run at
2026-10-17T12:33:25.849Z passes the existing desktop/phone regression and synthetic hook,
including closed/reopened-session handlers, with zero browser exceptions/backend calls.
Existing automated no-note/no-GPS simulated report: **91ms**, not human/device timing.
Two preceding reruns hit the unchanged 30-second cold Vite helper startup limit. Fixed-source
helper servers now disable unnecessary file watching; final false/invalid-mode startup
checks pass in23.404/10.614 seconds. No assertions/time limits were weakened; failure
reports now include completed stages. No actual GPS/device, Auth0, Tiger Data, distance
persistence or live multipart metadata acceptance is claimed. Initial test diagnostics:
corrected an overbroad fixture-string comparison and a test filename.

## Final T034A acceptance after owners integrate

Leave the checkbox pending until all of these pass against the published contract:

1. On crew report opening, browser-granted device position persists/returns source and
   accuracy. Denied/unavailable/timeout uses labeled approximate site coordinates with
   source `site` and no accuracy; manual edits persist/return `pin` with no GPS accuracy.
2. Pending GPS never blocks no-note submission; test present + required photo and absent
   branches, each under 30 seconds. Verify actual form, not only this hook harness.
3. Switch/close/reopen sites and race late callbacks; no dashboard requests, tracking,
   stored private demo GPS, or unexpected requests. Verify browser permission flow on
   intended device/secure origin. Browser/provider behavior is separate from synthetic tests.
4. Validate actual multipart and returned canonical DTO fields, stored read-back after
   reload, backend distance, roles and field validation. Real demo accounts remain the
   existing Auth0 aliases; no new identities/migrations from Cache.
5. Re-run current Node/backend/browser/lint/TS/build checks. Only then check **T034A**;
   T053A belongs to Rudra/Braydin. No T063–T068 task is completed here.
