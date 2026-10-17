# Evaluation

**Current evidence: newly rerun, boundary-purged historical Flood backtest; production eligibility is false.** The 2025 period was previously inspected. It is out of time relative to fitting, but not a fresh untouched holdout.

## Provenance and correction

All five NOAA NCEI Storm Events 2021-2025 detail archives match sizes/SHA-256 in `ml/reports/source_manifest.json`. Parsing reproduced 349,030 rows, 10,322 valid Flood intervals, 1,249 malformed Flood exclusions, zero duplicate event IDs, and 2,945 episodes. Raw data and binary artifacts remain ignored.

Earliest-start assignment allowed later outcomes into training: one episode crosses 2024-01-01 and seven cross 2025-01-01. V2 purges all 12 records in those eight episodes from every split. Original `ml/reports/backtest_metrics.json`, weather reports, and models are retained as **superseded v1 evidence**. Current results are in `ml/reports/purged_v2/backtest_metrics.json`.

| Split | Records | Episodes | Snapshots |
|---|---:|---:|---:|
| Train, 2021-2023 | 6,245 | 1,787 | 10,558 |
| Validation, 2024 | 2,161 | 583 | 4,053 |
| Test, 2025 | 1,904 | 567 | 3,539 |

Final fitting uses 8,406 records / 2,370 episodes through 2024. No onset, injury, site safety, or severity/trend target is modeled.

## Full-cohort comparison

Identical eligible snapshots are used per horizon. Lower Brier is better. JSON includes reliability tables and 500-replicate episode-bootstrap 95% intervals.

| Period | Horizon | Age/month logistic | Conditional KM |
|---|---:|---:|---:|
| 2024 validation | 6h | 0.216986 | 0.211733 |
| 2024 validation | 12h | 0.242210 | 0.232385 |
| 2024 validation | 24h | 0.239856 | 0.224849 |
| 2025 corrected test | 6h | 0.219250 | 0.226955 |
| 2025 corrected test | 12h | 0.238631 | 0.243271 |
| 2025 corrected test | 24h | 0.208665 | 0.209916 |

KM wins all validation horizons and remains default. Logistic wins the inspected test comparisons, with small differences at 12/24h. This is not stable evidence of superiority or operational utility. Hyperparameters were not tuned on the 2025 correction.

| Test duration metric | Logistic | KM |
|---|---:|---:|
| Median remaining-time MAE, 3,539 snapshots | 40.71h | 41.26h |
| Identifiable p10/p90 interval count | 1,843 | 1,904 |
| Coverage among identified intervals | 88.28% | 79.52% |
| Unidentified interval count | 1,696 | 1,635 |

Coverage populations differ; these percentages are not a paired superiority comparison. Median-MAE bootstrap ranges are 30.38-54.45h (logistic) and 30.96-54.73h (KM). Large duration errors limit site-specific planning. Calibration is imperfect: test KM 24h predictions averaging 0.614 correspond to observed persistence 0.437 (686 snapshots). Episode resampling does not remove regional/storm reporting dependence.

## Matched retrospective weather experiment

`ml/reports/purged_v2/weather_comparison.json` was rerun with 100 cached ERA5 responses and zero network calls. There are 60 training, 20 validation, and 20 test episodes, one representative event per episode. All three models use identical fetched training event IDs. Weather is frozen at snapshot time, with train-only imputation/scaling. Its repeated-snapshot risk rows differ from event-level age/month fitting; gains cannot be attributed solely to added weather features.

Each horizon uses the prediction intersection: **28 validation snapshots / 20 episodes**, **26 test snapshots / 20 episodes**. The old unequal-sample report (34 versus 28 validation, 30 versus 26 test) is unsuitable for comparison.

| Period | Horizon | Weather | Age/month | KM |
|---|---:|---:|---:|---:|
| 2024 validation | 6h | 0.228451 | 0.242415 | 0.230903 |
| 2024 validation | 12h | 0.264725 | 0.240773 | 0.227844 |
| 2024 validation | 24h | 0.272163 | 0.244036 | 0.214405 |
| 2025 inspected test | 6h | 0.143758 | 0.211857 | 0.218938 |
| 2025 inspected test | 12h | 0.125528 | 0.187789 | 0.181733 |
| 2025 inspected test | 24h | 0.141386 | 0.162950 | 0.157605 |

Mean validation Brier is 0.255113 weather / 0.242408 age-month / 0.224384 KM. The existing rule requiring 2% improvement over both references does not select weather; the fallback selects KM. Test gains cannot reverse that decision.

JSON includes calibration, grouped Brier intervals, duration error/coverage intervals, per-model identifiable-tail counts, a separate duration comparison on common finite intervals, and weather response URL/hash provenance. ERA5 valid times precede as-of, but historical operational availability is unverified. Cached original acquisition times are unknown and labeled. Regional points do not verify EIA-site exposure. Weather never enters runtime inference, scoring, or operational instructions.

## Timing and Monte Carlo

See `ml/reports/purged_v2/benchmark.json` and `ml/TAKEOVER_REPORT.md`. The corrected full evaluation took about eight seconds including startup, with parsing, snapshot, fitting, scoring, and save timings recorded separately. This is not a measured speedup against the unfinished old job.

The preserved v1 Monte Carlo summary remains arithmetic evidence only. The newly rerun v2 5,000-draw check has absolute analytic/sampling errors 0.00308/0.00403/0.00090 at 6/12/24h and 172 unresolved draws. Unresolved draws remain in quantile denominators, so unidentified tails return null. Current simulation is offline/internal and excluded from inference. Agreement with model-implied persistence does not validate real-world accuracy. Replays and fixtures are labeled simulated.
