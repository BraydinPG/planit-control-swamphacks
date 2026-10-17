"""Curated hazard taxonomy and capability audit; never a predictive dispatch table."""

from collections import Counter
from functools import lru_cache
import json
from pathlib import Path
from typing import Literal
from pydantic import Field

from ml.worker.schema import Contract

ROOT = Path(__file__).resolve().parent
REGISTRY_PATH = ROOT / "hazard_registry.json"
SOURCES = {
    "noaa": "https://www.ncei.noaa.gov/stormevents/",
    "nws": "https://www.weather.gov/documentation/services-web-api",
    "nhc": "https://www.nhc.noaa.gov/data/",
    "water": "https://api.waterdata.usgs.gov/docs/ogcapi/",
    "water_migration": "https://waterdata.usgs.gov/blog/api-waterservices-decom/",
    "coops": "https://api.tidesandcurrents.noaa.gov/api/prod/",
    "ndbc": "https://www.ndbc.noaa.gov/measdes.shtml",
    "firms": "https://firms.modaps.eosdis.nasa.gov/api/",
    "nifc": "https://data-nifc.opendata.arcgis.com/",
    "airnow": "https://docs.airnowapi.org/faq",
    "aqs": "https://www.epa.gov/aqs",
    "quake": "https://earthquake.usgs.gov/data/shakemap/",
    "terrain": "https://www.usgs.gov/programs/landslide-hazards",
    "tsunami": "https://www.tsunami.gov/",
    "volcano": "https://volcanoes.usgs.gov/vsc/api/",
    "swpc": "https://www.swpc.noaa.gov/products/alerts-watches-and-warnings",
    "fema": "https://www.fema.gov/sites/default/files/documents/fema_national-risk-index_technical-documentation.pdf",
    "floodplain": "https://www.fema.gov/flood-maps/national-flood-hazard-layer",
    "drought": "https://droughtmonitor.unl.edu/Data.aspx",
    "soil": "https://www.nrcs.usda.gov/resources/data-and-reports/web-soil-survey",
    "dot": "https://fl511.com/",
    "osha_power": "https://www.osha.gov/laws-regs/regulations/standardnumber/1910/1910.269",
    "osha_construction": "https://www.osha.gov/laws-regs/regulations/standardnumber/1926/1926.950",
    "osha_response": "https://www.osha.gov/etools/hurricane",
    "niosh": "https://www.cdc.gov/niosh/emres/safety/index.html",
}

# User-requested taxonomy, cross-checked against the official references above.
# Labels are capability questions, not diagnoses, inspection results or predictions.
DEFINITIONS = """
thunderstorm|weather|Thunderstorms|ordinary thunderstorms;severe thunderstorms
thunderstorm_wind|weather|Thunderstorm wind|convective wind
high_wind|weather|High wind and damaging gusts|gusts;wind storm
strong_wind|weather|Strong wind|straight-line wind
derecho|weather|Derecho|widespread convective wind
microburst|weather|Microburst or downburst|downburst
lightning|weather|Lightning strikes and restrikes|strike proximity;lightning-feed outage
thunder|weather|Thunder|audible thunder
hail|weather|Hail|large hail
tornado|weather|Tornado|tornadic circulation
waterspout|weather|Waterspout|tornadic waterspout
funnel_cloud|weather|Funnel cloud|funnel
tropical_cyclone|weather|Tropical cyclone|hurricane;typhoon;tropical storm;tropical depression;extratropical cyclone;post-tropical cyclone;rainbands
rapid_intensification|weather|Cyclone rapid intensification|intensity change
local_cyclone_wind|weather|Cyclone local wind field|wind radii;local wind-field effects
heavy_rain|water|Heavy rainfall|heavy rain;prolonged rain
flash_flood|water|Flash flooding|flash flood
flood|water|River and areal flooding|river flood;urban flooding;areal flood
ponding|water|Ponding and local drainage|standing water;drainage failure
rain_on_snow|water|Rain on snow|snowmelt runoff
gauge_stage|water|River stage|gauge height;gage height
discharge|water|River discharge and runoff|streamflow;runoff
dam_levee|water|Dam or levee concern|dam failure;levee breach
floodplain|water|Mapped floodplain context|FIRM;NFHL
groundwater|water|Groundwater condition|groundwater flooding
extreme_heat|thermal|Excessive heat and heat waves|heat wave;excessive heat
humidity|thermal|Humidity|relative humidity
heat_index|thermal|Heat index|apparent temperature
wet_bulb|thermal|Wet-bulb temperature|psychrometric wet bulb
wbgt|thermal|Wet-bulb globe temperature|WBGT
overnight_heat|thermal|Overnight heat retention|warm overnight minimum
extreme_cold|winter|Extreme cold|cold wave;extreme cold/wind chill;cold/wind chill
wind_chill|winter|Wind chill|apparent cold
freezing_precipitation|winter|Freezing precipitation|freezing rain;freezing drizzle
frost_freeze|winter|Frost and freeze|frost/freeze
snow|winter|Snow and heavy snow|heavy snow
winter_storm|winter|Winter storm|winter weather
ice_storm|winter|Ice storm|glaze ice
blizzard|winter|Blizzard|snowstorm
lake_effect_snow|winter|Lake-effect snow|lake effect snow
whiteout|winter|Whiteout|blowing snow
freezing_fog|winter|Freezing fog|ice fog
sleet|winter|Sleet|ice pellets
drought|land|Drought|soil dryness
low_water|land|Unusually low water|low water
fire_weather|fire|Elevated fire weather|dry vegetation;fire-weather conditions
red_flag|fire|Red Flag warning|critical fire weather
dust|air|Dust storm|dust devil
blowing_sand|air|Blowing sand|blowing dust
fog|air|Fog and poor visibility|dense fog
smoke_visibility|air|Smoke-obscured visibility|smoke haze;dense smoke
air_quality|air|Air-quality context|AQI;poor air quality
pm25|air|PM2.5 concentration|wildfire smoke;fine particles
ozone|air|Ozone concentration|ground-level ozone
aviation_weather|weather|Aviation and elevated-work weather|aerial work;aviation hazards
marine_wind_waves|coastal|Marine wind and waves|high seas;marine thunderstorm wind;marine hail;marine high wind;marine strong wind
coastal_flood|coastal|Coastal and tidal flooding|coastal flood;tidal flooding
storm_surge|coastal|Storm surge|storm surge/tide
extreme_tide|coastal|Extreme tides|astronomical low tide;king tide
surf|coastal|High surf|sneakerwave
rip_current|coastal|Rip-current context|rip current
coastal_erosion|coastal|Coastal erosion|shoreline erosion
tsunami|coastal|Tsunami notices|tsunami watch;tsunami warning
seiche|coastal|Seiche|standing wave
ice_jam|water|Ice-jam flooding|ice jam
coastal_ice|coastal|Coastal ice and freezing spray|heavy freezing spray
landslide|terrain|Landslide and mudslide|mudslide;landslump
debris_flow|terrain|Debris flow|mud flow
slope_instability|terrain|Slope instability|unstable slope
rockfall|terrain|Rockfall|falling rock
avalanche|terrain|Avalanche|snow avalanche
subsidence_sinkhole|terrain|Subsidence and sinkholes|sinkhole;subsidence
expansive_soil|terrain|Expansive soil|soil expansion
saturated_ground|terrain|Saturated or soft ground|unstable embankment;soft soil
wildfire|fire|Wildfire location and perimeter|wildland fire;hotspot;thermal detection
wildfire_growth|fire|Consecutive fire perimeter growth|fire spread;containment
evacuation|transport|Official evacuation context|evacuation zone;evacuation order
earthquake|geologic|Earthquake event|seismic event
shaking|geologic|ShakeMap shaking estimate|MMI;ground shaking
aftershock|geologic|Aftershock observations or outlook|aftershocks
liquefaction|geologic|Liquefaction context|ground failure
volcanic_eruption|geologic|Volcanic eruption|volcanic activity
volcanic_ash|geologic|Volcanic ash|ashfall;volcanic ashfall
volcanic_gas|geologic|Volcanic gas|volcanic aviation effects
geomagnetic_storm|space|Geomagnetic storm context|Kp;space weather;solar storm
downed_lines|electrical|Energized, downed or low-hanging lines|downed wires;electrocution
arc_flash|electrical|Arc-flash exposure|arc blast
backfeed|electrical|Electrical backfeed|generator backfeed
induction|electrical|Electrical induction|induced voltage
step_touch|electrical|Step and touch potential|step potential;touch potential
ground_fault|electrical|Ground fault|fault current
energized_floodwater|electrical|Potentially energized floodwater|electrified water
flooded_electrical_equipment|electrical|Flooded electrical equipment|submerged electrical equipment
equipment_damage|asset|Substation or equipment damage|damaged transformer
electrical_fire|asset|Transformer or electrical fire|blown transformer
pole_tower_instability|asset|Unstable poles or towers|broken pole;damaged tower
fallen_trees|asset|Fallen trees or limbs|tree damage;falling branches
wind_loaded_lines|asset|Wind-loaded lines|line loading
clearance_restrictions|asset|Electrical clearance restrictions|approach restrictions
fuel_gas_leak|chemical|Fuel or gas leak|natural gas leak
carbon_monoxide|chemical|Generator carbon monoxide|CO exposure
chemical_release|chemical|Chemical release|industrial chemicals
spills|chemical|Spill|fuel spill;chemical spill
industrial_smoke|chemical|Industrial smoke|combustion products
asbestos|chemical|Asbestos exposure context|asbestos debris
silica|chemical|Silica exposure context|respirable crystalline silica
mold|biological|Mold exposure context|post-flood mold
hazardous_dust|chemical|Hazardous dust|toxic dust
contaminated_water|biological|Contaminated water or sewage|sewage;contaminated floodwater
oxygen_deficiency|chemical|Oxygen-deficient atmosphere|low oxygen
confined_space|chemical|Confined-space atmosphere|hazardous atmosphere
structural_collapse|structural|Structural collapse|unstable building
roof_instability|structural|Unstable roof|roof collapse
debris|structural|Broken glass and debris|sharp debris
excavation_collapse|structural|Unstable excavation or trench|trench collapse
utility_strike|structural|Underground utility strike|buried utility
slips_trips_falls|occupational|Slips, trips and falls|unstable access way
road_closure|transport|Road closure or inaccessible route|road inaccessibility;road washout
bridge_washout|transport|Washed-out bridge or unstable access|bridge damage
blocked_egress|transport|Debris-blocked egress|blocked escape route
traffic|transport|Traffic and moving vehicles|vehicle movement
restoration_driving|transport|Storm-restoration driving|driving conditions
lift_crane|motion|Aerial lift or crane exposure|elevated work;crane operations
falling_loads|motion|Falling loads|suspended load
heat_illness|occupational|Worker heat-exposure context|heat illness
cold_exposure|occupational|Worker cold-exposure context|hypothermia;frostbite
dehydration|occupational|Dehydration context|fluid loss
fatigue|occupational|Fatigue and extended shifts|extended shifts
ergonomic|occupational|Environmental ergonomic exposure|manual handling
visibility_impairment|occupational|Worker visibility impairment|impaired visibility
wildlife|biological|Wildlife encounter|alligator;snake;insect;animal hazard
bites_stings|biological|Bites or stings|animal bite;insect sting
infectious_exposure|biological|Infectious or biological exposure|infectious disease
communications|operations|Communications degradation|radio degradation
gps_interference|operations|GPS interference|GNSS disruption
connectivity|operations|Connectivity loss|network outage
power_failure|operations|Power failure|outage
dispatch_emergency|operations|Dispatch or emergency access interruption|emergency response interruption
urban_fire_transition|cascade|Wildland/urban interface fire transition|WUI fire
postfire_debris_flow|cascade|Post-fire flooding or debris flow|burn scar
compound_cyclone|cascade|Cyclone wind-rain-flood cascade|compound hurricane hazards
quake_tsunami_landslide|cascade|Earthquake-tsunami-landslide cascade|cascading seismic hazards
security|official_context|Security or public safety notice|public safety event
transport_incident|official_context|Major transportation incident|rail incident
hazmat_incident|official_context|Hazardous-material emergency|hazmat emergency
radiological|official_context|Radiological notice|radiological alert
"""

MANUAL_FAMILIES = {
    "electrical",
    "asset",
    "chemical",
    "biological",
    "structural",
    "transport",
    "motion",
    "occupational",
    "operations",
    "official_context",
}
FAMILY_SOURCES = {
    "weather": ["noaa", "nws", "nhc"],
    "water": ["noaa", "nws", "water", "floodplain"],
    "thermal": ["noaa", "nws", "niosh"],
    "winter": ["noaa", "nws", "dot"],
    "land": ["noaa", "drought", "soil"],
    "air": ["nws", "airnow", "aqs"],
    "coastal": ["noaa", "coops", "ndbc", "tsunami"],
    "terrain": ["terrain", "soil", "noaa"],
    "fire": ["nifc", "firms", "nws"],
    "geologic": ["quake", "volcano"],
    "space": ["swpc"],
    "cascade": ["nws", "terrain", "quake", "niosh"],
}
MODEL_TARGETS = {
    "flood": "Flood",
    "flash_flood": "Flash Flood",
    "high_wind": "High Wind",
    "heavy_rain": "Heavy Rain",
    "winter_storm": "Winter Storm",
    "heat_index": "Heat Index Exceedance",
}
SITE_VARIABLES = {
    "high_wind": ["wind_speed", "wind_gust", "wind_speed_min", "wind_speed_max"],
    "heavy_rain": ["rainfall", "rain_probability"],
    "extreme_heat": ["temperature"],
    "humidity": ["relative_humidity"],
    "heat_index": ["heat_index"],
    "gauge_stage": ["gauge_height"],
    "coastal_flood": ["coastal_water_level"],
    "marine_wind_waves": ["wave_height"],
    "fog": ["visibility"],
    "air_quality": ["air_quality_index"],
    "pm25": ["pm25"],
    "wildfire": ["thermal_detection"],
    "earthquake": ["earthquake_magnitude"],
    "geomagnetic_storm": ["geomagnetic_kp"],
    "snow": ["snow_depth"],
    "ice_storm": ["ice_accretion"],
}
EVENT_CHECKS = {
    "Flood": [
        "flood",
        "gauge_stage",
        "heavy_rain",
        "road_closure",
        "energized_floodwater",
        "contaminated_water",
        "saturated_ground",
    ],
    "Flash Flood": [
        "flash_flood",
        "heavy_rain",
        "road_closure",
        "bridge_washout",
        "energized_floodwater",
    ],
    "High Wind": [
        "high_wind",
        "downed_lines",
        "pole_tower_instability",
        "fallen_trees",
        "lift_crane",
    ],
    "Heavy Rain": ["heavy_rain", "ponding", "saturated_ground", "road_closure"],
    "Winter Storm": [
        "winter_storm",
        "snow",
        "ice_storm",
        "extreme_cold",
        "wind_chill",
        "road_closure",
        "wind_loaded_lines",
    ],
    "Heat Index Exceedance": [
        "extreme_heat",
        "humidity",
        "heat_index",
        "heat_illness",
        "dehydration",
    ],
    "Hurricane": [
        "tropical_cyclone",
        "local_cyclone_wind",
        "high_wind",
        "heavy_rain",
        "storm_surge",
        "flood",
        "compound_cyclone",
    ],
    "Tropical Storm": [
        "tropical_cyclone",
        "high_wind",
        "heavy_rain",
        "storm_surge",
        "compound_cyclone",
    ],
    "Wildfire": [
        "wildfire",
        "wildfire_growth",
        "pm25",
        "air_quality",
        "evacuation",
        "postfire_debris_flow",
        "urban_fire_transition",
    ],
    "Earthquake": [
        "earthquake",
        "shaking",
        "aftershock",
        "liquefaction",
        "tsunami",
        "structural_collapse",
        "quake_tsunami_landslide",
    ],
    "Lightning": ["lightning", "thunder", "communications"],
    "Geomagnetic Storm": [
        "geomagnetic_storm",
        "gps_interference",
        "communications",
        "power_failure",
    ],
    "Tornado": ["tornado", "debris", "downed_lines", "structural_collapse"],
    "Hail": ["hail", "equipment_damage"],
    "Dust Storm": ["dust", "fog", "visibility_impairment"],
    "Landslide": ["landslide", "slope_instability", "road_closure"],
    "Drought": ["drought", "fire_weather", "expansive_soil"],
    "Storm Surge/Tide": ["storm_surge", "coastal_flood", "extreme_tide"],
}
RAW_MAP = {
    "Astronomical Low Tide": "extreme_tide",
    "Avalanche": "avalanche",
    "Blizzard": "blizzard",
    "Coastal Flood": "coastal_flood",
    "Cold/Wind Chill": "extreme_cold",
    "Debris Flow": "debris_flow",
    "Dense Fog": "fog",
    "Dense Smoke": "smoke_visibility",
    "Drought": "drought",
    "Dust Devil": "dust",
    "Dust Storm": "dust",
    "Excessive Heat": "extreme_heat",
    "Extreme Cold/Wind Chill": "extreme_cold",
    "Flash Flood": "flash_flood",
    "Flood": "flood",
    "Freezing Fog": "freezing_fog",
    "Frost/Freeze": "frost_freeze",
    "Funnel Cloud": "funnel_cloud",
    "Hail": "hail",
    "Heat": "extreme_heat",
    "Heavy Rain": "heavy_rain",
    "Heavy Snow": "snow",
    "High Surf": "surf",
    "High Wind": "high_wind",
    "Hurricane": "tropical_cyclone",
    "Hurricane (Typhoon)": "tropical_cyclone",
    "Ice Storm": "ice_storm",
    "Lake-Effect Snow": "lake_effect_snow",
    "Lakeshore Flood": "flood",
    "Lightning": "lightning",
    "Marine Dense Fog": "fog",
    "Marine Hail": "marine_wind_waves",
    "Marine High Wind": "marine_wind_waves",
    "Marine Hurricane/Typhoon": "tropical_cyclone",
    "Marine Lightning": "lightning",
    "Marine Strong Wind": "marine_wind_waves",
    "Marine Thunderstorm Wind": "marine_wind_waves",
    "Marine Tropical Depression": "tropical_cyclone",
    "Marine Tropical Storm": "tropical_cyclone",
    "Rip Current": "rip_current",
    "Seiche": "seiche",
    "Sleet": "sleet",
    "Sneakerwave": "surf",
    "Storm Surge/Tide": "storm_surge",
    "Strong Wind": "strong_wind",
    "Thunderstorm Wind": "thunderstorm_wind",
    "Tornado": "tornado",
    "Tropical Depression": "tropical_cyclone",
    "Tropical Storm": "tropical_cyclone",
    "Tsunami": "tsunami",
    "Volcanic Ash": "volcanic_ash",
    "Volcanic Ashfall": "volcanic_ash",
    "Waterspout": "waterspout",
    "Wildfire": "wildfire",
    "Winter Storm": "winter_storm",
    "Winter Weather": "winter_storm",
}
FEMA_CROSSWALK = {
    "Avalanche": "avalanche",
    "Coastal Flooding": "coastal_flood",
    "Cold Wave": "extreme_cold",
    "Drought": "drought",
    "Earthquake": "earthquake",
    "Hail": "hail",
    "Heat Wave": "extreme_heat",
    "Hurricane": "tropical_cyclone",
    "Ice Storm": "ice_storm",
    "Inland Flooding": "flood",
    "Landslide": "landslide",
    "Lightning": "lightning",
    "Strong Wind": "strong_wind",
    "Tornado": "tornado",
    "Tsunami": "tsunami",
    "Volcanic Activity": "volcanic_eruption",
    "Wildfire": "wildfire",
    "Winter Weather": "winter_storm",
}


class HazardEntry(Contract):
    id: str
    category: str
    label: str
    synonyms: list[str]
    upstream_causes: list[str]
    cascading_effects: list[str]
    worker_exposure_pathways: list[str]
    official_sources: list[str]
    geographic_time_coverage: str
    collection_auth: str
    adapter_fixture: list[str]
    freshness_vintage_constraints: str
    raw_noaa_types: list[str]
    historical_record_count: int = Field(ge=0)
    event_label_availability: str
    site_match_requirements: str
    model_family: str | None
    eligible_outcomes: list[str]
    validation_status: str
    operational_eligibility: Literal[False] = False
    owner: str
    tests: list[str]
    critical_missing_inputs: list[str]
    fallback: str
    next_action: str
    stages: list[str]
    signoff: Literal[
        "implemented_tested_evidence",
        "implemented_research_model",
        "context_only",
        "fixture_only",
        "needs_teammate_feed",
        "blocked_source",
    ]
    review_question: str


@lru_cache(maxsize=1)
def load_registry() -> dict[str, HazardEntry]:
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if data["schema_version"] != "1.0.0":
        raise ValueError("Unreviewed hazard registry version")
    entries = [HazardEntry.model_validate(item) for item in data["hazards"]]
    if len({entry.id for entry in entries}) != len(entries):
        raise ValueError("Duplicate registry hazard ID")
    return {entry.id: entry for entry in entries}


def build() -> dict:
    census = json.loads((ROOT / "reports/worker_outlook/noaa_census.json").read_text())
    missing = set(census["categories"]) - RAW_MAP.keys()
    if missing:
        raise ValueError(f"Unmapped verbatim NOAA labels: {sorted(missing)}")
    snapshot_path = ROOT / "fixtures/hazard_coverage/source_snapshot.json"
    snapshot = json.loads(snapshot_path.read_text()) if snapshot_path.exists() else {}
    from ml.sources.hazard_feeds import alert_hazards

    retrieved = {
        hid for alert in snapshot.get("alerts", []) for hid in alert_hazards(alert["event"])
    }
    retrieved.update(
        hid
        for e in snapshot.get("evidence", [])
        for hid, variables in SITE_VARIABLES.items()
        if e["variable"] in variables
    )
    if snapshot.get("context_signals"):
        retrieved.add("geomagnetic_storm")
    if (ROOT / "fixtures/hazard_coverage/real_shakemap_probe.json").exists():
        retrieved.add("shaking")
    acceptance_path = ROOT / "reports/hazard_coverage/acceptance.json"
    acceptance = json.loads(acceptance_path.read_text()) if acceptance_path.exists() else {}
    verified_sites = set(acceptance.get("verified_site_hazard_ids", []))
    special_gaps = {
        "gauge_stage": [
            "Independently verified gauge/site basin relationship and vertical datum; provisional values need review"
        ],
        "discharge": [
            "Native 00060 discharge collection, units, QC and basin relationship; current sample is stage only"
        ],
        "coastal_flood": [
            "Station datum and verified coastal association; no transfer from gauge height to site depth"
        ],
        "storm_surge": [
            "Actual issued surge/inundation product with vertical reference and coastal site coverage"
        ],
        "wet_bulb": [
            "Validated psychrometric implementation and qualified time-matched inputs; not implemented"
        ],
        "wbgt": [
            "Qualified globe/radiant and ambient inputs, validated method; heat index is not WBGT"
        ],
        "overnight_heat": [
            "Continuous source-qualified local overnight time window and timezone; sparse readings are insufficient"
        ],
        "rapid_intensification": [
            "Historical issued advisory vintages and matched intensity outcomes; HURDAT is post-analysis"
        ],
        "local_cyclone_wind": [
            "Issued wind-field/radii/grid coverage, not track center or cone membership"
        ],
        "wildfire_growth": [
            "Consecutive time-varying perimeter geometries for the same incident; earlier probe collected attributes only"
        ],
        "wildfire": [
            "FIRMS MAP_KEY/archive authorization and actual perimeter geometry; no new authenticated collection"
        ],
        "air_quality": [
            "AirNow credentials for timely reporting-area values; AQS separately requires historical acquisition"
        ],
        "pm25": [
            "Source-qualified concentration and averaging interval, location and AirNow/AQS access; AQI is a different quantity"
        ],
        "shaking": [
            "Actual grid covering the monitored site; retrieved Pakistan grid covers zero US EIA locations; uncertainty grid not retrieved"
        ],
        "aftershock": [
            "An actual issued aftershock product or observations; no independently validated local forecast here"
        ],
        "tsunami": [
            "Official issued notice and coastal mapping; event occurrence alone does not imply inundation"
        ],
        "road_closure": [
            "Jurisdiction-specific authoritative DOT/511 feed or trusted reviewed report; no universal authenticated API verified"
        ],
        "evacuation": [
            "Jurisdiction-specific official order, boundary and current validity; no live evacuation feed acquired"
        ],
        "floodplain": [
            "Acquired/vintaged NFHL/FIRM context with site overlay; not live flooding or water depth"
        ],
    }
    hazards = []
    for line in DEFINITIONS.strip().splitlines():
        hid, category, label, synonyms = line.split("|")
        manual = category in MANUAL_FAMILIES
        raw = sorted(
            name
            for name, target in RAW_MAP.items()
            if target == hid and name in census["categories"]
        )
        trained = hid in MODEL_TARGETS
        supported = hid in verified_sites
        fixture = hid in {
            "air_quality",
            "pm25",
            "wildfire",
            "road_closure",
            "evacuation",
            "tsunami",
            "snow",
            "ice_storm",
        }
        sources = FAMILY_SOURCES.get(
            category, ["osha_power", "osha_construction", "osha_response", "niosh"]
        )
        stages = ["source_discovered"]
        if raw:
            stages.append("historical_data_verified")
        if raw or hid in retrieved:
            stages.append("real_retrieval_verified")
        if supported:
            stages += ["site_evidence_supported"]
        if fixture or manual:
            stages.append("fixture_only")
        if trained:
            stages += ["research_model_trained", "historically_backtested"]
        if hid in {"strong_wind", "snow", "ice_storm", "tropical_cyclone"}:
            stages += ["research_model_trained", "historically_backtested"]
        if hid in {"air_quality", "pm25", "wildfire"}:
            stages.append("blocked/unsupported")
        if hid in acceptance.get("offline_tested_hazard_ids", []):
            stages.append("integrated_tested")
        signoff = (
            "implemented_research_model"
            if trained
            else "implemented_tested_evidence"
            if supported
            else "needs_teammate_feed"
            if manual
            else "fixture_only"
            if fixture
            else "context_only"
        )
        disabled = {
            "strong_wind": "Strong Wind failed calibration; dispatch disabled",
            "snow": "Heavy Snow failed calibration; duration dispatch disabled",
            "ice_storm": "Ice Storm sparse support/calibration; duration dispatch disabled",
        }.get(hid)
        causes = [event for event, checks in EVENT_CHECKS.items() if hid in checks]
        entry = HazardEntry(
            id=hid,
            category=category,
            label=label,
            synonyms=synonyms.split(";"),
            upstream_causes=causes
            or [
                "Source-specific conditions; no automatic activation or causal probability inferred"
            ],
            cascading_effects=[
                "Asset, access and worker consequences require independent verified evidence"
            ],
            worker_exposure_pathways=[
                f"Possible contact with or operational exposure to {label.lower()}; presence is unverified without evidence"
            ],
            official_sources=[SOURCES[key] for key in sources],
            geographic_time_coverage="Per-source footprint/window; NOAA 2021-2025 where raw labels exist; current snapshots are bounded probes, not universal site coverage",
            collection_auth=(
                "Authorized reviewed report/asset/official local feed required; no personal data collected"
                if manual
                else "Public agency products where retrieved; AirNow/AQS/FIRMS need unsupplied credentials; see source inventory"
            ),
            adapter_fixture=(
                [
                    "ml/worker/comprehensive.py:report gate",
                    "ml/fixtures/hazard_coverage/scenarios.json",
                ]
                if manual
                else [
                    "ml/sources/hazard_feeds.py",
                    "ml/sources/worker_feeds.py",
                    "ml/source_catalog.json",
                ]
            ),
            freshness_vintage_constraints="Issue/update/available times <= as-of; actual validity and QC; no backdated revised/reanalysis features; absent data is unknown",
            raw_noaa_types=raw,
            historical_record_count=sum(census["categories"][name]["records"] for name in raw),
            event_label_availability=(
                "Regional recorded intervals / station threshold episodes only"
                if trained
                else "No validated future site outcome label; records and notices are evidence/context"
            ),
            site_match_requirements=(
                "Trusted site ID and coordinates, source review/role/issuer, observation/review time and freshness; schema is not authentication"
                if manual
                else "Source polygon including holes or bounded station distance; gauges additionally require independently verified basin relation and datum"
            ),
            model_family=(
                "training-only conditional Kaplan-Meier baseline / reviewed comparison"
                if trained
                else "disabled prior recorded-duration fit; failed gate"
                if disabled
                else "offline Atlantic post-analysis wind-change experiment; no active dispatch"
                if hid == "tropical_cyclone"
                else None
            ),
            eligible_outcomes=[
                MODEL_TARGETS[hid]
                + " recorded/observed episode persistence and supported remaining duration"
            ]
            if trained
            else [],
            validation_status=disabled
            or (
                "Prior grouped chronological research screen; not operationally validated"
                if trained
                else "Evidence normalization only; no independent site probability validation"
            ),
            owner="Cache library; Rudra deterministic alerts/routes; Braydin trusted ingestion/auth; Nick presentation",
            tests=["ml/tests/test_hazard_coverage.py", "ml/tests/test_worker_outlook.py"],
            critical_missing_inputs=special_gaps.get(
                hid,
                (
                    ["Authenticated human/asset feed and qualified field verification"]
                    if manual
                    else [
                        "Current site-qualified source evidence",
                        "Independent site outcome labels for any probability claim",
                    ]
                ),
            ),
            fallback="Explicit unknown/rejected/stale; null probability/severity; never clearance or risk/alert reduction",
            next_action="Supply verified source/report evidence upstream; preserve deterministic authority and evaluate any new predictive target independently",
            stages=stages,
            signoff=signoff,
            review_question=f"What verified evidence describes {label.lower()} at this site and time?",
        )
        hazards.append(entry.model_dump(mode="json"))
    ids = {entry["id"] for entry in hazards}
    if (
        set(RAW_MAP.values())
        | set(FEMA_CROSSWALK.values())
        | {h for values in EVENT_CHECKS.values() for h in values}
    ) - ids:
        raise ValueError("Taxonomy crosswalk points to missing hazards")
    report = {
        "schema_version": "1.0.0",
        "scope": "Capability inventory, never proof of presence or safety",
        "taxonomy_sources": SOURCES,
        "fema_18_crosswalk": FEMA_CROSSWALK,
        "noaa_raw_type_count": len(census["categories"]),
        "noaa_raw_crosswalk": {key: RAW_MAP[key] for key in sorted(census["categories"])},
        "event_to_evidence_checks": EVENT_CHECKS,
        "operationally_validated_count": 0,
        "hazards": hazards,
        "stage_counts_nonexclusive": dict(Counter(s for h in hazards for s in h["stages"])),
        "signoff_counts_exclusive": dict(Counter(h["signoff"] for h in hazards)),
        "known_gaps": [
            "No independent site probability/injury labels",
            "No live trusted crew/asset feed",
            "AirNow/AQS/FIRMS credentials absent",
            "No verified gauge-to-site basin/datum transfers",
            "No universal DOT/evacuation feed",
            "No operational model validation",
        ],
        "stage_definitions": {
            "source_discovered": "Official taxonomy/data pointer; not proof of collection",
            "fixture_only": "A relevant parser/report contract is exercised synthetically; not a live feed",
            "real_retrieval_verified": "Real source data retrieved for this hazard, possibly historical or regional; not proof of site coverage",
            "historical_data_verified": "Pinned historical records, not operational issue-time features",
            "site_evidence_supported": "At least one real, accepted site measurement/issued notice in the 50-site replay; not exposure or probability validation",
            "research_model_trained": "Existing fitted experiment, including explicitly disabled or offline-only fits",
            "historically_backtested": "Existing grouped chronological evaluation; no fresh holdout rerun in this push",
            "integrated_tested": "Independent offline library rehearsal only, never production route/auth integration",
            "operationally_validated": "None claimed",
            "blocked/unsupported": "Specific missing inputs/access prevent an advertised capability; other evidence may coexist",
        },
    }
    REGISTRY_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def write_audit(report: dict) -> None:
    lines = [
        "# Hazard coverage audit and sign-off",
        "",
        "This is an inventory of evidence capabilities and explicit gaps, not a claim that every hazard is predicted or present. The user-requested taxonomy is cross-checked against FEMA's 18 groups, exact NOAA labels and OSHA/NIOSH response references. No compliance or individualized safety advice is generated.",
        "",
        f"**{len(report['hazards'])} registry hazards; {report['noaa_raw_type_count']} verbatim NOAA labels; 18 FEMA crosswalk groups; zero operationally validated models.** Raw labels and standardized groups remain separate. Counts and receipts for the existing datasets remain in [DISASTER_COVERAGE.md](DISASTER_COVERAGE.md).",
        "",
        "## Maturity totals",
        "",
        "Stages overlap; sign-off states are exclusive.",
        "",
        "```json",
        json.dumps(
            {
                "stages": report["stage_counts_nonexclusive"],
                "signoff": report["signoff_counts_exclusive"],
            },
            indent=2,
        ),
        "```",
        "",
        "## Family sign-off matrix",
        "",
        "| Hazard | Family | State | Evidence / limit |",
        "|---|---|---|---|",
    ]
    for h in report["hazards"]:
        lines.append(
            f"| {h['id']}: {h['label']} | {h['category']} | {h['signoff']} | {h['validation_status']}; {h['critical_missing_inputs'][0]} |"
        )
    lines += ["", "## Sources and cross-checks", ""]
    lines += [f"- [{name}]({url})" for name, url in SOURCES.items()]
    lines += [
        "",
        "## Interpretation and unresolved inputs",
        "",
        "Every manual/asset hazard defaults to unknown, even during an active disaster. Weather never confirms energized water, equipment failure, electrical isolation, structural condition, hazardous atmospheres, wildlife, route availability or an outage. A reviewed absence report is a timestamped statement, not clearance. Employer procedures and qualified inspection remain separate.",
        "",
        "A CAP alert with no usable polygon remains regional/unmatched. Empty successful retrieval means only no notices in that response; failure/staleness is distinct. Cancellation/expiration changes source-product currency, never deterministic alert state. Site probability and severity remain null. Generic registry references establish taxonomy/discovery, not source collection or a model.",
        "",
        "No new model training, held-out target selection or outcome accuracy claim is part of this push. Existing per-category evaluations remain in [MULTIDISASTER.md](MULTIDISASTER.md) and [EVALUATION.md](EVALUATION.md).",
        "",
        "Source additions, retrieval failures, actual record windows and migration notes are in [SOURCE_INVENTORY_DIFF.md](SOURCE_INVENTORY_DIFF.md). Full per-hazard sources, match rules, missing inputs, fallback and owner are machine-readable in [hazard_registry.json](hazard_registry.json).",
        "",
    ]
    (ROOT / "HAZARD_COVERAGE_AUDIT.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    result = build()
    write_audit(result)
    print(f"{len(result['hazards'])} hazard entries; 54 raw labels; no training or downloads")
