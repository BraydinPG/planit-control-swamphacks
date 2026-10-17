# Frontend redesign handoff

## Scoring display issue for Claude — 2026-10-17

Visual [PR #32](https://github.com/BraydinPG/planit-control-swamphacks/pull/32) is open at `ac5861c`; no merge by Codex. Its CROSS_SCOPE_CHANGES append does not overlap this branch's new leading entry. The functional changes preserve all modified visual paths.

Main `07a459d` and reviewed `feature/rudra-ui` `ac5861c` both show an incomplete numeric zero as an unqualified low band in ScorePanel. Controlled phone/desktop renders reproduce `0.0 / 10 · low`, completeness0%, with no explicit unknown warning beside the band. The diagnostic now flags this; no production component/page/style file changed by Codex. Preserve the actual backend number, nulls, alerts and Client/hook props. Add prominent incomplete/unknown wording and appropriate RiskBadge/ScoreBar/list/map treatment without independently calculating risk or changing DTOs. Include partial0.67, stale/replay, healthy-zero, null and held-alert cases. Rudra owns any additive evidence-status/ranking contract; see [SITE_SCORING_INTEGRATION.md](SITE_SCORING_INTEGRATION.md).

Functional client change: a single detail DTO whose headline and stored score disagree on value/band/version/completeness/time now rejects with502; scored detail requires its breakdown. Existing error views handle this. All canonical fields/signatures and auth exports remain stable. 648 Python/70 Node, lint/TS/both builds and standard browser regression pass; actual Auth0/Tiger acceptance remains blocked. Claude's visual branch is unmerged at inspection, not silently integrated here.

Current explicit authorization (2026-10-17): **Claude is actively redesigning presentation**; Codex/Cache owns functional API/state/Auth0 consumption/diagnostics/tests in a separate worktree. Nick's attribution remains. See [FUNCTIONAL_INTEGRATION_HANDOFF.md](FUNCTIONAL_INTEGRATION_HANDOFF.md) for exact path ownership, stable callable/hook contracts, verified tests, demo-account clarification and service blockers. Codex has not changed the visual/page/component files in this run.

| Module | Responsibility | Safe visual work |
| --- | --- | --- |
| `frontend/src/components/shell/AppShell.tsx`, `Icon.tsx` | Shared desktop/phone navigation, real-role override, route focus and skip link | Layout, spacing, icon treatment, typography; preserve route destinations, semantics and focus |
| `frontend/src/components/data/Status.tsx` | Score/source/missingness/factor/observation display | Cards/badges; retain all text states, nulls, provenance and legacy-score withholding |
| `frontend/src/components/data/AlertCard.tsx` | Server state/evidence/countdown/ack action | Alert hierarchy; keep primary action above the small-phone fold and no timer-driven clearance |
| `frontend/src/components/data/NoticeCard.tsx` | Potential vs confirmed notice and approved instruction | Notice layout; retain confirming-principal check, server response validation, explicit 500-character final send, and no instruction on potential notices. Preserve stable notice-ID keys so GET refresh never erases an edited draft |
| `frontend/src/components/data/StoredBriefings.tsx` | Read-only scheduled site/organization briefing retrieval and Gemini/template cards | Preserve GET-only transport, 404 empty state, forecast window, evidence and generation provenance |
| `frontend/src/components/data/Interaction.tsx` | Shared controls, loading/error/retry and action state | Button/form design; retain busy/disabled/live-unavailable states and accessible names |
| `frontend/src/components/data/SiteMap.tsx`, `styles/map.css` | Geographic points, optional basemap and linked list alternative | Map framing; preserve attribution, opt-in network, 44px zoom controls and keyboard alternative |
| `frontend/src/components/data/Advisory.tsx` | Exact-site 2.1 demo/T050 compact advisory | Evidence layout; preserve research/demo labels, site match, times, unknown hazards and limitations |
| `frontend/src/pages/ConnectedPages.tsx` | Shared crew/supervisor page composition and forms | Restructure presentation; preserve data calls, controlled fields, routing and status semantics |

Keep transport, identity and persistence outside styling changes: `api/contracts.ts`, `api/http-client.ts`, `demo/client.ts`, `application/*` and `App.tsx` select data/session mode and state lifecycle. `src/types/api.ts`, `src/fixtures/*.json` remain Rudra-owned canonical contracts; `src/auth/**` remains Braydin-owned. Generated `src/demo/generated/*` is derived from validated ML fixtures, not hand-authored page data. Do not embed fixture copies or remote request logic inside new decorative components.

Preserve these behaviors:

- Default mode is conspicuously simulated; real mode has actual provider/token integration and no preview persona switch. Never make a fixture badge look like authenticated security or live monitoring.
- Null is not zero/low risk. Legacy model-containing fixture scores cannot influence ranking. Reference plants are not active construction jobs.
- Countdown is a display of server timestamps; acknowledgement, ML, Gemini and elapsed time never clear an alert or authorize work.
- A pending/absent/rejected report is not a confirmed danger. Potential notices contain no instructions. Only the confirming supervisor edits/sends an instruction; server permission checks remain authoritative in real mode.
- Keep present/absent mandatory, note optional, coordinates labeled, selected photo limitations visible. Do not require a text narrative to submit the demo form.
- Keep evidence IDs, source/method, issue/observation/availability windows, stale/rejected/unknown states and field-verification requirements readable. Research event persistence is not local hazard or injury probability.
- Preserve DOM semantics, screen-reader status/error announcements, visible keyboard focus, skip link, non-color state text, >=44px primary targets, and 320px phone layout. Avoid color-only risk labels or hover-only actions.

Rerun `npm run lint`, `npm run build`, the current 68 focused Node tests, and `node scripts/check-shell.mjs http://localhost:5173/` after redesign. Compare actual phone and supervisor screenshots. The browser script uses visible labels as behavior assertions; update wording deliberately without weakening checks. Keep all ten destinations navigable, report/review/instruction persistence isolated and map/list identities consistent. Full live integration/accessibility T063-T068 remains separate acceptance.
