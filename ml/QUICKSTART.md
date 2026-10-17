# ML quickstart

For the combined worker advisory, follow [WORKER_OUTLOOK.md](WORKER_OUTLOOK.md), then run `python -m ml.demo_worker_outlook --require-models` after provisioning. The demo is offline and uses real captured weather with labeled hypothetical event contexts; it does not assert a real active disaster.

Run from the repository root. The preserved **Flood** default is conditional Kaplan-Meier recorded-duration persistence. Five additional research targets and their separate provisioning are documented in [MULTIDISASTER.md](MULTIDISASTER.md). Outputs are marked `production_eligibility=false` and cannot affect alerts, work clearance, or site scores. Weather remains retrospective research.

## Windows setup and pinned provisioning

```powershell
./ml/setup.ps1 -ProvisionModel
$MlPython = ".\ml\.venv\Scripts\python.exe"
& $MlPython -m ml.provision --verify-only
& $MlPython -m ml.smoke
& $MlPython -m pytest ml/tests -q
```

The setup script creates `ml/.venv` only if absent, installs `ml/requirements-lock.txt`, and leaves the root environment alone. The pinned environment was verified in a new Python 3.14.5 environment. Other runtimes/platforms need their own dependency and numerical checks.

`ml.provision --download` retrieves only missing exact revisions from `ml/reports/source_manifest.json`, sequentially, with bounded retries and a 25 MiB limit. It verifies SHA-256, byte size, and the complete gzip stream. Existing mismatched files are preserved and rejected. It never discovers newer revisions or rewrites source manifests. Without `--download`, provisioning uses local files only.

Provisioning trains from pinned intervals using the purged episode split, checks version/counts and six synthetic reference contexts against `ml/model_reference.json` (both estimators; tolerance 1e-10), and writes:

- `ml/artifacts/provisioned_v2/active_event.joblib`
- `ml/artifacts/provisioned_v2/active_event.manifest.json`: artifact/source-manifest hashes, dependency versions, and verification result.

These are the default inference paths. Original models, optimization backups, and takeover backups remain intact. No binary model, raw archive, environment, or downloaded weather is committed. Teammates regenerate the artifact from checked-in provenance and code. Changed reference arithmetic fails verification instead of silently becoming an approved model.

## Bounded development and profiling

```powershell
& $MlPython -m ml.backtest --fast --workers 1 --output-dir ml/reports/dev --model-path ml/artifacts/dev/model.joblib
& $MlPython -m ml.benchmark --events-per-year 20 --worker-counts 1 4 8 12 --output ml/reports/dev/benchmark.json
```

`--fast` and `--smoke` are aliases. Sample metrics carry `SMOKE_TEST_NOT_FINAL_VALIDATION`; default smoke paths cannot overwrite default full metrics/artifacts. One worker is the measured default. Optional multiprocessing uses Windows spawn, preserves input order/seeded metrics, and limits worker BLAS threads to one. The benchmark compares bounded equivalent prediction paths, profiles stages, inspects cached weather only, and reports RSS/throughput. More workers were slower; 16/20 were not justified.

## Historical evaluation

Check active processes first. Write separate evaluation files:

```powershell
& $MlPython -m ml.backtest --workers 1 --output-dir ml/reports/purged_v2 --model-path ml/artifacts/evaluated_v2/active_event.joblib
& $MlPython -m ml.weather_backtest --per-year 20 --cache-only --output ml/reports/purged_v2/weather_comparison.json
& $MlPython -m ml.monte_carlo --event-fixture ml/fixtures/active_flood.json --trials 5000 --seed 42 --output ml/reports/dev/monte_carlo.json
```

The corrected full evaluation took about eight seconds here. Entire episodes crossing fit/selection boundaries are purged. The 2025 period was already inspected; a correction does not make it an untouched holdout.

The weather command makes zero network requests in cache-only mode. A fresh checkout has no weather cache; insufficient cached support fails explicitly. An intentional run without `--cache-only` may fetch up to 20 responses per year sequentially. ERA5 valid time does not establish historical operational availability.

See `ml/INTEGRATION.md` for typed input, the tested adapter, exact output example, receipt verification, and backend import setup. No ML route is added.
# Comprehensive hazard acceptance: `python -m ml.hazard_rehearsal --require-models`

After the existing provisioning steps below, this runs the 31 scenarios and 50 reconciled EIA sites offline. See [HAZARD_INTEGRATION.md](HAZARD_INTEGRATION.md) for 2.1 migration, frozen schemas, source gaps and owner handoffs.

