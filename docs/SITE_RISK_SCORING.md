# T051A: deterministic Site Hazard Index

`backend/app/rules/score.py`, version **rules-0.2**, implements the existing
`compute_score(site_id, observations, alerts, reports, now, previous=None,
settings=None, site=None) -> HazardScore` interface. Defaults live in `RuleSettings`.
All weights, bands, report caps and regional thresholds are **prototype choices**,
not calibrated likelihoods, employer policy or regulatory thresholds. A numerical
band never authorizes work, suppresses an alert or establishes site safety.

## Formula, weights and bands

```text
index = round(clamp(sum(qualified contributions), 0, 10), 1)
```

Classify the rounded index: `[0,3)` low; `[3,6)` moderate; `[6,8)` high;
`[8,10]` critical. These are numeric bands, not hazard-specific action rules.
For example, lightning's 3-point contribution is in the moderate band while its
independent stop-work alert remains fully authoritative.

| Factor | Default points | Qualification / interpretation |
| --- | ---: | --- |
| Lightning | 3 | One active site lightning stop-work alert; no extra points per strike/reset |
| Heat index | 0 or 0.5–2 | Highest eligible published observed HI or derived observed/next-12h forecast HI; one factor |
| Flood | 0 / 1 / 2 | Explicit successful no-alert result / Flood Watch / Flood or Flash Flood Warning; strongest once |
| Hurricane/tropical storm | 2 | Existing T049A NWS Hurricane/Tropical Storm Warning for site or NHC center within 50 mi |
| Earthquake | 1.5 | Existing T049A USGS magnitude >=4 within 25 mi |
| Confirmed-present report | 0.5 / 1 / 1.5 | Reviewed low/moderate/high; at most 3 points per reviewed category |

Heat reuses T049's NWS heat-index calculation. Let `H` be HI rounded to one decimal
Fahrenheit, as in the existing factor implementation. If `H < 103`, points are 0;
otherwise `round(0.5 + 1.5 * min(1, (H - 103) / 22), 2)`. Thus 103 F adds 0.5,
110 F adds 0.98 and >=125 F adds 2. This precision precedes final index rounding.
There is no separate contribution from temperature or humidity.

Lightning receives the largest single default weight because it represents an
existing explicit stop-work state. Heat, flood and tropical contributions retain
the team's 2-point maxima; nearby earthquakes retain 1.5 because a regional
epicenter is not local damage evidence. Report weights preserve reviewed severity;
the 3-point category budget bounds repetition while allowing two high-severity
reports. These are transparent design rationales, **not empirically estimated
relative harm**. The defaults intentionally preserve T051/T049A ordering.

Simultaneous different hazards add. Correlated hurricane, flood and heat signals
are not independent probabilities: the index is an additive prioritization
heuristic. A local flooding report and an official warning may both contribute
because their evidence pathways differ; their joint harm is not calibrated.
The uncapped factor sum may exceed 10; factors retain original credit and the
index saturates. Displaying 10 must not imply that all hazards have been measured.

## Evidence qualification and provenance

Inputs must be trusted normalized backend schemas, not arbitrary browser assertions.
Source names are an allowlist, **not proof of authenticity**. Existing ingestion,
confirmation and authorization paths remain responsible for that trust.

- All scoring clocks and evidence timestamps require timezones. Observation/issue
  and successful fetch times must be <= `now`; issue time cannot follow fetch time.
  Direct callers also receive the existing latest-fetch-per-type/source selection.
  Lightning is one feed across GOES/replay sources, so a newer fallback cannot
  reuse an older live snapshot as current coverage.
  A newer unavailable snapshot does not resurrect an older current warning.
- Local NWS weather/flood/tropical notices and lightning require this exact site's
  association. Other sites are ignored. Unscoped NHC centers and USGS epicenters can
  be evaluated using the supplied site's coordinates; a mismatched/invalid site
  argument fails explicitly. Production `score_site` supplies the actual DB site.
- NWS direct HI/temperature require finite Fahrenheit (`°F` or `F`). Derived HI
  requires finite temperature plus humidity in `[0,100]` percent. Pairing requires
  identical station/grid reference, coordinates, observed/issued time, valid time,
  hazard type and replay flag. Pair freshness is conservative: stale humidity
  makes derived HI stale. Labels cite the humidity evidence in addition to the
  factor's primary temperature evidence ID. Raw values are never added again.
- Forecast temperature/humidity must have been issued/fetched as of `now`, with a
  valid time from `now` through `now + heat_window_hours` (12 default). Expired,
  future-issued and contradictory records cannot be operational features.
- NWS flood values must be the adapter's three supported event names. Null is
  current only with its exact successful `NO_ACTIVE_ALERTS` marker. If a flood or
  NWS tropical notice carries `valid_at` (normalized expiration), it must be > now.
  An absent expiration relies on the trusted current active-alert query; it is not
  independently reconstructed from a CAP archive.
- Regional factors reuse T049A distances, inclusive boundaries, warning types and
  magnitude rules. NWS and NHC descriptions of the same storm, or many earthquakes,
  yield at most one factor per hazard. An NHC intensity is not a local wind-field
  measurement; an epicenter/magnitude is not structural inspection or ShakeMap.
- Each credited factor retains source, evidence ID, source observation/valid time,
  value/unit where available and prototype/state labels. Full fetch/issue/geometry
  provenance remains on the linked Observation/Alert; FactorContribution cannot
  store every timestamp, polygon or secondary evidence ID structurally.

The Observation contract does not carry alert status, polygon, forecast-period end,
station distance or verified gauge/basin/datum linkage. The scorer cannot independently
revalidate those upstream relationships. No geometry, local inundation, damage or
field inspection is inferred from a site ID. Additional provenance is an ingestion/
contract handoff, not something this module fabricates.

## Freshness, unknowns and completeness

Existing `IngestionSettings` control cache ages: default **>60 minutes stale,
>360 minutes unavailable**. Exactly 60 minutes remains current; exactly 360 remains
stale. Existing stale/unavailable states are never upgraded by scoring. Fetch age
drives event-query freshness; for station weather the older of observation/fetch
also matters. A warning issued yesterday can still be current after a fresh
active-alert query. Missing fetch time uses observation/issue time conservatively;
it does not prove historical availability. Optional feed settings are unchanged.

Stale dangerous readings retain points within availability limits with explicit
`stale; not live coverage` labels. Unavailable, expired or rejected measurements
do not provide measured points; their factor is **unknown**, not verified absent.
As evidence expires, the numeric partial index can fall. No artificial safety
floor or previous-score carry-forward conceals this lack of current evidence.
Active authoritative lightning alerts keep their contribution through failure
and even an elapsed `clear_after`; only the existing deterministic rule changes
alert state. This scorer neither resets the timer nor clears an alert.

```text
data_completeness = round((current_heat + current_flood + current_live_lightning) / 3, 2)
confidence = data_completeness
```

Heat/flood refer to the selected qualified factor. Lightning coverage comes from
the current feed, independently of an alert. `observed`/`forecast` qualify as
current; `simulated`, replay source/flag, `stale`, `unavailable` and reports do not.
A replay can show the prototype arithmetic and keeps its label, but cannot stand
in for live monitoring. A stale high HI selected over a lower current HI makes
heat completeness conservative. Confidence is a **coverage proxy**, never a
statistically calibrated probability.

Regional feeds are optional and outside this **P0-only** denominator. If reported
and the site is supplied, their factors expose stale/unavailable states. No factor
when never reported/without site means **not evaluated**, not no regional hazard.
Consequently 1.0 does not mean full regional, report, electrical or worker-hazard
coverage; neither crew report absence nor an optional-feed outage changes P0 coverage.

### Frozen contract gap: insufficient evidence is not low risk

`HazardScore.risk_score` is mandatory numeric and `risk_level` has only the four
numeric bands. No-data and healthy no-trigger inputs both produce `0 / low`, but
only the former has completeness 0 and three explicit unavailable factors. This
known limitation also applies to stored site summaries and next-day briefings.
**Do not present an incomplete numeric band as verified low risk.**

Proposal for **Rudra's review**, not implemented: publish a compatible additive
`score_evidence_status` (`unavailable`, `partial`, `current_supported_inputs`) and
source-specific coverage alongside existing index/band fields, with matching
persistence, SiteSummary/Detail/Briefing schemas and fixtures. For example:

```json
{"risk_score": 0, "risk_level": "low", "data_completeness": 0,
 "score_evidence_status": "unavailable"}
```

This JSON is a proposal, **not a currently valid canonical response**. Until that
change is approved, Claude should use existing completeness/states to label
“Evidence incomplete / conditions unknown” beside the number and avoid a standalone
low-risk claim. The backend must not sort an incomplete zero as evidence that a site
is safer, and briefings must preserve unknowns. Ranking policy and UI/briefing
changes belong to Rudra/Claude/Braydin; no shared contract or UI was changed here.

## Confirmed reports and bounded duplication

Only this site's trusted `confirmed` + `hazard_present=true` reports count. Pending,
rejected, absent and potential notices add no points; Gemini enrichment is ignored.
Created/reviewed times must be known as of scoring and review cannot precede creation.
Reviewed category/severity win; legacy missing severity uses the previous moderate
weight with an explicit label, rather than accepting an AI suggestion.

Latest version per report ID wins; tied timestamps prefer noneligible states.
Identical IDs count once. Distinct IDs sharing a trusted notice ID describe one
underlying notice: highest reviewed severity (then stable ID) receives credit once.
Other distinct IDs are never guessed to be duplicates from location/time/category.
They all remain in the breakdown. Highest severity then stable ID receive credit
within each reviewed category's 3-point budget; partially/fully capped factors
retain evidence IDs and explicit cap labels. Independent categories retain their
own budgets. Reports have no automatic age expiry: unresolved confirmed hazards
require a qualified resolution lifecycle, absent from the frozen report schema.
That owner follow-up should precede treating old confirmation as current inspection.

## Excluded measurements and dependencies

Raw temperature/humidity are HI inputs. Rain probability, raw wind/gusts, gauge
stage/discharge without site-linked flood thresholds/datum, soil, smoke and other
context receive **no invented weights**. They may be displayed as evidence. Heat
index is not WBGT or individualized heat illness. Weather cannot confirm energized
water, downed lines, structural/chemical/wildlife hazards or road access; only the
trusted report pathway supplies report contributions for supported categories.
No ML onset/persistence/intensity, offline Monte Carlo, Gemini suggestion, injury
probability or frontend-calculated term enters this score.

## Reproduce and evaluate

From repository root with Python >=3.11 and existing backend dev requirements:

```powershell
python -m pip install -r backend/requirements-dev.txt
python backend/tests/score_scenarios.py --output docs/site-risk-scoring-evaluation.json
python -m pytest backend/tests -q
python -m ruff check backend
```

The runner makes no network calls or DB writes, pins UTC `2026-10-17T18:00:00Z`
and explicitly supplies all default rule/cache settings, overriding local env for
this evaluation only. Its JSON is byte-reproducible and validated by a regression
test. Live scoring still uses the deployed RuleSettings/IngestionSettings.

The [evaluation JSON](site-risk-scoring-evaluation.json) contains 35 controlled
scenarios and five canonical examples. At equal coverage, two existing reconciled
EIA reference IDs each rank synthetic lightning + confirmed report (4.5) above
healthy no-trigger evidence (0). These are hypothetical inputs at reference
coordinates, **not actual incidents, live monitoring or active work orders**.

| Controlled case | Index | Completeness | Meaning |
| --- | ---: | ---: | --- |
| No evidence | 0 | 0 | Unknown, numeric contract limitation |
| Healthy supported inputs, no triggers | 0 | 1 | No scored trigger in those inputs; not clearance |
| Heat 110 F | 1.0 | 1 | HI contributes 0.98 before final rounding |
| Flood Watch / Warning | 1 / 2 | 1 | One strongest official-alert factor |
| Active lightning, later feed failure | 3 | 0.67 | Alert retained; current monitoring incomplete |
| Six independent high reports, same category | 3 | 1 | Two get 1.5 each; all six evidence IDs retained |
| Extreme heat + flood + lightning + storm + quake + high report | 10 | 1 | Raw sum 12; saturated, not a probability |

Existing frontend `site-detail.json` is also parsed and rescored. The original
archived 7.6 fixture used obsolete illustrative model terms. The demo-fixture fix
now calls `compute_score` in the canonical generator: **6.1 / 10 (high), rules-0.2**.
Its points are lightning 3.0, simulated heat index 112 °F 1.11, Flood Watch 1.0 and
confirmed-moderate wildlife 1.0; the approved algorithm rounds the total to one
decimal. Weather values reuse T069's simulated inputs. Current live completeness
is 0, explicitly incomplete. List/detail/both briefings agree; ML cards stay separate.
The checked evaluation report reproduces this fixture comparison, not live parity.
After updating, click **Reset demo** once to replace old browser-saved fixtures;
this updates only `planit:frontend-demo:v1`, preserving Auth0 and other storage.

No single default environmental factor dominates the whole index. Many categories
can saturate it; one report category cannot grow without bound. Incomplete and
healthy zeros still tie numerically, so comparisons across different coverage
must not be represented as validated safety rankings. These checks establish rule
consistency, **not predictive accuracy, calibrated injury risk or operational safety**.

## Integration and owner handoff

- **Rudra:** review the category budget and incomplete-index status proposal before
  merge/operational display. `services/scoring.py` and all routes remain unchanged.
  Existing refresh ingests, evaluates alerts and calls `score_site`; report confirmation
  atomically calls it; previous-score ordering/locks and full report queries remain.
  Regression tests cover refresh trigger/clear/rescore, held alerts, persistence,
  stored site reads, concurrency/rollback and canonical schemas. A standalone
  `apply_lightning_rule` call does not itself rescore; callers outside refresh must
  retain that orchestration. Feed refresh remains opt-in, not enabled by this change.
- **Braydin:** existing 18:00 briefing tests verify its risk level comes from the stored
  deterministic score, not Gemini. Review insufficient-evidence wording/status there.
  Preserve source/fetch/expiration/site provenance and supply canonical metric units;
  additional CAP geometry/status or inspection resolution needs an owner contract.
  No auth, DB, ingestion, schedule, Gemini provider or deployment settings changed.
- **Claude:** no component migration or frontend edit in this PR. Existing field names
  and states remain valid; render actual backend contributions, visible unknowns and
  replay labels. Archived fixtures are illustrative; completeness 1 covers P0 only.
  No countdown-to-clearance or client score calculation may be derived from the index.

Version rules-0.2 records qualification, report budgets/deduplication, truthful
completeness and explanatory labels. It preserves weights/bands, callable signature,
canonical DTOs, T049A rules and all deterministic alert logic. Record deployed weight
and cache configuration alongside version when evaluating custom settings; weights
are validated finite, nonnegative, <=10 and ordered by severity. New policy/default
changes require versioned review. Existing SQLite/API/fixture tests are independent
checks, not proof of live Auth0/Tiger Data deployment acceptance. ML is unchanged.

## Verified acceptance (2026-10-17)

Initial focused baseline: 73 passed. Final `python -m pytest backend/tests -q`:
**637 passed**, zero skipped, 11.15s. The only warning is the existing Starlette
TestClient/httpx deprecation. `python -m ruff check backend` passes; all seven
changed Python files pass Ruff format check at the repository's 100-column style.
The 35-case evaluation regenerates and matches its checked JSON exactly; a fresh
Python subprocess succeeds with ML/Gemini imports blocked and Gemini key absent.
No frontend, canonical schema, provider adapter, route, persistence or ML change
requires a new UI build here. No live-service or workplace-safety acceptance claimed.
