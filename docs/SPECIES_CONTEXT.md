# Site species context

Read-only field awareness for sites with an assigned team: which federally listed species
have a known range or critical habitat near the site, their protection status, and cited
encounter guidance. It never feeds the hazard score, alerts, report review, or work
clearance.

Route: `GET /api/sites/{id}/species` → `SiteSpeciesContext` (`backend/app/schemas/species.py`,
TS mirror in `frontend/src/types/api.ts`). Same access as `GET /api/sites/{id}`: supervisors
any site, crew only their team's site. A site without a team returns 404
`{"detail": {"reason": "no_team", ...}}`.

## Sources, reviewed 2026-10-17

### USFWS IPaC Location API

`POST https://ipac.ecosphere.fws.gov/location/api/resources` (OpenAPI 3.0, served version 1.2.0).

| Question | Finding |
|---|---|
| Authentication | None today. The docs say a key will eventually be required (contact fwhq_ipac@fws.gov). Add it to `SpeciesSettings` as a secret when that happens. |
| Rate limits | None documented. We cache per site for 24 h and back off 5 min after a failure. HTTP 429 is handled as a failure. |
| Input | A GeoJSON Polygon/MultiPolygon or WKT footprint. We send a 1 km square centered on the site. |
| Coverage | Federally listed (ESA) populations only: endangered, threatened, candidate, proposed, similarity of appearance. Non-listed species never appear. |
| Geographic meaning | A species is returned when its range intersects the footprint, i.e. it "should be considered" for the location. It is not an observation. `conditional: true` means field-office conditions (habitat, season) apply. |
| Vintage | No per-record date. "As of" is our retrieval time. |
| Provenance | Each population carries an ECOS species profile URL; the response names the responsible FWS field office. |
| Licensing | U.S. federal government data; attribute USFWS IPaC. |
| Failure semantics | 404/other status, invalid JSON, missing `populationsBySid`, timeout, and 429 all become `FeedError`. |
| Observed latency | About 2 s with `includeOtherFwsResources=false`. |

The Everglades demo site (25.395, -80.583) and the fixture site (25.76, -80.49) both return
about 30 species: alligator (Similarity of Appearance, Threatened), American crocodile
(Threatened), Eastern indigo snake (Threatened), Florida panther (Endangered), Florida
bonneted bat (Endangered), West Indian manatee (Threatened), and many listed plants.

**The water moccasin is not returned**, because it is not federally listed. IPaC cannot
support a "regional context" claim for it, so it is not shown as a species row. Instead,
every response states that IPaC covers only federally listed species and names the water
moccasin as an example of what is absent.

### USFWS Critical Habitat map service

`https://services.arcgis.com/QVENGdaPbd4LUkLV/ArcGIS/rest/services/USFWS_Critical_Habitat/FeatureServer`,
layer 0 (final) and layer 2 (proposed). Public, no key, `maxRecordCount` 1000. We query a 6 km
square around the site with server-side simplification (~50 m) and clip polygons to that
window. A statewide boundary is otherwise up to 1 MB. Features carry `fedreg` and `pubdate`;
`entity_id` matches IPaC's `Population$Sid[...]`. Placeholder attributes ("Please check
current species specific shapefile") are treated as unknown.

IPaC and the map service can disagree. At the fixture site IPaC flags final manatee critical
habitat in the footprint without a mapped boundary, while the map service has only a
proposed (2024) manatee boundary nearby. Both are shown, each with its own source and status.
Neither is merged into the other.

## Design

- `backend/app/species/`: `ipac.py` and `crithab.py` adapters, `guidance.py` (curated
  encounter guidance), `service.py` (cache, freshness, assembly, template), `geometry.py`
  (footprint and clipping), `settings.py`. No database tables or migrations.
- Two independent fields per species. `protection` comes only from IPaC. `encounter` comes
  only from `guidance.py`. Either may be null, and null is shown as unknown, never as
  "not protected" or "harmless".
- `match_basis`: IPaC rows are `regional_range` or `possible_regional_context`, and the
  match note says "Not a sighting". `confirmed_report` is used only in `wildlife_reports`,
  which lists crew wildlife reports with their human review state. The frontend validator
  rejects a species row that claims `confirmed_report`.
- Freshness per source: `observed`, `stale` (last refresh failed, previous data shown with
  its retrieval time), or `unavailable` (empty list plus an explicit "this does not mean
  nothing is there").

### Gemini (`backend/app/gemini/species.py`)

Gemini only rewords supplied facts into one line per species. Each line is checked against
that species' facts and rejected when it:

- cites an evidence id not supplied for that species;
- omits or changes the listing status;
- uses a risk or presence word (safe, harmless, venomous, seen, present, capture, ...) or a
  number that the facts do not contain; or
- gives advice for a species with no curated guidance.

Rejected or missing lines keep the deterministic template, and so do Gemini timeouts,
errors, invalid output, and missing configuration. Crew reports and photos are never sent.
A live run on 2026-10-17 accepted 25 of 27 lines. The alligator and crocodile lines were
rejected for adding "if seen".

### Curated encounter guidance

| Species (IPaC scientific name) | Source |
|---|---|
| American alligator | FWC, Living with Alligators; hotline 866-392-4286 |
| American crocodile | FWC, American Crocodile; same hotline |
| Florida panther, Puma (similarity of appearance) | FWC, Living with Panthers; 888-404-3922 for dead/injured |
| Eastern indigo snake | USFWS, Standard Protection Measures for the Eastern Indigo Snake; (352) 448-9151 |
| Florida bonneted bat, tricolored bat | CDC, Rabies |

All entries are `pending_review`. **Review owner:** the organization's safety lead must
confirm the wording and set `reviewed_by` before the guidance is treated as reviewed. The
guidance never covers handling, capture, or relocation, and it is not legal advice or a
substitute for employer site procedures.

## Limitations

- Federal ESA status only. State status (Florida FWC) is not supplied and is listed as unknown.
- Range is not presence. Nothing here says an animal is at the site.
- A crew wildlife report does not identify a species.
- The in-memory cache is per process and resets on restart.
- Encounter guidance covers seven IPaC species. All other species show "not reviewed".

## Demo wording

> "For the Everglades crew, PlanIT pulls the federally listed species whose range overlaps
> the site from the Fish and Wildlife Service's IPaC API, plus nearby critical habitat.
> Protection status and encounter guidance are separate and sourced. This is regional
> context, not a sighting. The crew's own confirmed alligator report is shown apart from it.
> Gemini only rewords these facts, and any line it cannot ground falls back to a template.
> None of this changes the score or the alerts."

In demo/fixture mode, the panel shows a recorded snapshot labeled "Recorded demo snapshot"
and `simulated`. Its species wording is one real Gemini response (`gemini-3.5-flash-lite`,
recorded 2026-10-17 in `backend/app/species/fixtures/gemini_species_everglades.json`),
replayed by the fixture generator through the same grounding check. All 27 lines passed, so
every card reads "Gemini wording" and the panel says "recorded Gemini response". The demo makes
no live Gemini call.

## Settings (`backend/.env`)

`IPAC_RESOURCES_URL`, `CRITHAB_SERVICE_URL`, `SPECIES_TIMEOUT_SECONDS` (20),
`SPECIES_CACHE_HOURS` (24), `SPECIES_UNAVAILABLE_AFTER_HOURS` (168),
`SPECIES_FOOTPRINT_HALF_KM` (0.5), `CRITHAB_WINDOW_HALF_KM` (3).

## Checks

- `backend/tests/test_species.py`: 47 tests covering parsing, regional matching, independent
  fields, outages and stale data, critical habitat clipping, Gemini grounding and fallback,
  route access, separated crew reports, and score/alert invariance.
- `frontend/tests/species.test.mjs`: 9 tests covering client, validation, demo client, and
  panel rendering.
- Regenerate the fixture with `cd backend; python -m scripts.generate_fixtures`. It is built
  from the recorded responses in `backend/app/species/fixtures/`.
