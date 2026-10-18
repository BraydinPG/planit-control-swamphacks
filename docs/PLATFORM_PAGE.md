# Public Platform page

[PR #93](https://github.com/BraydinPG/planit-control-swamphacks/pull/93): verified implementation `7f64b3b`; user-authorized merge.

Verified 2026-10-18. User-authorized stage one only, branch
`feature/cache-interactive-platform`, initially based on main `88b87ae`.
Main `bc525ea` is reconciled in `78794bf` without conflicts, preserving the
team's map-color changes. The subsequent organization/ownership update `9bb0e4e`
is reconciled in `0f5c8b5`, also without conflicts. Final frontend/build/browser
checks pass, plus 47 upstream organization/Auth0 mock tests (one existing
dependency deprecation warning).
The accompanying user message explicitly authorizes merge after verification,
superseding the attachment's original request to leave the PR open.

## Public documents and navigation

`/platform.html` is an independent static document alongside `/landing.html` and
`/data.html`. It uses the established public-page architecture; no new application,
router, API, service configuration or dependency is introduced. Normal Vite builds
copy it to `dist/platform.html`. The existing Caddy file-server rule serves actual
files before the SPA fallback. Local production previews verify this behavior;
this change does not claim a remote deployment or live Auth0 acceptance check.

The shared header is logo/Home, Platform, Data, About and Sign In. The logo remains Home
instead of restoring the text button the user previously asked to remove. Phones
use the shared accessible disclosure menu; all controls retain 44px targets.
Without JavaScript, links remain visible in two rows. Active-page state is present on each document.
Platform and Data use the same footer styles from `public-site.css`.

The homepage's hero, statistics, three product features and CTA destinations are
preserved. Data's generated research section, every chart/export and its controls
remain unchanged. Homepage does not load Platform CSS/JS or research assets.

## Interactive architecture

The centerpiece contains five layers and 27 source-backed components. The map is
conceptual architecture, explicitly labeled as such, not current service telemetry.

| Layer | Components | Primary source references |
| --- | --- | --- |
| Environmental intelligence | NWS; NOAA; NHC; USGS; EIA reference locations; crew field evidence | `backend/app/ingestion/{nws_weather,glm,hurricanes,flood_gauges,eia860m}.py`, `backend/app/api/reports.py` |
| Data processing | Geographic matching; time/source checks; normalization; caching/deduplication; freshness; Tiger Data persistence | `backend/app/ingestion/{geo,base,cache}.py`, `backend/app/services/{refresh,scoring}.py` |
| Analytical systems | Deterministic index; lightning rules; event-duration research; survival/persistence; offline Monte Carlo | `backend/app/rules/{score,lightning}.py`, `backend/app/outlook/events.py`, `ml/{train,monte_carlo}.py` |
| Decision support | Gemini evidence summaries; structured reports; human-reviewed instructions; scheduled briefings; permissions | `backend/app/gemini/{client,briefing_schedule}.py`, `backend/app/services/{reports,hazards}.py`, `backend/app/security/dependencies.py` |
| Operational interface | Crew; supervisor; team coordination; photo evidence; alerts | `frontend/src/pages/ConnectedPages.tsx`, `backend/app/services/{hazards,alerts}.py`, `backend/app/storage/photos.py` |

Every component has its own explanation, responsibility boundary and exact source
link in the static HTML. Selecting it copies that existing reference into the
inspector. JavaScript makes no network, session or storage calls. Native anchors
provide keyboard operation; selection preserves focus and announces the change.

Desktop shows five connected columns and an inspector. Below 900px, an accessible
layer picker shows one layer at a time. The selected component and layer remain
consistent when resizing. Without JavaScript, all layers and all 27 reference
articles remain available through the native expandable reference section.

The separate dashed research branch includes duration models, survival analysis
and Monte Carlo. It is deliberately separate from the operational score and
alert rules. No inference or simulation runs in this page.

## Workflow, stack and trust boundaries

The six-step workflow connects observations, site evidence, evaluation, crew
awareness, supervisor review and authorized instructions. Separate path summaries
explain automatic deterministic alerts, crew-submitted reports and conditional
duration research. Alerts do not wait for supervisor review. Pending reports,
potential notices and confirmed hazards remain distinct.

The human approval boundary states that Gemini supplies structured suggestions;
the notified organization's supervisor confirms and sends its own instruction.
Neither AI output nor a countdown authorizes work or clears an alert. Organization
and backend permission boundaries follow the current spec/services, including the
per-organization confirmation implementation. Organization ownership is database-backed,
not an Auth0 role; the latest team update limits each organization to one supervisor.

The stack section connects React/TypeScript/Vite/Tailwind to Python/FastAPI, then
explains the Auth0, Tiger Data, scikit-learn/survival, Gemini, Vultr and source-adapter
interfaces. EIA sites are reference locations; gauge values and regional events
are not described as measured site damage. Official product collection and research
eligibility are not advertised as universal current forecast coverage.

Both Explore Live Demo buttons retain `/?demo#/crew/overview`. The production
`GuestApplication` uses read-only server-scoped guest accounts; authenticated users
need the correct role for writes. Fixture-build browser checks verify the existing
entry, not real authentication or guest backend acceptance. Sign In stays `/?signin`.
The research CTA opens the existing Data document without copying its figures.

## Engineering evidence

The request-reduction claim is sourced to
[the existing controlled benchmark](FEED_REFRESH_PERFORMANCE.md):

- 256 synthetic sites in 16 shared-resource clusters, mocked HTTP and an isolated
  test database. The original reports were reused; this task does not rerun ingestion.
- Requests: **1,794 to 578**, a rounded **67.8%** reduction.
- `observation_sha256_by_feed` and `site_score_sha256` match between the original
  [baseline](feed-refresh-baseline.json) and [optimized](feed-refresh-optimized.json)
  reports. Browser acceptance verifies the counts and hashes before checking the page.
- The panel explicitly says controlled/archived/synthetic, not a measured production
  SLA or real-source coverage guarantee. No new live-performance claim is made.

Other reliability statements point to existing per-feed cache states, API failure
handling, role/membership dependencies, source provenance, reviewed instructions
and reproducible regression/evaluation tooling. No operational score, alert, schema,
training input, model gate or service configuration changes.

Shared decorative motion now respects reduced motion at load and when the setting
changes: it cancels lightning timers, ends the frame loop, draws static fog, disables
grain motion and completes counters. Normal mode retains the existing rendering
and resumes when the preference changes back. Diagram lines follow the same CSS
preference. The actual lightning alert logic is unrelated and untouched.

## Verification

From `frontend/`, with the documented Node environment:

```powershell
node --test tests/*.test.mjs
npm run lint
.\node_modules\.bin\tsc.cmd -b
npm run build
node scripts/check-public-pages.mjs http://localhost:5177/ --fixtures
```

Verified: **199 frontend tests**, lint/TypeScript, both production builds and the
development/built browser suites pass with zero clipping, exceptions or API calls.
Saved-report/figure reproducibility checks pass; no research retraining is performed.

Production default/live and explicit fixture builds are checked independently using
the same public-page acceptance against Vite preview. No service credentials are
needed for this public-page check. Existing SPA bundle-size warnings remain.

The browser suite covers all three public documents at 1440, 768, 390 and 320px:
direct access/reload/history; consistent active links; mouse/keyboard navigation;
all 27 components; phone layer selection; desktop-to-phone selection preservation;
expanded reference layout; no-script fallback; normal/reduced motion and live
preference changes; existing Data figures/selectors/failure fallback; unchanged
demo/sign-in destinations; synthetic session preservation and zero API requests.

Research reproducibility remains checkable without refitting:

```powershell
python frontend/scripts/export-research-dashboard.py --check
# Existing isolated plotting environment:
& $plotPython frontend/scripts/prepare-landing-research.py --check
```

## Screenshots and handoff

[Complete desktop](screenshots/platform-desktop.png) /
[complete phone](screenshots/platform-mobile.png).
[Desktop explorer](screenshots/platform-architecture-desktop.png) /
[phone explorer](screenshots/platform-architecture-mobile.png).

Rudra: maintain `platform.html`, `platform.css` and the small read-only `platform.js`.
Component explanations live in the static reference articles; node links select
them rather than duplicating copy in JavaScript. Keep the research branch separate,
org approval semantics, source references, guest restrictions and existing CTA URLs.
The public header/footer CSS is shared; Data-only plot styles remain separate.

Braydin: no tenant, Tiger Data, external-service, credential or deployment edit is
required by this PR. Existing static-file deployment should include `platform.html`.
Cache: no model, scoring or research-artifact action. Future public-site stages are
outside this change. Task checkboxes remain unchanged. Exact commit/PR attribution
is recorded in Git history and the cross-scope log.
