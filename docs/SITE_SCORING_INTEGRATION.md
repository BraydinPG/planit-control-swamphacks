# Site scoring integration acceptance — 2026-10-17

**The authenticated Tiger Data milestone is blocked, not complete.** T051A merged
in PR #31 (`07a459d`). This verification uses `feature/cache-scoring-integration`
initially from that main in the separate functional worktree. Maintainers then merged
Claude's [PR #32](https://github.com/BraydinPG/planit-control-swamphacks/pull/32)
as `176cf36`. This branch incorporates that main as `3b8dfe2`; every presentation
file remains byte-for-byte equal to main. No manual visual edits or merge into main
by Codex. The shared-log entries merged cleanly without overwriting either owner.
T063–T068 remain unchecked. Implementation `b7d1293`; [PR #33](https://github.com/BraydinPG/planit-control-swamphacks/pull/33) is open against main at publication; no Codex merge. Machine evidence: [verification JSON](site-scoring-integration-verification.json).

## What was exercised

The new single whole-path regression reuses existing NWS MockTransport JSON, the
real NWS adapters/FeedCache, `refresh_all`, T051A, `score_site`, the existing test DB,
FastAPI site/report/confirmation routes and test-only signed crew/supervisor JWTs.
It joins pieces previously tested separately. This is **controlled test evidence**:
the DB is the existing in-memory SQLite test fixture, the signing key/JWKS is fake,
and NWS JSON is canned. No production auth bypass, real database, private account,
provider request, new seed implementation or alternative application service.

| Controlled transition at site-a | Persisted/API index | What was checked |
| --- | ---: | --- |
| Canned NWS weather/hourly forecast + Flood Watch | 2.1 | Adapter normalization, forecast HI qualification, score persistence |
| Changed station HI in raw source JSON | 3.0 | Refresh recalculates score; previous score 2.1 |
| Pending present wildlife report | 3.0 | Photo/report creation does not add a score term |
| Notified supervisor confirms present report | 4.0 | Atomic stored report contribution; previous score 3; crew confirmation denied |
| Confirmed-absent and rejected-absent reports | 4.0 | No contribution; rejected-present state filtering is also covered by existing T055 tests |
| Explicitly replayed lightning | 7.0 | Existing stop-work rule triggers, score reads its active alert |
| Provider failures after the lightning window | 7.0 | Alert remains active with unchanged window; stale positive evidence retained; completeness 0 |

Every stage checks DB factor equality, canonical SiteDetail validation, crew and
supervisor score equality, latest list/detail score equality, top-factor membership
in the persisted breakdown and assigned-first/backend numeric ranking. No-token
and unrelated-site requests are denied in the test security path. Existing full
tests additionally cover concurrency, rollback, all report-state exclusions,
scheduled briefing score authority, ML absence and Gemini failure.

A local one-off browser inspection loaded these seven **test API response** snapshots
through the production HttpClient and existing mock-auth browser harness. At 1440
and 390 widths, all seven supervisor stages and the crew held-alert view rendered
the supplied score (16 successful comparisons). Two additional no-evidence cases
reproduced the missing score-panel warning. Zero browser exceptions; zero real
backend requests. The helper and screenshots are ignored local inspection artifacts,
not a new shipped runner, API, Auth0 session or reproducible production demo.

The existing full Edge browser runner also passes at 1440/390/320: demo navigation,
report/review/instruction lifecycle, acknowledgement/reload, errors and mock role
boundaries. Screenshots were inspected. These remain demo/mock checks, not live
T063–T068 or redesigned-UI acceptance.

## Focused functional fixes

- `frontend/src/api/live-read-validation.ts` now rejects a single detail DTO whose
  headline score/level/version/completeness/time disagree with its nested stored
  score, or a scored detail without its breakdown. Equivalent timezone notation
  and genuine null/unscored responses remain valid. This compares backend fields;
  it never recalculates a score, changes a band or clears an alert. Existing error
  handling receives ApiError502 and does not substitute fixtures.
- Existing test mock responses now carry consistent nested versions and truly
  unscored other-site details. Canonical fixtures/types are untouched.
- The existing diagnostic renders the full factor breakdown and checks the actual
  ScorePanel against T051A's existing controlled zero-evidence output. A percentage
  beside `0/low` alone is not an explicit unknown warning. The current component
  fails this check, so the runner now reports a failed display gate instead of
  treating renderability as safety-display acceptance. Its text sentinel is not
  proof of visual prominence, accessibility, permissions or work authorization.

## Actual local readiness and blockers

Read-only diagnostics inspected the approved primary configuration root and the
existing localhost services without printing values or copying configuration:

- Backend DATABASE_URL and Auth0 domain/audience are missing; SPA Auth0 public
  domain/client/audience are missing; Vite is in explicit demo mode. Existing
  Auth0 test aliases/roles are owner evidence, not local app-session evidence.
- Database connection/counts/memberships are **unknown**, not zero. No Tiger Data
  connection, score write, report write or authenticated read was attempted.
- Feed refresh is off and NWS_USER_AGENT missing. No adapter was started against
  a real provider. Optional Gemini/storage configuration is also missing locally.
- Health/OpenAPI return200; all11 published operations match; ten anonymous/dev-header
  denials return401 and the Vite proxy returns401. Invalid bearer returns503 with
  Auth0 unconfigured, so real signature/expiry validation is unverified.
- The existing backend process on8000 was not restarted; route agreement/liveness
  does not establish that its loaded code is the newly merged scoring version.
  The protected primary checkout remains at `a3f46d0` with source `rules-0.1`;
  the verification worktree uses merged `rules-0.2`. Do not conflate those instances.
  Owners must start the reviewed main with approved settings for actual acceptance.
- T069 remains unchecked. `backend/app/db/seed.py` explicitly creates schema and
  inserts no demo scenario rows. No reproducible owner scenario was available in
  the reviewed source; actual remote DB contents were not inspected.
- **Known display failure:** current main ScorePanel shows `0.0 / 10 · low` at 0%
  completeness without an explicit warning beside the band. Claude's reviewed
  branch has the same issue in ScorePanel/RiskBadge/ScoreBar. No UI fix was made.

Diagnostic exit **1** now means the controlled display gate fails, alongside the
separate missing-service blockers. After Claude fixes the warning, missing private
configuration should still prevent live acceptance; do not describe that as success.

## Reproduce the checks

Use the existing backend dev environment and frontend dependencies/Node24. From root:

```powershell
python -m pytest backend/tests/test_site_scoring_workflow.py -q
python -m pytest backend/tests frontend/tests/test_integration_probe.py -q
python -m ruff check backend frontend/scripts/probe-integration.py frontend/tests/test_integration_probe.py
node frontend/scripts/check-live-integration.mjs --python <backend-python> --configuration-root <approved-project-root> --frontend-origin http://localhost:5176 --check-database
```

The whole-path test writes `scoring-workflow.json` in pytest's temporary directory
with public synthetic responses only. It never exports JWTs. From `frontend/`:

```powershell
node --test tests/*.test.mjs
npm.cmd run lint
npm.cmd run build
node scripts/check-shell.mjs http://localhost:5176/
```

`npm.cmd` avoids PowerShell's blocked npm.ps1 without changing execution policy.
`$env:VITE_USE_FIXTURES='false'; npm.cmd run build` also passes; its 553.81kB chunk
warning remains after incorporating the redesign (the earlier build was 531.64kB). Do not copy private values into VITE settings. Commands assume
the existing Vite process; this run did not restart Claude's server.

Final verification: **648 Python tests (638 backend +10 probe)**, **70 Node tests**,
Ruff/changed-Python formatting, frontend lint/TypeScript, fixture and API builds
pass. The sole Python warning is existing Starlette TestClient/httpx deprecation.
The display acceptance failure and real-service blockers remain open. Passing
these checks does not complete T063–T068.

## Owner actions for the persistent authenticated milestone

1. **Braydin:** make approved local Auth0 SPA/backend and Tiger Data settings usable
   through existing private setup, keep DEV_AUTH_BYPASS=false, and verify TLS/schema
   and the existing demo crew/supervisor subject memberships. No new accounts or
   employee records needed. Configure existing storage if the demo photo needs it.
2. **Rudra (T069):** finish/use one labeled restorable scenario with approved test site,
   teams/memberships, observed/replay evidence, wildlife report, lightning replay and
   stored briefing. Tell Cache which site/notice can receive a deliberate demo
   report/confirmation. Do not run the generic empty seed and claim T069 acceptance.
3. **Rudra:** start the reviewed merged backend with its approved `.env` actually
   loaded. Enable or deliberately invoke the existing feed refresh only under owner
   control. UI “Refresh server state” only rereads the API; it does not ingest feeds.
4. **Claude:** update `components/data/Status.tsx:ScorePanel` and the redesigned
   `Risk.tsx`/page/map/list call sites to show “Evidence incomplete / conditions
   unknown” prominently for incomplete indices. Preserve the supplied number as a
   partial index, no independent score/clearance or zero-to-null DTO rewrite. Test
   completeness0/0.67, stale/replay, null, healthy-zero and held-alert cases at phone
   and desktop sizes. Existing props/Client/hooks are unchanged by this PR.
5. **Rudra + Claude:** decide incomplete-score ranking/presentation policy. Backend
   `_sort_key` and frontend `sortSites` currently agree on numeric ordering, which
   cannot establish that an unknown zero is safer. Refer to the additive evidence-status
   proposal in SITE_RISK_SCORING.md; Cache did not change schemas or ordering.
   Stored completeness is as of `score.created_at`, not proof of present feed health;
   disabled refresh/old score timestamps must remain visible. Braydin should apply
   the same qualification to scheduled briefing wording.
6. **Cache with owners' ready scenario:** use existing normal Auth0 sign-in with both
   demo accounts. Run `frontend/scripts/run-live-account-check.py` privately (tokens
   hidden/stdin only) and the existing LIVE_INTEGRATION checklist. Verify assigned
   site read vs supervisor ranking, direct crew403 for unrelated/review actions,
   matching stored list/detail/factors, a controlled source refresh and previous
   score, pending report unchanged, notified supervisor confirmation, crew/supervisor
   reread and browser reload persistence. Check excluded report states and outage/
   unknown wording. Record actual response times/IDs privately; retain redacted
   outcomes. No guessed route, bypass, unattended seed or automatic confirmation.

Only after those actual checks pass should each task's own criterion be evaluated.
The merged redesign passes the repeated mock/demo/browser checks; T068 still needs
the live workflows and their accessibility acceptance. The functional Vite5176
instance is a development preview, not a newly approved Auth0 callback. Use an
owner-approved origin (normally5173) for real login, or have Braydin configure it.

## Score display integration review — Rudra, 2026-10-17 (rules-0.2, T069)

Reviewed main `ca99e64` before changing anything. Already correct and kept: stored
`HazardScore` rows are the only score source; list/detail/briefing read them; live mode
never substitutes fixtures (`HttpClient` errors instead); `live-read-validation.ts`
rejects headline/stored disagreement; ScorePanel, ranked list, search and map already
carry the unknown/incomplete wording from PR #36; briefings show the stored index and
per-hazard points (T058C); pending/rejected/absent reports add nothing (T055/T051A tests).

Fixed (actual integration problems):

| Problem | Fix |
| --- | --- |
| T069 seeds a **7.1 high** score at **0%** completeness (replay is never live coverage). The UI treated every 0% score as "Unknown", demoting a real 7.1 to small print. | `evidence.ts`: only a **zero** with no current input is "Unknown"; a positive index at 0% shows its number qualified as "Evidence incomplete". |
| Site detail showed `top_factors` (top 3) as the "score factors" breakdown, so lower factors and their points were missing. | Site page renders the full stored `score.factor_contributions`; stale/replay detection uses it too. |
| Ranking tied an unknown zero with an observed zero and broke ties by name, so missing evidence could sort as "safer". | Backend `_sort_key` and frontend `sortSites`: at equal scores, lower completeness ranks first. Numeric order, assigned-first and unscored-last are unchanged. |
| Briefings put a **stale** factor that still adds points only in `unknowns`, so hazard points no longer summed to the stored index. | The factor stays a hazard with its points and is also listed as unknown. |
| Briefings did not label an incomplete index; "0.0/10 (low)" at 0% read as low risk. | `unknowns` states when no monitored input is current ("not evidence of low risk") or what share is current. Gemini still never sets score, level or points. |

No canonical schema, DTO, scoring weight or `compute_score` change. Files touched outside
Rudra's paths: `gemini/briefings.py` (Braydin) and `api/contracts.ts` (Codex) — focused
lines, noted in CROSS_SCOPE_CHANGES.md.

Controlled evidence (in-memory SQLite, fake JWTs, canned/replayed inputs; **not** Tiger
Data or Auth0 acceptance): `backend/tests/test_score_display_integration.py` seeds T069 and
checks list = detail = latest DB row = briefing snapshot for crew and supervisor,
`rules-0.2`, top factors ⊂ stored breakdown, briefing points sum to the index, and the
ranking/briefing cases above. `frontend/tests/score-display.test.mjs` renders those
shapes (7.1@0%, unknown zero, observed zero, 3@67% outage, unscored) through ScorePanel.
Existing `test_site_scoring_workflow.py` still covers weather change 2.1→3.0, pending
report unchanged, confirmation 3.0→4.0, rejected/absent unchanged, lightning 7.0 and
feed outage held at 7.0 with completeness 0. Results: 727 backend, 108 frontend tests,
Ruff, lint, build and `check-shell.mjs` pass.

Not verified here: a running backend with the approved `.env` against Tiger Data and
real Auth0 sign-in. No backend was running locally, and seeding T069 rewrites the
shared demo rows, so that run needs an owner go-ahead. Check `model_version` in
`GET /api/sites` reads `rules-0.2` to confirm the server is the merged scorer.
