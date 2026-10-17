# Multi-event outlook integration preview

This is an independently runnable Cache package, **not live application integration**.
It reuses the existing duration predictors and adds read-only parsers for issued
NHC cyclone and USGS aftershock forecasts. It starts no server and changes no
canonical API, UI, database, score, alert, instruction or authorization behavior.

## Run from the repository root (Windows PowerShell)

Use the pinned ML environment described in [QUICKSTART.md](QUICKSTART.md).
Creating the environment alone does not require archives or training:

```powershell
py -3.14 -m venv ml/.venv
$MlPython = '.\ml\.venv\Scripts\python.exe'
& $MlPython -m pip install -r ml/requirements-lock.txt
& $MlPython -m ml.event_outlook_preview
Start-Process (Resolve-Path ml/reports/event_outlook_preview/index.html).Path
```

The preview works offline without credentials or model artifacts. Missing models
produce explicit unavailable cards; the two captured official forecasts still
render. Every request/response is Pydantic-validated. The default output contains
`index.html`, 16 request/response pairs, both JSON schemas, and `summary.json`.
No API server, Auth0 account, model training, download or Monte Carlo UI is needed.

To reuse models **already provisioned by a trusted teammate**, with the pinned
environment, supply that checkout's existing artifact directory:

```powershell
& $MlPython -m ml.event_outlooks.reuse_artifacts --from-artifacts 'C:\path\to\trusted-checkout\ml\artifacts'
& $MlPython -m ml.event_outlook_preview --require-models
```

Reuse checks all five expansion hashes against the reviewed registry, validates
their event/model identities, checks the Flood receipt/hash and six existing
reference contexts for both estimators against `model_reference.json`, then copies
only six qualified artifacts and the Flood receipt into ignored local paths.
Different existing files are preserved/rejected. Hashes identify files; they do
not make an untrusted pickle safe. No archives or raw station files are required.
This run reused existing artifacts; it did not refit or evaluate a new model.
Full from-source provisioning remains documented in MULTIDISASTER/QUICKSTART;
those training/download commands are intentionally not part of this preview.

`--require-models` requires all six genuine duration examples to succeed. It first
saves typed output and then fails clearly if artifacts are absent. The missing
and corrupt examples always use isolated temporary files, preserving good models.

## Coverage and exact distinctions

| Event | Working preview | Horizons / scope | Backend activation gap |
|---|---|---|---|
| Flood | Existing KM duration research | 6/12/24h; recorded NOAA Flood interval | Existing singular backend integration retained. New adapter requires actual start and independent current local confirmation for non-replay use. |
| Flash Flood | Separate qualified KM research | 1/3/6h; positive continuous NOAA interval, age >=1h | T050A pending: confirmed notice plus target identity, actual start and independent local active-event evidence. NWS warning alone is insufficient. |
| High Wind | Separate qualified KM research | 6/12/24h; positive continuous interval, age >=1h | No target-specific trusted backend activation/category yet; controlled replay only here. |
| Heavy Rain | Separate qualified KM research | 1/3/6h; positive continuous interval, age >=1h | Same missing activation feed; rain forecast/warning alone is not confirmation. |
| Winter Storm | Separate qualified KM research | 6/12/24h; positive continuous interval, age >=1h | Same missing activation feed; no inference of line icing. |
| Heat Index Exceedance | Qualified station logistic research | 1/3/6h; hourly observed HI >=90F prototype | Historical replay at three evaluated stations only; not Excessive Heat/Heat category prediction or site transfer. |
| Hurricane / Tropical Storm / Tropical Depression | Issued NHC FST parser | Provider position, phase, maximum sustained wind/gust in **knots**, exact valid times | Archived example; requires matching current issued product and independently trusted event association for future integration. No site wind or event-end forecast. |
| Earthquake | Issued USGS OAF parser | Mainshock, regional windows/magnitude thresholds, P(at least one), provider count ranges | Archived sequence forecast, not quake duration. Matching mainshock, published forecast and site within supported circular region required. Other region formats fail explicitly. |
| Wildfire | Explicit unavailable forecast | Existing hotspot/perimeter/air-quality evidence remains in worker package | Repeated valid-time perimeters/incident labels, issue-time vintages and separately validated growth/containment target would be needed. Hotspot is not containment. |
| Strong Wind / Ice Storm / Heavy Snow | Disabled | Existing failed research gates preserved | New labels/independent qualification, not renaming or enabling failed models. |
| Lightning / all other targets | Explicit unavailable forecast | Existing deterministic lightning authority stays separate | No substitute duration model; no onset, injury or work-clearance target. |

Six research duration targets and two official forecast **formats** are usable in
the controlled preview. Neither format count nor the 146-hazard inventory means
all hazards are predicted. [hazard_registry.json](hazard_registry.json),
[HAZARD_COVERAGE_AUDIT.md](HAZARD_COVERAGE_AUDIT.md) and
[SOURCE_INVENTORY_DIFF.md](SOURCE_INVENTORY_DIFF.md) retain their broader evidence
inventory; this change does not promote their operational maturity.

Original contracts remain unchanged. The internal Flood definition token
`noaa_recorded_flood_interval` names the original recorded-interval target; the
original `predict_active_event()` does not require that token. The stricter new
adapter requires it to avoid accidental target substitution. The five expansion
definitions, estimator selections and horizons come from the existing registry.

## Actual source captures

Raw bytes, original receipts and hashes are under `fixtures/event_outlooks/`.
Its local `.gitattributes` preserves exact bytes across Windows/Linux checkouts.
`manifest.json` verifies every captured file before examples are loaded.

- **NHC Helene AL092024 advisory 15:** [original issued technical text](https://ftp.nhc.noaa.gov/atcf/archive/2024/messages/al092024.fstadv.015),
  issued 2024-09-27 03:00 UTC, next advisory 09:00 UTC. Five forecast position/wind
  points are retained. Initial maximum sustained wind is 120kt; first forecast
  point is 55kt. This is an issued forecast, not HURDAT post-analysis. Forecast
  phase text is retained; a dissipation line is not turned into a duration estimate.
- **USGS Ridgecrest ci38457511:** [ComCat detail](https://earthquake.usgs.gov/earthquakes/feed/v1.0/detail/ci38457511.geojson)
  links the exact [published OAF forecast](https://earthquake.usgs.gov/product/oaf/ci38457511/us/1788406203671/forecast.json)
  and provider SHA256. Mainshock M7.1 occurred 2019-07-06 03:19:53.040 UTC. This
  captured **2026-09-03 03:30:03.671 UTC** sequence update is years after the
  mainshock; it is not an early-response forecast. Four original day/week/month/year
  windows, threshold probabilities and 95% expected-count ranges are retained.
  [USGS explanation and archive](https://earthquake.usgs.gov/data/oaf/) describe
  forecast purpose. No probabilities are shifted to start at the chosen as-of,
  multiplied across overlapping windows or converted to point-site probabilities.
- The OAF region is explicitly a 60km circle. The additional EIA reference
  `eia860m-CA-57764` (Naval Air Weapons Station China Lake) is 14.30km from its
  center. It was read using the existing backend's `load_plants` mapping from the
  previously checksummed August 2026 workbook, without downloads, seeds or DB
  writes. The reference fixture includes the workbook receipt and selection.
  It is not a monitored work order, asserted historical incident or verified DB row.
- The other examples reuse the reconciled 50-site catalog, selecting
  `eia860m-FL-59611`. All duration activations are **hypothetical replays**, not
  new captured NOAA incident records. The heat example explicitly concerns Miami
  station 722020-12839, not conditions measured at the displayed EIA reference.

Captures were retrieved on 2026-10-17 (exact UTC times in receipts). Publication,
validity and retrieval remain separate. Historical availability is **unverified**;
these archive records cannot become operational features in an earlier snapshot.
Official agencies are attributed, original public scientific products are
preserved, and agency product/use notices apply. No third-party imagery or
credentials are included. Capture reused `ml.sources.bounded.snapshot`: approved
HTTPS hosts/redirects, <=1 request/second/host, bounded size, 15s timeout and two
attempts by default. This local cap is not a provider quota promise. Only NHC's
two public hosts were added; normal inference/replay performs zero HTTP requests.

## Typed import and admission rules

```python
from ml.event_outlooks import EventOutlookAdapter, OutlookRequest, TrustPolicy

# AFTER existing backend role/assigned-site authorization and trusted ingestion.
adapter = EventOutlookAdapter(trust_policy=TrustPolicy(
    confirmation_sources=frozenset({"reviewed-active-event"}),
    association_sources=frozenset({"verified-event-site-link"}),
    observation_sources=frozenset({"qualified-local-observation"}),
    allow_replay=False,
))
response = adapter.build(OutlookRequest.model_validate(trusted_request))
payload = response.model_dump(mode="json")
```

Default allowlists are empty and replay is disabled. A caller-owned policy is
evidence admission, **not authentication or proof that a report was reviewed**.
Never accept policies, confirmation flags, official product objects or source
allowlists from a browser request. No inference routine can verify who inspected
a site; Rudra/Braydin must establish that trust through existing protected feeds.
An admitted local observation must establish the exact active target, not merely
a nearby environmental measurement. Non-replay duration evidence/confirmation is
fresh within one hour and site-verified. Event start, confirmation, availability
and observation chronology are checked independently. Missing starts stay missing.

Malformed IDs/coordinates/duplicate event IDs are Pydantic validation errors for
an owner to map to 422. Valid requests with unavailable sources/models produce
typed per-event unavailable cards; other cards survive. Empty/unconfirmed events
are not applicable, never zero risk. The discriminated `forecast.kind` selects
duration/official-event/official-aftershock/unavailable. Every card retains its
notice ID, exact event name/type, confirmation, association, times, source references,
method, limitations and replay label. Unsupported local probabilities are null.
No composite probability, score or work authorization is calculated.

Official products are parsed read-only with `parse_nhc` / `parse_oaf` and supplied
server-side via `official_products={key: parsed_product}`. NHC's source identity,
full track parsing, chronology and next-advisory deadline are checked. USGS links
the product hash/URL/mainshock and validates region, magnitude bins, probability
bounds and windows. Missing, mismatched, future-issued, revised-after-as-of,
expired or geographically inapplicable products yield unavailable. Completed OAF
windows are removed; retained overlapping windows are original provider windows.
Archive captures require explicit replay. A future real collector must preserve
contemporaneous retrieval/availability, updates, deletion/cancellation and freshness.

## Rudra handoff: T050A and multiple events (proposal only)

1. Keep `SiteDetail.event_outlook`, `EventOutlookService`, current routes and role
   dependencies unchanged for existing callers. Publish an additive canonical
   `event_outlooks: list[...]` and matching TypeScript union only after review.
   The internal envelope/version here is not a silent SiteDetail schema upgrade.
2. In `backend/app/outlook/context.py`, supply **actual event start** instead of
   deriving it from `notice.created_at`. Require independent confirmation of
   continued activity and a verified site relationship. For Flash Flood, an
   NWS Flash Flood Warning can identify the category; human-confirmed/local
   evidence must independently confirm activity. A notice's label alone cannot.
3. In `backend/app/outlook/service.py` and `backend/app/api/sites.py`, authorize
   first, build one typed event input per qualifying confirmed event, call this
   adapter once per batch, and retain every card by `(site_id,event_id)`; do not
   replace one event with another or feed ML outcomes into `score_site()`.
4. For official formats, trusted ingestion supplies the exact product/event IDs,
   original issue/valid/retrieval times and verified regional relationship. Do not
   infer hurricane exposure from distance to center. USGS circle membership is
   regional context, not a point hazard model. Other OAF geometry remains unsupported.
5. Review `multiple-events.request.json` / `.response.json`, `flash-flood.*` and
   both JSON schemas generated by the command. Acceptance: existing authenticated
   crew/supervisor scope tests; Flood+Flash Flood with true starts and local
   confirmation; warning-only/stale/late/wrong-site rejections; multi-event partial
   failure; unchanged persisted index, deterministic alerts and lightning timer.

**T050A remains unchecked.** This ML preview does not satisfy server-backed
acceptance or authorize edits to Rudra's pending implementation. T063–T068 and
all other task states are unchanged.

## Claude handoff: component inputs (proposal only)

Consume the future Rudra-published union through the existing API client. Suggested
panel interface: `{ siteId: string; eventOutlooks: EventOutlookCard[]; mode:
'live' | 'replay'; loading: boolean; error: string | null }`. JSON schema and exact
examples are generated beside `index.html`; no frontend imports of Python modules.

Key cards by event ID. Branch on `forecast.kind`, not the event display label:
duration cards show only provided horizons and nullable quantiles; NHC cards show
provider track/wind units/valid times without local wind or an end timer; OAF cards
show mainshock, exact original windows/magnitude thresholds and regional scope.
Unavailable is a visible reason, never 0%. Differentiate research, issued, replay,
rejected and missing evidence. Show as-of/issue/retrieval and spatial relationship.
`production_eligibility=false` is explicit for this whole package. Keep existing
`Duration.tsx` singular input stable until Rudra publishes compatibility types.
No page/component/style/auth/API client file was changed in this implementation.

## Scientific limits and verification

The existing [Flood evaluation](EVALUATION.md),
[per-target evaluation](MULTIDISASTER_EVALUATION.md), model cards and fixed registry
remain unchanged. KM remains selected for five NOAA targets; heat retains logistic.
Previously inspected test periods are not a new untouched holdout. Persistence
qualification does not certify duration interval calibration (for example Heavy
Rain's selected-KM nominal 80% interval coverage was about 57.86%). Unidentified
quantiles remain null. No severity trajectory, individual injury, local exposure
or site hazard probability was independently validated in this change.

No new Monte Carlo run, historical retraining or holdout study was performed.
Existing seeded MC checks concern conditional distribution arithmetic/sensitivity;
they do not establish predictive accuracy. Official provider forecasts are evidence
with their own scope, not newly validated PlanIT models.

Verification commands and actual outcomes for this branch are recorded in
`reports/event_outlooks_verification.json`. Focused unit tests exercise admission,
source/target isolation, chronology, model failure, official parsing, region checks,
null quantiles, partial multi-event failure and deterministic offline replay. A
separate no-artifact export verifies graceful clean-checkout behavior. Passing
tests do not establish operational forecast skill or authenticated integration.
