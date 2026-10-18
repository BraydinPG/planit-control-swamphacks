# Landing-page research showcase

Verified 2026-10-18. Branch `feature/cache-landing-research-evidence` starts from
main `a824964`. The user requests a focused PR and **no automatic merge**.

The new section immediately follows the hero/statistics:
**Built on Real Data. Tested with Real Simulations.** It presents four source cards,
three short method explanations, three report-backed charts and a decision-authority
statement. The existing hero, product features, brand, animation JavaScript,
demo/sign-in links and application workflows are unchanged.

## Claims and their sources

The [existing headline-statistic audit](LANDING_PREDICTIVE_MESSAGING.md) still applies.
The export reads these six versioned inputs, recording their SHA-256 hashes in
[evidence.json](../frontend/public/research/evidence.json):

Source hashes use UTF-8 text normalized to LF, matching the Git content on Windows
and Linux. Figure hashes cover the actual exported bytes; an asset-local
`.gitattributes` preserves LF for generated SVGs/JSON in clean Windows checkouts.

| Input | Values used and interpretation |
| --- | --- |
| [Flood backtest](../ml/reports/purged_v2/backtest_metrics.json) | `source_row_counts.rows_total`: **349,030** NOAA Storm Events rows. `validation_2024_train_through_2023`: **4,053** snapshots / **583** reporting episodes at every displayed horizon. Default estimator: **Kaplan–Meier**. Production eligibility remains false. |
| [Station coverage](../ml/reports/multidisaster/station_coverage.json) | Sum of `stations.*.source_rows`: **122,270** hourly source measurements at three evaluated stations. Source volume includes records outside final eligible training/evaluation cohorts. |
| [NHC coverage](../ml/reports/multidisaster/hurdat_coverage.json) | `full_archive.track_points`: **55,524** Atlantic historical track points. Full-archive post-analysis best tracks, not operational issue-time forecasts or local worksite winds. |
| [EIA coverage](../ml/reports/worker_outlook/eia_coverage.json) | `selected_research_locations`: **50** representative mapped infrastructure locations, not verified active work orders or universal live coverage. |
| [Monte Carlo summary](../ml/reports/purged_v2/monte_carlo_summary.json) | **5,000** draws, seed **42**, simulated Flood replay as of **2024-09-10T16:00:00Z**, model `noaa-flood-pooled-logistic-v2`. This archived experiment is separate from the selected KM default. |
| [Target registry](../ml/reports/multidisaster/registry.json) | Six research-eligible duration targets remain: Flood, Flash Flood, High Wind, Heavy Rain, Winter Storm and restricted Heat Index Exceedance. The exporter checks the count; no eligibility changes. |

The historical inventory sums to **526,824** mixed records and measurements. It is
not a count of independent training examples. The live-evidence note describes the
separate existing NWS/NHC/USGS layer, with varying coverage/freshness and explicit
unknown inputs; it does not assert a current connection or use live data in these charts.

## What the charts show

1. **Monte Carlo consistency:** zero-to-100% grouped bars compare analytical
   persistence with sampled ongoing proportions. Largest absolute difference is
   **0.4031657295 percentage points**, displayed as **0.40 percentage points**.
   The chart is labeled an archived simulated replay, not a current forecast or
   independent evidence of predictive skill.
2. **Historical validation:** zero-based Brier-error bars compare KM with logistic
   on the same 2024 validation snapshots, with training through 2023. Whiskers use
   the saved **95% episode-bootstrap intervals / 500 resamples**. KM's lower errors
   at all three horizons explain keeping the simpler baseline. Overlapping intervals
   do not establish statistical superiority. This was a selection cohort, not a
   fresh untouched holdout; calibration and duration errors remain limitations.
3. **Source scale:** zero-based count bars compare the three historical inventories.
   The units/processes differ; the bars measure volume, never model accuracy or
   current site exposure. The separate EIA card is excluded from this count scale.

Displayed table values below are rounded to six decimals. The downloadable JSON
retains the original values and bootstrap intervals.

| Horizon | Analytical ongoing | Simulated ongoing | KM validation Brier | Logistic validation Brier |
| --- | ---: | ---: | ---: | ---: |
| 6h | 0.619922 | 0.623000 | 0.211733 | 0.216986 |
| 12h | 0.447168 | 0.451200 | 0.232385 | 0.242210 |
| 24h | 0.281102 | 0.282000 | 0.224849 | 0.239856 |

Each chart has a descriptive image alternative, a native expandable data table
and original-report links. Dedicated desktop/mobile SVG exports preserve label
sizes and proportions. Source hashes and figure hashes make the displayed evidence
inspectable. No charting library, runtime data fetch, simulation controls or new
runtime JavaScript is introduced. Three images total **71,385 bytes** on desktop
or **71,261 bytes** on mobile, before compression; images are lazy-loaded.

## Reproduce or inspect

Normal `npm ci` / `npm run build` uses the committed HTML, SVGs and JSON. Python,
credentials, network access and model artifacts are unnecessary to serve the section.
To regenerate from saved reports, use an isolated plotting environment from repo root:

```powershell
python -m venv frontend/.shell-check/landing-plots
$plotPython = Join-Path $PWD 'frontend/.shell-check/landing-plots/Scripts/python.exe'
& $plotPython -m pip install -r frontend/scripts/landing-research-requirements.txt
& $plotPython frontend/scripts/prepare-landing-research.py
& $plotPython frontend/scripts/prepare-landing-research.py --check
```

The generator uses Matplotlib **3.10.7** and pinned plotting dependencies. It reads
only saved reports, renders deterministic SVGs, writes the public JSON and replaces
the marked research section in `landing.html`. `--check` verifies byte-identical
figures/data and the generated HTML without writing. No raw archive, model load,
training, Monte Carlo rerun, provider call or ML change occurs. SVG font outlines
avoid client-font differences; accessible labels/tables accompany the artwork.
Edit the generator's section template for content, and landing CSS for presentation.
Update source/figure exports together if an audited source changes.

Open `http://localhost:5177/landing.html#lab-title` on the existing functional demo
server (or the origin printed by Vite). Normal live deployment serves this same public
page. No external Auth0, database or deployment acceptance is claimed.

## Verified checks and review evidence

- **198** frontend tests pass: `node --test tests/*.test.mjs` from `frontend/`.
- `npm.cmd run lint` and `npm.cmd run build` pass, including TypeScript. A separate
  explicit-fixture production build passes. Existing bundle/plugin-timing advisories remain.
- New Python exporter: Ruff check/format and `--check` pass. Independent inspection
  confirms all six source hashes and six SVG hashes match the current files.
- Edge/CDP development and built-demo smoke checks pass at **1440/768/390/320px**:
  all three SVGs decode with the correct mobile/desktop variant and aspect ratio;
  figures have captions, tables/values/source counts match, and text does not clip
  or overflow, including open data disclosures. Desktop/mobile screenshots were
  visually inspected, including full-size mobile Monte Carlo and backtest cards.
- Existing headline/statistics/logo and 44px demo/sign-in controls remain; reduced
  motion, short-screen fallback fonts, count-up and actual demo navigation pass.
  No browser exceptions, console errors or actual backend API calls.
- Hero and product-section markup and the animation JavaScript match the base.
  Backend/ML tests are not rerun because no code, artifacts or inputs there changed.

[Desktop section](landing-research/desktop.png) ·
[Mobile section](landing-research/mobile.png) ·
[Mobile Monte Carlo card](landing-research/monte-carlo-mobile.png) ·
[Mobile backtest card](landing-research/backtest-mobile.png).

Intentionally excluded: invented raw simulation paths/histograms (the saved summary
contains no raw trials), site injury/safety probabilities, an exact clearance countdown,
universal hazard/coverage claims, unsupported performance improvements, operational
certification, and claims that the previously inspected 2025 Flood test is a fresh
holdout. Nothing changes the 0–10 index, alert state, model gates or human authority.

Rudra: preserve this generated section and its qualifiers during frontend maintenance.
Braydin: normal static-asset publication is sufficient after review; no configuration
or service change is required. The PR remains open for review; its link/commit can be
recovered from this document's Git history.
