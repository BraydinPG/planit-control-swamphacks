# Multi-disaster research extension

The Flood v2 model, cutoff purge, KM default, artifacts, reference probabilities, and score exclusion are preserved. PR #4 was merged before this branch was created from `origin/main` (`cf9d3bb`). This extension adds separate targets and a fail-closed registry; it does not train an onset classifier or change deterministic alerts.

Five additional duration targets passed the predeclared research checks: **Flash Flood, High Wind, Heavy Rain, Winter Storm, and Heat Index Exceedance**. These checks establish limited retrospective evidence, not operational validation. No model is production eligible or eligible for operational evaluation. Strong Wind, Ice Storm, and Heavy Snow trained but failed checks and are unavailable at inference. Hurricane wind-change is a separate offline retrospective experiment. Thunderstorm lifetime, wildfire containment, geographic growth, and worksite severity remain unsupported.

See [coverage](COVERAGE.md), [all new evaluation results](MULTIDISASTER_EVALUATION.md), [machine-readable registry](reports/multidisaster/registry.json), [examples](reports/multidisaster/examples.json), and [runtime/Monte Carlo checks](reports/multidisaster/runtime_checks.json). Flood's existing results remain in [EVALUATION.md](EVALUATION.md).

## Sources and targets

NOAA NCEI: the same five checksum-pinned 2021–2025 Storm Events archives used for Flood, totaling 349,030 source rows. The inventory retains all 15 requested original types alongside normalized families. Counts, years, state/region coverage, invalid rows, point records, missing geometry, durations, and episode counts are in [coverage.json](reports/multidisaster/coverage.json). No training is restricted to EIA sites. NOAA episodes are reporting groups, not verified independent meteorological disasters. High Wind and other zone records often have no point geometry. The numeric source timezone offset retains the existing daylight-saving uncertainty.

New NOAA duration targets condition on a **positive continuous recorded interval that is independently confirmed still active at age >=1 hour**. Point reports are excluded. Features are event age and start month; no intensity or weather measurement enters these models. Original types have separate fits, selection, and holdouts. A 1/3/6h horizon is used for Flash Flood, Strong Wind, and Heavy Rain; 6/12/24h for High Wind and winter types. Zero-duration reports are counted in coverage rather than called bad continuous-duration labels. Thunderstorm Wind has 67,969 instantaneous reports and 27,738 sub-hour positive intervals; this does not establish a storm lifetime. Station wind speed is ingested with its units but does not supply a thunderstorm severity target.

Observed heat: 122,270 ISD-Lite hourly records from Miami, Houston, and Phoenix, 2021 through August 2025, produce 2,586 complete threshold episodes in 416 station/week groups. The target is **hourly derived heat index >=90°F**, explicitly a prototype research definition. This differs from NOAA Heat/Excessive Heat reporting intervals. Temperature/dewpoint are observed, RH is calculated with the NWS vapor-pressure relation, and heat index uses the NWS simple estimate/Rothfusz formula with published humidity adjustments. Missing/invalid pairs are not filled. Hourly gaps and unknown starting/ending crossings are excluded as censored, never labeled resolved; complete-case selection remains a limitation. Crossings have one-hour quantization, not exact exposure timing. Station/week clustering cannot establish regional heatwave independence. The model uses age/month and does not claim generalization beyond those three stations or to worksites. The interface permits explicit station replay only.

NHC: the pinned Atlantic HURDAT2 `1851-2025-092326` revision contains 55,524 track points in 1,988 storms; the selected 2000–2025 subset has 13,836 points in 459 storms. Wind/pressure missing sentinels become missing values. 327 storms have a sampled terminal tropical-to-nontropical transition; 132 end with an unknown terminal phase. No duration predictor is fitted to that selected complete-end cohort. The offline trend experiment instead uses 8,689 snapshots in 442 storm identities with exact past 6h and future 24h wind measurements. It predicts cyclone maximum sustained wind change of >=+10 kt / between / <=-10 kt over 24h, not local wind or worker danger. Two real Helene 2024 issued public advisories were retrieved and examined, demonstrating archive access; they do not constitute an operational-vintage training cohort. HURDAT2 is post-analysis. All hurricane/typhoon/tropical live interface calls remain unavailable, including Pacific typhoons outside this Atlantic dataset.

Wildfire: a bounded official NIFC historical layer probe found 98,168 perimeter records overall; the 2021–2025 filter returned 191 records / 177 incident identifiers, actually dated 2021–2024. These counts describe this legacy layer, not all national fires. An unfiltered newest-record sample included invalid year `9999`, which is disclosed and excluded from period claims. The source lacks containment histories. FIRMS detection normalization is implemented/tested, but no historical detections were downloaded; historical standard-product acquisition requires archive access. Detections, mapped perimeters, and incident containment remain distinct. No wildfire model or invented metrics are supplied.

Flood observations: the USGS modern OGC continuous API returned 97 gage-height measurements in feet for `USGS-02303000`, 2024-10-08 to 2024-10-09. This is a feasibility probe. No validated event/gauge/site join, local flood-stage label, or datum mapping exists, so Flood features are unchanged.

Official source documentation: [NOAA bulk format](https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/Storm-Data-Bulk-csv-Format.pdf), [ISD-Lite format](https://www.ncei.noaa.gov/pub/data/noaa/isd-lite/isd-lite-format.txt), [NWS heat index](https://www.weather.gov/tbw/heatindex), [NWS vapor-pressure formula](https://www.weather.gov/media/epz/wxcalc/vaporPressure.pdf), [NHC HURDAT2 format](https://www.nhc.noaa.gov/data/hurdat/hurdat2-format-nov2019.pdf), [NHC data](https://www.nhc.noaa.gov/data/), [NASA FIRMS downloads](https://firms.modaps.eosdis.nasa.gov/content/active_fire/), [NIFC maps](https://www.nifc.gov/fire-information/maps), [USGS OGC API](https://api.waterdata.usgs.gov/docs/ogcapi/). Exact downloaded URLs, retrieval times, byte counts, and SHA-256 are in the source coverage reports. Downloads are bounded, cached, serial, and checked; no credentials or personal data are stored.

## Evaluation policy

New duration targets use 2021–2023 training, 2024 validation, and a fixed 2025 test. Whole reporting episodes are purged across fit/selection boundaries; a seven-day boundary embargo removes connected groups. Split metadata carries bounds across all inventoried types. This strengthens grouping but cannot identify a storm spanning distinct reporting IDs. Heat groups by station/week. No episode enters multiple splits.

The existing pooled logistic survival model and training-only conditional Kaplan–Meier baseline are reused per event type with fixed hyperparameters. Each snapshot computes one logistic curve and one KM curve; horizons and quantiles reuse those curves. Logistic is selected only if mean validation Brier improves at least 2% over KM. Both estimators are reported on matched eligible snapshots per persistence horizon. There is no test-driven estimator substitution, recalibration, horizon dropping, or gate adjustment.

Gates were fixed before the first new-category test evaluation: >=30 evaluation episode groups, >=10 labels in each class at every horizon, and ECE <=0.15 in both validation/test. Passing means `evaluated_research`, with `production_eligibility=false`. Three failed targets remain disabled. ECE alone does not establish utility: coarse bins, regional dependence, source revision, event ascertainment, complete-case selection, and geographic transfer remain limitations. These gates are an engineering research screen, not a statistical certification.

Reports include Brier, reliability bins, support and class counts, and seeded 500-replicate episode-bootstrap 95% intervals. Duration errors/10–90% interval coverage use only identified quantiles; null quantiles remain null, and eligible counts accompany metrics. Logistic and KM duration eligibility can differ. Nominal 80% interval coverage can be poor despite the persistence screen; duration summaries must remain experimental. No individual confidence scalar is fabricated.

Hurricane wind-change uses a separate fixed whole-storm split: train 2000–2019, validation 2020–2022, test 2023–2025, purging storm tracks crossing the boundaries (zero here). Current wind, pressure, position, month, and observed past 6h wind change are the complete feature list; future wind supplies labels only. Train-only median imputation/scaling and storm-normalized training weights are applied. A training-only storm-weighted class-frequency baseline is compared to logistic. Test scores were not used to tune this experiment. Its good retrospective metrics do not resolve the post-analysis availability problem. Duration error/coverage do not apply to a categorical wind-change target.

These are first fixed evaluations for the new targets. Reproducing their reports does not create another untouched test. Flood 2025 was already inspected before this work; its old status is unchanged.

## Reproduce and run

From the repository root, use the pinned environment in [QUICKSTART.md](QUICKSTART.md):

```powershell
./ml/setup.ps1 -ProvisionModel
$MlPython = ".\ml\.venv\Scripts\python.exe"
& $MlPython -m ml.provision_expansion --download
& $MlPython -m ml.expansion_checks
& $MlPython -m pytest ml/tests backend/tests -q
```

The expansion provisioner obtains only missing exact pinned NOAA/station files and uses reviewed selected-station metadata. It trains through 2024 and verifies cohort counts, artifact hashes, and reference probabilities. It does **not** rerun holdout backtests. Existing artifacts are checked and preserved, never silently replaced. The same eight artifacts were independently rebuilt byte-for-byte in `ml/artifacts/multidisaster_rebuild/`. Raw archives, environments, and binary artifacts remain ignored. An unavailable/revised pinned source fails explicitly; no newer vintage is silently substituted. Binary identity is verified in the pinned Python 3.14.5 environment; other environments require numerical review.

To intentionally reproduce research evaluations, run one command at a time; these commands overwrite the corresponding research reports and are not a new test period:

```powershell
& $MlPython -m ml.coverage
& $MlPython -m ml.multidisaster
& $MlPython -m ml.sources.hurdat
& $MlPython -m ml.hurricane
& $MlPython -m ml.sources.wildfire
& $MlPython -m ml.sources.gauges
```

Heat evaluation is explicit rather than silently rerun by provisioning:

```python
from ml.provision_expansion import ensure_station_sources
from ml.sources.stations import HEAT_EVENT_TYPE, HEAT_DEFINITION
from ml.multidisaster import run_category, update_registry
import json
from ml.config import REPORT_DIR
card = json.loads((REPORT_DIR / "multidisaster/heat_index_exceedance.json").read_text())
result = run_category(ensure_station_sources(), HEAT_EVENT_TYPE, horizons=(1, 3, 6),
    source_scope=card["target"], source_version=card["data_version"], definition=HEAT_DEFINITION,
    offsets=(0, 3, 6, 9), minimum_age=0, source_receipts=card["source_receipts"],
    extra_limitations=card["limitations"][4:])
update_registry([result])
```

One worker is retained. First serial category runs took 0.72–12.34 seconds each; heat 0.81 seconds; hurricane 0.22 seconds. Runtime details are measured in each model card. The later checksum/deterministic-gzip inventory took 15.36 seconds. Warm adapter medians were 0.077–0.084 ms for NOAA targets and 0.180 ms for heat (200 calls/type, one process). Timing is machine/run specific. There is no new multiprocessing or simultaneous full backtest. Twenty thousand seeded Monte Carlo draws per qualified target match its selected fitted distribution; raw trajectories are not returned. Analytical agreement checks arithmetic only. Historical duration errors and the observed replay duration are recorded separately, not presented as Monte Carlo validation of real-world accuracy.

## Rudra handoff: contract 1.1

`predict_active_event(event_context)` and `ActiveEventPredictor.predict_for_site(site, event_context)` retain their signatures. Initialize one adapter per backend process; it caches each qualified model by event type and pinned hash. No shared API schema or production route was added. Two focused backend tests demonstrate that existing `ModelOutput` accepts 1/3/6h persistence dictionaries while excluding ML from scoring.

For a new NOAA target, supply exact original `event_type`, known start/as-of times, and `event_definition="noaa_positive_continuous_recorded_interval"`. A historical replay needs its applicable region and is marked simulated. A `confirmed_active` call additionally requires a site ID, caller-verified event/site association, and local confirmation evidence with both `valid_time_utc` and `available_at_utc` no later than prediction time and within one hour. The adapter cannot infer association from coordinates. Independent continuing activity must establish the target definition; a single point damage report is insufficient. This boundary still does not validate local transfer or make the model operationally eligible.

Heat uses `event_type="Heat Index Exceedance"`, the exact heat threshold definition above, and one of the three evaluated `station_id` values; only explicit historical replay is allowed. NOAA `Heat` and `Excessive Heat` are not aliases. Hurricane, Thunderstorm Wind, and Wildfire return unavailable. Failed categories do not fall back to Flood or substitute a test-favored estimator.

Existing result keys remain. Additions are `contract_version`, `event_category`, `applicable_location`, `data_version`, `research_only`, and `operational_evaluation_eligible`. New targets return only their declared horizons. `trend` stays unknown in unified duration outputs. Evidence IDs/timestamps, risk-set/training counts, spatial quality, missingness, null completeness/confidence, and limitations are explicit. Unavailable/no-event results contain no probabilities. Site compatibility keys are `active_event_persists_1`, etc.; component remains zero/excluded with null confidence. Never interpret these as onset probabilities, severity, clearance, or permission to suppress warnings.

Copy a complete replay context from [examples.json](reports/multidisaster/examples.json), then call the existing adapter. Keep this separate from site risk and alerts. Before any live product exposure, Rudra should review the target definition, research labeling, source vintage, geographic association policy, and UI handling of unavailable/null durations. These are review requirements for an operational product change, not unfinished ML dispatch work in this PR.
