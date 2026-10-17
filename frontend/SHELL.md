# T030: PlanIT Control responsive shell

This is the application shell, not the completed site/alert/report product. `App.tsx` mounts `components/shell/AppShell.tsx`; `pages/WorkspaceOverview.tsx` provides a fixture-backed overview and the other navigation destinations are explicit connection states. Styling uses existing Tailwind utility classes; no new framework, router, dependency, API or authentication mechanism was added.

From `frontend/`, with Node 24 and dependencies installed:

```powershell
npm ci
npm run dev
```

Use Vite's printed localhost URL. `npm run lint` and `npm run build` are the existing checks. Crew/supervisor switches change **preview navigation only**. Hash links support direct URLs, reload and browser back. They never establish a role, identity, assignment or permission. Auth0's existing independent `auth-check.html` and `src/auth/**` remain untouched; connecting that module to the application remains T066.

## Fixture configuration

The existing `VITE_USE_FIXTURES` setting is consumed by `src/api/shell-fixtures.ts`:

| Setting | Result |
| --- | --- |
| Unset or `true` | Clearly labeled fixture mode; reads the existing generated `sites.json` and `site-detail.json` using canonical `SiteSummary`/`SiteDetail` types. |
| `false` | No site context displayed; explicit live-connection unavailable state. Does not call the backend or substitute fixtures. |
| Any other value | Explicit invalid-configuration state, without displayed sample data. |

For a persistent local setting, use `frontend/.env.local` per the existing `.env.example` and restart Vite. The default works without Tiger Data or Auth0 credentials. A production preview also defaults to labeled fixture mode; this is not an authenticated application deployment. Public fixture JSON is bundled with the client, including when display is disabled; it is demonstration data, never a place for secrets or private records. There are no fixture/live API toggles in the UI and no automatic fallback to live data.

The selected Everglades-style fixture is **simulated**, not an EIA record, verified active job or signed-in crew's assigned location. Its fixed timestamp is shown as scenario provenance, not a live update. Team and region come from that same fixture. Legacy fixture scores/model-onset factors are deliberately not displayed; they must not imply approval of score semantics. A null score renders “Not scored yet,” never low risk or zero. Missing live conditions and account-session integration remain unavailable. No countdown, alert control, report write, ML inference or work clearance is implemented by this shell.

## Reproducible browser acceptance

Keep Vite running, then from `frontend/`:

```powershell
node scripts/check-shell.mjs http://localhost:5173/
```

The script uses Node 24's built-in WebSocket and an installed Edge/Chrome through CDP. Windows Edge is the default; set `SHELL_BROWSER` to an installed Chromium browser path elsewhere. No browser/test package is downloaded. It launches an isolated headless test profile and temporary loopback Vite processes for `false` and invalid fixture settings, then closes only its own processes. The original developer server stays running.

Acceptance covers desktop 1440×1000, phone 390×844 and small phone 320×740, ten crew/supervisor destinations per viewport, no horizontal overflow, >=44px navigation targets, reload/back, keyboard skip-link focus, explicit fixture labels, unavailable modes, no runtime exceptions and no backend API requests. Null-score handling is tested by changing a fixture object in the isolated browser's memory only; committed fixtures remain untouched. Screenshots and `acceptance.json` are generated under ignored `frontend/.shell-check/`.

T030's prerequisites T003/T007 are checked; its exact done criterion is “app renders on phone and desktop sizes.” That acceptance does not finish T031–T038, T063, Auth0 integration, accessibility sign-off or the full application demo. The next unblocked task is **T031 (Nick)**, using T006/T007. The shell's connection labels are not a replacement for those forthcoming score/status components.

Ownership and review handoff: [CROSS_SCOPE_CHANGES.md](../docs/CROSS_SCOPE_CHANGES.md). Nick can replace each destination's connection state with his page component without changing the shell's navigation contract. Rudra's API types and generated fixture files must remain canonical; Braydin's auth exports should be integrated through their documented public interface in the appropriate later task.
