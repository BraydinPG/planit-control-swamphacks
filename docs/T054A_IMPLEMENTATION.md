# T054A: supervisor-approved hazard instructions

T054A builds on T054 on `feature/nick-hazard-confirmation`. It uses the existing
`HazardConfirmResponse`, `InstructionSend`, `HazardNotice` and database columns. No
canonical API fields, migrations, dependency manifests or frontend capabilities change.

## Confirmation and draft

`POST /api/hazards/{id}/confirm` retains T054's recipient, role and permission checks.
It commits human confirmation first, then calls the instruction service, which delegates
to `app.gemini.suggest_confirmed_instruction`. No Gemini calls are placed in route or
deterministic rule logic.

The new helper in `backend/app/gemini/instructions.py` uses the existing `GeminiClient`
and an internal structured schema: `suggested_instruction`, `evidence` (supplied IDs),
and `unknowns`. It rejects empty/overlong drafts, unknown fields, unsupplied evidence IDs,
and common clearance/alert-override claims. These lexical checks are defense in depth,
not comprehensive semantic grounding; human approval remains required, and broader
Gemini evaluations remain T061. Input evidence is treated as data in the prompt.

With a valid result, confirmation returns `generated_by="gemini"` and an unsent draft.
Missing key/model/evidence, timeout, provider error, or invalid output returns null
suggestion/generated-by fields without undoing confirmation. The supervisor can write
the instruction manually. Real Gemini behavior has not been verified in this task.

Only the confirming supervisor sees the draft in site detail. Crew and other supervisors
see no draft. Potential notices never contain a draft or final instruction.

## Send the final text

The confirming supervisor submits the accepted or edited text:

```http
POST /api/hazards/{id}/instruction
Authorization: Bearer <access token>
Content-Type: application/json

{"instruction":"Stay behind the marked barrier and contact the supervisor."}
```

The endpoint requires the supervisor role, `send:instructions` permission, a confirmed
notice, and an exact match to `confirmed_by`. Another notified supervisor cannot send
for the first confirmer. The final text is validated to 1-500 characters, with surrounding
whitespace trimmed; no generated replacement is substituted for the submitted text.

The service atomically stores `instruction` and `instruction_sent_at` only once, records
`notice.instruction.send` and one `notice.instruction.deliver` audit per team currently
inside the original stored radius, and commits those changes together. Concurrent or
repeat sends return 409 and cannot overwrite the first instruction. Delivery-audit
failure rolls back the instruction. Gemini is not asked for a new radius.

Delivery follows T053's existing application model: eligible teams read the saved final
text from site detail. It is not an email, push notification or offline delivery guarantee.
Instruction sending does not mutate alerts, scores or countdowns. Real UI integration
remains T065. The preceding human confirmation now refreshes the reporting site's score
through T055; see `T055_IMPLEMENTATION.md`.

## Owner handoff and validation

Braydin: the focused Gemini helper is a required T054A integration addition under this
task's explicit authorization. Export:

```python
suggest_confirmed_instruction(
    *, hazard_label: str, radius_miles: float, source: str,
    evidence: list[dict], client: GeminiClient,
) -> GeminiResult[InstructionSuggestion]
```

Preserve its unavailable/manual-entry behavior while implementing the other T057
functions. Rudra: review the route, send-once policy, current-team radius selection,
draft visibility and audit names. Cache: keep real instruction UI capability disabled
until T065 acceptance; consume the existing canonical types instead of adding fields.

Verified locally with synthetic providers and separate-connection race tests:

- Focused report/confirmation/instruction tests: 73 passed.
- Follow-up full backend suite with declared ML dependencies: 399 passed, zero skipped,
  one existing Starlette/httpx deprecation warning (9.06s). This supersedes the earlier
  393-passed run that skipped the optional ML integration checks.
- Backend Ruff lint and format checks pass; no live Auth0/Tiger Data/Gemini deployment
  or frontend acceptance is claimed.

From `backend/`:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_instructions_api.py tests/test_hazards_api.py tests/test_reports_api.py -q
.venv/Scripts/python.exe -m pytest -q -rs
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
```
