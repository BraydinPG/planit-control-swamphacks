# Feed refresh performance and reliability

Cache's explicitly authorized ingestion/refresh change, based on main `11c62b6`,
on `feature/cache-feed-refresh-performance`. Review owners: Braydin (providers,
configuration) and Rudra (persistence, notices and scoring integration).

## What was measured

The reported production baseline was approximately 20 minutes for 256 sites, with
219 current sites, 13 USGS timeouts, eight MA/NY NWS errors and one NWS connection
timeout. Those are operator reports, **not measurements reproduced here**. No raw
production error logs were available to establish their individual causes.

The committed benchmark uses 256 synthetic locations in 16 shared-resource clusters,
10 ms of mocked latency per request, in-memory SQLite, five network adapters and the
real serial persistence/scoring pipeline. Weather includes hourly forecasts;
hurricanes include NHC and NWS. It excludes lightning network retrieval/GLM polling,
but exercises the unchanged lightning rule with missing evidence. One demo site is
excluded. It never opens provider sockets or uses the application database.

Baseline: export tracked `backend/` from `11c62b6` and copy the **same** benchmark
script into it. After: run the script on this branch. Both clients have pacing
disabled for this comparison, isolating deduplication and bounded concurrency.
The separate paced run exercises conservative production pacing with mocked HTTP.
These are individual elapsed measurements, sensitive to host load, not live SLAs.

| Metric | Original controlled run | Optimized controlled run |
|---|---:|---:|
| Total | 21.05 s | 4.44 s |
| NWS requests | 1,536 | 560 |
| USGS gauge requests | 256 | 16 |
| USGS earthquake requests | 1 | 1 |
| NHC requests | 1 | 1 |
| Total requests | 1,794 | 578 |
| Synthetic timeouts | 0 | 0 |
| Sites processed | 256 | 256 |
| Peak HTTP concurrency | 1 | 4 |
| Serial DB and remaining processing | 1.11 s | 2.22 s |
| Persistence only | 0.74 s | 1.34 s |
| Scoring only | 0.26 s | 0.58 s |

**1,216 requests eliminated (67.8%)**. Observation hashes for every feed and the
stored score hash match before/after; IDs, site associations, coordinates, source
times and numerical outputs match. Database processing remains serial. Detailed
fetch, persistence, scoring, mean/max transport time and coverage metrics are in
[baseline](feed-refresh-baseline.json), [optimized](feed-refresh-optimized.json)
and [paced](feed-refresh-paced.json). Each report records source hashes and Python
version. Request times in those benchmark tables measure the transport handler;
runtime HTTP attempt times additionally include waiting for provider slots/pacing.
The DB portion was slower in these individual measurements; it has not been
optimized or claimed faster. The measured gain is in network retrieval.

The separate paced run took **152.96 seconds** (2 min 33 s), with the same 578
requests, 256 sites and matching observation/score hashes. Its peak was one because
the artificial 10 ms responses finish before the default start-spacing interval.
It does not demonstrate real provider latency, database latency or outage coverage.
**The real 256-site refresh has not been run.** The reported production 20 minutes,
219-site coverage and individual MA/NY failures remain live acceptance items.

## Coverage in the controlled workload

Each row covers all 256 sites; stale, unavailable and confirmed not-covered counts
are **zero** in this deliberately healthy workload. This is synthetic coverage only.

| Source / outcome | Current observations or forecasts | Successful query, no qualifying event |
|---|---:|---:|
| NWS weather | 256 | 0 |
| NWS forecast | 256 | 0 |
| NWS flood notices | 0 | 256 |
| NHC storms | 0 | 256 |
| NWS tropical notices | 0 | 256 |
| USGS earthquakes | 0 | 256 |
| USGS gauge measurements | 256 | 0 |

No-qualifying-event rows have `value=null`, never zero. A successful empty gauge
query says there are no usable nearby measurements and flood conditions are unknown;
it is not a measurement of absent flooding. Gauge height/discharge remain gauge
observations, with their actual coordinates, source identity, units and time; no
basin linkage, site depth or flood stage is inferred.

`RefreshResult.metrics.coverage` groups retrieval status by actual source/hazard,
counting each site once per group as `current`, `no_qualifying_result`, `partial`,
`stale`, `unavailable` or `not_covered`. These are **internal metrics**, not new API
DataState values. `complete_feed_sites` includes healthy empty queries and excludes
stale/unavailable subfeeds. It does not mean complete worksite hazard knowledge.
`fully_processed_sites` separately counts sites finishing persistence/rules/scoring;
`failed_sites` and cancellation must also be inspected. Invalid site coordinates
are reported and skipped without fabricated placeholder coordinates.

## Implementation and safety

- Network workers receive immutable `SiteSnapshot` values. Adapters fetch concurrently
  with a bounded submission queue, then the existing ORM session writes in sorted
  site order. Observation upsert keys, scoring, alert and notice functions are preserved.
  A site moved/deleted while fetching is rejected before attaching old evidence.
- `NwsClient` and `JsonClient` own pooled synchronous HTTPX clients. Explicit close and
  context managers are available; lazy module clients live for the process and have
  finalizer cleanup. Caller-owned clients must be closed after workers finish.
- Identical GET resources are single-flight within a round, including failures, so
  several workers do not independently retry one failing endpoint. New rounds retry
  transient failures. Responses are detached after bounded streaming and parsed into
  independent dictionaries. Ordinary connection pooling does not imply a real TCP
  handshake reduction measured by MockTransport.
- NWS points are keyed by coordinates with 24-hour revalidation; station metadata
  expires after one hour. Concurrent lookups share a Future. Metadata cache is bounded
  to 4,096 entries. Explicit outside-coverage point errors get one-hour negative TTL;
  generic 404, InvalidPoint alone, 429 and 5xx do not become permanent exclusions.
  Observation fallback cache keys include coordinates, preventing reuse after a move.
- NWS alert queries use authoritative forecast/county/fire-zone mappings when supplied
  by `/points`. Queries are shared across sites and flood/tropical adapters. Actual
  Polygon/MultiPolygon geometry (including holes) determines polygon inclusion; otherwise
  exact affected-zone association is required. Uncertain or complex geometry falls
  back to the provider's point query; unverified point-query geometry is unavailable.
  No state-wide alert is assigned to every site. Pagination is followed within the
  trusted NWS origin (30-page cap); expired/test/cancelled/future-issued or invalid-time
  messages are excluded or rejected. Other event types are not added by this change.
- USGS queries batch up to 32 sites per half-degree cell **and region**, union their
  search boxes, round boundaries outward, and enforce the documented 25-square-degree
  bbox cap. Each site independently filters actual gauge distance and selects its
  nearest three usable gauges. A failed group affects only that group. Nonfinite,
  future-dated, wrong-unit and numerical/string no-data values are discarded.
- Retry connection errors/timeouts, read timeouts and 429/500/502/503/504 only, with
  bounded exponential jitter. Do not retry 400/401/403/404, malformed responses,
  invalid coordinates or configuration errors. Respect numeric/date Retry-After;
  429/503 cooldown is shared between workers. Too-long cooldown does not sleep past
  the request budget. Response bodies are capped at 20 MB; redirects are rejected.
- Cancellation and deadline checks stop new requests and backoff. An in-flight
  synchronous socket can take its remaining read/connect timeout to finish. The
  round budget bounds cooperative **network work**, not SQL execution or a hard
  wall-clock process deadline. Cancellation stops subsequent database writes.
- The live demo site remains excluded. Failed providers never change another feed's
  cached state; timestamps of stale evidence are retained. Missing forecasts and
  missing NHC/NWS subresults receive separate unavailable placeholders. No scoring
  weights, lightning detection/10-mile trigger/30-minute timer, ML, Gemini, canonical
  schema, frontend, security, database migration or shared environment template changed.

HTTP attempt and final site-result JSON logs are correlated by feed/site or group:
provider, method, redacted endpoint, status, exception class, region, attempt, duration,
retry flags and final stale/unavailable/not-covered state. Shared summary failures are
reported under `shared`, not incorrectly assigned to one state. Parser failures are
separate `feed_invalid_response` events; they do not inflate HTTP request counts.
Raw exceptions, response bodies, headers and database URLs are not logged. HTTPX URL
logs are also filtered to redact userinfo, unknown query values, sensitive path values
and fragments. Endpoint filters retain ordinary point/zone/bbox parameters for diagnosis.

## Configuration

Existing settings and environment templates remain compatible. Optional environment
variables below are read through the existing ingestion settings, with conservative
defaults. Limits and spacing are process-local, shared between same-policy clients
for a host, not distributed across backend instances. Do not mix different policies
for the same provider or run competing job owners. NWS does not publish an exact
rate limit; these settings are a starting policy, not an agency entitlement.

| Environment variable | Default | Meaning |
|---|---:|---|
| `FEED_SITE_WORKERS` | 6 | 1–16 network tasks; DB stays serial |
| `FEED_ROUND_BUDGET_SECONDS` | 480 | Cooperative network budget |
| `FEED_HTTP_MAX_RETRIES` | 1 | At most two attempts; configurable 0–3 retries |
| `FEED_HTTP_BUDGET_SECONDS` | 20 | Per-resource budget including gate/backoff |
| `FEED_HTTP_CONNECT_SECONDS` | 3 | Connect timeout |
| `FEED_HTTP_BACKOFF_SECONDS` | 0.5 | Exponential base plus uniform jitter |
| `NWS_HTTP_CONNECTIONS` | 4 | Shared NWS in-flight cap |
| `NWS_MIN_INTERVAL_SECONDS` | 0.25 | Minimum between NWS request starts |
| `USGS_HTTP_CONNECTIONS` | 2 | JSON client host cap (also applies separately to NHC) |
| `USGS_MIN_INTERVAL_SECONDS` | 0.5 | JSON client per-host start spacing |
| `NWS_POINT_CACHE_SECONDS` | 86400 | Grid mapping TTL |
| `NWS_NOT_COVERED_CACHE_SECONDS` | 3600 | Explicit coverage rejection TTL |
| `NWS_STATION_CACHE_SECONDS` | 3600 | Station metadata TTL |
| `FLOOD_GAUGE_BATCH_DEGREES` | 0.5 | Cell width, max 1 degree |
| `FLOOD_GAUGE_BATCH_SITES` | 32 | Max sites/query, max 100 |

Existing `NWS_TIMEOUT_SECONDS` and `FEED_TIMEOUT_SECONDS` remain read timeouts;
stale/unavailable windows remain 60/360 minutes by default. Caches are in-process,
so the first round after restart is cold. Pooled JsonClient also serves existing
GLM binary retrieval; transport pacing/retries/size bounds apply without changing
lightning detection. The full GLM fixture tests are part of backend acceptance.

## Reproduce offline

Use the existing pinned backend environment; no credentials or ML artifacts required.
From repository root in Windows PowerShell:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m scripts.benchmark_refresh --output ..\docs\feed-refresh-optimized.json
.\.venv\Scripts\python.exe -m scripts.benchmark_refresh --paced --output ..\docs\feed-refresh-paced.json
```

The baseline can be reproduced without changing any working branch or configuration:

```powershell
Set-Location .. # repository root
$benchmarkExport = Join-Path (Resolve-Path backend\.pytest_cache) 'feed-baseline-11c62b6'
New-Item -ItemType Directory -Force -Path $benchmarkExport | Out-Null
git archive --format=zip --output "$benchmarkExport\baseline.zip" 11c62b6 backend
Expand-Archive -LiteralPath "$benchmarkExport\baseline.zip" -DestinationPath $benchmarkExport -Force
Copy-Item -LiteralPath backend\scripts\benchmark_refresh.py -Destination "$benchmarkExport\backend\scripts\benchmark_refresh.py"
$benchmarkPython = (Resolve-Path backend\.venv\Scripts\python.exe).Path
Push-Location "$benchmarkExport\backend"
& $benchmarkPython -m scripts.benchmark_refresh --output baseline.json
Pop-Location
```

The export contains tracked backend files and the benchmark, no `.env` or secrets.
If `.pytest_cache` does not exist yet, create it first. The actual run here used the
existing `hazard_clean_check` Python environment (3.14) at its absolute local path;
`.venv` above denotes a teammate's normally provisioned backend environment.

## Safe operator one-shot procedure (not executed here)

1. Braydin confirms the intended Tiger Data host/database and authorized job owner
   privately; ensure no scheduler/manual round is already using that database. Keep
   **`FEED_REFRESH_ENABLED=false`** in this checkout. Do not stop teammate processes.
2. Supply the approved `DATABASE_URL` and identifying `NWS_USER_AGENT` through ignored
   backend configuration. Do not print connection strings. Confirm the legacy USGS
   service status and migration plan below. Do not seed/migrate/reset shared data.
3. From `backend`, run `.\.venv\Scripts\python.exe -m app.services.refresh --check-only`.
   It connects to nothing and prints only readiness plus driver/host/port/database,
   omitting username/password/query. Confirm target with Braydin before proceeding.
4. Only after the owner approves the single write round:
   `.\.venv\Scripts\python.exe -m app.services.refresh --report-json .pytest_cache\approved-refresh.json`.
   This is the existing one-shot command with optional reporting, not a scheduler.
5. Inspect total/fetch/DB phases, request statuses/exception regions, explicit coverage
   counts, failed sites and fully processed count. Compare with 256 current eligible
   sites, not an assumed fixed site count; excluded demos do not count. Review MA/NY
   endpoint/status details before declaring unsupported coverage. Check observation
   source times, stored score breakdown and retained active lightning state.

Local preflight in this run: `database_configured=false`,
`nws_user_agent_configured=false`, `feed_refresh_enabled=false`. No shared database
was connected to, written or benchmarked. Other servers and worktrees are untouched.

## Verification

- Initial existing focused ingestion/refresh baseline: **85 passed**.
- Final complete backend suite: **923 passed**, including 42 new offline cases;
  the existing Starlette TestClient deprecation warning remains. The final run
  rejected external socket connections, allowing loopback for Windows asyncio's
  internal socketpair. The first over-strict guard blocked that internal mechanism;
  it was corrected without weakening application assertions or changing app code.
- Ruff lint passes; Ruff formatting checks pass for **153 files**. Canonical schema
  mirror, scoring, alert timing, GLM, refresh upsert, demo exclusion and provider-outage
  regressions are included in the full suite. No frontend build is needed for this
  backend-only change; frontend sources/contracts are unchanged.
- Both baseline/optimized observation and score hashes match. The paced report was
  captured just before the final diagnostics-only shared-region refinement; source
  hashes in each report make that difference explicit. The final full suite includes
  the shared-provider failure regression. No historical training or live feed round.

## Source limits and owner handoff

- [NWS API documentation](https://www.weather.gov/documentation/services-web-API)
  describes cache-friendly resources, unpublished rate limits and `/points` mapping
  revalidation. [NWS alert guide](https://www.weather.gov/documentation/services-web-alerts)
  documents official alert access. Regional resource reuse is not independent site
  measurement and does not imply universal coverage.
- [USGS IV query documentation](https://waterservices.usgs.gov/docs/instantaneous-values/instantaneous-values-details/)
  specifies bbox order and the 25-square-degree constraint. This adapter retains that
  compatible endpoint; it has not silently interpreted modern OGC responses as legacy IV.
- [USGS migration guide](https://api.waterdata.usgs.gov/docs/ogcapi/migration/)
  maps latest IV readings to `latest-continuous`. Modern service access requires an
  approved API key for more than a few queries/hour. No approved local key was found.
  [USGS degradation notice](https://waterdata.usgs.gov/blog/wdfn-waterservices-degradation/)
  describes intentional legacy slowdowns/blackouts before retirement on **2027-02-22**.
  These may contribute to observed timeouts; this run cannot establish their cause.
- [HTTPX API](https://www.python-httpx.org/api/) documents reusable clients and pooling.

**Braydin:** review provider gates, identifying User-Agent, metadata/negative TTL,
USGS batching/provisional readings and a separately reviewed modern USGS migration
with approved credentials, pagination, units/time/quality and offline contract tests.
Schedule one approved live round to measure genuine coverage and latency; do not infer
the 13 USGS timeout or MA/NY causes from synthetic tests.

**Rudra:** review immutable snapshots, serial writes, unavailable subfeed placeholders,
coverage versus persisted-site metrics, cancellation and unchanged scoring/alert calls.
Current CLI rejects manual execution when the local scheduler flag is enabled but
cannot discover distributed schedulers on other machines. Coordinate job ownership.
No frontend/schema adaptation is required. No task checkbox is changed; the live
speed/coverage portion of this request remains unverified until that approved round.
