# Agent Instructions for PlanIT Control

This file assigns implementation ownership to the four coding agents. Read `spec.md` before making changes. Each agent works in its owned paths and integrates through the contracts below.

## Task workflow

Before coding, read `spec.md`, `AGENTS.md`, and `tasks.md`.
Use the backlog to track work, but an explicit task-specific user authorization may revise scope, dependencies, and ownership boundaries. Update affected docs/contracts when scope changes; do not leave known conflicts in place.
Keep changes focused, preserve teammate work, run acceptance checks, and mark tasks complete only after their checks pass.
Default ownership is a coordination boundary, not a reason to block explicitly authorized project work. Do not rewrite unrelated teammate features.

## Project-wide rules

1. Use React + TypeScript with Vite and Tailwind CSS for the frontend, and FastAPI for every backend route. PostgreSQL, Auth0, Gemini API, and scikit-learn complete the stack. Style UI with Tailwind utility classes. Do not add a second CSS framework. The existing Vite app does not replace the API. Do not implement routes in Next.js, Express, Flask, or another server. Preserve other repository conventions.
2. Respect the ownership map as the default. Explicit project-level authorization can permit focused edits outside an owner's paths; preserve unrelated work and coordinate interface changes.
3. Avoid root manifests, lockfiles, shared environment templates, migrations, and API contracts by default. Explicit project-level authorization permits focused changes when required; notify the relevant owner and preserve unrelated work.
4. Begin with fixtures and stable interfaces. Do not wait for another agent’s implementation to finish before building your independent module.
5. Do not commit secrets, API keys, tokens, private photos, or real personal data.
6. Label simulated, stale, mocked, and unavailable data in code and UI.
7. Gemini can explain and structure supplied information. Deterministic rules control alerts. Human review confirms report classifications. No AI output can declare work safe or clear an alert.
8. Make small commits on your own branch. Do not commit directly to `main`. Rudra coordinates merges.
9. Keep the project demoable. Merge only code that builds and passes its focused checks.

## Shared contract

Rudra owns the canonical API and schema definitions. All agents use these names unless Rudra publishes a versioned change.

### Site summary

```json
{
  "id": "site-id",
  "name": "Example Site",
  "lat": 27.0,
  "lon": -82.0,
  "risk_score": 0.0,
  "risk_level": "low",
  "updated_at": "ISO-8601 timestamp",
  "active_alerts": 0,
  "top_factors": [],
  "data_completeness": 1.0,
  "model_version": "string"
}
```

### Cache model interface

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

Primary active-event interface:

```text
predict_active_event(event_context) -> {
  status, scope, event_id, event_type, as_of_utc,
  outcomes: { recorded_event_ongoing_probability,
              recorded_event_ended_probability,
              remaining_duration_hours, trend, trend_basis },
  evidence_quality, model_version, is_simulated
}
```

The outcome target is conditional on a verified/confirmed active event or an explicitly labeled historical replay. `recorded_event_end` is not worksite clearance. Trend is `unknown` unless valid time-varying severity labels exist. The compatibility `predict_site` must use explicit active-event persistence keys, return no conditional probabilities when no event is confirmed, and mark its model component excluded until Rudra explicitly approves its semantics. Rudra owns the final site score and deterministic alert state; neither ML nor Gemini may suppress or clear an alert.

### Backend routes

- `GET /api/sites`
- `GET /api/sites/{id}`
- `GET /api/alerts`
- `POST /api/alerts/{id}/acknowledge`
- `POST /api/reports`
- `GET /api/reports`
- `POST /api/reports/{id}/review`
- `POST /api/sites/{id}/briefings`
- `POST /api/sites/{id}/explanations`

These routes are FastAPI routes in `backend/app/`. Do not add a second API server. Nick uses these routes through `frontend/src/api/`. The frontend must support fixture mode until routes are ready.

### Auth module interface

Braydin publishes frontend exports from `frontend/src/auth/`:

```text
AuthProvider
useAuth() -> { user, role, isAuthenticated, isLoading, login(), logout(), getAccessToken() }
RequireRole
```

Braydin publishes FastAPI dependencies from `backend/app/security/`. Rudra imports them into protected routes and owns endpoint policy.

## Ownership and individual instructions
The `Do not edit` lists below are default coordination boundaries. An explicit project-level user authorization may permit focused changes outside them; preserve unrelated work and notify affected owners of integration changes.

### Cache: AI/ML

**Owned paths:** `ml/**`, including training, features, prediction, evaluation, and model notes.

**Do not edit:** backend routes, DB models/migrations, frontend, root README, shared contracts, manifests, lockfiles.

**Tasks:**

- Build a reproducible model conditional on a confirmed active event. Do not predict event onset or normal-day hazard occurrence.
- Prioritize recorded-event persistence/resolution and remaining duration. Estimate worsening/stable/improving only when matched time-varying outcome labels support it.
- Use trustworthy historical events and as-of environmental features. Treat regional event matching as uncertain and event records as proxies, not worker-injury or worksite-safety outcomes.
- Compare a training-only conditional survival baseline with any fitted model using episode/storm-grouped chronological holdout backtests.
- Report Brier/calibration, support counts, duration errors and interval coverage where valid; never invent or overstate metrics.
- Implement `predict_active_event(event_context)` as the primary callable. Keep `predict_site(features)` only as a compatibility adapter; it must not emit event-onset probabilities or an unapproved safety-score contribution.
- Add unavailable/fallback behavior when evidence, artifacts, or supported event types are missing.
- Keep Monte Carlo offline/internal. Production inference returns compact deterministic summaries, never simulation trajectories.
- Provide `ml/EVALUATION.md`, `ml/METHODOLOGY.md`, `ml/INTEGRATION.md`, and runnable instructions.

**Can start immediately:** Yes. Use mock feature rows until Rudra’s site ingestion is ready.

**Integration dependency:** Rudra imports the function and combines its output with live deterministic factors. Do not implement the final risk score or lightning alert logic.

### Braydin: Auth0 and access control

**Owned paths:** `backend/app/security/**`, `frontend/src/auth/**`, `auth/SETUP.md`.

**Do not edit:** Nick’s pages/components/styles, Rudra’s route files and DB schema, shared manifests, lockfiles, root README.

**Tasks:**

- Configure `crew` and `supervisor` roles and permissions.
- Implement sign-in, sign-out, token acquisition, `AuthProvider`, `useAuth()`, and `RequireRole`.
- Implement FastAPI token validation and reusable role/permission dependencies.
- Document Auth0 tenant setup, callback/logout URLs, environment variables, demo accounts, roles, and permissions.
- Ensure the backend rejects unauthorized requests even if a user bypasses the interface.
- Keep development bypass disabled by default and local-only if one is needed.
- Never commit credentials.

**Can start immediately:** Yes. Create the Auth0 module and setup instructions independently.

**Integration dependency:** Nick imports frontend exports. Rudra imports backend dependencies and attaches them to routes. Send both import examples as soon as the module interface is stable.

### Nick: frontend and UI/UX

**Owned paths:** `frontend/src/pages/**`, `frontend/src/components/**`, `frontend/src/styles/**`, `frontend/src/api/**`.

**Do not edit:** `frontend/src/auth/**`, backend files, shared manifests, lockfiles, root README.

**Tasks:**

- Build mobile-first crew screens and desktop/tablet supervisor screens.
- Include crew home, alert detail and timer, hazard report, supervisor map/ranking, site detail, briefing, and Gemini explanation views.
- Use mock JSON that follows the shared contract. Add a fixture switch so the interface works before backend integration.
- Show data freshness, source, simulated/stale/unavailable status, score factors, and evidence references.
- Style screens with Tailwind utility classes. Do not add a second CSS framework.
- Use high contrast, large text, labeled icons, minimum 44 by 44 CSS pixel primary touch targets, and no color-only risk communication.
- Include keyboard navigation, visible focus, semantic labels, loading/error/empty states, and screen-reader support.
- Keep report text optional and core actions quick for gloved field use.

**Can start immediately:** Yes. Build with mock APIs. Do not wait for Auth0 or backend completion.

**Integration dependency:** Replace fixture calls with Rudra’s API client and import Braydin’s auth exports when available. Keep all auth code inside Braydin’s paths.

### Rudra: backend, data, Gemini, and integration

**Owned paths:** `backend/app/**` except `backend/app/security/**`, migrations/schema, shared API types, data ingestion, root `README.md`, deployment files, shared configuration and manifests.

**Do not edit:** `ml/**`, `backend/app/security/**`, Nick’s frontend pages/components/styles, `frontend/src/auth/**`.

**Tasks:**

- First publish the shared API and model contracts. Provide fixture JSON for Nick.
- Import and validate 50 or more EIA-860M locations. Label these as representative power plant locations.
- Add one dependable weather/forecast feed with caching and freshness labels. Keep the data adapter replaceable.
- Implement DB entities and FastAPI routes from the shared contract. Do not add those routes in another framework.
- Implement lightning stop-work within 10 miles and a resettable 30-minute all-clear. Provide a labeled replay fixture if live lightning access is unreliable.
- Implement documented prototype flood/heat rules where data is available. Do not claim prototype thresholds are official policy.
- Integrate Cache’s approved model output and compute the final score from current factors and confirmed reports. Coordinate any opt-in active-event outlook separately; do not interpret recorded-event persistence as onset, site severity, safety, or clearance, and do not include an unapproved compatibility score component.
- Implement crew reports, photo handling, review state, acknowledgements, and audit events.
- Implement Gemini briefing and explanation endpoints with structured output validation, evidence IDs, explicit unknowns, and deterministic fallbacks.
- Use Gemini for report enrichment only as a suggestion pending human confirmation.
- Import Braydin’s Auth0 dependencies and protect routes according to the role policy in `spec.md`.
- Add seed/demo data, health check, focused backend tests, deployment notes, and README.
- Own package/lockfile changes and shared configuration. Tell teammates before changing shared contracts.

**Can start immediately:** Yes. Start with contract, app skeleton, seed fixtures, site endpoints, and deterministic alert logic.

**Integration dependencies:** Cache supplies the model function. Braydin supplies token/role dependencies. Nick supplies the frontend. Use temporary stubs until each module arrives.

## Role and permission policy

| Action | Crew | Supervisor |
|---|---:|---:|
| Read assigned sites and alerts | Yes | Yes |
| Acknowledge alert | Yes | Yes |
| Submit hazard report | Yes | Yes |
| Read all sites and rankings | No | Yes |
| Review/confirm reports | No | Yes |
| Generate organization-wide briefings | No | Yes |
| Request score explanation | Assigned site only | Yes |

The backend is the authority for permissions. Frontend guards improve UX but do not replace API checks.

## Integration and merge schedule

1. **Kickoff, hour 0–1:** Rudra creates the skeleton and publishes contracts. Each person confirms path ownership and creates a branch.
2. **Parallel build, hours 1–8:** Cache works in `ml/`, Braydin in auth paths, Nick in frontend paths, Rudra in backend/data paths. Use fixtures and stubs.
3. **First integration, hours 8–12:** Merge API contract and seed data, then Cache interface, Braydin modules, then Nick screens. Keep `main` runnable.
4. **Feature integration, hours 12–27:** Connect model, Auth0, API, and UI. Each owner keeps edits inside their paths. Resolve interface questions in the contract before editing code.
5. **Freeze, hours 27–32:** Stop adding features. Test role boundaries, lightning reset, report review, Gemini fallback, model fallback, and stale data.
6. **Demo prep, hours 32–36:** Seed stable data, rehearse the full script, finish README and Devpost materials, record a fallback if useful.

## Branch and merge rules

- Branch names: `feature/cache-ml`, `feature/braydin-auth0`, `feature/nick-ui`, `feature/rudra-api`.
- Commit small, focused changes. Open a pull request before merging.
- Rudra merges one pull request at a time and runs the app after each merge.
- Only the owner edits a shared file. For an API contract change, Rudra updates the canonical schema and notifies all agents before implementation.
- Do not edit lockfiles from multiple branches. Send dependency requests to Rudra.
- If an integration is blocked, use the agreed stub rather than editing another owner’s module.
- Keep a working demo on `main` by hour 12. After that, merge only changes that pass a quick end-to-end check.

## Cross-feature acceptance checklist

- 50+ validated site points appear in both map and ranked list.
- Site risk includes current deterministic factors, confirmed reports, freshness, and explainable contributions. Any conditional active-event outlook stays separate unless Rudra explicitly approves score semantics; it can never reduce risk or clear an alert.
- Lightning within 10 miles triggers stop-work, and a new strike resets the 30-minute countdown.
- Crew can acknowledge alerts and submit photo-plus-pin reports.
- Supervisor can rank sites and review reports.
- Gemini briefings and explanations cite supplied evidence, state unknowns, validate against schemas, and fall back safely.
- Auth0 roles change available actions and backend permissions.
- The interface works on mobile and desktop and includes stale, unavailable, loading, and error states.
- The public README describes data sources, model evaluation and limitations, Gemini safeguards, Auth0 setup, and demo steps.
