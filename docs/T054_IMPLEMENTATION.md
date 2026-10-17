# T054: hazard confirmation and absent-report review

This change implements the two supervisor actions in T054 using the existing FastAPI,
Auth0 dependencies, database models and canonical response schemas. Nick owns this task;
Rudra reviews the backend integration. No API fields, database tables, migrations,
frontend files or dependency manifests change.

Follow-up: T054A and T055 are now implemented; see `T054A_IMPLEMENTATION.md` and
`T055_IMPLEMENTATION.md`. The descriptions below record the original T054 boundary
before draft generation, sending and atomic score refresh were added.

## 1. Snapshot notice recipients

`backend/app/services/reports.py` records one `notice.supervisor.deliver` audit for each
supervisor selected when T053 creates a notice. The entity is
`{notice_id}->{supervisor_user_id}` and the actor is `system:notices`. Existing team
delivery audits remain unchanged. All receipts are committed with the report and notice.

These records preserve who received a notice even if teams subsequently move. Future
feed-notice producers must persist the same supervisor receipts when delivering notices.
Older notices without a supervisor receipt are denied confirmation (403); this change
does not infer historical recipients from current team locations or backfill receipts.

## 2. Confirm a hazard

`backend/app/api/hazards.py` publishes `POST /api/hazards/{notice_id}/confirm`, registered
in `backend/app/main.py`. No request body is needed. Both the supervisor role and
`confirm:hazards` permission are required, followed by an exact stored-receipt check.
A notified supervisor from another organization can confirm.

`backend/app/services/hazards.py::confirm_hazard` atomically changes a potential notice
to confirmed only if nobody has claimed it. It stores the first supervisor and time,
confirms the matching pending present report when the source is a crew report, and
audits both changes in one transaction. Feed notices need no crew report. The crew's
chosen category is accepted; no Gemini classification or severity is silently adopted.

Responses: 401 without authentication, 403 without role/permission/receipt, 404 for an
unknown notice, 409 for repeat/conflicting confirmation or inconsistent linked report,
and 200 with the existing `HazardConfirmResponse` on success. The instruction suggestion
and generated-by fields are null until T054A implements the Gemini suggestion flow.
No instruction is sent and no score recomputation or alert transition is performed.

## 3. Review an absent report

`backend/app/api/reports.py` publishes `POST /api/reports/{report_id}/review` using the
existing `ReportReview` body and `CrewReport` response:

```json
{"decision":"confirmed","category":"on_site_fire","note":"Reviewed field evidence"}
```

The supervisor role and `review:reports` permission are required. The supervisor must
belong to the report's organization. Only pending absent reports use this endpoint;
present reports use notice confirmation. Decisions are `confirmed` or `rejected`.
Reviewer/time and accepted classification fields are saved; an optional review note is
retained in a separate JSON audit record without overwriting the crew's original note.
The report's `hazard_present=false` remains unchanged and no notice is created.

Site-detail responses now hide absent reports from other organizations; internal scoring
loaders retain their full site view. Existing report-list organization filtering remains.

## 4. Tests and remaining work

From `backend/`, with its virtual environment installed:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_hazards_api.py tests/test_reports_api.py tests/test_sites_api.py tests/test_score.py -q
.venv/Scripts/python.exe -m pytest -q -rs
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
```

`tests/test_hazards_api.py` reuses T053's authenticated fixture and tests cross-organization
recipients, crew/permission denials, absent-report privacy, persistence, repeat requests,
receipt snapshots, rollback and concurrent confirmation from separate database connections.
These are offline tests with synthetic data, not a real Auth0/Tiger Data deployment check.
T054A (Gemini suggestion and supervisor instruction send) and T055 (persist refreshed
scores after confirmation) remain separate tasks. No frontend capability is enabled here.
