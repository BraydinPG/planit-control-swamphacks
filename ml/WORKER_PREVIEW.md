# Independent worker-outlook developer preview (T087)

This read-only developer artifact runs the existing `build_comprehensive_outlook()` callable and strict **2.1.0** models. It generates static HTML, a terminal summary and canonical request/response JSON. It starts no server, performs no retrieval, requires no credentials, and blocks socket connections during composition. All activations are **hypothetical replays**, even when the source readings are real. EIA reference plants are not verified active jobs. No production integration or permission verification is claimed.

## Run from repository root in Windows PowerShell

Install the existing pinned environment once if needed:

```powershell
./ml/setup.ps1
```

Then the single acceptance/run command is:

```powershell
.\ml\.venv\Scripts\python.exe -m ml.worker_preview
```

The command prints worker-readable Flood, High Wind and missing-evidence summaries and saves `ml/reports/worker_preview/index.html`. Open that local file in a browser; choose a reference plant, then Flood, High Wind or Missing evidence. No web service or teammate application is required. All 50 sites and 150 outputs are generated. For one location, append `--site-id eia860m-FL-59611`. Use a fresh `--output` directory for a separately identifiable run.

The default succeeds with typed **unavailable** Layer A when model artifacts are missing. It does not download archives or refit anything. When the reviewed artifacts are already provisioned, append `--require-models` to require supported Flood/High Wind research results. That stricter mode exits nonzero if artifacts are absent. Optional artifact provisioning remains the existing process in [HAZARD_INTEGRATION.md](HAZARD_INTEGRATION.md); restart after provisioning. No new training or evaluation is part of T087.

## What to inspect

- `index.html`: real `eia860m-{state}-{plant_id}` identities from the pinned backend selector export, 50 site links and actual evidence-coverage counts.
- `site-001.html`: LKL BLBD, LLC (`eia860m-FL-59611`), Flood replay with actual captured NWS observations/issued forecasts, and an explicitly hypothetical missing-source example. Unlinked/datum-less gauge readings remain rejected.
- `site-002.html`: Catclaw Solar (`eia860m-AZ-68414`), High Wind replay with captured wind/forecast evidence.
- Every page: fixed as-of and generation times, replay confirmation, model/target/horizons/limitations, qualified conditions, notice provenance, unknown electrical/structural/chemical/wildlife/access hazards, source availability, and expandable rejected-evidence details. Local probabilities/severity remain null. Source freshness means freshness **at replay time**, not live currency.
- `site-001-flood-request.json`, `site-001-flood-response.json`, `site-002-wind-*.json` and `site-001-missing-*.json`: full canonical examples. Every site has all three pairs; filenames use generated ordinals, never unchecked site input.
- `request.schema.json`, `response.schema.json`: unchanged runtime schemas, emitted with the examples. `acceptance.json` records counts; `preview.txt` is the terminal summary.

Generated pages/JSON live in the already ignored reports directory, so large repeated captures are not committed. Re-run the command to reproduce them from checksummed committed fixtures. The fixed snapshot is **2026-10-17T07:18:48.564672Z**. It has qualified environmental evidence for **2/50** sites and qualified notices for **10/50**; it does not imply live coverage elsewhere or confirm an incident at any plant. Missing source data never establish absence of hazards. The outage case reuses `missing_credentials_and_failed_source_explicit`; its NWS timeout is synthetic, and unavailable credentials are not tested live.

The preview reuses named `ml.hazard_scenarios` cases, `DEMO_POLICY`, the rehearsal scope/safety checks, identity reconciliation and source gates. It replaces native point-query notices/source states for each selected site rather than transferring a seed site's receipt. Fixture report trust remains local to this replay harness, never a deployable authentication mechanism. HTML escapes source text, has no JavaScript or external assets, and links only to generated local pages/JSON. Monte Carlo is absent from the presentation.

## Done check and owner handoffs

```powershell
.\ml\.venv\Scripts\python.exe -m pytest ml/tests/test_worker_preview.py -q
.\ml\.venv\Scripts\python.exe -m ml.worker_preview
```

The focused suite checks all 150 saved outputs against the runtime Pydantic contracts, real identity/replay labels, missing artifacts and sources, unsupported event type, future issue/availability, malformed/forged coordinates, client trust rejection, required unknowns/nulls, static HTML escaping and local navigation. Full pre-existing 31-scenario/50-site acceptance remains `python -m ml.hazard_rehearsal`; this preview does not replace it. Passing checks are software acceptance, not operational predictive validation. Previously reviewed periods are not a pristine holdout, and no local severity model was added.

- **Rudra / T050:** consume the unchanged callable and generated request/response pairs using [HAZARD_INTEGRATION.md](HAZARD_INTEGRATION.md). Proposed work belongs in your trusted event/as-of adapter and approved authenticated advisory route, with unavailable/422 tests and unchanged alerts/scores. T087 does not finish T050. The old `tasks.md` Shared contracts paragraph and AGENTS Rudra scoring bullet still suggest using `predict_site()` for scoring; they conflict with the explicit research-only primary contract, spec section 5 and T050/T051. Owner review should reconcile that wording before integration; this task leaves shared specifications intact.
- **Nick / T063–T068:** inspect local HTML and canonical 2.1 JSON as a display reference. Preserve observed/issued/research/replay/rejected/unknown distinctions, provenance and the independent deterministic alert display. No shared API type or page was changed; live-vs-fixture views and application acceptance remain yours.
- **Braydin / trusted activation and auth:** provide server-verified organization/team/site access and activation/report provenance before any route consumes this data. The local fixture principal is not Auth0 proof. Your newly merged T045–T045D feeds remain unchanged; converting their observations to the fuller advisory provenance contract requires a reviewed upstream adapter.

Single next unblocked task for a later run: **Nick T063**, whose T041/T042 prerequisites are checked, can connect site list/detail APIs while retaining fixture mode. Cache's preview supplies examples only; it does not complete T063, T070, deployment or the whole application demo.
