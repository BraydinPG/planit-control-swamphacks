# T050A event outlooks: published API contract (2026-10-17)

Rudra's additive contract for Cache's multi-event adapter (`ml/event_outlooks`, PR #39).
Backward compatible: every existing field, route and role check is unchanged.

## What changed in `GET /api/sites/{id}`

| Field | Status |
| --- | --- |
| `event_outlook` | **Unchanged shape.** Still the singular Flood advisory. It now skips Flash Flood notices and is `unavailable` when the event has no trusted start. |
| `event_outlooks: EventOutlookCard[]` | **New.** One card per confirmed event at the site, keyed by `event_id`. Defaults to `[]`. |
| `EvidenceKind` `"event_start"` | **New value.** A server-written Evidence item on a notice whose `observed_at` is the event's actual start. |

Canonical models: `backend/app/schemas/outlook.py` (`EventOutlookCard` and its parts).
TypeScript mirror: `frontend/src/types/api.ts`, checked by `test_ts_mirror.py`.
`EventOutlookCard` follows `ml-event-outlooks-1.0.0`'s `EventOutlook`, plus:

- `site_id`: the site the card was built for.
- `presentation`: `current` (a real confirmed event), `replay` (a notice the server stored
  as simulated, such as the T069 demo), or `historical_example` (an archived official product
  shown as an example, never a current prediction).
- `advisory_notice`: the same fixed advisory text as `event_outlook`.

Branch on `forecast.kind`: `historical_duration_research`, `official_event_forecast` (NHC),
`official_aftershock_forecast` (USGS), or `unavailable` (`reason_code`, `reason`,
`required_inputs`). `production_eligibility` is always false and
`site_hazard_probability` always null.

## How the backend builds cards (`backend/app/outlook/events.py`)

Inputs come only from data the route has already authorized: notices covering the site,
reports visible to the caller, and stored readings. Nothing is taken from the request.

- **Confirmed events only.** A supervisor-confirmed notice. Potential notices and warnings
  alone never make an event.
- **Event type.**
  - **Flood vs Flash Flood:** decided by the notice's own NWS source or evidence, then by
    the site's flood-alert readings. They are separate targets with separate models. A crew
    "flooding" notice with no NWS product gets `flood_category_unidentified` rather than a
    guess.
  - **Hurricane/tropical and earthquake:** go to the issued-forecast path, using the
    provider event ID from the notice's source reading.
  - **Everything else:** gets the adapter's `unsupported_target` card.
- **Event start (the `context.py` fix).** Only `event_start` evidence that precedes
  confirmation is used. `notice.created_at` and warning issue times are never used. With no
  start, duration cards come back `event_start_missing`.
- **Site link.** `site_verified` when the notice's source report or reading belongs to this
  site; otherwise `regional_context`, which the adapter refuses for duration research.
- **Local evidence.** Confirmed present crew reports of the same hazard at this site. The
  adapter requires these to be within one hour for a live duration estimate.
- **Trust policy.** Server-owned source IDs (`supervisor-confirmed-notice`,
  `backend-site-link`, `confirmed-crew-report`). Replay applies only to notices the server
  stored as simulated.
- **Official products.** `EventOutlooksService(official_products=…)` accepts parsed NHC/USGS
  products keyed by provider event ID. No live collector exists yet, so current hurricane
  and earthquake cards say `official_forecast_missing`. An archive capture is never
  accepted as current (`historical_availability_unverified`).
- **Archived examples.** PR #39's Helene and Ridgecrest products appear only on sites with
  simulated notices (the demo). They are evaluated at their own historical as-of, labeled
  `historical_example`, and carry "Historical example … not a current prediction" as their
  first limitation. Ridgecrest is outside its 60 km region at the Florida demo site, so it
  shows as unavailable.
- **Isolation.** One adapter batch per request. A missing ML package, model or product, or
  a failure, gives unavailable cards; the site route always answers. Cards are computed
  after the score and alerts and never feed `score_site`, alert rules or the lightning timer.

## Demo (T069 seed)

`python -m app.demo seed` now writes a trusted simulated start on the Flood notice and adds a
separate simulated Flash Flood notice. The score is unchanged (flood counts once). With the
Flood artifact provisioned, the demo site shows:
- Flood: a replay duration estimate.
- Flash Flood: an unavailable card until its artifact is provisioned (`ml/EVENT_OUTLOOKS.md`).
- Wildlife: unsupported.
- Hurricane Helene: an issued-track historical example.
- Ridgecrest: a historical example outside its region (unavailable).

## Verification and limits

- **Tests.**
  - `backend/tests/test_event_outlooks.py` (18 tests): the start fix, Flood/Flash Flood
    separation, confirmation, site-link and local-evidence admission, ML-unavailable and
    failure isolation, archived products not being current, and the demo route for crew and
    supervisor with score and alert rows unchanged.
  - `frontend/tests/event-outlooks.test.mjs` (5 tests): rendering, unavailable cards, and
    malformed or missing data.
- **Real Tiger Data, read-only.** The current demo rows predate this seed. Their Flood
  notice has no trusted start, so it correctly shows `event_start_missing`; Wildlife shows
  unsupported, Helene is an available example, and Ridgecrest is outside its region.
- **Not shown here:** forecast skill, live NHC/USGS collection, or a signed-in browser run
  against Auth0. **T050A stays unchecked** until those owner checks pass.

Codex: test against this contract through the existing HttpClient. `validateSiteDetail`
turns a malformed card into an "unavailable" card instead of failing the page, and treats a
missing `event_outlooks` (older backend) as `[]`.
