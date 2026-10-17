# Historical coverage and label audit

Source: checksum-pinned NOAA NCEI Storm Events detail archives, 2021-2025; 349,030 rows inspected once.

| Original NOAA type | Rows | Episode groups | Positive intervals | Zero-duration | Positive median hours | Missing coordinates |
|---|---:|---:|---:|---:|---:|---:|
| Flood | 11,571 | 3,306 | 10,322 | 1,242 | 5.0 | 0 |
| Flash Flood | 21,573 | 5,581 | 19,544 | 2,019 | 2.0 | 0 |
| Thunderstorm Wind | 96,112 | 15,736 | 28,139 | 67,969 | 0.03333333333333333 | 6 |
| High Wind | 21,866 | 4,858 | 15,754 | 6,110 | 4.6 | 21,864 |
| Strong Wind | 5,457 | 1,291 | 4,415 | 1,038 | 7.0 | 5,453 |
| Hurricane (Typhoon) | 154 | 23 | 136 | 12 | 18.0 | 148 |
| Tropical Storm | 1,286 | 160 | 1,099 | 179 | 9.0 | 1,278 |
| Tropical Depression | 105 | 28 | 94 | 4 | 18.0 | 98 |
| Excessive Heat | 11,409 | 1,088 | 11,390 | 19 | 13.983333333333333 | 11,409 |
| Heat | 12,638 | 1,213 | 12,447 | 191 | 9.0 | 12,638 |
| Heavy Rain | 4,834 | 1,181 | 3,200 | 1,634 | 9.4 | 0 |
| Wildfire | 1,756 | 1,364 | 1,713 | 42 | 98.0 | 1,755 |
| Winter Storm | 14,119 | 2,288 | 14,081 | 38 | 21.0 | 14,119 |
| Ice Storm | 1,188 | 222 | 1,184 | 4 | 18.5 | 1,188 |
| Heavy Snow | 11,108 | 2,326 | 10,929 | 179 | 22.0 | 11,108 |

Counts are real records and reporting groups, not a verified count of independent meteorological disasters. Per-year/state coverage, exclusions, durations, and checksums are in `ml/reports/multidisaster/coverage.json`. All original NOAA types are retained separately from normalized families.

Thunderstorm Wind: 67,969 records are instantaneous; 27,738 of 28,139 positive intervals last under one hour. This does not label a continuous storm/intensity trajectory. Ingestion only; no duration prediction will be claimed.

NOAA Heat/Excessive Heat intervals are administrative regional records. They will not train local heat-exposure predictions. A separate observed station threshold dataset is required.

Tropical NOAA reports need NHC storm identities; wildfire reports need incident identities and timestamped containment history. Neither will be trained as interchangeable regional-duration labels.

Candidate interval models: Flash Flood, High Wind, Strong Wind, Heavy Rain, Winter Storm, Ice Storm, Heavy Snow. Each receives a separate model/backtest; positive continuous intervals only, with at least one observed hour of activity required for new NOAA categories. This conditioning and excluded point reports must be disclosed. Flood stays unchanged.

Before inspecting new model test scores, qualification requires at least 30 evaluation episode groups per split, both outcome classes with at least 10 labels at each supported horizon, and validation/test expected calibration error <= 0.15. All outcomes remain research only; failing a gate leaves the category unavailable. Selected logistic requires at least 2% mean validation Brier improvement over KM; otherwise retain KM. The predeclared split is train 2021-2023, validation 2024, test 2025. Hyperparameters stay fixed. New-category 2025 metrics have not been used for tuning; the original Flood 2025 data were previously inspected.

Additional NOAA expansion evaluation purges full episodes crossing year boundaries and applies a seven-day boundary embargo, with no episode split. Residual reporting/regional dependence remains. Unsupported trends stay unknown.

Official definitions: [NOAA bulk format](https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/Storm-Data-Bulk-csv-Format.pdf), [NHC format](https://www.nhc.noaa.gov/data/hurdat/hurdat2-format-nov2019.pdf), [ISD-Lite format](https://www.ncei.noaa.gov/pub/data/noaa/isd-lite/isd-lite-format.txt).
