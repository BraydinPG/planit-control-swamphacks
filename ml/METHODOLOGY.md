# Methodology

This page describes the preserved Flood baseline. The separately defined multi-disaster targets, grouping, source limitations, and evaluation gates are in [MULTIDISASTER.md](MULTIDISASTER.md).

## Prediction scope

This package estimates the recorded continuation/resolution of a NOAA Flood event conditional on that event already being active at an as-of time. It does not estimate disaster onset, local water depth, damage, injury, infrastructure condition, worksite accessibility, or safe-to-work status. `trend` remains `unknown` because this dataset does not provide matched time-varying severity labels available at prediction time.

The ground-truth label is the end of an event record. NOAA records can describe county/zone or a reported point and may be finalized after the event. Recorded event resolution is not evidence that a worksite is safe or that an alert can be cleared.

## Source data and join quality

Training and evaluation use the official NOAA NCEI Storm Events bulk detail archives for 2021–2025:

- Index: https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/
- Archive documentation: https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/README
- Event detail fields include `EVENT_ID`, `EPISODE_ID`, `EVENT_TYPE`, `BEGIN_DATE_TIME`, `END_DATE_TIME`, `CZ_TIMEZONE`, `STATE`, `CZ_TYPE`, `CZ_NAME`, and optional reported coordinates.

The exact archive revision, URL, byte count, retrieval timestamp, and SHA-256 are recorded in `ml/reports/source_manifest.json`. Only `EVENT_TYPE == "Flood"` is modeled. For 2021–2025, the parser read 349,030 detail rows, retained 10,322 valid Flood intervals, rejected 1,249 malformed Flood rows, observed no duplicate event IDs, and found no Flood rows with missing recorded ends. These are event records, not independent disasters: the 10,322 retained rows map to 2,945 `EPISODE_ID` groups.

NOAA county/zone names and reported coordinates are not joined to Rudra's EIA locations. A coordinate reported in an event record is not proof of site exposure. No EIA catalog or verified jobsite inventory existed in the audited repository.

NOAA date/time fields are local. The parser uses the numeric fixed offset in `CZ_TIMEZONE` to normalize both endpoints to UTC. This preserves interval arithmetic for most rows but can misstate absolute UTC time and durations across daylight-saving transitions. This limitation must be resolved with timezone-aware NOAA metadata before any finer time-of-day operational use.

## Features and leakage controls

At most three snapshots are generated per complete event record: event start, +6 hours, and +12 hours, and only while `as_of < recorded_end`. Every snapshot has a separate feature and label section.

The complete predictor allowlist is:

- `event_type` (only Flood is currently trained)
- `elapsed_hours` conditional on the event still being active
- `start_month` represented as sine/cosine terms in the fitted model

`END_DATE_TIME`, total duration, final event magnitude, damage, casualties, narratives, and all post-as-of observations are never features. The generated hazard training rows contain one row per at-risk hour, with an event-end indicator for the next hour. Episodes stay intact across splits. Events longer than 168 hours are administratively right-censored at that horizon; unknown-end rows are excluded rather than labeled resolved. The Flood archive subset happened to contain no unknown-end intervals.

Runtime inference does not use weather or current site observations. A separate research experiment joins cached Open-Meteo ERA5 reanalysis to 100 reported NOAA event points, retaining only valid times at or before each snapshot. Historical operational availability and site exposure remain unverified. Acquisition-time gaps are explicit. This experiment is production-ineligible and is not an archived issued-forecast backtest.

## Models

The required comparison is an empirical Kaplan–Meier recorded-duration baseline. For elapsed event age $a$ and forecast horizon $h$, the baseline estimates conditional persistence as $S(a+h)/S(a)$, with a training-only risk-set support check. It does not draw an unconditional total duration and subtract event age.

KM is the default advisory estimator because corrected 2024 validation favors it at all horizons. Logistic remains an explicit comparison. Both use the same trusted artifact bundle. V2 artifacts include a boundary-purging training policy; legacy artifacts are labeled superseded. No estimator contributes to the site score.

The fitted model is a regularized pooled-logistic discrete-time hazard model (`scikit-learn LogisticRegression`, `C=0.1`, fixed seed 42). Features are `log1p(elapsed_hours)`, `sin(start_month)`, and `cos(start_month)`. Hourly conditional end hazards are multiplied to obtain consistent, non-increasing persistence probabilities. Event rows within one NOAA episode are downweighted by the count of rows in that episode. The artifact stores training event/episode counts, support limits, the KM baseline records, and model version.

## Validation design

- Train: event-onset years 2021–2023, 1,787 episode groups.
- Validation: 2024, 583 episode groups, with all same-episode records assigned together.
- Final out-of-time test: 2025, 567 episode groups, not used to fit the reported final model.
- Snapshot counts: 10,558 train, 4,053 validation, and 3,539 test. Snapshot-level metrics are correlated and are reported with episode counts and episode-group bootstrap intervals.

Entire episodes whose recorded outcomes cross 2024-01-01 or 2025-01-01 are purged before fitting or selection: eight episodes / 12 records. Earliest-start grouping alone leaked later outcomes in v1. Weather sampling retains full episode boundaries even when the earliest event has no reported coordinates. Unknown-end events never become resolved labels. The inspected 2025 period is not a fresh untouched holdout after correction.

Current metrics and the replay are in `ml/EVALUATION.md` and `ml/reports/purged_v2/backtest_metrics.json`. The original report is preserved as superseded v1 evidence. Bootstrap resamples complete episodes and computes snapshot-weighted metrics; preaggregated group sums preserve seeded estimates within floating-point tolerance. Monte Carlo is an offline arithmetic check, not independent accuracy evidence.
