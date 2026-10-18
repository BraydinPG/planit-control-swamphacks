# Crew workspace: phone and desktop

User-authorized presentation update, 2026-10-18. One React workspace uses the same
data, permissions and actions across screen sizes; there is no device detection,
separate application, transport or stored state.

- Below **1024 CSS px**, retain the existing centered field layout (512 px maximum),
  header logo and bottom navigation. The five crew screens keep their original order,
  spacing and controls.
- From **1024 px**, use the existing desktop sidebar pattern and a flexible main
  area capped at **1440 px**. Header navigation reflects the crew workspace; the
  supervisor-only Team destination remains absent.
- From **1280 px**, Home places the active alert beside hazards/supervisor
  instructions, with direct Report a hazard and View briefing links above. My
  Worksite places the score/factors beside weather conditions. Reports, alerts,
  outlooks and briefings use their existing responsive components in the wider area.
- At larger and ultrawide sizes, bounded content widths preserve readable text
  and intentional spacing. The storm backdrop, approved logos and theme are retained.

[Desktop preview](crew-desktop.png) · [Unchanged phone preview](crew-mobile.png)

## Review locally

Use the existing demo server and open `http://localhost:5177/#/crew/overview`
(or the port printed by Vite). Check Home, My worksite, Alerts, Reports and Briefings
at phone and desktop widths. Demo controls remain visibly labeled. Live mode uses
these same components with the existing authenticated client.

```powershell
Set-Location frontend
npm.cmd run lint
node --test tests/*.test.mjs
npm.cmd run build
node scripts/check-shell.mjs http://localhost:5177/
```

The existing browser suite now checks crew navigation and content widths at
320/390/1024/1280/1440/1920/2560, desktop alert/instruction and score/conditions
alignment, and the existing report, acknowledgement, instruction and role flows.
Its score-reset/outlook checks read the current canonical fixture instead of stale
6.1-point/six-visible-card constants: main's fixture is 7.9 and its unavailable
Wildfire outlook is hidden by the existing presentation policy. No fixture or
application scoring/prediction behavior changes in this update.
The missing-auth check requests the protected workspace directly; the bare URL now
opens the public landing page, which is not a missing-configuration error.

An additional local before/after browser comparison covered all five crew screens
at 320/390/768/1024/1280/1440/1920/2560. Below 1024, main bounds and the positions,
dimensions and labels of visible headings, buttons, selects, textareas and navigation
links were identical. Captures use reduced motion; screenshots contain only the
existing sample data. This is demo/mocked verification, not real-service acceptance.

Verified: 178 frontend tests, lint, TypeScript, default/live and explicit-demo production
builds, and complete development/built-demo browser suites pass. Existing bundle-size
warning remains. Browser suites cover all eleven destinations, the report/instruction
lifecycle, acknowledgements/reloads, keyboard flow, mocked roles and failure states,
with zero browser exceptions or real backend requests. No backend tests were rerun.

Rudra maintains these frontend paths. Braydin's Auth0 internals and services, backend
contracts, deterministic scores/alerts and ML are unchanged. Crew cannot review or
confirm a worksite notice. Existing task states, including live T063-T068 acceptance,
remain unchanged. PR71's logo merge is separately user-authorized; its hosted Auth0
logo setting still needs Braydin's action described in `auth/BRANDING.md`.
