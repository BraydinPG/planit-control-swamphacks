# Current FORESITE logo

The approved replacement is the white FORESITE wordmark, cyan/blue cyclone and
silver-white **INTELLIGENT WORKSITE OPERATIONS** tagline supplied on 2026-10-18.

`foresite-logo-source.png` is the unmodified 1983×793 RGB upload, including its dark
background. Its SHA-256 is
`2f14dd3437f22fe1ef9c420f0edc7b86878ddb6fec9144540c77caa9aa90d3db`.
It is retained here for reproducibility, not served as the app logo.

The transparent download is [public/foresite-logo.png](../public/foresite-logo.png).
Its SHA-256 is
`daaf53225c030bb152e04b084b49ab210929f4d44db6191b4b574130dccb25e8`.
The complete authoritative output hashes are in
[foresite-brand-assets.json](../public/foresite-brand-assets.json).

## Pixel cutout

The user explicitly approved a pixel-based cutout after two built-in imagegen edits
introduced artifacts. Neither generated draft is used in the repository.
[prepare-brand-assets.py](../scripts/prepare-brand-assets.py) changes alpha, retaining
the supplied RGB at every remaining foreground pixel. Fully removed pixels have zero
RGB as well as zero alpha. No new lettering, symbol, white outline, plate or filter is
generated.

The fixed source's measured background channels are 9–18. Alpha transitions from
transparent at max-channel 18 to opaque at 32, keeping its antialiased edges and dark
blue arms. The enclosed cyclone eye is removed with a bounded connected-region mask
(2,624 source pixels); letter counters/gaps key out with the background. These pinned
coordinates and settings are specific to this approved image, not a generic uploader.

Derived assets preserve aspect ratios and existing display sizes:

| Asset in `frontend/public/` | Size | Use |
|---|---:|---|
| `foresite-logo.png` | 1983×793 | Full-resolution transparent download |
| `foresite-logo-full.png` | 1200×300 | Full logo/tagline, footer and sign-in |
| `foresite-logo-light.png` | 1200×300 | Approved navy-letter variant for Auth0's light hosted widget |
| `foresite-wordmark.png` | 768×166 | Header and sidebar |
| `foresite-cyclone.png` | 384×384 | Compact symbol |
| `foresite-favicon-16.png`, `foresite-favicon-32.png` | 16/32 | Transparent browser icons |
| `foresite-favicon.ico` | 16/32/48 | Browser compatibility |
| `foresite-apple-touch-icon.png`, `foresite-icon-192.png` | 180/192 | Mobile icons |
| `foresite-social.png` | 1200×630 | Social preview on an explicit dark presentation canvas |

All logo/icon PNGs have real transparency. The social preview alone has a dark
presentation canvas so white lettering survives sharing-platform previews.

## Reproduce

Assets are committed; normal frontend builds require no image-processing dependency.
Optional developer-only regeneration, from repository root in Windows PowerShell:

```powershell
python -m venv frontend\.shell-check\logo-tools
.\frontend\.shell-check\logo-tools\Scripts\python.exe -m pip install Pillow==13.0.0
.\frontend\.shell-check\logo-tools\Scripts\python.exe frontend/scripts/prepare-brand-assets.py
```

The source hash, eye mask and dimensions are checked. Output is deterministic with
the pinned Pillow version. Manifest hashes, transparent corners/eye, alpha ranges
and original visible RGB were verified. Existing entrypoints and `Brand.tsx` use
`?v=daaf5322` to refresh old cached artwork.

## Integration and review

The standalone dark landing page also uses the current white wordmark. Its sign-in
links still target `/?signin`. The separate `foresite-logo-light.png` is the unmodified
approved original full logo from commit `4508e9d`, pinned/validated in the generator;
it is used only where navy lettering is required on a light background. See the
[Auth0 branding handoff](../../auth/BRANDING.md) for its public URL and owner steps.

The existing `Brand` component updates header/sidebar/home links, footer, app-owned
sign-in/loading/access panels and the auth-check page. The team's always-dark theme
(PR64) provides contrast; no separate theme or auth behavior change is introduced.
Existing compact/full sizes, touch targets, alt text and home links are retained.

Verification on incorporated main `0605e7b`: 177 frontend tests, lint, TypeScript,
live/demo builds, Python asset-script lint/format, deterministic asset checks and
focused installed-Edge branding checks pass. Browser checks cover all 11 demo
destinations at 1440/768/390/320 in development and built-demo mode, actual image alpha,
metadata assets, OS light/dark sign-in appearance and mocked Sign out contrast.
No browser exceptions or real API calls. Existing bundle-size warnings remain.
Backend tests and the full report-mutation browser suite were not rerun for this
asset-only change. Screenshots are in [docs/branding](../../docs/branding/).

Rudra reviews asset placement/cache refresh; Braydin coordinates any externally
hosted Auth0 Universal Login logo through the existing tenant process. That external
page is not configured here. After normal frontend release, the public full logo is
`/foresite-logo-full.png?v=daaf5322`. No credentials, contracts, scoring, ML, backend,
deployment or task checkboxes change. No automatic merge is authorized.
