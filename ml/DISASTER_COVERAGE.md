# Disaster evidence coverage

Verified from the five pinned 2021–2025 NOAA archives and bounded official-source snapshots. All source versions, receipt URLs/hashes/times, access requirements and readiness stages are in [source_catalog.json](source_catalog.json). Taxonomy version: `raw-NOAA-2021-2025-v1`.

The cached archives contain **349,030 records / 54 verbatim event types**. The often cited 48-type expectation is not imposed on these actual archives; marine/newer labels are retained. Missing types such as Freezing Rain are not fabricated. This census is not training or model validation.

## NOAA families

| Inventory family | Real rows | Distinct reporting episode IDs within family |
|---|---:|---:|
| coastal_ocean | 3,179 | 1,131 |
| drought_soil | 23,527 | 2,918 |
| heat | 24,047 | 2,011 |
| inland_water_rain | 37,978 | 8,347 |
| marine_weather | 12,765 | 3,326 |
| terrain_ground | 1,065 | 592 |
| tropical_cyclone | 1,873 | 258 |
| visibility_air_quality | 4,078 | 1,114 |
| volcanic | 8 | 4 |
| wildfire | 1,756 | 1,364 |
| wind_convective | 178,233 | 26,350 |
| winter_cold_ice | 60,521 | 8,534 |

Episode IDs are reporting groups, not verified independent meteorological disasters. IDs can occur across families; do not sum groups across rows or providers. Statistical independence remains unknown. Per-type missing episode IDs, coordinate gaps, invalid rows, state/year coverage and instantaneous reports are in [noaa_census.json](reports/worker_outlook/noaa_census.json).

## Original event types and model maturity

| Verbatim NOAA type | Real rows | Reporting groups | Model state |
|---|---:|---:|---|
| Astronomical Low Tide | 145 | 77 | inventory_only |
| Avalanche | 175 | 150 | inventory_only |
| Blizzard | 2,440 | 496 | inventory_only |
| Coastal Flood | 1,279 | 417 | inventory_only |
| Cold/Wind Chill | 3,647 | 457 | inventory_only |
| Debris Flow | 890 | 445 | inventory_only |
| Dense Fog | 3,103 | 682 | inventory_only |
| Dense Smoke | 49 | 6 | inventory_only |
| Drought | 23,527 | 2,918 | inventory_only |
| Dust Devil | 22 | 22 | inventory_only |
| Dust Storm | 841 | 382 | inventory_only |
| Excessive Heat | 11,409 | 1,088 | ingestion_only |
| Extreme Cold/Wind Chill | 5,677 | 493 | inventory_only |
| Flash Flood | 21,573 | 5,581 | evaluated_research |
| Flood | 11,571 | 3,306 | preserved_research_default |
| Freezing Fog | 63 | 28 | inventory_only |
| Frost/Freeze | 2,206 | 430 | inventory_only |
| Funnel Cloud | 1,063 | 755 | inventory_only |
| Hail | 43,359 | 8,997 | inventory_only |
| Heat | 12,638 | 1,213 | ingestion_only |
| Heavy Rain | 4,834 | 1,181 | evaluated_research |
| Heavy Snow | 11,108 | 2,326 | trained_not_qualified |
| High Surf | 1,007 | 177 | inventory_only |
| High Wind | 21,866 | 4,858 | evaluated_research |
| Hurricane (Typhoon) | 154 | 23 | ingestion_only |
| Ice Storm | 1,188 | 222 | trained_not_qualified |
| Lake-Effect Snow | 452 | 153 | inventory_only |
| Lakeshore Flood | 26 | 11 | inventory_only |
| Lightning | 1,246 | 1,031 | inventory_only |
| Marine Dense Fog | 12 | 12 | inventory_only |
| Marine Hail | 129 | 86 | inventory_only |
| Marine High Wind | 381 | 177 | inventory_only |
| Marine Hurricane/Typhoon | 32 | 11 | inventory_only |
| Marine Lightning | 1 | 1 | inventory_only |
| Marine Strong Wind | 18 | 14 | inventory_only |
| Marine Thunderstorm Wind | 12,224 | 3,102 | inventory_only |
| Marine Tropical Depression | 16 | 8 | inventory_only |
| Marine Tropical Storm | 280 | 79 | inventory_only |
| Rip Current | 457 | 387 | inventory_only |
| Seiche | 7 | 4 | inventory_only |
| Sleet | 124 | 19 | inventory_only |
| Sneakerwave | 43 | 28 | inventory_only |
| Storm Surge/Tide | 196 | 54 | inventory_only |
| Strong Wind | 5,457 | 1,291 | trained_not_qualified |
| Thunderstorm Wind | 96,112 | 15,736 | ingestion_only |
| Tornado | 8,179 | 2,775 | inventory_only |
| Tropical Depression | 105 | 28 | ingestion_only |
| Tropical Storm | 1,286 | 160 | ingestion_only |
| Tsunami | 19 | 11 | inventory_only |
| Volcanic Ashfall | 8 | 4 | inventory_only |
| Waterspout | 951 | 726 | inventory_only |
| Wildfire | 1,756 | 1,364 | ingestion_only |
| Winter Storm | 14,119 | 2,288 | evaluated_research |
| Winter Weather | 19,560 | 3,906 | inventory_only |

Only existing Flood, Flash Flood, High Wind, Heavy Rain and Winter Storm duration research is dispatched. Station Heat Index Exceedance is a different observed target, not an alias for NOAA Heat/Excessive Heat. Strong Wind, Ice Storm and Heavy Snow remain disabled after their previous gates failed. Hurricane wind-change is offline post-analysis research, with no live dispatch. None is operationally eligible.

## Specialized sources

Counts below describe downloaded records, not a complete national inventory. `unknown` means not acquired/not established, not zero events. Only two site weather snapshots are associated with the demo; other probes do not establish site exposure.

| Source | Retrieved records | Source groups (independence unproven) | Stage | Access / main gap |
|---|---:|---:|---|---|
| [NHC Atlantic tracks/advisories](https://www.nhc.noaa.gov/data/) | 13,836 | 459 | real data retrieved | Post-analysis tracks; issued advisories are a small probe, not an operational training cohort. |
| [Observed station heat/wind](https://www.ncei.noaa.gov/products/land-based-station/integrated-surface-database) | 122,270 | 416 | real data retrieved | Rounded station observations; original availability/QC vintages absent. |
| [NIFC historical perimeters](https://data-nifc.opendata.arcgis.com/) | 191 | 177 | real data retrieved | 191 perimeter attribute records (geometry not retrieved) do not reconstruct containment or as-of progression. |
| [USGS gauge feasibility](https://api.waterdata.usgs.gov/docs/ogcapi/) | 97 | unknown | real data retrieved | Gauge datum/basin/site transfer not validated. |
| [NWS captured environmental evidence](https://www.weather.gov/documentation/services-web-API) | 316 | unknown | real data retrieved | Descriptive evidence only; no learned site probability or original historical vintage reconstructed. |
| [COOPS captured environmental evidence](https://api.tidesandcurrents.noaa.gov/api/prod/) | 1,439 | unknown | real data retrieved | Descriptive evidence only; no learned site probability or original historical vintage reconstructed. |
| [USGS_earthquakes captured environmental evidence](https://earthquake.usgs.gov/fdsnws/event/1/) | 20 | unknown | real data retrieved | Descriptive evidence only; no learned site probability or original historical vintage reconstructed. |
| [SWPC captured environmental evidence](https://www.swpc.noaa.gov/products/planetary-k-index) | 57 | unknown | real data retrieved | Descriptive evidence only; no learned site probability or original historical vintage reconstructed. |
| [NDBC captured environmental evidence](https://www.ndbc.noaa.gov/measdes.shtml) | 6,390 | unknown | real data retrieved | Descriptive evidence only; no learned site probability or original historical vintage reconstructed. |
| [EIA-860M representative location metadata](https://www.eia.gov/electricity/data/eia860m/) | 28,379 | 14,700 | real data retrieved | 50 validated locations exported for the research harness; no backend database import or active-worksite verification. |
| [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/) | unknown | unknown | fixture tested, not retrieved | Thermal anomalies are not containment or a complete fire perimeter. |
| [EPA AirNow reporting-area API](https://docs.airnowapi.org/) | unknown | unknown | fixture tested, not retrieved | Fixture-tested parser only; preliminary reporting-area data do not establish on-site exposure. |
| [EPA AQS regulatory archive](https://www.epa.gov/aqs) | unknown | unknown | identified only | Identified only: no AQS records retrieved or adapter tested; regulatory observations do not establish site exposure. |
| [NWPS river forecasts](https://water.noaa.gov/) | unknown | unknown | identified only | Flood stage is gauge/datum specific; no automatic site inundation mapping. |
| [USGS landslide inventories](https://www.usgs.gov/programs/landslide-hazards) | unknown | unknown | identified only | Susceptibility/occurrence inventories lack validated local future labels in this package. |
| [NOAA tsunami history/warnings](https://www.ncei.noaa.gov/products/natural-hazards/tsunamis-earthquakes-volcanoes/tsunamis) | unknown | unknown | identified only | Historical occurrence is not an issued site warning or evacuation forecast. |
| [USGS volcano alerts](https://volcanoes.usgs.gov/vsc/api/) | unknown | unknown | identified only | No volcanic unrest or ash exposure model. |
| [Drought / soil moisture / flood terrain context](https://www.drought.gov/) | unknown | unknown | identified only | No parcel ground stability, saturated soil, flood depth or FEMA map forecast inferred. |
| [Confirmed crew infrastructure reports](https://github.com/BraydinPG/planit-control-swamphacks) | unknown | unknown | identified only | Weather cannot identify energized water, broken poles, wildlife, chemicals or access condition. |

NWS counts include two point metadata records, two station observation records and 312 hourly forecast periods. First 25 periods/site were normalized; four explicit windows and latest local station variables were exported. NDBC includes 6,390 table rows; only its latest three rows were normalized. CO-OPS humidity was unavailable; its error response is receipted but is not a valid measurement. The preliminary coastal water reading has a quality flag and is rejected for site assessment.

The EIA workbook has 28,379 generator rows, 14,700 validated unique plant locations and two invalid/missing location rows; 50 public representative locations are exported. This is a Cache research fixture set, not a completed backend/database import or verified jobsite inventory.

## Availability and scientific limits

- Captured NWS forecasts retain generated/update time, future valid windows, actual retrieval/known-availability time and forecast polygon. They are actual issued products, not newly trained predictions.
- NWS/CO-OPS/USGS/NDBC/SWPC snapshots prove availability at capture, not an earlier historical issue time. Revised catalog values cannot be backdated to event occurrence.
- HURDAT2/NOAA final records and legacy ISD archives remain retrospective; no operational-vintage cohort was created.
- Real environmental demo evidence is paired with explicitly hypothetical confirmed-event contexts. No actual ongoing flood/high-wind event at either plant is asserted. The compound warning and earthquake example are synthetic and labeled.
- Layer B is descriptive evidence only. No learned site target, Brier/PR-AUC, injury likelihood, joint hazard probability, flood depth, containment, ground stability or work clearance is claimed.
- AirNow and FIRMS adapters are fixture-tested, with no authenticated archive collection. NWPS, landslide, soil/terrain, tsunami warning and volcano products remain identified-only dependencies.

Run `python -m ml.disaster_catalog` to intentionally rebuild the census/catalog from verified cached archives. It makes no training/model-selection changes. Run `python -m ml.collect_worker_evidence` only to intentionally reconstruct the pinned snapshot from cache; changed dynamic URLs fail checksum verification rather than silently becoming the same vintage. Offline demos use committed normalized extracts, not live requests.
