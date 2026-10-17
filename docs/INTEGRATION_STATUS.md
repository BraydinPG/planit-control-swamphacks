# Frontend integration status

Phase-4 checkpoint verified 2026-10-17. PR #19 merged as `64cf632` during this run. Branch `feature/cache-live-integration-checks` now incorporates reviewed main `9ba1b7c` (T052/T053, PR #20/#21) by fast-forward without overwriting the new frontend work. It will target main. Rudra's canonical backend/auth/types/fixtures remain unchanged by Cache.

## Actual readiness and task state

Local process/environment-file audit found no configured DATABASE_URL, Auth0 domain/audience/SPA client, Gemini key/model or Vultr credentials. No local private environment files existed. Global tenant/account/database existence cannot be inferred from that absence: actual accounts, site seed, memberships and database contents are **unknown**, not zero/nonexistent. Development bypass remains false; the known local FastAPI process was restarted from backend/ with false explicitly set to load newly merged routes.

Health/OpenAPI return 200. Six operations are published and match the running server: site list/detail, alert list/ack and report list/create. Site, alert and report unauthenticated reads, unauthenticated ack, and an attempted development-role header all return 401. Invalid bearer returns 503 because Auth0 is unconfigured, so real token validation/expiry/role enforcement has not been verified. Vite's proxy returns the same 401 boundary. No actual signed-in site query, SQL connection, report/photo write or acknowledgement was performed.

| Task | Prerequisites / current evidence | Checkbox |
| --- | --- | --- |
| T063 | T041/T042 checked; existing shared views/client plus new real-response canonical validation/rendering runner are ready. No real account/site response yet. | **Unchecked** |
| T064 | T048 checked; existing client and new explicit-test-alert independent crew/supervisor read-back checks are ready. No real account or database-backed ack yet. | **Unchecked** |
| T065 | T053 now checked/published: report listing/create enabled, canonical multipart fields, photo required for live present reports, optional for absent. Full demo flow remains working. T054/T054A review/instructions are absent and owned by Nick under Rudra review. | **Unchecked** |
| T066 | Existing Auth0 provider/guard reused. T025/T026 remain unchecked and real tenant/role/accounts/memberships are unavailable. Mocked-provider proof is not live acceptance. | **Unchecked** |
| T067 | T057-T060/Gemini routes still absent. Existing prerecorded/fallback UI is explicit demo; live AI disabled. Radius/instruction functions remain owner work. | **Unchecked** |
| T068 | Foundation/demo phone/keyboard checks pass; live acceptance still depends on T063-T067. | **Unchecked** |

T031-T038 remain checked with their original foundation acceptance. Cache changed no task checkboxes in this phase; owner T052/T053 state/ownership changes came from reviewed main. Nick's newly assigned backend T054/T054A/T055 is preserved. No T070/T072/deployment or whole-app live acceptance is claimed.

## Useful implementation around the blockers

- `frontend/scripts/check-live-integration.mjs`: redacted local readiness, Vite environment/configuration flags, public tenant discovery when configured, source-versus-running route inventory, actual negative HTTP checks, and optional real-account API orchestration using the app's existing HttpClient.
- `frontend/scripts/probe-integration.py`: existing backend settings/OpenAPI/Pydantic models and an optional bounded read-only remote PostgreSQL/seed inspection. No local/mock database acceptance, initialization, migration or seed writes. Aggregate EIA-format/coordinate counts do not establish new source reconciliation or cloud-account provenance.
- `frontend/scripts/run-live-account-check.py`: optional private hidden token prompts and direct stdin pipe; no token argv, environment, saved credential file, user IDs or raw response bodies in the report. It reuses real existing Auth0 tokens and does not authenticate/mint tokens.
- `frontend/scripts/integration/acceptance.mjs`: reject unsafe/unprotected targets before sending account tokens; actual role reads, known unrelated-site denial, conditional review denial, canonical validation/shared display rendering, and deliberately selected active simulated alert read-back using fresh crew/supervisor clients. Default is no acknowledgement or real report writes. Signature verification remains FastAPI's.
- T053 frontend capability is separated from unavailable review. Existing report form, API client and components are reused; no second backend/UI/auth implementation or API schema change. Private photo retrieval is still unconnected; frontend currently accepts JPEG/PNG/WebP while backend also supports HEIC.
- Browser checks add mocked live present/absent photo requirements. Diagnostic/test Vite caches are isolated from the running developer server. Cold configuration-server compilation measured approximately 13-15 seconds; the browser driver now allows 30 seconds with the same assertions and captures timing/network failure diagnostics.

These APIs/fixtures are not work authorization. The ML library/contracts are unchanged, and the existing research/demo labels, source timestamps, explicit unknowns, null probabilities and deterministic alert authority remain intact. Gemini output stays a suggestion. A client acknowledgement, timer expiry or ML result cannot clear an alert.

## Checks actually run

See `docs/phase4-integration-verification.json` for the exact recorded commands/results and the redacted actual HTTP report. Current totals: **39 Node frontend tests** (23 existing + 16 new orchestration checks), **355 Python checks** (348 existing backend + 7 probe checks), frontend lint/TypeScript/build, Ruff lint/format and complete installed headless Edge workflow at 1440/390/320 widths. One pre-existing Starlette/httpx deprecation remains. New orchestration/SQL unit mocks are explicitly test-only; no real credentials/database verification is substituted.

The existing browser workflow still exercises crew ack/report and supervisor review/confirm/send in demo, 55-point map/list, exact-site advisory, generated/fallback text, mock provider transitions/HTTP failures, phone/touch/labels/focus and fixture-off/invalid modes. Early configuration-server checks exceeded the old 10-second cold-start limit; final measured runs pass at 13-15 seconds with isolated caches/30-second allowance. This was developer-server compilation, not a real Auth0 login measurement.

Backend requirements now include Rudra's declared boto3/python-multipart additions; those were installed into the existing local test environment, with no Cache manifest change. No ML behavior/model/artifact changed or training/evaluation was rerun.

## Precise owner actions and next acceptance

**Braydin:** configure the private Tiger Data URL/TLS and initialized schema, import real EIA records via the existing importer, and supply organizations/teams/memberships linked to actual Auth0 subjects. The existing seed command alone inserts no demo rows. Configure the public SPA/domain/audience, RBAC/roles Action, callback/logout origins and both real accounts; verify T025/T026. Keep DEV_AUTH_BYPASS=false. Provision Vultr storage and implement T057-T060 Gemini endpoints/fallbacks/functions; no credentials in browser or Git.

**Rudra:** review the narrow T053 client/photo requirement and private photo retrieval gap. Keep the published request/response and backend scope authoritative; review Nick's T054/T054A/T055 implementation. **Nick:** implement the newly assigned report review/notice confirmation and confirming-supervisor instruction delivery plus confirmed-report scoring under those task criteria. Those missing routes are not implemented by Cache.

**Cache:** after configuration, run the existing real Auth0 app and the new checker, verify T063/T066 real role views and direct API scope, then T064 with an actual database-stored simulated test alert and browser reload. After Nick/Braydin publish remaining routes, complete T065/T067/T068. No phase-4 task can currently be accepted with real services; the next acceptance to unblock is **T063**. Run and private/manual evidence checklist: [frontend/LIVE_INTEGRATION.md](../frontend/LIVE_INTEGRATION.md). Separate visual redesign remains in the existing Claude handoff.
