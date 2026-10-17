# PlanIT Control Project Specification
For the step-by-step implementation backlog, see tasks.md

## 1. Project summary

PlanIT Control is a web platform that helps utility field crews and supervisors make site safety decisions using one shared view of current hazards, forecasts, historical risk, and crew reports.

The product combines three distinct functions:

- Deterministic rules trigger operational alerts, including the required lightning stop-work and all-clear logic.
- A trained machine-learning model estimates recorded-event persistence and remaining duration conditional on an already-confirmed active event. It does not estimate event onset or safe-to-work status.
- Gemini summarizes supplied evidence and suggests structured labels for crew reports. Gemini does not set, explain, or interpret scores, trigger alerts, or declare work safe.

The demo should show an Everglades-style site scenario, a lightning alert, a crew hazard report, a ranked supervisor view, and a next-day briefing.

## 2. Challenge requirements and scope assumptions

The Sperry Tech brief asks for:

1. At least 50 actual power plant locations.
2. A combined environmental risk picture for each location.
3. Immediate hazard alerts, including a lightning strike within 10 miles that triggers stop-work and a 30-minute all-clear countdown that resets after every new strike.
4. A next-day safety briefing at 6 PM local time.
5. Crew hazard reports with a photo and map pin, shared with the team and retained for future site planning.
6. A supervisor dashboard that ranks sites by risk.
7. A 0–10 site hazard index based on the approved scoring method and current evidence. The active-event ML outlook is a separate conditional persistence signal, not event severity, a risk-score reduction, or a work-clearance decision.

The pasted track rules also identify Best Use of Gemini API, Best UI/UX, Best Use of Auth0, and Best Use of AI/ML. Auth0, Tiger Data, and Vultr are sponsors for tracks. The team should submit to the sponsor tracks and the other listed tracks if registration permits.

### Scope assumptions to state in the demo and README

- EIA-860M locations are power plant locations, not proof of active construction sites. Display them as representative monitored sites. Confirm with the organizer whether these meet the intended meaning of “job site.”
- A crew report stores coordinates and whether the hazard is present. The crew screen does not include a map snippet. The supervisor screen keeps the full map. A detected or crew-marked hazard sends a “potential {hazard}” notice with no instructions. Instructions go out only after a notified supervisor confirms the hazard and accepts or edits Gemini’s suggestion.
- NOAA Storm Events and related historical weather data are proxies for hazard events. They do not represent worker injury outcomes unless the team obtains and validates separate outcome data.
- If a live lightning feed is unavailable, use a deterministic replay fixture and label it as simulated.
- Live hazard data comes from public NWS, NHC, and USGS feeds, plus the lightning replay fixture. Section 5 lists each source. Every reading shows its source and data state. Hurricanes and earthquakes are regional events near a site, not on-site observations.
- On-site hazards that no feed can detect, such as a broken electrical pole, a downed line, or a fire on site, come only from in-person crew reports.
- Include only hazard feeds the team can source and timestamp. Mark missing, stale, mocked, or unavailable data clearly.
- Safety thresholds beyond the explicit lightning rule are configurable prototype rules. Do not present them as official employer or regulatory policy.

## 3. Users and workflows

### Crew member

1. Sign in and open the assigned or selected site.
2. Check current status, active alerts, immediate action, and last data update.
3. Open an alert to see its trigger, evidence, distance, and countdown.
4. Acknowledge an alert.
5. Submit a hazard report with a photo, category, coordinates, whether the hazard is present, and an optional note. Marking the hazard present creates a potential-hazard notice. A report that the hazard is absent stays with that crew member’s organization for its supervisor to review.
6. Receive a “potential {hazard}” notice when the crew member’s team is inside the notice radius. That notice does not include instructions. After a supervisor confirms the hazard, receive the instruction that supervisor accepted or edited.

### Supervisor

1. Sign in as the supervisor for one organization. That organization can have multiple teams, and each team can have multiple crew members.
2. See the full map and a list of every monitored location with the team assigned to it. Locations that have a team appear above locations that do not. Within each group, higher risk stays above lower risk.
3. Filter by location, hazard type, or alert status.
4. Open a site to inspect score factors, observations, freshness, active alerts, and crew reports.
5. Review this organization’s reports that say no hazard is present, and make the final call on those reports.
6. Receive a “potential {hazard}” notice, with no instructions, when one of this supervisor’s teams is inside the radius. Any supervisor who received that notice can confirm the hazard.
7. After confirming, review Gemini’s suggested instruction, change it if needed, and send that text to every team inside the same radius.
8. Review the next-day briefing, generated automatically at 6 PM local time, and use the evidence links to inspect its inputs.

## 4. MVP scope and priorities

### P0: required end-to-end product

- Import and validate at least 50 EIA-860M coordinates.
- Display all sites in a map and a location list. Show the assigned team, and place locations that have a team above locations that do not.
- Show a per-site hazard index, factor breakdown, confidence or data completeness, and last-updated time.
- Ingest the P0 live feeds from section 5: NWS weather and forecast, NWS flood alerts, and the labeled lightning replay fixture. Cache results and expose stale and unavailable states.
- Implement the lightning stop-work rule and resettable 30-minute countdown.
- Support crew hazard reports with a photo, coordinates, and a present-or-absent answer.
- Support one supervisor per organization, with multiple teams and crew members. Many organizations share one deployment.
- When a connected source detects a hazard, or a crew member marks a hazard present, notify every team and supervisor inside a Gemini-chosen radius. The notice says “potential {hazard}” and contains no instructions.
- After any notified supervisor confirms the hazard, have Gemini suggest one concise instruction. Send the text that supervisor accepts or edits to every team inside that radius.
- Support supervisor review of absent reports and a full map plus the occupied-first location list.
- Train and evaluate an active-event recorded-outcome model on historical event intervals, with episode-grouped chronological holdout and explicit geographic/data limitations.
- Enforce crew and supervisor roles with Auth0 on protected backend routes.

### P1: judging-track features

- Gemini-generated, evidence-grounded next-day briefing.
- Gemini-assisted report classification with human confirmation.
- Mobile-first crew interface and polished supervisor dashboard.
- Briefings generated automatically every day at 6 PM site-local time and stored. There is no manual generation; the demo shows a briefing the schedule already produced (seeded for the demo site).
- P1 live feeds from section 5: hurricanes (NHC and NWS tropical alerts), earthquakes (USGS), USGS flood gauges, and a best-effort live lightning feed that falls back to the replay fixture.
- Public repository README documenting architecture, data, model, evaluation, Gemini safeguards, Auth0 setup, and demo steps.

### P2: only after P0 and P1 work

- Additional live data feeds for wildfire, soil saturation, and other hazards.
- Push notifications, offline sync, what-if scheduling, or a conversational assistant.
- Auth0 AI Agent security features, if the basic role-protected Gemini endpoints are stable and the team can show a meaningful use.

## 5. Hazard data and scoring

### Data states

Every observation must carry a source, value, unit when relevant, observation time, valid time, location, and data state. Use these visible states: observed, forecast, crew reported, simulated, stale, unavailable.

### Live data sources

Ingestion adapters in `backend/app/ingestion/` fetch these feeds and normalize them into `Observation` records. Rudra owns the NWS weather, forecast, and flood-alert feeds and the shared `FeedCache`. Braydin owns the other adapters, and each wraps its fetch in `FeedCache`. Confirm access, rate limits, and terms for each source before building it.

| Hazard | Source | Tier | Data state | When unavailable |
|---|---|---|---|---|
| Weather and forecast, including heat index inputs | NWS API (`api.weather.gov`): point lookup, hourly forecast, latest station observation. No key, but send a `User-Agent`. | P0 | observed, forecast | Keep the last reading and mark it stale, then unavailable |
| Flooding | NWS active alerts for the site point: Flood Warning, Flash Flood Warning, Flood Watch | P0 | observed | Mark unavailable. Never treat a missing alert as no flood risk. |
| Lightning | Deterministic replay fixture | P0 | simulated | Fixture is always available |
| Lightning, live | NOAA GOES GLM lightning data on AWS Open Data, best effort | P1 | observed | Fall back to the replay fixture and label it simulated |
| Hurricanes | NHC active storms (`CurrentStorms.json`) plus NWS Hurricane and Tropical Storm Warning and Watch alerts | P1 | observed, forecast | Mark unavailable |
| Earthquakes | USGS earthquake GeoJSON summary feed, for example the past-hour feed | P1 | observed | Mark unavailable |
| Flood gauges | USGS Water Services instantaneous gauge readings | P1 | observed | Fall back to NWS flood alerts and mark gauges unavailable |
| Broken electrical pole, downed line, on-site fire, wildlife, other on-site hazards | No feed. In-person crew reports only. | P0, through the report flow | crew reported | Not applicable |

For each feed, cache the last successful result with its fetch time. Mark it stale after a configurable age and unavailable when no successful result exists. Never present a stale reading as current. A feed outage never clears or resolves an alert. Feed outputs follow the conventions in `AGENTS.md`, "Ingestion interface": one metric per weather Observation, an explicit "none active" Observation when an alert or event feed succeeds with nothing found, and unavailable placeholders on failure.

### ML model: outcomes conditional on an active event

The ML model does not predict whether a disaster starts. It estimates how a verified/confirmed active event may develop based on historical event outcomes and evidence available as of a specified time. Historical replays must be labeled as simulated/replay inputs and must not be presented as live confirmation.

The primary supported target is the probability that the recorded event remains ongoing or has a recorded end by appropriate horizons (prefer 6, 12, and 24 hours where data support them), plus a conditional remaining-duration distribution and uncertainty. Recorded event intervals are regional/reporting labels, not proof that site conditions have cleared. Trend outputs (`worsening`, `stable`, `improving`) require matched, time-varying outcome labels; otherwise return `unknown`.

Use as-of snapshots, strict feature allowlists, and episode/storm-grouped chronological holdouts. No event end time, final narrative, final magnitude, future observation, or post-event report may enter predictors. Compare a training-only conditional survival baseline with the fitted model. Report Brier/calibration, event support, duration error and interval coverage only where valid; label fixture-only results and never claim unrun real validation.

The primary callable is `predict_active_event(event_context)`. Keep the documented `predict_site(features)` shape as a compatibility adapter only: it must not emit event-onset probabilities, and its model score component is excluded until Rudra explicitly approves its meaning. The model does not set the final Hazard Index, deterministic alerts, lightning timer, or work status. No model output may authorize work, declare a site safe, or suppress an alert. Missing evidence/artifacts produce an explicit unavailable/fallback result, never a fabricated low-risk probability.

Monte Carlo is an offline/internal validation and stress-testing tool only. It does not establish real-world accuracy; independent historical backtesting is the validation method. Production inference must be deterministic and return compact summaries, not simulation trajectories.

### Deterministic rules

- Lightning: a qualifying strike within 10 miles creates a stop-work alert. The 30-minute all-clear window starts from the latest strike and resets after each new qualifying strike. Resolve only when the window expires with no new strike.
- Flooding: use a documented rule based on a warning, gauge threshold, or rainfall plus site context. The brief sets no numeric threshold, so label a chosen threshold as a prototype setting.
- Heat: show the forecast heat index and use a documented configurable threshold. Do not infer work/rest schedules from the brief.
- Hurricane (prototype): an active NWS Hurricane or Tropical Storm Warning covering the site, or an NHC active storm within a configurable distance, creates a potential-hazard notice and a score factor. Label the distance as a prototype setting.
- Earthquake (prototype): a USGS event at or above a configurable magnitude within a configurable distance of the site creates a potential-hazard notice and a score factor. Label both settings as prototype values, not official policy.
- Hurricane and earthquake prototype settings: NHC storm center within 50 miles, USGS magnitude 4.0 or higher within 25 miles. A hurricane factor adds 2.0 points and an earthquake factor adds 1.5. Hurricane and Tropical Storm Watches are shown but don't qualify. Stale readings still count in the score and stay labeled stale, but only fresh readings send a notice. Each event sends one notice: per storm or warning per site, and per USGS event. These P1 factors appear only after their feed reports and don't count toward data completeness. All values are configurable in `RuleSettings`.
- Crew-reported only: no feed detects a broken electrical pole, a downed line, a fire on site, or similar on-site hazards. These enter the system only when an in-person crew member submits a report marked present.
- Crew reports: only a confirmed report that the hazard is present can contribute to the final score. A report that the hazard is absent does not raise the score and does not send a potential-hazard notice. A potential notice does not change the score.
- Potential-hazard notice: a connected source detection or a crew member marking a hazard present notifies every team and every supervisor assigned to a location inside the radius. The notice text is “potential {hazard}” and includes no instructions. The radius comes from Gemini. Accept only a positive radius of 50 miles or less. If Gemini is unresponsive or returns an invalid radius, use that category’s default radius below and label it as a default. The lightning stop-work rule remains a separate 10-mile deterministic rule.

| Category | Default radius when Gemini is unresponsive |
|---|---:|
| Lightning | 10 miles |
| Flood | 5 miles |
| Heat | 15 miles |
| Wildlife | 1 mile |
| Wildfire | 10 miles |
| Hurricane | 50 miles |
| Earthquake | 25 miles |
| Broken electrical pole or downed line | 1 mile |
| On-site fire | 1 mile |
| Any other category | 1 mile |

These defaults are prototype notice distances, except lightning, which matches the required stop-work distance. Do not present the other defaults as official policy.
- Instruction: the first notified supervisor to confirm the hazard asks Gemini for one direct, concise instruction. That supervisor can edit it. The accepted or edited text is what the teams inside the stored radius receive. Gemini does not send the instruction on its own, does not declare work safe, and does not clear the alert. If Gemini cannot draft the instruction, the supervisor writes it.

Every alert must store and display the rule, triggering inputs, trigger time, latest qualifying event, status, and clear-after time.

## 6. Gemini behavior and safeguards

All Gemini calls run server-side. Send only the evidence needed for the task. Validate structured output. Store evidence identifiers with generated text and show evidence in the interface.

### Next-day briefing

Input: forecast observations, site score and factors, active alerts, confirmed crew reports, timestamps, and missing-data flags.

Output fields: `summary`, `risk_level`, `hazards[]`, `recommended_actions[]`, `evidence[]`, `unknowns[]`.

Rules: each material claim must reference supplied evidence. The model must state unknowns and must not declare work safe or clear an alert. On failure, generate a deterministic template briefing from the same data.

Schedule: generated automatically at 6 PM in each site's local time zone, once per day, for every site with an assigned team whose organization has a supervisor. Unassigned sites and organizations without a supervisor get none. It covers the next workday (07:00–19:00 local) and is stored, then read back; it is never generated on request. The briefing's overall `risk_level` is the site's computed score level at generation time, never Gemini's judgment.

### Hazard score: no generated explanation

Gemini does not explain or interpret the hazard score. The 0–10 score is a deterministic weighted algorithm over current risk factors and confirmed reports. The interface shows its factor breakdown as the explanation: each factor's weighted contribution, source, time, data state, and prototype label. There is no score-explanation route.

### Crew report enrichment

Input: photo, crew-selected category, optional note, pin, and site context.

Output fields: `suggested_category`, `description`, `severity_suggestion`, `confidence`, `visible_evidence[]`, `needs_review`.

Rules: label output as a suggestion. A person confirms the category and severity before the report affects risk. On failure, save the original report without enrichment.

### Notice radius

Input: hazard name, source, coordinates, supplied observations, and whether a crew member marked it present.

Output fields: `radius_miles`, `hazard_label`, `evidence[]`, `unknowns[]`.

Rules: Gemini chooses the radius only. It does not write instructions in this step. Validate a positive number no greater than 50. If Gemini is unresponsive or the radius is invalid, store that category’s labeled default from the table in section 5 and still send the potential notice.

### Confirmed instruction

Input: confirmed hazard label, radius, source, and the evidence already stored with the notice.

Output fields: `suggested_instruction`, `evidence[]`, `unknowns[]`.

Rules: return one direct, concise instruction. The confirming supervisor can edit it before it is sent. Send the supervisor’s final text, not an unreviewed Gemini draft. Gemini cannot declare work safe or clear the alert. On failure, leave the suggestion empty and require the supervisor to write the instruction.

Create a small evaluation set for grounding, schema validity, unknown handling, and unsupported safety claims. Include examples and results in the repository.

## 7. UI/UX requirements

### Crew experience

- Mobile-first site and alert screens.
- Put site status, current alert, immediate action, and update time at the top.
- Large, glove-friendly controls, minimum 44 by 44 CSS pixels for primary touch targets.
- Report hazard flow with photo, category, coordinates, a required present-or-absent choice, and optional text. Categories include broken electrical pole or downed line, on-site fire, wildlife, flooding, and other. These on-site hazards have no automated feed, so the crew report is how they enter the system.
- High contrast and large text suitable for bright outdoor use.
- Use icons and labels in addition to color. Support keyboard access, visible focus, semantic labels, and screen readers.

### Supervisor experience

- Desktop and tablet map of all monitored locations, plus a list of every location and the team assigned to it. Locations with a team appear first.
- Show score, trend, active alerts, data freshness, and top factors without opening each site.
- Filters for region, hazard, and alert state.
- Site detail with observations, sources, timestamps, reports, and score breakdown.
- Briefing view with action recommendations, evidence links, and unknowns.

### UX acceptance checks

- A crew member can identify an active alert and its immediate action within 10 seconds.
- A crew member can submit a report in under 30 seconds without typing a required note.
- A supervisor can identify the three highest-risk sites from the dashboard.
- Risk remains understandable without color.
- Loading, empty, stale, unavailable, and error states are implemented.

## 8. Auth0 roles and permissions

Use two roles: `crew` and `supervisor`. Validate access tokens on the backend. Hiding a button in the frontend is not authorization.

| Action | Crew | Supervisor |
|---|---:|---:|
| Read assigned site and alerts | Yes | Yes |
| Acknowledge alert | Yes | Yes |
| Submit hazard report | Yes | Yes |
| Read all sites, assigned teams, and the full map | No | Yes |
| Review a report that no hazard is present | No | Own organization only |
| Receive a potential-hazard notice inside the radius | Team is inside the radius | Team is inside the radius |
| Confirm a potential hazard from a received notice | No | Any notified supervisor |
| Edit and send the instruction for that hazard | No | The confirming supervisor |
| Read organization-wide briefings | Own organization only | Own organization only |

Keep secrets in environment variables. Provide one demo account per role. Any development bypass must be explicit, local-only, and disabled by default.

## 9. Architecture and API contract

Required stack: React + TypeScript with Vite and Tailwind CSS for the frontend, FastAPI for every backend route, Tiger Data for the application database, Vultr for application hosting and photo object storage, a geospatial map library, scikit-learn, Gemini API, and Auth0. Auth0, Tiger Data, and Vultr are sponsors for tracks. Style the UI with Tailwind utility classes. Do not add a second CSS framework. The Vite app is the UI only. Implement API routes, Auth0 token checks, Gemini calls, scoring, alerts, and data ingestion in FastAPI under `backend/app/`. Live-feed adapters live in `backend/app/ingestion/`. Do not implement those routes in Next.js, Express, Flask, or another server.

Tiger Data is the PostgreSQL-compatible database. Connect with a Postgres URL and `sslmode=require`. Store sites, reports, scores, alerts, and observations there. Convert time-ordered `Observation`, `Alert`, and `AuditEvent` tables to hypertables. Keep `Organization`, `Team`, `Site`, `CrewReport`, `HazardNotice`, `Acknowledgement`, `Briefing`, `HazardPrediction`, and `HazardScore` as regular tables. One deployment serves many organizations. A supervisor belongs to one organization and manages all of its teams. A crew member belongs to one team. Auth0 is the only identity provider. Deploy the FastAPI app and the frontend on Vultr. Store crew photos in Vultr Object Storage, with a private local directory allowed for development. Do not add a second database, identity provider, or application host.

### Routes

| Route | Purpose |
|---|---|
| `GET /api/sites` | Every location with its assigned team, score, factors, alerts, and freshness. Locations with a team come first. |
| `GET /api/sites/{id}` | Site details, observations, score, reports. |
| `GET /api/alerts` | Visible alerts and countdown state. |
| `POST /api/alerts/{id}/acknowledge` | Record user and acknowledgement time. |
| `POST /api/reports` | Submit category, photo, coordinates, whether the hazard is present, and an optional note. |
| `GET /api/reports` | List reports visible to the caller, optionally filtered by site. |
| `POST /api/reports/{id}/review` | A supervisor in the reporting organization reviews a report that no hazard is present. |
| `POST /api/hazards/{id}/confirm` | A notified supervisor confirms a potential hazard and receives Gemini’s suggested instruction. |
| `POST /api/hazards/{id}/instruction` | The confirming supervisor sends the accepted or edited instruction to teams inside the stored radius. |
| `GET /api/sites/{id}/briefing` | The site's latest stored next-day briefing. Same site access as `GET /api/sites/{id}`. |
| `GET /api/briefings` | The latest briefing for every team site in the caller's organization (crew and supervisors). |

Use a stable response contract. Site summaries include `id`, `name`, `lat`, `lon`, `assigned_team`, `risk_score`, `risk_level`, `updated_at`, `active_alerts`, `top_factors`, `data_completeness`, and `model_version`. `assigned_team` is null when no team is assigned.

Cache exports:

```text
predict_site(features) -> {
  hazard_probabilities,
  model_component_0_10,
  factor_contributions,
  confidence,
  model_version,
  data_quality
}
```

The primary active-event model export is `predict_active_event(event_context)`. Its input identifies `event_id`, `event_type`, `event_status`, `as_of_utc`, optional `event_start_utc`, site/region association, evidence timestamps, and only observations valid at or before `as_of_utc`. See `ml/INTEGRATION.md` for the JSON contract and compatibility behavior. Rudra's backend remains the authority for event confirmation, authorization, site scoring, and deterministic alerts; integrating an optional event outlook must not change existing route behavior until its response contract is approved.

### Core entities

- `Organization`: identity and name. Many organizations share the deployment.
- `Team`: organization, name, and the one location it is assigned to. A team has many crew members. A location lists at most one assigned team.
- `Site`: identity, name, coordinates, location type, source, region.
- `Observation`: hazard type, value, unit, source, observed and valid times, freshness, simulated flag. Hazard types include `weather`, `forecast`, `flood_alert`, `flood_gauge`, `lightning_strike`, `hurricane`, and `earthquake`.
- `HazardPrediction`: probabilities, model version, created time.
- `HazardScore`: final score, factor contributions, model version, created time.
- `Alert`: site, rule, state, trigger time, latest qualifying event, clear-after time.
- `CrewReport`: organization, team, site, reporter, category, whether the hazard is present, note, photo reference, coordinates, review status, timestamps.
- `HazardNotice`: hazard label, source, coordinates, radius in miles, whether the radius came from Gemini or that category’s default, potential status, confirming supervisor, and the instruction text that supervisor sent. The potential notice itself stores no instruction.
- `Acknowledgement`: alert, user, timestamp.
- `Briefing`: site or region, forecast window, generated text, evidence IDs, created time.
- `AuditEvent`: actor, action, entity, timestamp.

## 10. Reliability, privacy, and failure states

- Keep weather data cached and show freshness.
- If Gemini fails, show deterministic text or factor data.
- If the active-event model fails, show an unavailable advisory outlook and retain deterministic score and alert behavior.
- If a feed is stale or unavailable, show that state and reduce confidence. Do not present stale observations as current. Track freshness per feed, so one failed feed does not mark the others stale.
- A feed outage never clears an alert or lowers a score to zero risk.
- Keep lightning alerts and rule evaluation independent from Gemini and model availability.
- Restrict photo size and file types. Keep photo storage private. Use Vultr Object Storage outside local development.
- Keep credentials out of git. Log alert triggers, acknowledgements, report review, and scheduled briefing generation.
- Do not store more user data than needed for roles and audit records.

## 11. Team ownership and parallel work

See `AGENTS.md` for detailed individual ownership, prompts, path boundaries, contracts, dependencies, and merge routine.

Ownership summary:

- Cache: `ml/`, model training, features, evaluation, model handoff, and the deterministic 0–10 site risk algorithm (`backend/app/rules/score.py`).
- Braydin: `backend/app/security/`, `backend/app/db/`, `backend/app/ingestion/` except Rudra's NWS and cache files, `backend/app/gemini/`, database migrations, EIA-860M site import, lightning, hurricane, earthquake, and flood-gauge feeds, Gemini endpoints, Vultr deployment, `frontend/src/auth/`, Auth0 setup notes.
- Nick: `frontend/src/pages/`, `frontend/src/components/`, `frontend/src/styles/`, `frontend/src/api/`. Nick deploys the frontend.
- Rudra: `backend/app/` except `security/`, `db/`, Braydin's adapters in `ingestion/`, and `gemini/`, API contracts, NWS weather, forecast, and flood-alert feeds and the shared feed cache in `ingestion/`, deterministic alert rules, scoring, report and notice persistence, root README. Rudra imports Braydin’s database session, other ingestion adapters, and Gemini functions, and does not edit migrations, Braydin's feed adapters, or Gemini calls.

Rudra creates and publishes the shared schemas first. Other members start against fixtures and their own module boundaries. Do not have two people edit the same file. Shared manifest and lockfile changes go through Rudra.

## 12. 36-hour build sequence

| Time | Milestone |
|---|---|
| 0–1 hours | Confirm scope, create repository skeleton, freeze API contract, assign file ownership. |
| 1–8 hours | Parallel build: site/API foundation, model pipeline, Auth0 module, frontend using mocks. |
| 8–12 hours | Integrate first working site list, role modules, model interface, and screens. Keep a runnable demo on main. |
| 12–20 hours | Add score pipeline, lightning rule, report flow, supervisor ranking, Gemini endpoints. |
| 20–27 hours | Connect UX and auth, add report enrichment, briefing, stale/error states. |
| 27–32 hours | Freeze scope, test roles and end-to-end flows, document model and Gemini evaluations. |
| 32–36 hours | Seed demo, rehearse, finish README and Devpost material, record fallback demo if useful. |

If the core flow is unstable by hour 19, stop adding data sources and stretch features. Finish site map, lightning alert, report, ranking, briefing, and role checks.

## 13. Track strategy

| Track | Proof to show |
|---|---|
| Sperry Tech | 50+ real locations, multi-hazard site view with live weather, flood, lightning, hurricane, and earthquake data, lightning rule, crew reports, ranking, next-day brief. |
| Gemini API | Useful, grounded structured briefing, report classification, notice radius, and instruction suggestions, with evidence and fallbacks. |
| UI/UX | Fast crew flow, readable field interface, polished supervisor dashboard, accessible controls. |
| Auth0 (sponsor track) | Role-based sign-in and backend authorization demonstrated with two accounts. |
| Tiger Data (sponsor track) | Time-ordered hazard records in Tiger Data, including hypertables for observations, alerts, and audit events. |
| Vultr (sponsor track) | FastAPI app and frontend hosted on Vultr, with crew photos in Vultr Object Storage. |
| AI/ML | Trained historical-data model, documented features, time-based evaluation, baseline comparison, public README. |

## 14. Demo script and acceptance criteria

### Demo, 3–5 minutes

1. Show the Everglades-style site with heat, rain, wet-ground context, and a confirmed wildlife report.
2. Show 50+ mapped locations and the supervisor’s ranked list.
3. Replay a lightning strike within 10 miles. Show stop-work, evidence, acknowledgement, and 30-minute timer. Replay another strike and show the timer reset.
4. Sign in as crew and submit a hazard photo and pin. Show Gemini’s suggested classification, then confirm it as a person.
5. Sign in as supervisor. Review the report and inspect the score's weighted factor breakdown.
6. Show tomorrow’s briefing, generated automatically at 6 PM local time, and its recommended actions linked to evidence.
7. Point to the public README’s model evaluation, data sources, Auth0 roles, and Gemini safeguards.

### Release acceptance

- At least 50 valid EIA coordinates render in map and ranked list.
- Every site shows score, factors, timestamp, model version, and data completeness.
- Lightning alert triggers and timer resets correctly.
- Crew can submit a photo and pin. Supervisor can review it.
- Gemini outputs validate against schemas, cite supplied evidence, and expose unknowns.
- Crew and supervisor access differs at the UI and API boundaries.
- Model training and evaluation are documented and reproducible from the repository.
- Core demo works with simulated lightning and fallback behavior when external feeds or Gemini are unavailable.
