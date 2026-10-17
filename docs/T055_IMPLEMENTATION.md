# T055: confirmed-present reports in persisted site scores

PR #26 integration with main `9b395f0`: preserves the `compute_score(site=...)` regional
rules and `score_site(observations=...)` refresh-loop input. Feed-created notices now
record supervisor receipt snapshots so their recipients can use T054 confirmation.
Integrated backend verification: 487 passed, zero skipped; lint and format (109 files)
pass. The earlier 409-test checkpoint below predates those main-branch additions.

T055 connects T054's human confirmation to the existing T051 deterministic scorer.
Only a report with `review_status="confirmed"` and `hazard_present=true` contributes.
Pending, rejected and confirmed-absent reports, potential notices, Gemini drafts and
conditional ML outlooks do not contribute.

## Transaction and score behavior

`services/hazards.py::confirm_hazard` refreshes the linked crew report in the ORM after
its atomic review update, then calls `score_site(..., commit=False)`. Report review,
notice confirmation, new score and audits commit together. A scoring or audit error
rolls everything back. Repeated or unauthorized confirmation cannot add another score.
Feed notices with no crew report do not trigger this report-specific refresh.

`services/scoring.py::score_site` retains its committing default for existing callers.
The new keyword-only `commit=False` flushes without committing so confirmation owns the
transaction. It reads all eligible reports rather than the site UI's latest 50 reports.
Older confirmed hazards therefore remain factors when newer reports fill the UI window.

Existing prototype weights, severity fallback, cap at 10, source/freshness reporting and
ML exclusion remain unchanged. Each report factor retains its report evidence ID. No
new severity is inferred by Gemini. Absent-report review does not refresh the score or
turn an absent report into a present hazard. Instruction drafting/sending does not score.

Score refreshes lock the site's row on PostgreSQL to serialize competing refreshes.
Score row IDs now include UUIDs. Versions sharing a supplied request time receive
strictly increasing `created_at` values (previous timestamp plus one microsecond when
needed), keeping existing latest-score reads unambiguous. Rule inputs still use the
original request time; `previous_score` records the prior stored total.

## API and owner handoff

No new route, canonical API field, migration, dependency, frontend or ML change is needed.
After a present report is confirmed, existing `GET /api/sites` and site detail return
the refreshed score and evidence factors. Only that report's site is refreshed; nearby
teams receiving its notice do not acquire a confirmed site-report factor automatically.
Lightning state, latest strike time and clear-after time are not modified.

Nick owns T055 under the task assignment; Rudra reviews the scoring and confirmation
integration. Cache can consume the existing site-score fields in T065 without schema
changes. Production PostgreSQL/Auth0/Gemini/UI acceptance remains separate.

## Verification

`tests/test_report_scoring.py` covers API-visible score persistence, pending/rejected/
absent/other-site exclusions, old reports beyond the 50-report display window,
same-time and concurrent distinct confirmations, preserved lightning/other-site state,
and rollback after scoring/audit failures. Prior instruction tests now compare scores
before/after sending, preserving the instruction action's score invariance while
allowing the earlier confirmation to persist a score.

Full backend suite: **409 passed, zero skipped**, one existing Starlette/httpx deprecation
warning (10.01s). Ruff lint and formatting (103 files) pass. Tests use synthetic providers
and local SQLite, including separate-connection race tests; a live Tiger Data concurrency
test was not run. Existing ML integration checks ran with the declared ML dependencies.

From `backend/`:

```powershell
.venv/Scripts/python.exe -m pytest -q -rs
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
```
