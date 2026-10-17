# Multi-disaster evaluation

All values are actual retrospective results. Passing the stated screen means research only. No category is operationally eligible. Flood v2 results remain in [EVALUATION.md](EVALUATION.md). Read [MULTIDISASTER.md](MULTIDISASTER.md) for source vintages, targets, predeclared gates, grouping, missingness, and selection.

## Separate cohorts

| Target | Train records / groups / snapshots | Validation records / groups / snapshots | Test records / groups / snapshots | Selected | Status |
|---|---:|---:|---:|---|---|
| Flash Flood | 10696 / 3067 / 11186 | 4198 / 948 / 4752 | 4625 / 1105 / 5041 | kaplan_meier | evaluated_research |
| Heat Index Exceedance | 1666 / 265 / 4391 | 524 / 92 / 1438 | 396 / 59 / 1116 | logistic | evaluated_research |
| Heavy Rain | 2206 / 602 / 5751 | 569 / 148 / 1642 | 419 / 142 / 821 | kaplan_meier | evaluated_research |
| Heavy Snow | 7002 / 1425 / 26123 | 1848 / 443 / 7032 | 1717 / 365 / 6282 | logistic | trained_not_qualified |
| High Wind | 9520 / 2227 / 17756 | 2749 / 734 / 5231 | 3307 / 721 / 6952 | kaplan_meier | evaluated_research |
| Ice Storm | 856 / 147 / 3171 | 112 / 22 / 417 | 117 / 36 / 427 | logistic | trained_not_qualified |
| Strong Wind | 2334 / 553 / 5157 | 1045 / 208 / 2375 | 939 / 207 / 2557 | logistic | trained_not_qualified |
| Winter Storm | 8874 / 1415 / 33295 | 2006 / 371 / 7731 | 2579 / 399 / 9629 | kaplan_meier | evaluated_research |

Groups above include all records in the split; evaluation groups below count only eligible snapshots. They are reporting clusters/station weeks, not proven independent disasters. Chronological years are 2021?2023 / 2024 / 2025; heat 2025 ends in August.

## Persistence comparisons

| Target | Horizon | Val logistic Brier | Val KM Brier | Test logistic Brier | Test KM Brier | Selected test ECE | Test snapshots / groups | Selected test Brier 95% CI |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Flash Flood | 1h | 0.227569 | 0.230807 | 0.231981 | 0.231067 | 0.0031 | 5041 / 880 | 0.221170?0.242941 |
| Flash Flood | 3h | 0.192295 | 0.182601 | 0.190386 | 0.190365 | 0.0391 | 5041 / 880 | 0.161440?0.215181 |
| Flash Flood | 6h | 0.077661 | 0.070508 | 0.090033 | 0.092018 | 0.0373 | 5041 / 880 | 0.063294?0.120662 |
| Heat Index Exceedance | 1h | 0.094068 | 0.095448 | 0.093563 | 0.095752 | 0.0098 | 1116 / 59 | 0.076440?0.112098 |
| Heat Index Exceedance | 3h | 0.177651 | 0.186137 | 0.172261 | 0.177199 | 0.0312 | 1116 / 59 | 0.150982?0.196818 |
| Heat Index Exceedance | 6h | 0.231351 | 0.244864 | 0.230244 | 0.240589 | 0.0624 | 1116 / 59 | 0.213751?0.247808 |
| Heavy Rain | 1h | 0.059119 | 0.058268 | 0.099221 | 0.102663 | 0.0421 | 821 / 103 | 0.065778?0.157181 |
| Heavy Rain | 3h | 0.133236 | 0.123465 | 0.157414 | 0.160640 | 0.0423 | 821 / 103 | 0.113860?0.229531 |
| Heavy Rain | 6h | 0.208538 | 0.175454 | 0.211247 | 0.199389 | 0.0374 | 821 / 103 | 0.151984?0.254834 |
| Heavy Snow | 6h | 0.086582 | 0.088229 | 0.131606 | 0.126539 | 0.0398 | 6282 / 363 | 0.115115?0.149293 |
| Heavy Snow | 12h | 0.183965 | 0.193368 | 0.269917 | 0.259768 | 0.1556 | 6282 / 363 | 0.246437?0.292400 |
| Heavy Snow | 24h | 0.246280 | 0.260807 | 0.187596 | 0.168203 | 0.1820 | 6282 / 363 | 0.177796?0.199265 |
| High Wind | 6h | 0.255165 | 0.249835 | 0.254755 | 0.251375 | 0.0280 | 6952 / 580 | 0.244726?0.257593 |
| High Wind | 12h | 0.184305 | 0.181513 | 0.165637 | 0.163174 | 0.0510 | 6952 / 580 | 0.141655?0.183967 |
| High Wind | 24h | 0.076379 | 0.074965 | 0.048488 | 0.046757 | 0.0511 | 6952 / 580 | 0.033555?0.062677 |
| Ice Storm | 6h | 0.158888 | 0.155597 | 0.154901 | 0.153985 | 0.0542 | 427 / 36 | 0.116452?0.209667 |
| Ice Storm | 12h | 0.238995 | 0.246124 | 0.238901 | 0.238631 | 0.0840 | 427 / 36 | 0.223803?0.254411 |
| Ice Storm | 24h | 0.046649 | 0.075958 | 0.210446 | 0.204821 | 0.0975 | 427 / 36 | 0.077269?0.358047 |
| Strong Wind | 1h | 0.075278 | 0.069183 | 0.067964 | 0.062716 | 0.0768 | 2557 / 166 | 0.050611?0.091089 |
| Strong Wind | 3h | 0.203322 | 0.202500 | 0.180893 | 0.159622 | 0.1520 | 2557 / 166 | 0.160828?0.204628 |
| Strong Wind | 6h | 0.241368 | 0.263085 | 0.268342 | 0.252523 | 0.1416 | 2557 / 166 | 0.256659?0.280932 |
| Winter Storm | 6h | 0.084289 | 0.083657 | 0.135275 | 0.132659 | 0.0386 | 9629 / 398 | 0.110701?0.160180 |
| Winter Storm | 12h | 0.188698 | 0.192980 | 0.245666 | 0.240151 | 0.0961 | 9629 / 398 | 0.224204?0.258459 |
| Winter Storm | 24h | 0.224983 | 0.229275 | 0.174661 | 0.160578 | 0.1361 | 9629 / 398 | 0.147523?0.174416 |

Full reliability bins, positive/negative class support, validation confidence intervals, fixed gates, and exclusions are in each [model card](reports/multidisaster/). Confidence intervals use 500 seeded group-bootstrap replicates. Matching eligible cohorts are used for each persistence comparison.

## Remaining duration

| Target | Estimator | Test median MAE hours | Median support | 10?90% interval coverage | Interval support | Unidentified intervals |
|---|---|---:|---:|---:|---:|---:|
| Flash Flood | logistic | 3.251 | 5041 | 0.6961 | 5041 | 0 |
| Flash Flood | kaplan_meier | 3.267 | 5041 | 0.6733 | 5041 | 0 |
| Heat Index Exceedance | logistic | 6.262 | 1116 | 0.9211 | 1116 | 0 |
| Heat Index Exceedance | kaplan_meier | 6.164 | 1116 | 0.8871 | 1116 | 0 |
| Heavy Rain | logistic | 24.552 | 821 | 0.6078 | 821 | 0 |
| Heavy Rain | kaplan_meier | 23.884 | 821 | 0.5786 | 821 | 0 |
| Heavy Snow | logistic | 9.627 | 6282 | 0.8889 | 6282 | 0 |
| Heavy Snow | kaplan_meier | 9.230 | 6282 | 0.8594 | 6282 | 0 |
| High Wind | logistic | 6.004 | 6952 | 0.8790 | 6952 | 0 |
| High Wind | kaplan_meier | 5.947 | 6952 | 0.8787 | 6952 | 0 |
| Ice Storm | logistic | 11.665 | 427 | 0.7354 | 427 | 0 |
| Ice Storm | kaplan_meier | 11.857 | 427 | 0.7049 | 427 | 0 |
| Strong Wind | logistic | 6.201 | 2557 | 0.8893 | 2557 | 0 |
| Strong Wind | kaplan_meier | 5.928 | 2557 | 0.8072 | 2557 | 0 |
| Winter Storm | logistic | 8.952 | 9629 | 0.8735 | 9629 | 0 |
| Winter Storm | kaplan_meier | 8.643 | 9629 | 0.8283 | 9629 | 0 |

Coverage is conditional on identified quantiles before the 168h total-age modeling limit. Duration support can differ by estimator and from persistence support. Nominal 80% intervals are experimental; the persistence gate does not certify duration calibration. Per-model JSON includes group-bootstrap MAE/coverage intervals.

## Disabled trained targets

- **Heavy Snow**: test_12h_calibration_gate_failed, test_24h_calibration_gate_failed. No replacement estimator or horizon subset was chosen using test results.
- **Ice Storm**: validation_6h_insufficient_episode_groups, validation_12h_insufficient_episode_groups, validation_24h_insufficient_episode_groups, validation_24h_sparse_outcome_class, validation_24h_calibration_gate_failed. No replacement estimator or horizon subset was chosen using test results.
- **Strong Wind**: test_3h_calibration_gate_failed. No replacement estimator or horizon subset was chosen using test results.

## NHC retrospective wind change

Separate categorical target, not persistence or worksite severity. Train/validation/test storm counts: **325 / 67 / 50**; snapshots: **6,522 / 1,191 / 976**. Selected logistic from 2020?2022 validation; 2023?2025 test was then scored once.

| Period | Logistic multiclass Brier | Training-frequency baseline |
|---|---:|---:|
| validation | 0.570662 | 0.655172 |
| test | 0.554661 | 0.678992 |

| Test class | Logistic Brier | Baseline Brier | Logistic ECE | Positive / negative labels | Logistic Brier 95% CI |
|---|---:|---:|---:|---:|---|
| improving | 0.150582 | 0.212556 | 0.0621 | 298 / 678 | 0.134194?0.169632 |
| stable | 0.205659 | 0.237434 | 0.0672 | 347 / 629 | 0.191256?0.219794 |
| worsening | 0.198420 | 0.229001 | 0.1070 | 331 / 645 | 0.183563?0.216693 |

No hurricane live inference is enabled: these are post-analysis best tracks without validated historical operational availability. Pressure/position/wind are storm-scale. Missing future observations are excluded, not assigned improving labels. There is no duration metric for this categorical target. Full results: [hurricane_trend.json](reports/multidisaster/hurricane_trend.json).

## Execution and examples

| Target | First serial backtest seconds | Warm inference median ms |
|---|---:|---:|
| Flash Flood | 9.55 | 0.0773 |
| Heat Index Exceedance | 0.81 | 0.1811 |
| Heavy Rain | 1.96 | 0.0789 |
| Heavy Snow | 9.15 | disabled |
| High Wind | 4.97 | 0.0801 |
| Ice Storm | 0.72 | disabled |
| Strong Wind | 1.65 | disabled |
| Winter Storm | 12.34 | 0.0825 |

Hurricane experiment: 0.22s. No multiple full backtests ran simultaneously; no new multiprocessing was introduced. One fitted model is cached per type/hash in the backend adapter. [examples.json](reports/multidisaster/examples.json) contains real historical replay contexts/results for all five qualified new duration targets, labeled simulated. [runtime_checks.json](reports/multidisaster/runtime_checks.json) includes first-call/p95 timing, analytical/Monte Carlo comparisons, historical duration errors, and per-replay observed remaining duration. Flood reference checks also pass.
