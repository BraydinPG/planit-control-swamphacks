# Source inventory diff from merged PR #9

Snapshot as-of: **2026-10-17T07:18:48.564672Z**. All activations remain hypothetical; records are not independent disasters or worker incidents.

| Provider | Actual state | Count / limits |
|---|---|---|
| NOAA NCEI / existing duration sources | existing_historical_verified | records=349030; 54 raw labels, prior fitted/gated models unchanged; no archive download or refit |
| NWS native CAP/API notices | new_real_retrieval_verified | records=553, point_query_records=11, point_queries_succeeded=50; National and point records overlap; never sum as independent events. Native status/message lifecycle and actual polygon or provider point-filter provenance are retained. |
| NWS local observations/issued hourly forecast | new_real_retrieval_verified | normalized_records=48, sites=2; Actual backend-selected coordinates; four explicit forecast windows plus latest available station readings, not universal 50-site weather coverage |
| USGS modern water v1 | new_real_retrieval_verified | records=5; Parameter 63160 historical/provisional stage sample, not latest-live guarantee. Datum and basin/site transfer absent; rejected as site water evidence. Legacy WaterServices retirement is February 22, 2027 per official notice; new acquisition uses api.waterdata.usgs.gov/ogcapi/v1. |
| USGS earthquake/ShakeMap | new_real_retrieval_verified | catalog_events=3, grid_products=1; Real automatic Pakistan grid, real model estimate at hypothetical source location; zero US EIA-site coverage. Uncertainty product and damage labels absent. |
| NOAA SWPC issued messages | new_real_retrieval_verified | records=80, normalized_geomagnetic=46; Only K-index message families mapped to geomagnetic context. No structured expiry inferred from prose; no current site warning or outage estimate. |
| EIA-860M backend identity export | existing_source_new_verified_export | backend_selected_locations=260, acceptance_sites=50; Actual read-only backend selector export, source hash/state/plant/coordinates checked; no deployed DB contents or active work orders verified. |
| NHC / CO-OPS / NDBC / ISD / NIFC | existing_probes_preserved | ; Prior receipts/limitations retained. NIFC sample is attributes only; no new perimeter geometry, containment, historical issued cohort or basin transfer. |
| NASA FIRMS | fixture_only_blocked_credentials | ; MAP_KEY/archive access not supplied. Existing detector parser and synthetic hotspot/perimeter scenario are not authenticated collection. |
| EPA AirNow | fixture_only_blocked_credentials | ; Account/API key not supplied. Concentration units and explicit averaging windows remain distinct from AQI. |
| EPA AQS | source_discovered_not_retrieved | ; Separate historical regulatory archive; no AQS adapter/records claimed and not used as live AirNow. |
| FEMA NRI/NFHL; USDM/NRCS; terrain; volcano/tsunami | context_sources_discovered_or_fixture_only | ; No new mapped background raster/soil/coastal issuance histories. NRI is long-term background, not a current event. Synthetic drought/tsunami contexts do not establish collection. |
| DOT/511 / evacuation / local emergency notices | needs_jurisdiction_feed | ; No universal or authenticated regional API acquired. Reviewed-notice contracts and fixtures only; no scraping/auth bypass. |
| Human reports / utility telemetry | needs_teammate_feed_fixture_contract_tested | ; Server-owned issuer/role/time/site review gates; no actual reports, sensor measurements, identities or production writes collected. |

## Availability, access and attribution

- NWS/USGS/SWPC products were publicly accessible without credentials. Public availability is not operational validation. Retain agency attribution and source/product terms; no separate redistribution clearance is claimed.
- The local collection cap is one request per second per host, 15-second timeout and two attempts. This is our ceiling, not a claim about a provider's quota. Cache receipts preserve request URL, byte count, SHA-256 and capture time; no inference network request is allowed.
- [NWS API documentation](https://www.weather.gov/documentation/services-web-api) supplies CAP/API semantics. No-polygon alerts need a checked original point-filter request tied to this site, or remain unmatched. An excluding polygon/hole takes precedence. Captures older than one hour are marked stale by a research freshness policy, not an employer safety threshold.
- [USGS migration notice](https://waterdata.usgs.gov/blog/api-waterservices-decom/) and [modern API documentation](https://api.waterdata.usgs.gov/docs/ogcapi/) were checked. New code uses v1; no request fallback to retiring WaterServices is added. Existing cached historical probes remain provenance-preserved. Source retrieval, revision and original observation times are distinct.
- [AirNow rate/access guidance](https://docs.airnowapi.org/faq) and [FIRMS access](https://firms.modaps.eosdis.nasa.gov/api/) require provider credentials/limits for the relevant APIs. No credentials were requested or extracted from the workspace. [AQS](https://www.epa.gov/aqs) is a separate archive.
- [USGS ShakeMap format](https://ghsc.code-pages.usgs.gov/esi/shakemap/docs2020/manual4_0/ug_products.html): UTC grid generation, version, original grid-node coordinates/spacing and nearest-cell method are retained. The acquired grid is an automatic model product, not local equipment inspection or a measured injury outcome. No uncertainty grid was acquired.
- [FEMA NRI](https://www.fema.gov/sites/default/files/documents/fema_national-risk-index_technical-documentation.pdf), [NFHL](https://www.fema.gov/flood-maps/national-flood-hazard-layer), [USDM](https://droughtmonitor.unl.edu/Data.aspx) and [NRCS](https://www.nrcs.usda.gov/resources/data-and-reports/web-soil-survey) remain context/discovery pointers, not newly collected site forecasts.

Exact receipts and failure states: [source_inventory.json](reports/hazard_coverage/source_inventory.json). Normalized fixture hashes: [manifest.json](fixtures/hazard_coverage/manifest.json). Full hazard sign-off: [HAZARD_COVERAGE_AUDIT.md](HAZARD_COVERAGE_AUDIT.md).
