# Codex takeover delivery - October 17, 2026

The existing workspace was preserved on `feature/cache-ml`. Initial HEAD was `8db7dac` with 17 uncommitted ML files. Fetch succeeded; team changes through `origin/main` at `5bde676` were integrated without rewriting backend, frontend, auth, database, or ingestion implementations.

## Git and scope

- `561439a`: secured the reviewed survival optimization, weather experiment, and tests; fixed the untracked benchmark syntax error.
- `586ed56`: integrated current team scope, preserving Tiger Data/Vultr, Braydin's ingestion/database ownership, and the authorized conditional-event boundary.
- `545d898`: boundary-purged v2 training/evaluation, KM default, typed inference/adapter safeguards, pinned provisioning, and regression tests.
- Subsequent documentation/evidence commits contain this report, updated guides, current JSON reports, and PR handoff. See `git log` and the final delivery message for the final HEAD/PR.

Shared documentation edits are limited to resolving merge conflicts, retaining the authorized active-event contract, removing a duplicated Cache task, and correcting model-failure behavior. Root manifests, lockfiles, teammate source, migrations, and secrets were not changed. README changes came from the team merge.

## Audit, preservation, and processes

Both root `.venv` and `ml/.venv` were valid; work used `ml/.venv` (Python 3.14.5). The initial suite passed 63 tests, while compilation caught an indentation error in the untracked benchmark. Existing model inference and archive checks succeeded.

Old PIDs 23928/28572 were a verified parent/child full backtest using pre-optimization code. They remained running during initial inspection/short benchmarks. A later chronology audit established that their evaluation allowed outcomes past fitting cutoffs. Current artifacts/reports were copied with verified hashes into ignored `ml/artifacts/takeover_preserved/`; original optimization backups also remain. Only then were the exact command lines/PIDs reverified and stopped. No replacement evaluation overlapped that obsolete job. No ML job remained running at delivery checks.

Original model SHA-256: `4f296347ef289bad37cf6623dccae35d06b7e269f7b5118ae5897d1946a40a80`.

Current provisioned model SHA-256: `2d33812b2d238bfa0ad18665f0b447c5d0d6925c1398c763814d4e5889067598`. A newly created environment rebuilt exactly the same bytes. Existing original model/report/weather hashes were checked again and remained unchanged.

## Data and model evidence

All five 2021-2025 NOAA archives match the checked-in provenance manifest. Parsing reproduced 349,030 source rows, 10,322 retained Flood records, 1,249 malformed/unsupported-interval Flood exclusions, zero duplicate IDs, and 2,945 episodes. See `ml/reports/source_manifest.json` for exact official URLs, revision filenames, original acquisition times, sizes, and SHA-256 values.

Eight episodes (12 records) crossed fitting/selection boundaries and are now purged. Current populations: training 6,245 records / 1,787 episodes / 10,558 snapshots; validation 2,161 / 583 / 4,053; test 1,904 / 567 / 3,539. Final model fitting uses 8,406 records / 2,370 episodes through 2024. The 2025 data were already inspected; corrected results are not an untouched holdout.

| Full-cohort Brier, 6/12/24h | Logistic | KM |
|---|---|---|
| 2024 validation | 0.216986 / 0.242210 / 0.239856 | 0.211733 / 0.232385 / 0.224849 |
| 2025 corrected test | 0.219250 / 0.238631 / 0.208665 | 0.226955 / 0.243271 / 0.209916 |

KM remains default because it wins validation at every horizon. Test median-duration MAE is 40.71h logistic / 41.26h KM. Interval coverage is 88.28% on 1,843 identified logistic intervals and 79.52% on 1,904 KM intervals; these are different identifiable-tail populations. Complete calibration, support, grouped Brier/MAE/coverage intervals, and limitations are in `ml/EVALUATION.md` and `ml/reports/purged_v2/backtest_metrics.json`. Original v1 metrics remain preserved and explicitly superseded.

The weather comparison reuses 100 cached ERA5 responses with zero network calls. Matched populations are 28 validation snapshots / 20 episodes and 26 test snapshots / 20 episodes. Mean validation Brier is 0.255113 weather / 0.242408 age-month / 0.224384 KM, selecting KM. Matched 2025 Brier at 6/12/24h is weather 0.143758/0.125528/0.141386, age-month 0.211857/0.187789/0.162950, KM 0.218938/0.181733/0.157605. Full calibration/duration/interval/support/provenance appears in `weather_comparison.json`. Valid-time filtering does not establish historical operational availability. No weather promotion occurred.

Only Flood is supported. Flash Flood, severe thunderstorms, high wind, hurricanes/tropical storms, heat, heavy rain, and severity trends remain unsupported pending separate labels/backtests. NOAA regional recorded ends are not site exposure, safety, or clearance outcomes. All returned outlooks have `production_eligibility=false`; trend is unknown; score components stay excluded.

## Runtime measurements

Hardware reports 12 physical cores / 24 logical processors. The final bounded benchmark uses 100 events / 161 snapshots. All tested process counts match serial metrics. A short smoke run and dependency installation were concurrent, so these are not uncontended machine measurements.

| Workers | Scoring/metrics seconds | Snapshots/s | Peak process-tree RSS MiB |
|---|---:|---:|---:|
| 1 | 0.162 | 995.9 | 137.6 |
| 4 | 7.401 | 21.8 | 623.0 |
| 8 | 11.318 | 14.2 | 987.7 |
| 12 | 13.170 | 12.2 | 1108.7 |

One worker is now default; 16/20 were not sensible given spawn/import overhead. On 24 paired snapshots over five alternating-order repetitions, preserved repeated-curve prediction took median 17.439ms versus 5.450ms for reuse: **3.20x measured prediction speedup**, parity tolerance 1e-12. A shared KM-duration addition is included in both paths. The earlier narrower pre-addition comparison measured 4.24x. Neither is a full-backtest speedup claim.

Profiled stages: NOAA parsing 3.056s; grouping/snapshots 0.01695s; artifact load 0.00715s; smoke fit 0.00489s; cached weather attachment 0.04004s; survival prediction 0.02237s; quantile extraction 0.00179s; 200-replicate bootstrap 0.00322s; 500-trial Monte Carlo 0.00912s; serialization 0.00043s. Preaggregation replaced repeated bootstrap flattening after profiling identified it as the remaining scoring hotspot; a seeded reference test checks arithmetic equivalence.

The corrected full backtest including both duration estimators took **8.35s including startup**. Its recorded stages were parsing 2.861s, snapshots 0.097s, validation/final fitting 0.339/0.522s, validation/test scoring 1.427/1.297s, and save 0.014s. The old job never completed, so no full-run old/new wall-clock ratio is available.

The separate 5,000-draw v2 offline Monte Carlo check has absolute analytic/sampling differences 0.00308/0.00403/0.00090 at 6/12/24h, with 172 unresolved draws. Unresolved draws now stay in duration-quantile denominators. This tests sampler arithmetic, not real-world accuracy, and exposes no trajectories to production.

## Reproduction and checks

`ml/setup.ps1`, exact `ml/requirements-lock.txt`, immutable source provenance, reference predictions, and checksum receipts provide regeneration without ignored local artifacts. Clean reproduction was actually executed, including byte-identical output. `ml/QUICKSTART.md` has exact setup, fast evaluation, full evaluation, and profiling commands.

Final focused checks:

```powershell
.\ml\.venv\takeover_clean_check\Scripts\python.exe -m pytest ml/tests backend/tests -q -c backend/pytest.ini
# 82 passed: 81 ML + 1 backend health; one upstream Starlette/httpx deprecation warning.
.\ml\.venv\Scripts\python.exe -m compileall -q ml -x '\.venv'
git diff origin/main --check
```

Additional executed checks: pinned `pip check`, artifact provisioning and `--verify-only`, fresh-environment model regeneration, direct/saved-model inference, backend-working-directory adapter import, `ml.smoke`, `ml.backtest --fast`, full purged backtest, matched cache-only weather comparison, worker benchmark at 1/4/8/12, and 5,000 seeded Monte Carlo draws. No Python lint/type checker is configured. Frontend build/lint were not run: Node/npm are unavailable in this shell and frontend source was not edited.

## Integration and remaining work

`ml/INTEGRATION.md` contains a copy-ready Rudra handoff, typed input/output, exact synthetic JSON example, full measured output link, process-level loader, missing-artifact behavior, and import setup from `backend/`. For the example active replay, KM persistence is 0.709366/0.604959/0.473003 at 6/12/24h, median remaining duration 22h, p90 unknown. Adapter latency was 6.88ms cold load, 0.099ms warm median, 0.112ms warm p95 over 100 calls. These are local component timings, not route latency.

Rudra still needs the confirmed-event/as-of API contract, authorization, and optional outlook response field (T050). Braydin's actual site/event ingestion and auth modules are absent. No live ML route, site-safety claim, severity trend model, additional supported category, or frontend integration is claimed. ERA5 needs genuinely historical-as-of available inputs before operational evaluation. New untouched episodes/periods are needed for a fresh holdout; test-set tuning was not performed.
