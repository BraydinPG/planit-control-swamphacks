# FORESITE branding and deployment handoff

The official application name is **FORESITE**, in exactly this capitalization.
This is the application formerly called PlanIT Control. The rename changes display
copy and metadata, not service identities or application behavior.

Branch `feature/cache-foresite-rebrand` starts from main `ea6dcfa`. It is independent
of the open feed-performance PR #50; that branch and all teammate work are preserved.

## Updated display surfaces

- The shared Crew/Supervisor shell uses FORESITE in the wordmark, header, sidebar,
  footer and overview accessible name. Navigation behavior and all visual classes
  are unchanged. The browser tab stays exactly **FORESITE** on every destination.
- The entry HTML includes FORESITE title/application-name, current product description
  and Open Graph text. The development sign-in check also has the correct title,
  favicon and heading. App-owned missing-role messages use the current brand.
- FastAPI's documentation title, human-readable role-denial message, site-record
  provenance labels and species retrieval note use FORESITE. Pydantic/TypeScript
  documentation changes only descriptions/comments, not fields or validation.
- The canonical fixture generator was rerun offline. Only one species-context note
  changed; scores, sites, briefings, alerts, reports and all six outlooks are unchanged.
  Existing saved demo state needs no migration or reset for this rebrand: shell text
  comes from code and the species note comes from the current fixture, not saved state.
- ML developer-preview titles and the derived-condition publisher's display label
  use FORESITE. No model name, artifact, algorithm, probability, model gate, contract
  identifier or source record changes. Generated local previews were refreshed offline.
- README, specification, agent/backlog titles, frontend guide, Auth0 setup, demo wording
  and current model documentation identify the application as FORESITE. Environment
  templates change only comments, preserving every setting/value. No task checked off.

## Logo and assets

The existing abstract utility symbol, colors, fonts and layouts are retained. The
favicon's SVG title is FORESITE; its geometry is unchanged. `/planit-mark.svg` remains
a legacy asset URL for compatibility with existing HTML/caches. It contains no old
wordmark. A new FORESITE logo can be designed separately; it is not required to render
the new text wordmark and browser identity.

## Intentional legacy references

The final tracked-source search was reviewed across code, documentation, fixtures,
metadata and tests. Remaining old-name matches fall into these categories:

| Reference | Why retained |
|---|---|
| Repository/package `planit-control-swamphacks`, GitHub links and local checkout paths | Existing repository/package identity and historical links; no rename or move |
| Auth0 audience `https://api.planit-control` | Token issuer/audience compatibility; unchanged |
| Claim namespace `https://planit-control/roles` and related profile claims | Existing deployed Action/token contract; unchanged |
| Auth0 tenant/client IDs and legacy dashboard/API/SPA/Action labels | Actual published resources; setup notes explicitly distinguish them from product branding |
| Demo key `planit:frontend-demo:v1`, test storage/probe IDs and temporary prefixes | Preserve saved workflows, sessions and existing tests; no blanket localStorage clearing |
| `/planit-mark.svg` and CSS/internal names | Existing technical asset/style identifiers; no visible old wordmark |
| Legacy HTTP User-Agent/application identifiers | Preserve external-provider request identity and captured URL provenance; not UI branding |
| Historical evaluation records, previous PR titles, captures, hashes and fixture timestamps | Preserve the actual historical evidence instead of rewriting it |
| Test-only fake domains, database names and function names | Internal compatibility/test identifiers; no effect on product display |

The only remaining plain old product-name string in production application source
is the legacy provider User-Agent in `backend/app/ingestion/json_client.py`. Other
remaining matches are the compatibility identifiers above or the deployed Auth0
Action's exact name in a code comment. They are not rendered as application branding.
User-authored reports and historical agency/AI text are not rewritten by this feature.

## Verification

Existing Node 24 dependencies and the approved Python environment were used; no
package/lockfile updates, new frameworks, provider credentials or model training.

- **168 frontend tests**: `node --test tests/*.test.mjs` from `frontend`.
- **881 backend tests**: `python -m pytest -q` from `backend`; final run rejected
  external socket connections (Windows asyncio internal loopback allowed).
- **297 ML tests**: `python -m pytest ml/tests -q` from root.
- Frontend lint: `npm.cmd run lint`; TypeScript: `node node_modules/typescript/bin/tsc -b --pretty false`.
- Default/live-mode production build: `npm.cmd run build`.
- Explicit demo production build: set `VITE_USE_FIXTURES=true` for that process,
  then `npm.cmd run build -- --outDir .shell-check/foresite-dist --emptyOutDir`.
  No private environment file is edited. `npm.cmd` avoids the local PowerShell
  restriction on `npm.ps1`; execution policy is unchanged.
- Backend Ruff lint and formatting pass (**147 files**). The existing Starlette
  TestClient deprecation and default/live bundle-size warning remain.
- Existing installed-Edge browser suite passes on the development demo and built
  demo at **1440, 390 and 320 CSS pixels**. All eleven Crew/Supervisor destinations
  assert exact title/application-name, no visible old brand or old accessible name,
  keyboard access, labels and touch targets. Brand checks remove literal URLs before
  scanning visible text so necessary compatibility URLs are not misclassified.
- Browser scenarios retain **6.1/10 rules-0.2**, all six outlooks and their replay,
  historical and unavailable distinctions, report/photo/confirmation/instruction,
  acknowledgement/reset/reload, briefings, team/code actions, expanded evidence and
  failed/missing-source states. Zero browser exceptions and zero real backend calls.
  Mock role/error cases remain mocks, not a new authenticated acceptance claim.
- `python -m ml.event_outlook_preview`: 16 cases, six existing qualified models and
  captured NHC/USGS examples, expected unavailable outcomes, zero requests.
  `python -m ml.worker_preview`: 150 validated outputs for 50 reference sites.
- Desktop/phone screenshots were inspected visually; existing symbol and layout fit
  the new wordmark. Screenshots/browser profiles/builds remain ignored.
- `.env`/`.env.local` fingerprints match pre-run values. Schemas/table names, API
  paths, model names, weights, timers, Gemini prompts/integration, photo storage and
  infrastructure settings are unchanged. `tasks.md` changes its heading only.

Development browser results: 2026-10-17 23:43 UTC; built demo: 23:44 UTC.
Reproduce against the existing demo at http://localhost:5177/:

```powershell
Set-Location frontend
node scripts/check-shell.mjs http://localhost:5177/
```

The built-demo check used a temporary existing Vite preview on 127.0.0.1:5182 and
`node scripts/check-shell.mjs http://127.0.0.1:5182/ --production`. That test server
was closed afterward; no deployment process or existing development server stopped.

## Deployment owner actions

1. After review/merge, build and deploy the updated frontend through the **existing**
   Vultr workflow. Deploy this branch's backend display-copy changes as part of the
   normal backend release so API documentation, role errors and species notes match.
   No command, environment variable, audience, route, database, secret, hostname,
   DNS record, CORS/callback entry or workflow change is required by this PR.
2. Verify the deployed HTML/JavaScript belong to the new build; if the hosting/CDN
   still serves old HTML, refresh/invalidate it through the existing owner procedure.
   No cache policy or infrastructure configuration is changed here.
3. **Braydin:** inspect Auth0 Universal Login. The existing SPA may still display its
   legacy dashboard name on the externally hosted login/consent page. Coordinate a
   display-name/branding update to FORESITE if necessary. Do not recreate applications,
   change identifiers/roles/claims or reset users. That external page was not changed
   or verified using real accounts in this run.
4. Replace old screenshots/slides/demo recordings when preparing the submission;
   preserve the old assets as historical material. The local app at 5177 already uses
   FORESITE; other checkout/server processes intentionally retain their own source.

No teammate worktree, running backend, Auth0 tenant, shared database, Vultr setting
or deployment workflow was modified. Rudra reviews application copy/metadata;
Braydin reviews the hosted-login/display release handoff. No automatic merge.
