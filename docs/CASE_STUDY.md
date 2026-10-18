# Public Everglades Case Study

Verified 2026-10-18, feature branch `feature/cache-everglades-case-study`,
initially based on main `787b1ba`. The user's accompanying message authorizes
merge after checks, superseding the attachment's request to leave the PR open.
No task checkbox changes are intended.

`/case-study.html` is a separate static public document copied by the existing
Vite build. It reuses the public brand, navigation, storm atmosphere and footer.
Home, Platform and Data change only their header/footer links. The logo remains
Home, preserving the user's earlier preference. No app component, API contract,
auth setting, backend, scoring weight, model or deployment configuration changes.

## What visitors can inspect

Seven stages connect environmental evidence, deterministic factors, crew context,
field reports, supervisor confirmation, bounded research and coordinated response.
Crew/Supervisor controls change the explanatory perspective and final guest-demo
destination. They grant no permissions and execute no transactions. The existing
guest demo remains read-only, with its server-provided data and permission checks.

Stages support keyboard navigation, focused headings, an announced current stage,
direct `#stage-1` through `#stage-7` links and reload. All seven articles remain
available without JavaScript. Reduced motion stops both the existing storm loop
and case-study pulse/transition. The site visual is a labeled schematic, not a
map layer, boundary, modeled storm track or navigation aid.

## Source audit: two existing scenarios, deliberately kept separate

This page consistently uses the **bundled API fixture** at
`2026-10-17T18:00:00Z`. It does not assert these are live measurements.

| Detail | Verified source | Value used |
|---|---|---|
| Site identity | `frontend/src/fixtures/site-detail.json` | `site-demo-everglades`, 25.76 / -80.49; fictional, not EIA |
| Deterministic score | Same file, complete `score` | `rules-0.2`, 7.9/10, high, data completeness 0 |
| Factors | `score.factor_contributions` | Lightning 3 + heat 2.91 + Flood Watch 1 + confirmed wildlife 1 = 7.91, rounded by scorer to 7.9 |
| Lightning | `obs-ltg-1`, `obs-ltg-2` | Replayed 6.8 mi at 17:48 UTC; latest 4.2 mi at 17:57 UTC |
| Weather | `obs-wx-1` to `obs-wx-3` | Simulated NWS-shaped 94 °F, 68% RH, 112 °F heat index at 17:40 UTC |
| Flood observation | `obs-flood-1` | Simulated Flood Watch at 16:30 UTC; no local water depth inferred |
| Pending pole report | `frontend/src/fixtures/reports.json`, `report-pole-1` | Present, pending; created 17:54 UTC; device location 25.758 / -80.494, accuracy 12 m; photo reference only |
| Wildlife report | Same file, `report-wildlife-1` | Confirmed at 15:50 UTC; moderate severity; separate from pending pole |
| Approved instruction | `frontend/src/fixtures/hazard-notices.json`, `notice-wildlife-1` | Sent at 15:52 UTC: “Avoid the east access road. Use the west gate until wildlife control clears it.” |
| Research boundary | Site `event_outlook` and `event_outlooks` | Legacy 22-hour duration is explicitly synthetic; PR39 multi-event research examples refer to a different reference site/time. Neither is reused as a validated Everglades prediction. |

These are related fixture records, **not a chronological log of seven newly
executed transactions**. In particular, the wildlife confirmation predates the
pending pole report. The public page creates, confirms and persists nothing.

The database seed in `backend/app/demo/scenario.py` is a **different scenario**:
`demo-everglades`, 25.395 / -80.583, Flood Warning and the north-gate/levee-road
instruction. `backend/app/demo/freshen.py` slides its dates. The current guest demo
can therefore differ from the frozen case study. No seed is executed for this work.

### Existing fixture issues for Rudra

1. `alert-flood-demo.evidence` says Flood Warning while scored observation
   `obs-flood-1.value` says Flood Watch. This page follows the observation and
   authoritative computed score. It documents the discrepancy instead of editing
   Rudra's generator or substituting the rolling seed's stronger warning.
2. Fixture photo URLs are references, not captured photographs. No invented pole
   photo is displayed; energization cannot be established by a photo anyway.
3. The legacy duration is synthetic and multi-event associations refer to a
   separate EIA replay. Reconcile these in the canonical fixture generator if a
   fully site-qualified research example is desired. Cache's model gates and
   artifacts are unchanged; no new model result is claimed.

## Authentic application captures

`frontend/public/case-study/crew-overview.webp` is an actual crew overview from
the existing React app in **fixture mode**, with its simulation banner visible.
`supervisor-notice.webp` is a browser crop of the actual confirmed wildlife notice
in the supervisor site view. The quote is the stored fixture instruction, not an
AI-generated illustration or a new approval. The screenshot includes the existing
“Lightning + Severe Thunderstorm” merged alert because that is what the fixture
app renders; this page's numeric factor list comes from the separate complete score.

`capture-provenance.json` records the fixture (UTF-8, CRLF normalized to LF) and
binary image SHA-256 hashes, routes,
viewport and zero backend requests/mutations. Tests fail if fixtures change without
reviewing the narrative and captures. Captures use a new isolated browser profile;
the user's Auth0 sessions and other demo state are untouched.

To reproduce on Windows PowerShell, with existing Node 24 dependencies and Edge:

```powershell
Set-Location C:\Users\cache\planit-control-functional\frontend
# In a dedicated terminal, preserving the existing .env files:
$env:VITE_USE_FIXTURES = 'true'
npm.cmd run dev -- --host localhost --port 5177 --strictPort
# In a second terminal, from frontend/:
node scripts/check-public-pages.mjs http://localhost:5177/ --fixtures
# Optional deliberate refresh of the two public screenshots and their manifest:
node scripts/check-public-pages.mjs http://localhost:5177/ --fixtures --capture-fixtures
node --test tests/*.test.mjs
npm.cmd run lint
.\node_modules\.bin\tsc.cmd -b
npm.cmd run build
```

Choose an available local port if 5177 is occupied by another checkout, and use
that URL for the test command. Do not stop another developer's server. A normal
live build also serves the static Case Study without Auth0, API or model access;
only following a guest-demo link uses the existing application services.

Acceptance extends the existing `check-public-pages.mjs`, rather than introducing
a second browser harness. It covers all four public documents at 1440, 768, 390
and 320 pixels, seven stages × two perspectives, 44px controls, screenshots,
keyboard selection, deep links/reload, expanded sources, both motion preferences,
no-JS content, preserved storage sentinels and existing Data/Platform interactions.
Both default/live and fixture production builds passed those public checks.

## Verified results

- `node --test tests/*.test.mjs`: **203 passed**, including four new source,
  report-state, research-boundary and capture-provenance checks.
- `npm.cmd run lint`, explicit public-script/browser-test lint, and `tsc -b`: pass.
- Vite production builds in both `VITE_USE_FIXTURES=false` and `true`: pass.
  The existing SPA chunk-size warning remains; this static page adds no app chunk.
- Existing Edge public-page acceptance: development fixture run and both built
  modes pass at 1440/768/390/320. Four pages, seven stages × two perspectives,
  27 Platform components, 12 Data figures, keyboard/mouse, reload/deep links,
  no-JS, reduced/normal motion, 44px scenario controls, no clipping, zero browser
  exceptions or API requests. Existing guest-demo entry is exercised in the
  fixture build, not claimed as authenticated production acceptance.
- `git diff --check`: pass. Scripted comparison against base confirms the Home,
  Platform and Data documents are exact apart from Case Study navigation links;
  application source, research assets, backend, ML and task states are unchanged.

Built-page captures (actual browser screenshots, converted to WebP):
[Desktop](screenshots/case-study-desktop.webp),
[Mobile](screenshots/case-study-mobile.webp). Full PNGs and stage-specific shots
remain in the ignored `frontend/.shell-check/public-case-study-*.png` directory.

## Handoff

Rudra: maintain only public `case-study.{html,css,js}` and the shared nav links;
review the three canonical-fixture issues above separately. The public script has
no network, storage, auth or write dependencies. Braydin: the existing static-file
deployment rule serves this built file without a new route; no auth/DB/service
changes are requested. Cache: keep future research claims tied to qualified
event/site outputs. No live integration, task acceptance or operational validation
is implied by a passing public-document test.
