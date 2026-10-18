# Landing and Auth0 login logos

The dark public landing page (`/landing.html`) uses the transparent white-letter
wordmark: `/foresite-wordmark.png?v=daaf5322`.

Auth0's hosted light login card should use the **normal navy-letter logo**, not the
white app artwork. The prepared public file is `frontend/public/foresite-logo-light.png`.
It is the approved 1200×300 transparent full logo copied unchanged from original
branding commit `4508e9d`; SHA-256:
`05a688ff75edc55538eb2343ffa038aea76d3a0bea7aef604b95848c9cd60fd3`.
The generator validates its exact bytes and includes it in the asset hash manifest.

## Copy to Braydin after the frontend change is deployed

URL suffix:

```text
/foresite-logo-light.png?v=05a688ff
```

Full public HTTPS logo URL:

```text
https://foresiteoperations.org/foresite-logo-light.png?v=05a688ff
```

First open that URL without signing in and confirm it returns the PNG (HTTP 200),
not the SPA HTML fallback. The new file is not on production until its frontend
release completes. Use the full HTTPS URL in Auth0, not localhost or a repository path.

In the existing tenant, update the logo URL in **Settings → General → Settings →
Logo URL**, and the **Branding → Universal Login → Customization Options → Widget →
Logo URL** field if it is configured. Auth0 documents both locations in its
[logo-update troubleshooting guide](https://support.auth0.com/center/s/article/Logo-not-updating).
Retain the existing light widget appearance. Change only the logo setting; no new
tenant, app, credentials, callbacks, connections, roles or permissions are needed.

Verify in a private browser window: open the landing page, click Sign in, and check
the real Auth0 page displays the navy lettering. Do not enter or store passwords in
test scripts or screenshots. The public landing page and hosted login are separate
systems: updating repository images alone does not change an Auth0 logo URL.

## Current verification boundary

The user clarified that they do not have Auth0 management access and requested the
asset URL to give Braydin. No hosted tenant setting is changed by this implementation.
Available local configuration supports normal sign-in, with no management credentials;
no Auth0 connector was available. No management privileges were provisioned.

Local checks verify decoded white/navy images and genuine alpha, responsive landing
layout, keyboard focus, both existing `/?signin` targets, production static-file
packaging and deterministic asset hashes. These do not claim the hosted Auth0 image
or real-account sign-in has already been changed or verified.
