# Evaluation

**Status: REAL HISTORICAL OUT-OF-TIME BACKTEST COMPLETED.** This validates prediction of NOAA recorded Flood interval persistence only, not site-level flood conditions or worker safety.

## Data and split

Downloaded NOAA NCEI Storm Events detail archives for 2021–2025. The actual source filenames, URLs, byte sizes, retrieval timestamps, and SHA-256 hashes are in `ml/reports/source_manifest.json`; no raw data or model artifact is committed.

The parser read 349,030 rows, retained 10,322 valid Flood event records, rejected 1,249 malformed supported-type rows, and found zero duplicate event IDs and zero unknown-end Flood records. NOAA event records were grouped by `EPISODE_ID` before splitting:

| Split | Years | Event records | NOAA episode groups | Active snapshots |
|---|---:|---:|---:|---:|
| Train | 2021–2023 | 6,249 | 1,788 | 10,564 |
| Validation | 2024 | 2,169 | 590 | 4,077 |
| Out-of-time test | 2025 | 1,904 | 567 | 3,539 |

All records in an episode were assigned by the episode's earliest event-start year. Final test predictions use a model fit only on 2021–2024. There are no weather features in this model.

## Brier scores

Target is `P(recorded Flood event still ongoing at horizon | recorded event active at as-of time)`. Lower is better. Scores are computed over correlated snapshots; episode counts and episode-bootstrap ranges are included in the JSON report.

| Held-out period | Horizon | Pooled logistic | Conditional KM baseline |
|---|---:|---:|---:|
| 2024 validation (trained through 2023) | 6h | 0.2168 | 0.2116 |
| 2024 validation (trained through 2023) | 12h | 0.2425 | 0.2327 |
| 2024 validation (trained through 2023) | 24h | 0.2408 | 0.2255 |
| 2025 test (trained through 2024) | 6h | 0.2189 | 0.2269 |
| 2025 test (trained through 2024) | 12h | 0.2390 | 0.2433 |
| 2025 test (trained through 2024) | 24h | 0.2097 | 0.2100 |

The fitted model is slightly better on the 2025 6h and 12h Brier scores and essentially tied at 24h, but it is worse than the KM baseline at all three horizons on 2024 validation. This is not stable evidence that the fitted model is generally superior; do not present it as such or use the tiny test gains to claim operational utility.

Episode bootstrap 95% ranges for the 2025 logistic Brier scores were 0.2027–0.2373 (6h), 0.2245–0.2536 (12h), and 0.1949–0.2218 (24h). These intervals quantify resampling variability across observed episode groups, not geographic independence or future operational performance.

## Duration and calibration

On 3,539 test snapshots, median remaining-duration MAE was 40.83 hours. This large error reflects a long-tailed duration distribution and shows that the median duration is not a reliable site-specific planning estimate. The model could identify finite p10/p90 bounds for only 1,331 snapshots; their empirical p10–p90 coverage was 86.9%. For the remaining 2,208 snapshots at least one tail quantile was not identifiable before the 168-hour modeling horizon and is returned as null.

Reliability tables are in `backtest_metrics.json`. At 24 hours, for example, the 0.6–0.7 predicted-persistence bin averaged 0.623 while the observed frequency was 0.450 (391 snapshots), an overestimate of recorded persistence. The largest 6h probability errors include test event `1284116` / episode `205751`: predicted persistence 0.859, but the recorded interval ended within 6h. Such early recorded ends matter because overestimated persistence can mislead planning just as unsupported early-resolution claims can.

## Held-out replay

NOAA event `1230682` was replayed at `2025-02-25T21:30:00Z`, with the final model trained through 2024. The model estimated recorded-event persistence of 0.786 at 6h, 0.668 at 12h, and 0.530 at 24h; the conditional median remaining duration was 28h and p90 was unidentifiable. The later NOAA recorded end was `2025-02-27T00:45:00Z`, 27.25 hours after the replay time. The event is region-only and this result does not establish local conditions or clearance.

## Offline Monte Carlo

The synthetic, explicitly labeled fixture was sampled 5,000 times with seed 42. Absolute simulated-vs-analytic persistence differences were 0.0038 (6h), 0.0052 (12h), and 0.0029 (24h); 179/5,000 draws remained unresolved at the 168h simulation horizon. This confirms sampler arithmetic/reproducibility only. It does not validate the model; the historical backtest above is the independent outcome evaluation. Summary: `ml/reports/monte_carlo_summary.json`.

## Limitations

- NOAA county/zone records are regional proxies and are not verified EIA-site or worksite flood labels.
- Event time uses a fixed numeric source offset; daylight-saving ambiguity limits absolute-time precision.
- Current model features omit historical weather and current observations. The Open-Meteo adapter is tested and retrieved retrospective reanalysis, but it is not joined or treated as a forecast issued at the historical decision time.
- No matched severity time series exists here; trend is always `unknown`.
- The out-of-time test is one calendar year and shares broad geographic/reporting processes with training years.
- Event-record end is not an all-clear, safe-to-enter, or resume-work label.
