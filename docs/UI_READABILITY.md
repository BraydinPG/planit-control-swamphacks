# UI copy and worker readability

Cache's user-authorized presentation pass on `feature/cache-ui-readability-polish`.
Rudra remains the frontend maintainer. Start the existing app in explicit demo mode;
the change adds no API, service, identity or dataset.

## Screen audit

| Screen | Primary information | Expandable supporting information |
| --- | --- | --- |
| Crew overview | Assigned worksite, stop-work alert, watch window, links to other active alerts, reporting and approved instructions | Demo time, location and source records |
| Supervisor overview | Active alerts, hazards awaiting confirmation, reports awaiting review, highest scores | Full worksite evidence is one link away |
| Worksites and ranking | Short factor names, consistent status words, unchanged backend ordering, unknown/unscored states | Full factor descriptions on worksite detail |
| Worksite detail and weather | Score out of 10, incomplete-evidence warning, observed/forecast/stale/simulated states, readable values and times | Score version/completeness, factor evidence, source references and collection/validity times |
| Alerts and timer | Stop-work state, watch window, acknowledgement, explicit lack of work authorization | Trigger, distance, rule, source and evidence |
| Hazard report | Category, present/absent answer, photo, location and optional note | Report location/identity after submission |
| Supervisor review and analysis | Crew's original text, review state, Gemini verdict/summary and unknowns, review actions | Supporting/contradicting evidence, suggestions and confidence |
| Notices and instructions | Potential versus confirmed hazard; pending instruction or original approved instruction | Notice source, radius, record and timing |
| Six event outlooks | Separate hazard, simulated/current/historical/unavailable state, supplied estimate, uncertainty and as-of time | Model, recorded-event probabilities, agency forecast tables, provenance and limitations |
| Wildlife and habitat | Regional context is not a sighting; crew reports remain separate; sourced encounter guidance and review status | Original caveat, source coverage, protection records and additional unknowns |
| Shift briefings | Saved summary, hazards and points, suggested actions requiring review, unknowns, time window | Evidence IDs and briefing record |
| Teams and join codes | Organization, roster, assignment, code expiry, clearly simulated memory-only changes | Existing team-management controls |
| Navigation and failure states | Short headings, visible keyboard focus, readable local times, explicit failed/live/empty states | Original invalid-response diagnostics and startup configuration details |

## Display conventions

- Use **worksite** for work locations; preserve actual site names and identifiers.
- An **alert** is a deterministic backend state. A **potential hazard notice** still
  needs confirmation. A **confirmed hazard** may still be awaiting an instruction.
- **Simulated replay**, **historical example**, **stale**, **unavailable** and
  **unknown** retain different meanings. Historical agency cards explicitly say
  they are not current predictions. Missing data never becomes a low-risk reading.
- `frontend/src/presentation/display.ts` maps controlled enums only. Never pass
  crew notes, supervisor instructions, Gemini summaries or recommended actions
  through an enum formatter. Their wording is retained verbatim.
- `Timestamp` shows browser-local date/time and timezone; the original ISO value
  remains in `dateTime` and `title`. Unit labels change notation, not quantities.
- Native `<details>` controls keep evidence accessible to keyboard and screen
  reader users. Alerts, approved instructions and essential uncertainty stay
  outside closed disclosures. Primary controls retain at least 44 CSS pixels.

## Examples

| Before | After |
| --- | --- |
| `2026-10-17 17:57:00 UTC` | `Oct 17, 2026, 1:57 PM EDT` in a browser using Eastern time |
| `All-clear in` / `until all-clear` | `Watch window`; timer explicitly does not clear the alert or authorize work |
| `broken_pole_downed_line` or repeated category/present/review strings | `Broken pole or downed line`, with separate review/presence badges |
| Full source/model/record metadata on every prediction | Hazard, estimate, uncertainty and update first; `How was this estimated?` for technical evidence |
| `generated_by: fallback` | `Template fallback` |
| A long internal invalid-response error | `This information could not be verified. Try again.` with original diagnostic under `Error details` |

## Verification

From `frontend/`, with the repository's supported Node version:

```powershell
node --test tests/*.test.mjs
npm.cmd run lint
npm.cmd run build
$env:VITE_USE_FIXTURES = 'true'
npm.cmd run dev -- --host localhost --port 5177 --strictPort
# In another terminal, from frontend/:
node scripts/check-shell.mjs http://localhost:5177/
```

The browser runner uses an isolated headless Edge profile, never an existing Auth0
session. It checks all eleven Crew/Supervisor destinations at 1440/390/320 pixels,
report submission/confirmation/instructions, score reset/reload, six outlooks,
team creation/code revocation, long content, missing/stale data, multiple alerts,
expanded details, keyboard focus, touch targets, and mocked HTTP/auth failures.
Screenshots and machine-readable results remain under ignored
`frontend/.shell-check/`; `ui-polish-before/` holds the local baseline captures.
It does not establish real Auth0/Tiger Data acceptance or complete T063–T068.

The existing integration unit harness now disables file watching, matching the
other isolated Vite tests. Watching accumulated browser profiles could stall it.

## Backend-authored wording for owner review

- Rudra/Braydin: the saved Flood Watch instruction says to keep crews off roads
  "until the Flood Watch ends." Consider whether it needs an explicit qualified
  inspection/approved-procedure condition. This pass preserves the supplied
  instruction and never treats warning expiry as clearance.
- Rudra/Braydin: briefing summaries, suggested actions, notice labels/drafts and
  source observation labels remain backend-authored. Long prose can still occur;
  these strings were not rewritten, regenerated or reclassified here.
- Braydin/Rudra: species encounter guidance retains its source and pending
  safety-lead review status. Protection status is not proof of a sighting or a
  site-specific safety finding.

No scoring weights/calculations, ML, alert timing/state, permissions, backend
decisions, Gemini prompts, database data or private configuration are changed.
