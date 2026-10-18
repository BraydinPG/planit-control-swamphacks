# Public Data & Research page

[PR #91](https://github.com/BraydinPG/planit-control-swamphacks/pull/91) is verified; the subsequent user follow-up authorizes merge.

Verified 2026-10-18. Branch `feature/cache-dedicated-data-page`, initially based on
main `61ec526`. This corrects PR89: research lives at **`/data.html`**, an independent
public document. The homepage keeps its original hero, four statistics, three
features, brand, fog/lightning effects and demo/sign-in destinations. Public
navigation uses the logo as the Home link, followed by Data and Sign In. Data retains its active-page indicator.

The advanced-dashboard addendum initially requested no automatic merge. The user's
subsequent request explicitly authorizes merging PR91 after verification. Main
`b16bef4` was reconciled in `8bcb6d0`; the later `c951ae0` briefing update was
reconciled in `cf24867`, both without conflicts. The frontend tree is identical to
verified implementation `0b1269b`; all 12 additional upstream backend demo checks
pass, with one existing dependency deprecation warning. Commit/PR attribution is
in Git history and the PR description.

## Public-page cleanup (2026-10-18)

At the user's request, the generated Data page no longer displays the
"Evaluation includes saying no" panel or its separate hurricane-experiment paragraph.
The supporting research reports, disabled-model gates and all twelve figures remain
unchanged. Both public headers omit the Home text button; the accessible FORESITE
logo returns to `/landing.html`. The narrower header fits in one row on phones.
Screenshots below record the original PR91 layout before this small cleanup.

## What runs

`landing.html` and `data.html` share `public-site.css` and the original atmosphere
JavaScript extracted verbatim into `public-atmosphere.js`. Homepage research markup,
research CSS and research downloads are removed. Data-only CSS and read-only
`data-research.js` select committed results; neither accesses sessions, requests an
API token, calls the backend nor performs inference. There is no second application
or router. Both documents retain existing Sign In destinations.

Normal `npm ci` / `npm run build` serves all committed assets. No Python, model
artifact, secret, research backend or provider is required to view Data. The default
figures and numerical tables also work with JavaScript disabled. If static JSON is
unavailable, selectors stay disabled with a visible explanation; figures remain.

The existing Caddy configuration serves actual public files before its SPA fallback.
Vite production preview verifies the built documents locally; this run does not
claim a deployed Vultr acceptance check. Workspace/auth/backend routes are unchanged.

## Twelve figures and exact provenance

All charts are Matplotlib SVGs with separately laid-out phone variants, descriptive
alternatives, numerical tables, source links and lazy loading. The original six SVGs
and `research/evidence.json` remain byte-identical. Nine new figures plus saved
selector variants add 38 SVG files. [The figure ledger](../frontend/public/research/dashboard-figures.json)
records hashes, model/artifact version, cohort, horizons, support and censoring.
[Dashboard data](../frontend/public/research/dashboard.json) records normalized hashes
for every saved input report. It preserves precise values rather than rounded UI text.

| Figure | Source and method | Meaning / limitations |
| --- | --- | --- |
| 1. Historical source scale | Original `data-sources.svg`; Flood backtest, station coverage and HURDAT coverage reports | 349,030 NOAA rows, 122,270 hourly station source measurements, 55,524 post-analysis track points. Different populations and units, never independent training examples. |
| 2. Flood cohort construction and chronology | `cohort.svg`; `ml/reports/purged_v2/backtest_metrics.json` counts and split | 11,571 Flood rows, 10,322 valid intervals, 10,310 eligible after 12 boundary records are purged. Eligible interval counts by year; whole reporting episodes remain grouped. |
| 3. Monte Carlo versus analytical persistence | Original `monte-carlo.svg`; saved `monte_carlo_summary.json` | 5,000 draws, seed 42, logistic synthetic Flood replay, age 6h and September start. Analytical versus sampled ongoing probability at 6/12/24h, not observed predictive skill. |
| 4. Full conditional survival curve | `survival.svg`; exact approved-artifact curve and regenerated draws | Every remaining hour0-162, white analytical and red empirical persistence. Unresolved tail is retained. No observed survival cohort is invented. |
| 5. Sampled duration distribution | `duration-distribution.svg`; same raw 5,000 draws | Six-hour bins for 4,828 resolved draws; quantiles use the full sample including 172 unresolved. Resolution time is an event-record proxy. |
| 6. Sample event-end timelines | `sample-paths.svg`; first 60 draws in their original seeded order | Constant ongoing state until sampled end, arrow for unresolved. These are end-time samples, not physical intensity or location trajectories. |
| 7. Monte Carlo convergence | `convergence.svg`; nested prefixes N = 100/500/1,000/2,500/5,000 | 6/12/24h ongoing proportions versus analytical references; 95% Wilson binomial intervals for conditional i.i.d. simulation indicators. Prefixes share draws. Bands do not represent model or real-world forecast uncertainty. |
| 8. 2024 validation Brier comparison | Original `backtest.svg`; purged Flood backtest | 4,053 snapshots / 583 reporting episodes; fitted through 2023. KM has lower Brier at all 3 horizons and remains selected. Saved95% episode-bootstrap intervals / 500 resamples. |
| 9. Later 2025 Brier comparison | `brier-test.svg`; same saved report, distinct test population | 3,539 snapshots / 567 episodes; fitted through 2024. Logistic has lower Brier at all 3 horizons here. This previously inspected period does not reverse the validation-based selection or become a new untouched holdout. |
| 10. Probability reliability | `calibration.svg` and saved model/horizon variants; same report | Separate 2024/2025 panels. Mean predicted persistence versus recorded ongoing frequency in saved bins; dot sizes show count. Tables update to the selected model/horizon. No independent-snapshot confidence intervals are invented. |
| 11. Historical duration and absolute error | `duration-errors.svg` and model/log variants; approved artifact rescoring through existing `ml/backtest.py` | All 3,539 inspected 2025 snapshots/567 episodes, recorded remaining hours versus predicted median and absolute-error histogram. Original 6 Brier values and both MAEs reproduce. Repeated snapshots remain dependent; unknown interval bounds stay null. |
| 12. Six-target comparison | `multi-disaster.svg`; Flood report and `ml/reports/multidisaster/{flash_flood,high_wind,heavy_rain,winter_storm,heat_index_exceedance}.json` | Selected-estimator2025 Brier with saved group-bootstrap intervals. Category/horizon/period controls expose genuine saved support, calibration and limits. Different target prevalences, horizons and cohorts prevent a cross-disaster ranking. |

The displayed chronology is Historical Data -> Statistical Models -> Monte Carlo
-> Historical Backtesting -> Multi-Disaster Research -> Evidence & Limitations.
The benchmark is an additional numerical table, not a padded thirteenth chart:
`ml/reports/purged_v2/benchmark.json` reports a bounded 161-snapshot comparison with
1/4/8/12 workers, matching outputs and interference caveats. One worker was retained.
It is not a live-feed latency or full-backtest speed claim.

## Exact observed, fitted and sampled quantities

Source inventory totals 526,824 heterogeneous rows/measurements; 50 EIA research
locations are reference points, not active work orders or universally monitored sites.
The [existing headline audit](LANDING_PREDICTIVE_MESSAGING.md) still applies.

| Remaining horizon | Analytical model probability | Seeded sampled ongoing proportion | 2024 KM Brier | 2024 logistic Brier |
| --- | ---: | ---: | ---: | ---: |
| 6h | 0.6199216839402608 | 0.6230 | 0.21173329753360257 | 0.21698641660285573 |
| 12h | 0.44716834270464595 | 0.4512 | 0.23238483052498485 | 0.2422101837000786 |
| 24h | 0.2811015423152757 | 0.2820 | 0.2248488040017392 | 0.2398562677050223 |

MC minimum resolved 1h, p10 = 2h, median 10h, p90 = 73h. Maximum resolved within the
162h remaining model horizon is 162h; 172/5,000 draws remain unresolved. The total
modeled event-age limit is 168h with 6h already elapsed. **The true upper tail and
maximum possible disaster duration are unknown.** Largest analytical/sampled
horizon difference is 0.4031657295 percentage points, displayed 0.40.

Historical recorded remaining duration ranges 0.0166667-743.983333h in the inspected
2025 cohort. Logistic median MAE 40.7117358953h; KM 41.2644061411h. Predicted median
ranges 3-47h and 5-44h respectively. 1,696 logistic and 1,635 KM snapshots have at least
one unidentified interval bound; CSV uses empty/null, never zero, for those bounds.
Long recorded events are retained and shown with optional log scatter axes.

These are recorded administrative event intervals, not measured worksite exposure.
Historical archive revisions and fixed-offset timestamps do not establish original
issue-time availability. Only 6/12/24h Flood research results are shown. Flash Flood,
Heavy Rain and restricted Heat Index Exceedance use 1/3/6h; High Wind and Winter Storm
use 6/12/24h. Heat research covers the evaluated 3 stations and incomplete 2025 archive,
not national worker heat exposure. Each target's exact limits are selectable.

Strong Wind, Ice Storm and Heavy Snow remain disabled. The separate hurricane
wind-change experiment uses post-analysis tracks and is not a duration or operational
wind-field forecast. No artifact, selection criterion, training split, model gate,
score weight or alert rule is changed. Neither ML nor Gemini can authorize work.

## Exports and reproduction

Committed public downloads:

- `dashboard.json`: report extraction, exact curves, counts, saved results and 5,000 draws.
- `dashboard-figures.json`: 38 new figure hashes, provenance and input hashes.
- `monte-carlo-draws.csv`: every seeded end-time draw, including unresolved cases.
- `backtest-comparison.csv`: model/horizon/period metrics for all six qualified targets.
- `flood-holdout.json` / `.csv`: all 3539 historical snapshot predictions, IDs,
  recorded endpoints and both estimators' duration quantiles. These are public NOAA
  record IDs, not worker or private account data. Full holdout is download-only and
  is not loaded by page selectors.

From repo root, check saved exports with ordinary Python (stdlib only):

```powershell
python frontend/scripts/export-research-dashboard.py --check
```

Regenerate figures in the existing isolated plotting environment, or provision it:

```powershell
python -m venv frontend/.shell-check/landing-plots
$plotPython = Join-Path $PWD 'frontend/.shell-check/landing-plots/Scripts/python.exe'
& $plotPython -m pip install -r frontend/scripts/landing-research-requirements.txt
& $plotPython frontend/scripts/prepare-data-dashboard.py
& $plotPython frontend/scripts/prepare-data-dashboard.py --check
# Established command now delegates to the expanded Data document:
& $plotPython frontend/scripts/prepare-landing-research.py --check
```

Optional from-artifact reproduction requires the approved pinned ML environment,
trusted existing `ml/artifacts/provisioned_v2/active_event.joblib` and original
checksummed NOAA cache; [existing provisioning](../ml/EVENT_OUTLOOKS.md) applies.
No training or download is performed by this exporter:

```powershell
& $MlPython frontend/scripts/export-research-dashboard.py --with-model-samples --archive-dir 'C:\path\to\approved\ml\data\raw' --check
```

Approved Flood SHA-256:
`2d33812b2d238bfa0ad18665f0b447c5d0d6925c1398c763814d4e5889067598`.
The command verifies archive hashes, reconstructs the existing episode-purged test
snapshots, calls the fitted scorer without fitting, and asserts all 6 saved Briers
and both duration MAEs. Without raw data/artifacts, committed exports still render.
Input hashes normalize UTF-8/LF; local `.gitattributes` preserves generated byte hashes.

## Verification and review

- 198 frontend tests, lint, TypeScript and production build pass. Existing SPA chunk
warning remains; this page adds no app bundle dependency or chart library.
- 7 existing Monte Carlo/backtest-performance tests pass. From-artifact export check
reproduces all 5,000 draws and 3,539 historical snapshots; static and figure checks pass.
- Edge checks at 1440/768/390/320 verify both documents, all 12 figures, mobile SVG variants,
active/keyboard links, direct access/reload/history, supported horizon/model/log
controls, missing-JSON and script-disabled fallback, no clipping/overflow/exceptions
and zero backend API calls. Homepage loads no research assets. Existing demo CTA works.
- Synthetic local/session storage sentinels survive navigation; this is not a claim of
real Auth0 account acceptance. Auth code and authenticated app entry are untouched.
- Production live/default and explicit fixture builds are checked independently.

Run focused browser acceptance against an owned Vite instance:

```powershell
cd frontend
node --test tests/*.test.mjs
npm run lint
npm run build
node scripts/check-public-pages.mjs http://localhost:5177/ --fixtures
```

[Homepage desktop](screenshots/data-page-home-desktop.png) / [phone](screenshots/data-page-home-mobile.png).
[Complete Data desktop](screenshots/data-page-desktop.png) / [phone](screenshots/data-page-mobile.png).
[Data phone introduction](screenshots/data-page-mobile-top.png).
Full phone capture uses compositor-sized tiles joined without editing content.

## Handoff and limits

Rudra: preserve `/data.html` as a real public document, the public logo-to-Home/Data/Sign In
header, generated markers and research labels. Use the exporter to change chart
content; do not paste it back into the homepage or app layout. PR90's unrelated
briefing-picker changes are preserved when reconciling latest main.
Braydin: no tenant, database or deployment change required by this PR. Auth entry is
still `/?signin`; no credentials or session writes are introduced.
Cache: future exports must keep exact source/model hashes, original preserved assets,
selection gates and unknown/censored semantics.

No intensity/location trajectories, worker-injury probabilities, nationally valid
heat exposure or local hazard probability can be added from these saved intervals.
Those need appropriate historical time series/site outcome labels and independent
validation. Original vintages/QC limitations remain. More ambitious physical tracks
or conditional joint hazards need qualified sources and validation rather than
decorative simulated paths. The existing charts cover all twelve supported figures;
there is no claim of universal hazard prediction or operational clearance.
