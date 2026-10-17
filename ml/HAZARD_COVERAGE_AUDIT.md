# Hazard coverage audit and sign-off

This is an inventory of evidence capabilities and explicit gaps, not a claim that every hazard is predicted or present. The user-requested taxonomy is cross-checked against FEMA's 18 groups, exact NOAA labels and OSHA/NIOSH response references. No compliance or individualized safety advice is generated.

**146 registry hazards; 54 verbatim NOAA labels; 18 FEMA crosswalk groups; zero operationally validated models.** Raw labels and standardized groups remain separate. Counts and receipts for the existing datasets remain in [DISASTER_COVERAGE.md](DISASTER_COVERAGE.md).

## Maturity totals

Stages overlap; sign-off states are exclusive.

```json
{
  "stages": {
    "source_discovered": 146,
    "integrated_tested": 105,
    "historical_data_verified": 38,
    "real_retrieval_verified": 46,
    "site_evidence_supported": 9,
    "research_model_trained": 10,
    "historically_backtested": 10,
    "fixture_only": 64,
    "blocked/unsupported": 3
  },
  "signoff": {
    "context_only": 70,
    "implemented_research_model": 6,
    "implemented_tested_evidence": 6,
    "fixture_only": 6,
    "needs_teammate_feed": 58
  }
}
```

## Family sign-off matrix

| Hazard | Family | State | Evidence / limit |
|---|---|---|---|
| thunderstorm: Thunderstorms | weather | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| thunderstorm_wind: Thunderstorm wind | weather | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| high_wind: High wind and damaging gusts | weather | implemented_research_model | Prior grouped chronological research screen; not operationally validated; Current site-qualified source evidence |
| strong_wind: Strong wind | weather | context_only | Strong Wind failed calibration; dispatch disabled; Current site-qualified source evidence |
| derecho: Derecho | weather | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| microburst: Microburst or downburst | weather | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| lightning: Lightning strikes and restrikes | weather | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| thunder: Thunder | weather | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| hail: Hail | weather | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| tornado: Tornado | weather | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| waterspout: Waterspout | weather | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| funnel_cloud: Funnel cloud | weather | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| tropical_cyclone: Tropical cyclone | weather | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| rapid_intensification: Cyclone rapid intensification | weather | context_only | Evidence normalization only; no independent site probability validation; Historical issued advisory vintages and matched intensity outcomes; HURDAT is post-analysis |
| local_cyclone_wind: Cyclone local wind field | weather | context_only | Evidence normalization only; no independent site probability validation; Issued wind-field/radii/grid coverage, not track center or cone membership |
| heavy_rain: Heavy rainfall | water | implemented_research_model | Prior grouped chronological research screen; not operationally validated; Current site-qualified source evidence |
| flash_flood: Flash flooding | water | implemented_research_model | Prior grouped chronological research screen; not operationally validated; Current site-qualified source evidence |
| flood: River and areal flooding | water | implemented_research_model | Prior grouped chronological research screen; not operationally validated; Current site-qualified source evidence |
| ponding: Ponding and local drainage | water | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| rain_on_snow: Rain on snow | water | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| gauge_stage: River stage | water | context_only | Evidence normalization only; no independent site probability validation; Independently verified gauge/site basin relationship and vertical datum; provisional values need review |
| discharge: River discharge and runoff | water | context_only | Evidence normalization only; no independent site probability validation; Native 00060 discharge collection, units, QC and basin relationship; current sample is stage only |
| dam_levee: Dam or levee concern | water | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| floodplain: Mapped floodplain context | water | context_only | Evidence normalization only; no independent site probability validation; Acquired/vintaged NFHL/FIRM context with site overlay; not live flooding or water depth |
| groundwater: Groundwater condition | water | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| extreme_heat: Excessive heat and heat waves | thermal | implemented_tested_evidence | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| humidity: Humidity | thermal | implemented_tested_evidence | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| heat_index: Heat index | thermal | implemented_research_model | Prior grouped chronological research screen; not operationally validated; Current site-qualified source evidence |
| wet_bulb: Wet-bulb temperature | thermal | context_only | Evidence normalization only; no independent site probability validation; Validated psychrometric implementation and qualified time-matched inputs; not implemented |
| wbgt: Wet-bulb globe temperature | thermal | context_only | Evidence normalization only; no independent site probability validation; Qualified globe/radiant and ambient inputs, validated method; heat index is not WBGT |
| overnight_heat: Overnight heat retention | thermal | context_only | Evidence normalization only; no independent site probability validation; Continuous source-qualified local overnight time window and timezone; sparse readings are insufficient |
| extreme_cold: Extreme cold | winter | implemented_tested_evidence | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| wind_chill: Wind chill | winter | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| freezing_precipitation: Freezing precipitation | winter | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| frost_freeze: Frost and freeze | winter | implemented_tested_evidence | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| snow: Snow and heavy snow | winter | fixture_only | Heavy Snow failed calibration; duration dispatch disabled; Current site-qualified source evidence |
| winter_storm: Winter storm | winter | implemented_research_model | Prior grouped chronological research screen; not operationally validated; Current site-qualified source evidence |
| ice_storm: Ice storm | winter | fixture_only | Ice Storm sparse support/calibration; duration dispatch disabled; Current site-qualified source evidence |
| blizzard: Blizzard | winter | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| lake_effect_snow: Lake-effect snow | winter | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| whiteout: Whiteout | winter | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| freezing_fog: Freezing fog | winter | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| sleet: Sleet | winter | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| drought: Drought | land | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| low_water: Unusually low water | land | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| fire_weather: Elevated fire weather | fire | implemented_tested_evidence | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| red_flag: Red Flag warning | fire | implemented_tested_evidence | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| dust: Dust storm | air | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| blowing_sand: Blowing sand | air | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| fog: Fog and poor visibility | air | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| smoke_visibility: Smoke-obscured visibility | air | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| air_quality: Air-quality context | air | fixture_only | Evidence normalization only; no independent site probability validation; AirNow credentials for timely reporting-area values; AQS separately requires historical acquisition |
| pm25: PM2.5 concentration | air | fixture_only | Evidence normalization only; no independent site probability validation; Source-qualified concentration and averaging interval, location and AirNow/AQS access; AQI is a different quantity |
| ozone: Ozone concentration | air | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| aviation_weather: Aviation and elevated-work weather | weather | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| marine_wind_waves: Marine wind and waves | coastal | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| coastal_flood: Coastal and tidal flooding | coastal | context_only | Evidence normalization only; no independent site probability validation; Station datum and verified coastal association; no transfer from gauge height to site depth |
| storm_surge: Storm surge | coastal | context_only | Evidence normalization only; no independent site probability validation; Actual issued surge/inundation product with vertical reference and coastal site coverage |
| extreme_tide: Extreme tides | coastal | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| surf: High surf | coastal | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| rip_current: Rip-current context | coastal | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| coastal_erosion: Coastal erosion | coastal | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| tsunami: Tsunami notices | coastal | fixture_only | Evidence normalization only; no independent site probability validation; Official issued notice and coastal mapping; event occurrence alone does not imply inundation |
| seiche: Seiche | coastal | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| ice_jam: Ice-jam flooding | water | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| coastal_ice: Coastal ice and freezing spray | coastal | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| landslide: Landslide and mudslide | terrain | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| debris_flow: Debris flow | terrain | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| slope_instability: Slope instability | terrain | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| rockfall: Rockfall | terrain | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| avalanche: Avalanche | terrain | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| subsidence_sinkhole: Subsidence and sinkholes | terrain | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| expansive_soil: Expansive soil | terrain | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| saturated_ground: Saturated or soft ground | terrain | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| wildfire: Wildfire location and perimeter | fire | fixture_only | Evidence normalization only; no independent site probability validation; FIRMS MAP_KEY/archive authorization and actual perimeter geometry; no new authenticated collection |
| wildfire_growth: Consecutive fire perimeter growth | fire | context_only | Evidence normalization only; no independent site probability validation; Consecutive time-varying perimeter geometries for the same incident; earlier probe collected attributes only |
| evacuation: Official evacuation context | transport | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Jurisdiction-specific official order, boundary and current validity; no live evacuation feed acquired |
| earthquake: Earthquake event | geologic | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| shaking: ShakeMap shaking estimate | geologic | context_only | Evidence normalization only; no independent site probability validation; Actual grid covering the monitored site; retrieved Pakistan grid covers zero US EIA locations; uncertainty grid not retrieved |
| aftershock: Aftershock observations or outlook | geologic | context_only | Evidence normalization only; no independent site probability validation; An actual issued aftershock product or observations; no independently validated local forecast here |
| liquefaction: Liquefaction context | geologic | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| volcanic_eruption: Volcanic eruption | geologic | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| volcanic_ash: Volcanic ash | geologic | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| volcanic_gas: Volcanic gas | geologic | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| geomagnetic_storm: Geomagnetic storm context | space | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| downed_lines: Energized, downed or low-hanging lines | electrical | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| arc_flash: Arc-flash exposure | electrical | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| backfeed: Electrical backfeed | electrical | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| induction: Electrical induction | electrical | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| step_touch: Step and touch potential | electrical | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| ground_fault: Ground fault | electrical | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| energized_floodwater: Potentially energized floodwater | electrical | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| flooded_electrical_equipment: Flooded electrical equipment | electrical | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| equipment_damage: Substation or equipment damage | asset | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| electrical_fire: Transformer or electrical fire | asset | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| pole_tower_instability: Unstable poles or towers | asset | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| fallen_trees: Fallen trees or limbs | asset | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| wind_loaded_lines: Wind-loaded lines | asset | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| clearance_restrictions: Electrical clearance restrictions | asset | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| fuel_gas_leak: Fuel or gas leak | chemical | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| carbon_monoxide: Generator carbon monoxide | chemical | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| chemical_release: Chemical release | chemical | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| spills: Spill | chemical | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| industrial_smoke: Industrial smoke | chemical | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| asbestos: Asbestos exposure context | chemical | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| silica: Silica exposure context | chemical | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| mold: Mold exposure context | biological | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| hazardous_dust: Hazardous dust | chemical | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| contaminated_water: Contaminated water or sewage | biological | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| oxygen_deficiency: Oxygen-deficient atmosphere | chemical | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| confined_space: Confined-space atmosphere | chemical | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| structural_collapse: Structural collapse | structural | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| roof_instability: Unstable roof | structural | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| debris: Broken glass and debris | structural | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| excavation_collapse: Unstable excavation or trench | structural | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| utility_strike: Underground utility strike | structural | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| slips_trips_falls: Slips, trips and falls | occupational | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| road_closure: Road closure or inaccessible route | transport | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Jurisdiction-specific authoritative DOT/511 feed or trusted reviewed report; no universal authenticated API verified |
| bridge_washout: Washed-out bridge or unstable access | transport | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| blocked_egress: Debris-blocked egress | transport | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| traffic: Traffic and moving vehicles | transport | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| restoration_driving: Storm-restoration driving | transport | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| lift_crane: Aerial lift or crane exposure | motion | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| falling_loads: Falling loads | motion | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| heat_illness: Worker heat-exposure context | occupational | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| cold_exposure: Worker cold-exposure context | occupational | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| dehydration: Dehydration context | occupational | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| fatigue: Fatigue and extended shifts | occupational | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| ergonomic: Environmental ergonomic exposure | occupational | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| visibility_impairment: Worker visibility impairment | occupational | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| wildlife: Wildlife encounter | biological | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| bites_stings: Bites or stings | biological | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| infectious_exposure: Infectious or biological exposure | biological | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| communications: Communications degradation | operations | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| gps_interference: GPS interference | operations | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| connectivity: Connectivity loss | operations | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| power_failure: Power failure | operations | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| dispatch_emergency: Dispatch or emergency access interruption | operations | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| urban_fire_transition: Wildland/urban interface fire transition | cascade | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| postfire_debris_flow: Post-fire flooding or debris flow | cascade | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| compound_cyclone: Cyclone wind-rain-flood cascade | cascade | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| quake_tsunami_landslide: Earthquake-tsunami-landslide cascade | cascade | context_only | Evidence normalization only; no independent site probability validation; Current site-qualified source evidence |
| security: Security or public safety notice | official_context | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| transport_incident: Major transportation incident | official_context | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| hazmat_incident: Hazardous-material emergency | official_context | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |
| radiological: Radiological notice | official_context | needs_teammate_feed | Evidence normalization only; no independent site probability validation; Authenticated human/asset feed and qualified field verification |

## Sources and cross-checks

- [noaa](https://www.ncei.noaa.gov/stormevents/)
- [nws](https://www.weather.gov/documentation/services-web-api)
- [nhc](https://www.nhc.noaa.gov/data/)
- [water](https://api.waterdata.usgs.gov/docs/ogcapi/)
- [water_migration](https://waterdata.usgs.gov/blog/api-waterservices-decom/)
- [coops](https://api.tidesandcurrents.noaa.gov/api/prod/)
- [ndbc](https://www.ndbc.noaa.gov/measdes.shtml)
- [firms](https://firms.modaps.eosdis.nasa.gov/api/)
- [nifc](https://data-nifc.opendata.arcgis.com/)
- [airnow](https://docs.airnowapi.org/faq)
- [aqs](https://www.epa.gov/aqs)
- [quake](https://earthquake.usgs.gov/data/shakemap/)
- [terrain](https://www.usgs.gov/programs/landslide-hazards)
- [tsunami](https://www.tsunami.gov/)
- [volcano](https://volcanoes.usgs.gov/vsc/api/)
- [swpc](https://www.swpc.noaa.gov/products/alerts-watches-and-warnings)
- [fema](https://www.fema.gov/sites/default/files/documents/fema_national-risk-index_technical-documentation.pdf)
- [floodplain](https://www.fema.gov/flood-maps/national-flood-hazard-layer)
- [drought](https://droughtmonitor.unl.edu/Data.aspx)
- [soil](https://www.nrcs.usda.gov/resources/data-and-reports/web-soil-survey)
- [dot](https://fl511.com/)
- [osha_power](https://www.osha.gov/laws-regs/regulations/standardnumber/1910/1910.269)
- [osha_construction](https://www.osha.gov/laws-regs/regulations/standardnumber/1926/1926.950)
- [osha_response](https://www.osha.gov/etools/hurricane)
- [niosh](https://www.cdc.gov/niosh/emres/safety/index.html)

## Interpretation and unresolved inputs

Every manual/asset hazard defaults to unknown, even during an active disaster. Weather never confirms energized water, equipment failure, electrical isolation, structural condition, hazardous atmospheres, wildlife, route availability or an outage. A reviewed absence report is a timestamped statement, not clearance. Employer procedures and qualified inspection remain separate.

A CAP alert with no usable polygon remains regional/unmatched. Empty successful retrieval means only no notices in that response; failure/staleness is distinct. Cancellation/expiration changes source-product currency, never deterministic alert state. Site probability and severity remain null. Generic registry references establish taxonomy/discovery, not source collection or a model.

No new model training, held-out target selection or outcome accuracy claim is part of this push. Existing per-category evaluations remain in [MULTIDISASTER.md](MULTIDISASTER.md) and [EVALUATION.md](EVALUATION.md).

Source additions, retrieval failures, actual record windows and migration notes are in [SOURCE_INVENTORY_DIFF.md](SOURCE_INVENTORY_DIFF.md). Full per-hazard sources, match rules, missing inputs, fallback and owner are machine-readable in [hazard_registry.json](hazard_registry.json).
