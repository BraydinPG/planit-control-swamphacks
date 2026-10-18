# Auth0 setup for FORESITE

For the current landing-page logo and the separate navy logo URL to paste into the
hosted light login widget, see [BRANDING.md](BRANDING.md). The prepared asset does not
change tenant branding automatically.

FORESITE is the current product name. The working tenant may still label the existing
API/client `PlanIT Control API` / `PlanIT Control Web` and the Action `Add PlanIT roles`.
Those are legacy dashboard labels, not new resources to create for the rebrand.
Keep all audience, client ID, tenant, claim namespace, role, callback and environment
identifiers below unchanged. Braydin can coordinate hosted login display branding
separately; this rebrand does not change Auth0 settings.

This guide sets up the Auth0 tenant, both roles, the demo accounts, and the local environment. Auth0 is the only identity provider. It takes about 20 minutes in the Auth0 dashboard.

Never commit Auth0 secrets, demo passwords, or `.env` files. The frontend values below are public: they are compiled into the browser bundle.

## How it fits together

1. The React app signs in with Auth0 (Authorization Code + PKCE, through `@auth0/auth0-react`).
2. Auth0 issues an **access token** for the FORESITE API. A post-login Action adds the user's roles, and RBAC adds their permissions.
3. The FastAPI backend validates every token: signature (RS256, from the tenant's JWKS), issuer, audience, and expiry. Then it checks the role or permission for the action.
4. The frontend reads the role from the ID token only to choose screens. **The backend is the authority.** Hiding a button is not authorization.

Organization and team scope ("own organization only", "assigned site only") comes from the `memberships` table, keyed by the Auth0 user id. See [Demo accounts](#7-demo-accounts).

## Team tenant (already set up)

Steps 1–6 below were done for the team's tenant with the Auth0 MCP server (`auth0_onboarding`, then the API, app, and Action tools). These values are public: they appear in the browser bundle.

| Setting | Value |
|---|---|
| Tenant domain (`AUTH0_DOMAIN`, `VITE_AUTH0_DOMAIN`) | `dev-qwsm71sgsbiajl7x.us.auth0.com` |
| SPA client ID (`VITE_AUTH0_CLIENT_ID`) | `jGG6b8gfjLqdNFD7ZVuELdNGPMxV9qnD` (app "PlanIT Control Web") |
| API audience (`AUTH0_AUDIENCE`, `VITE_AUTH0_AUDIENCE`) | `https://api.planit-control` (API "PlanIT Control API") |
| Post-login Action | `Add PlanIT roles` (deployed) |

To work on this tenant, put these values in your own `backend/.env` and `frontend/.env.local` (step 6). The roles, the Action's place in the login flow, and the demo users are set in the dashboard (steps 3, 5, and 7), because the MCP server has no tools for them. Run the frontend on port 5173: `vite.config.ts` pins it, because Auth0 only accepts the registered callback URLs.

## 1. Create the tenant

1. Sign in at https://manage.auth0.com and create a tenant, for example `planit-control`. Pick the region nearest the team (US).
2. Note the **tenant domain**, for example `planit-control.us.auth0.com`. This is `AUTH0_DOMAIN`.

## 2. Create the API (audience)

**Applications → APIs → Create API**

| Field | Value |
|---|---|
| Name | `FORESITE API` (the existing tenant may retain the legacy label above) |
| Identifier | `https://api.planit-control` (any URI; it is never called. This is `AUTH0_AUDIENCE`.) |
| JSON Web Token Profile | Auth0 |
| Signing Algorithm | `RS256` |

Then, on the API:

- **Settings → RBAC Settings**: turn on **Enable RBAC** and **Add Permissions in the Access Token**.
- **Settings → Access Settings**: turn on **Allow Offline Access**, so the app can use refresh tokens.
- **Permissions**: add each permission below.

| Permission | Description | Crew | Supervisor |
|---|---|:---:|:---:|
| `read:assigned_sites` | Read assigned sites and alerts | ✓ | ✓ |
| `acknowledge:alerts` | Acknowledge alerts | ✓ | ✓ |
| `submit:reports` | Submit hazard reports | ✓ | ✓ |
| `read:all_sites` | Read all sites, assigned teams, and the full map | | ✓ |
| `review:reports` | Review reports that no hazard is present (own organization) | | ✓ |
| `confirm:hazards` | Confirm a potential hazard from a received notice | | ✓ |
| `send:instructions` | Edit and send the instruction for a confirmed hazard | | ✓ |
| `read:org_briefings` | Read the latest briefings for every team site (own organization) | ✓ | ✓ |

These match `backend/app/security/roles.py` and the role policy in `spec.md` section 8. If you change one, change both.

## 3. Create the roles

**User Management → Roles → Create Role**, twice:

- `crew`: description "Field crew". Under **Permissions → Add Permissions**, choose the API from step 2 and add the four crew permissions.
- `supervisor`: description "Supervisor". Add all eight permissions.

Name the roles `crew` and `supervisor`. Capitalization does not matter (`Supervisor` works); the spelling does.

## 4. Create the single-page application

**Applications → Applications → Create Application**, then choose **Single Page Web Applications**. For a new setup, name it `FORESITE Web`; reuse the published SPA in the working tenant instead of creating another for the rebrand.

On its **Settings** tab:

| Field | Local development value |
|---|---|
| Allowed Callback URLs | `http://localhost:5173, http://localhost:5173/auth-check.html` |
| Allowed Logout URLs | `http://localhost:5173, http://localhost:5173/auth-check.html` |
| Allowed Web Origins | `http://localhost:5173` |
| Refresh Token Rotation | turn on **Allow Refresh Token Rotation** |

Save, then note the **Client ID**. A single-page app has no client secret; do not create one.

Under **Connections**, keep **Username-Password-Authentication** enabled for this app. The demo accounts use it.

Deployed URLs are added in T081 once the Vultr URL exists. Use exact URLs, with no wildcards.

## 5. Add the roles claim (post-login Action)

Auth0 does not put role names in tokens by default. The app reads them from the custom claim `https://planit-control/roles`.

**Actions → Library → Create Action → Build from scratch**: name it `Add PlanIT roles`, choose trigger **Login / Post Login**, and paste:

```js
exports.onExecutePostLogin = async (event, api) => {
  const ns = 'https://planit-control/';
  const assigned = (event.authorization && event.authorization.roles) || [];
  // New accounts start as crew. Crew see nothing until they join a team with a
  // supervisor's join code. Supervisors are only ever assigned here in the dashboard.
  const roles = assigned.length ? assigned : ['crew'];
  api.idToken.setCustomClaim(ns + 'roles', roles);
  api.accessToken.setCustomClaim(ns + 'roles', roles);
  // Name and email for the supervisor's team roster (never used for access).
  if (event.user.email) api.accessToken.setCustomClaim(ns + 'email', event.user.email);
  if (event.user.name) api.accessToken.setCustomClaim(ns + 'name', event.user.name);
};
```

New accounts need no role assignment: they sign up, get `crew` from this Action, and join a team with a code their supervisor creates on the **Team** tab. Only supervisor accounts are assigned a role (Supervisor) in the dashboard, and an administrator links each to an organization (`DEMO_SUPERVISOR_USER_ID`, `BRIEFING_TEST_SUPERVISOR_USER_ID`). The backend gives the default `crew` role its permissions when the token's list is empty; a supervisor always needs its permissions assigned.

Click **Deploy**. Then open **Actions → Triggers → post-login**, drag `Add PlanIT roles` into the flow, and click **Apply**. Without this step, every user sees "No role assigned".

## 6. Environment variables

Backend (`backend/.env`, never committed):

```dotenv
AUTH0_DOMAIN=planit-control.us.auth0.com
AUTH0_AUDIENCE=https://api.planit-control
DEV_AUTH_BYPASS=false
```

Frontend (`frontend/.env.local`, never committed; all values are public):

```dotenv
VITE_AUTH0_DOMAIN=planit-control.us.auth0.com
VITE_AUTH0_CLIENT_ID=<Client ID from step 4>
VITE_AUTH0_AUDIENCE=https://api.planit-control
```

`VITE_AUTH0_AUDIENCE` must equal `AUTH0_AUDIENCE`, or the backend rejects every token with 401.

Without these values, the backend answers 503 for token-protected requests (it never lets requests through), and the frontend shows "Sign-in is not configured".

## 6a. Supervisor sign-up (role manager app)

A new account becomes a supervisor by redeeming a **supervisor key** that an existing supervisor creates on the Team tab, then naming its organization. The backend gives that account the `supervisor` role in Auth0, so nobody assigns roles by hand. It needs one machine-to-machine app, created once:

1. **Applications → Applications → Create Application**. Name it `FORESITE role manager` and choose **Machine to Machine Applications**.
2. Authorize it for the **Auth0 Management API** with only **`read:roles`** and **`create:role_members`**.
3. From its **Settings** tab, put the Client ID and Client Secret in `backend/.env` (and the server's `.env`) as `AUTH0_MGMT_CLIENT_ID` and `AUTH0_MGMT_CLIENT_SECRET`. Never commit them.

Flow: `POST /api/onboarding/supervisor` checks the key (one use, 7 days, revocable), asks Auth0 to add the user to the `supervisor` role, then creates the organization and the supervisor membership. If Auth0 refuses, nothing is saved and the key stays usable. The browser signs in again so the new role and permissions reach it. Without the app, the endpoint answers 503 `not_configured`.

## 7. Demo accounts

The demo needs one account per role (`spec.md` section 8). Create them in the dashboard. **Do not commit their emails, passwords, or user ids anywhere public.** Keep the passwords in the team's password manager or a private team chat.

1. **User Management → Users → Create User**, with connection **Username-Password-Authentication**:
   - Crew: an address the team controls, for example `yourteam+crew@gmail.com`, with a strong unique password.
   - Supervisor: for example `yourteam+supervisor@gmail.com`.
2. Open each user, then **Roles → Assign Roles**: give `crew` to the crew account and `supervisor` to the supervisor account.
3. Copy each user's **user_id** (it looks like `auth0|65f…`). The backend uses it to find the person's organization and team.
4. Link each account to an organization, and the crew account to a team, in the `memberships` table. Rudra's demo seed (T069) should do this from private configuration. To do it by hand on Tiger Data:

   ```sql
   -- Replace the placeholders. A crew membership needs a team; a supervisor's team_id is NULL.
   INSERT INTO memberships (id, user_id, organization_id, team_id, role) VALUES
     ('m-demo-crew', '<crew user_id>', '<organization id>', '<team id>', 'crew'),
     ('m-demo-supervisor', '<supervisor user_id>', '<organization id>', NULL, 'supervisor');
   ```

   Auth0 decides the role. The membership decides the organization and team. A signed-in user with no membership row gets no organization data.

### Check both roles

1. `cd frontend && npm run dev`, then open http://localhost:5173/auth-check.html.
2. Click **Sign in** and use the crew account. The page should show **Role: Crew**. The crew guard shows its content, and the supervisor guard shows "Not available for your role".
3. Click **Get access token**. It should report an access token with 4 permissions.
4. Sign out, sign in as the supervisor, and confirm **Role: Supervisor** and 8 permissions.

The backend tests (`backend/tests/test_security.py`) cover missing, invalid, expired, and valid tokens, and crew being refused supervisor actions, without a tenant.

## Public "Try demo" guests

`DEMO_GUEST_ENABLED=true` (the deployed server only; default `false`) lets anyone read the demo organization with no sign-in. A request **without** an `Authorization` header that sends `X-Demo-Role: crew` or `X-Demo-Role: supervisor` acts as `demo-guest|crew` (a crew member on the Everglades team) or `demo-guest|supervisor` (a supervisor of the demo organization). These are not Auth0 users; their memberships are written by `python -m app.demo freshen` and the server's demo-freshen loop.

- Guests may only read: sites, alerts, reports and photos within their scope, and briefings. Every other method is refused with 403, as are `/api/team` and `/api/supervisor-invites`.
- A request that sends a token is always validated normally; a guest header never upgrades it.
- The frontend's `/?demo` address uses this (`HttpClient.guest`), with every action shown as read-only.

## Local development without Auth0

Use this only on your own machine, for building screens before the tenant exists.

- Backend: `DEV_AUTH_BYPASS=true` in `backend/.env`. A request **without** an `Authorization` header may then send `X-Dev-Role: crew` or `X-Dev-Role: supervisor`. It is accepted only from `127.0.0.1` or `::1` with no proxy forwarding headers, and every use is logged as a warning. A request that sends a token is always validated normally.
- Frontend: `VITE_DEV_AUTH_ROLE=crew` (or `supervisor`) in `frontend/.env.local`. `useAuth()` then reports a fake local user with that role, and `getAuthHeaders()` returns the `X-Dev-Role` header. This only works on the Vite dev server (`npm run dev`), never in a production build.

Crew only see the site assigned to their team, so the dev crew user (`dev|crew`) sees no sites until it has a membership row in your local database:

```sql
INSERT INTO memberships (id, user_id, organization_id, team_id, role)
VALUES ('m-dev-crew', 'dev|crew', '<organization id>', '<team id with a site>', 'crew');
```

**Never set `DEV_AUTH_BYPASS=true` on Vultr or any shared server.** Keep it `false` in every deployed environment.

## Using the auth module in code

Frontend (`frontend/src/auth/`):

```tsx
import { AuthProvider, RequireRole, useAuth } from './auth'

// Once, near the root:
<AuthProvider><App /></AuthProvider>

// In a screen:
<RequireRole role="supervisor"><SupervisorMap /></RequireRole>

// In an API call:
const { getAuthHeaders } = useAuth()
fetch(`${API}/api/alerts`, { headers: await getAuthHeaders() })
```

`useAuth()` returns `user`, `role`, `isAuthenticated`, `isLoading`, `error`, `mode`, `login()`, `logout()`, `getAccessToken()`, and `getAuthHeaders()`.

Backend (`backend/app/security/`):

```python
from typing import Annotated
from fastapi import Depends
from app.security import AuthenticatedUser, CurrentUser, membership_for, require_permission, roles

@router.get("/api/alerts")
def list_alerts(user: AuthenticatedUser): ...

@router.post("/api/reports/{report_id}/review")
def review(user: Annotated[CurrentUser, Depends(require_permission(roles.REVIEW_REPORTS))]): ...
```

Responses: **401** missing, invalid, or expired token; **403** valid token without the role or permission (or with no FORESITE role); **503** Auth0 not configured or its keys unreachable. Scope checks such as "own organization only" use `membership_for(session, user)`. Treat `None` as no access.

## Security notes

- Tokens are RS256 only. The backend rejects HS256 and unsigned tokens, other tenants' tokens, and tokens for other APIs.
- When the access token has a `permissions` claim (RBAC on), it decides what the user may do. Without it, the backend falls back to the role's default permissions in `roles.py`.
- Session storage: the app keeps Auth0 tokens in `localStorage`, with refresh-token rotation, so a crew member's session survives a page reload on a phone. The cost is that malicious script on the page could read the tokens. Keep third-party scripts off the app. If that trade-off changes, switch `cacheLocation` to `memory` in `AuthProvider.tsx`; users then sign in again after each reload.
- Personal data: the app keeps only the Auth0 user id, name, and email in memory, and stores only the user id in the database.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Callback URL mismatch" on sign-in | Add the exact URL (including `/auth-check.html` for the check page) to Allowed Callback URLs. |
| Signed in, but "No role assigned" | Assign the role to the user, and check that the Action is deployed **and** in the post-login flow. Sign out and in again. |
| Backend 401 "Token is not valid for this API" | `VITE_AUTH0_AUDIENCE` and `AUTH0_AUDIENCE` differ, or `AUTH0_DOMAIN` points at another tenant. |
| Backend 403 "Missing permission" | The role is missing that permission on the API in Auth0 (step 3). |
| "Missing Refresh Token" in the browser | Turn on Allow Offline Access on the API and Refresh Token Rotation on the app. |
| Backend 503 "Auth0 is not configured" | Set `AUTH0_DOMAIN` and `AUTH0_AUDIENCE` in `backend/.env` and restart. |
