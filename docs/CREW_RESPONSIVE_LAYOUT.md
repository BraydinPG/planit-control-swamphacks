# Crew workspace: phone and desktop

Current presentation update, 2026-10-18. One React workspace uses the existing
data, permissions and actions across screen sizes.

- Below **1024 CSS px**, the field layout keeps its 512px maximum, header logo
  and bottom navigation. My Worksite now shows its complete content in a vertical flow.
- From **1024 px**, Crew and Supervisor navigation sits in the top bar, centered
  between the logo and account controls. PR75 already removed the sidebar. Crew
  has five destinations; only supervisors have Team. The main crew area is capped
  at **1440 px**, without a sidebar gutter.
- From **1280 px**, Home places the active alert beside supervisor instructions.
  My Worksite pairs the score and weather conditions with matching section headings
  so both cards start at the same height, then shows the complete score-factor
  breakdown in a separate responsive grid.
- My Worksite shows every supplied observation, available event tile, full report
  card and score factor without View more/View less controls. Reading
  and event grids gain columns when space permits; report columns are bounded by
  the actual report count. Named technical source/evidence disclosures remain available.
- Alerts uses one full-width card per row for both roles. The existing countdown,
  server status, evidence, acknowledgement and instruction behavior is preserved.
- The redundant **Unverified worksite conditions** panel is removed from crew and
  supervisor site pages. Duration estimates remain on the relevant confirmed notice
  and in the independent event outlooks; no ML contract or model was removed.
- Home and supervisor sites show **one Confirmed hazards list** with lightning,
  active alert tiers, positive stored score contributors and confirmed notices.
  Flood/Flooding share a row with points, duration and inline supervisor instructions;
  Flash Flood remains distinct. Counts describe merged rows, not evidence records.
  Original sources/times and observed/forecast/stale/simulated states remain visible.
  A scored report appears only when confirmed-present at the same site. Pending
  notices remain outside the list; rejected, absent and missing reports are excluded.
  A page-local cache preserves supervisor drafts when confirmation moves a notice
  into its merged row during refresh. Existing owner/role checks still control sending.
- Species source, state and retrieval time are contained in **Species sources and
  coverage** under Local species. No detached USFWS status footer sits below the habitat
  map. Regional-context caveats, unavailable states and map attribution remain intact.

[Home desktop](crew-desktop.png) ? [Home phone](crew-mobile.png) ?
[Expanded worksite](worksite-expanded.png) ? [Full-width alerts](alerts-full-width.png)
[Unified hazards on phone](confirmed-hazards-mobile.png).

## Review locally

Open the existing demo server at `http://localhost:5177/#/crew/sites` and
`http://localhost:5177/#/crew/alerts` (or the port Vite prints). Switch to Supervisor
to inspect its centered navigation and full-width alerts. These pages remain clearly
labeled demo data. Live mode uses the same components and authenticated client.

```powershell
Set-Location frontend
npm.cmd run lint
node --test tests/*.test.mjs
npm.cmd run build
node scripts/check-shell.mjs http://localhost:5177/
```

Regression checks cover centered navigation, full-width alerts, complete worksite
readings/reports/outlooks, visible score factors and absent View more controls.
Eleven hazard regression tests cover tier-independent lightning, source states,
all supported environmental score contributors, outage/elapsed-window alert retention,
report eligibility/deduplication, unified rows/instructions, distinct Flash Flood
and unfamiliar hazards, and site identity. Source details and existing
research/historical limitations remain available with their associated evidence.

Focused browser checks cover 40 role/page cases at 320/390/768/1024/1280/1440/1920/2560,
with zero horizontal overflow, exceptions or real backend calls and score/weather card
top alignment within 1px at desktop widths. Unit count: 198.
Lint, TypeScript, default/live and explicit-demo production builds and the complete
development/built-demo browser workflow suites also pass.
Unified-list implementation `2d293fb` and `d82a30f`; reconciliation `e96b190`
preserves main `c285cf5` / read-only guests. The prior PR80 baseline also passed
139 backend score/report/lightning/contract checks; this feature changes no backend code.
[Review branch](https://github.com/BraydinPG/planit-control-swamphacks/compare/main...feature/cache-unified-confirmed-hazards).
Existing bundle-size warnings remain; browser evidence is demo/mocked verification,
not live Auth0/Tiger Data or operational safety acceptance.

Rudra maintains these frontend paths. Auth0 internals/services, backend contracts,
scoring/alert logic and ML are unchanged. Crew cannot review/confirm a worksite notice.
No task checkboxes change; T063-T068 retain their real-service acceptance criteria.
