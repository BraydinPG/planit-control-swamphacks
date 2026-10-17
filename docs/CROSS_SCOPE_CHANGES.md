# Cross-scope changes

## T030 — Cache assisting Nick, 2026-10-17

Authorization: the user explicitly assigned T030 to Cache and stated, “Nick has given Cache permission to assist with frontend development.” Nick remains the owner and reviewer; this is not evidence that Nick has accepted the resulting PR. No merge is authorized without review.

Preflight: clean `feature/cache-worker-preview` checkout; fetched all remotes; current main `3dd52cc` includes merged PR #14 and Braydin's Auth0 implementation. No published Nick branch or open PR was returned by the remote/API checks, and no uncommitted frontend edits existed. Unpublished work on another machine is not observable here. New isolated branch: `feature/cache-t030-app-shell`, based on that main, preserving all published teammate changes.

T030 was unchecked. T003 and T007 are checked; the exact done criterion is “app renders on phone and desktop sizes.” Only T030 may be checked in this change. T031–T038 and T063 remain separate work.

Changed paths and handoff:

| Path | Change / owner handoff |
| --- | --- |
| `frontend/src/App.tsx` | Replaces starter content with one `AppShell` mount. Nick owns future application composition. |
| `frontend/index.html` | Removes starter root layout/dark styling, sets application metadata. No build/server configuration change. |
| `frontend/public/planit-mark.svg` | Small matching utility-grid favicon; leaves starter assets and the independent auth page untouched. |
| `frontend/src/components/shell/AppShell.tsx` | Desktop sidebar, phone bottom navigation, preview workspace selection, hash destinations, skip navigation, explicit connection states. Nick can replace destination content as each tracked page lands. |
| `frontend/src/components/shell/Icon.tsx` | Small shared SVG shell icon set; existing React/Tailwind only. |
| `frontend/src/pages/WorkspaceOverview.tsx` | Read-only reference context using existing simulated fixtures; no list/map, operational score, timer, report or briefing implementation. |
| `frontend/src/api/shell-fixtures.ts` | Bundled, typed fixture context and explicit default/false/invalid modes; no HTTP requests, tokens, writes or authentication bypass. Replace only through T063's reviewed client work. |
| `frontend/scripts/check-shell.mjs` | Reproducible installed-browser acceptance, isolated profiles/temporary test Vite servers; no new npm dependencies. |
| `frontend/.gitignore` | Ignores browser acceptance output/profile directory `.shell-check/`. |
| `frontend/SHELL.md` | Commands, fixture configuration, limits, testing and exact next owner task. |
| `docs/t030-acceptance.json` | Recorded browser/lint/build acceptance evidence. |
| `tasks.md` | Only T030 checkbox, after phone/desktop acceptance; all other task text/state preserved. |
| `PROJECT_CONTEXT.md` | Factual T030 index, current main/auth/PR state, entrypoint and review reference. |
| `docs/CROSS_SCOPE_CHANGES.md` | This authorization, file-by-file coordination and handoff record. |

Preserved without edits: `frontend/src/auth/**`, `frontend/src/types/api.ts`, generated fixture JSON, manifests/lockfiles, backend routes/security/schemas/database, ML code and contracts. `npm ci` installed main's declared dependencies; the lockfile did not change. No development auth role or backend bypass was enabled. No new test/format dependency was added to the project.

Verification: `npm run lint`, `npm run build`, and `node scripts/check-shell.mjs http://localhost:5173/`. Browser acceptance passed 1440×1000, 390×844 and 320×740; all ten preview destinations at each size, no horizontal overflow, >=44px navigation targets, reload/back/keyboard skip navigation, null-score wording and fixture-off/invalid states. No browser exceptions or backend API requests. Desktop/phone screenshots were visually inspected. Generated screenshots stay ignored; summary is in `docs/t030-acceptance.json`. A first browser test wait was corrected to ignore CSS uppercase text transformation; final assertions pass.

Limits: the app shell remains a demonstration. Preview workspace selection grants no permission. The reference site is a simulated fixture, not EIA/live work. Existing legacy onset/score examples are not shown. Account and live data remain unconnected to the shell, even though Braydin's independent auth modules now exist on main. Other page destinations show honest connection states, not working alert/report workflows.

Next owner work: **Nick T031**, prerequisites T006/T007 checked. T032 then needs T030 and T031. Rudra's T050 and API integration remain separate; Braydin's Auth0 module requires T066 wiring before the application can claim an authenticated session. Review the main fixture score wording with Rudra before any future scoring display; do not change or approve ML semantics through this shell.

Implementation checkpoint / review PR: pending publication; resolve the T030 implementation commit in this branch. Nick is the requested reviewer; Rudra coordinates merge after review.
