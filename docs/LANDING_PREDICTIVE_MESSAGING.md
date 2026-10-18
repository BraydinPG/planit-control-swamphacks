# Predictive-intelligence landing page

Verified 2026-10-18 on `feature/cache-predictive-landing-messaging`, based on main
`d801615`. This is a public landing-page content/presentation change only.

Current location: the [Data & Research guide](LANDING_RESEARCH_SECTION.md) documents
independent `/data.html`. Research charts and source disclosures have moved off the
homepage; its hero/statistics/features remain intact. Both public pages share the
same header, typography and atmosphere. The latest dashboard addendum requests a
reviewable PR without automatic merge.

The headline is **SEE THE RISK.** followed by **PLAN BEYOND THE ALERT.** The eyebrow
is **FORESITE · PREDICTIVE WORKSITE INTELLIGENCE**. The requested description and
the three Live intelligence, Predictive analytics and Connected operations blocks
are preserved verbatim in [landing.html](../frontend/public/landing.html).

The existing dark/red atmosphere, transparent hurricane wordmark, header,
fog/lightning shader and counter JavaScript remain. Explore Live Demo still opens
`/?demo#/crew/overview`; both Sign In links open `/?signin`. The existing application
decides between its configured guest demo and bundled fixture mode. No changes to
Auth0, dashboards, API contracts, alerts, scoring, models or deployment are included.

## Statistic audit

No requested number needed replacement. The Research scope and sources disclosure on the separate Data page explains the denominators and limitations and links to existing research.

| Display | Verified basis | Scope |
| --- | --- | --- |
| **526K+** Historical weather records analyzed | 349,030 NOAA rows in [EVALUATION](../ml/EVALUATION.md), 122,270 hourly station measurements in [DISASTER_COVERAGE](../ml/DISASTER_COVERAGE.md), and 55,524 full-archive NHC track points in [hurdat_coverage.json](../ml/reports/multidisaster/hurdat_coverage.json): **526,824 total**. | Heterogeneous source records, not independent training examples. NHC best tracks are post-analysis records, not issued operational forecasts. |
| **6** Backtested event-duration targets | [EVENT_OUTLOOKS](../ml/EVENT_OUTLOOKS.md) and [registry.json](../ml/reports/multidisaster/registry.json): Flood, Flash Flood, High Wind, Heavy Rain, Winter Storm, Heat Index Exceedance. | Retrospective research for already-active events; heat research is restricted to evaluated stations. No operational safety certification or universal hazard prediction. |
| **5,000** Monte Carlo simulations | [monte_carlo_summary.json](../ml/reports/purged_v2/monte_carlo_summary.json): 5,000 draws, seed 42, one offline flood-model experiment. | Distribution/sampling consistency, not independent predictive validation or a live simulation UI. This historical experiment does not change the currently selected models. |
| **50+** Mapped infrastructure locations | [eia_coverage.json](../ml/reports/worker_outlook/eia_coverage.json): 50 selected research reference locations. | At least 50 mapped representative EIA sites; no assertion of active work orders, crews or complete current observations at every site. |

The disclosure distinguishes deterministic alerts/the 0–10 index from conditional
ML outlooks. Gemini supplies summaries/suggestions; human review retains decision
authority. Neither predictions nor AI suggestions authorize work or clear alerts.

## Presentation and verification

The hero retains its oversized bold/thin hierarchy. Desktop/tablet statistics use
four columns; phones use two. Feature blocks stack on phones. Natural scrolling
replaces the former fixed-height page so the new section and complete description
remain accessible on short screens. Reduced-motion styling now removes entrance
animations explicitly: the previous competing delay selectors could leave copy
temporarily invisible. Default animation JavaScript is unchanged.

Commands run from `frontend/` with the existing Node 24 environment:

```powershell
node --test tests/*.test.mjs
npm.cmd run lint
npm.cmd run build
```

- **198 frontend tests pass**, lint passes; the production command passes TypeScript
  and the default/live Vite build. A separate explicit-fixture production build also
  passes. Existing bundle-size and build-plugin timing advisories remain.
- Edge/CDP checks and visual screenshot inspection pass at **1440, 768, 390 and
  320px**: headline/description/statistic text visible, no clipping/horizontal
  overflow, correct logo/aspect ratio, preserved CTA URLs and 44px controls.
- Additional checks cover a short 320×568 screen with fallback fonts, reduced
  motion, settled animated counters, the research disclosure and actual navigation
  through Explore Live Demo to the existing Simulated demo application.
- No browser exceptions, console errors or actual backend API requests occurred.
  This is local landing/demo acceptance, not live Auth0 or service acceptance.
- Backend/ML tests and training were not rerun: none of their code or inputs changed.
  No task checkboxes are changed.

Review captures: [desktop](landing-messaging/1440.png),
[tablet](landing-messaging/768.png), [phone](landing-messaging/390.png),
[narrow phone](landing-messaging/320.png),
[browser measurements](landing-messaging/acceptance.json).

Rudra owns subsequent UI integration; preserve the existing destinations and the
research qualifiers. No action is required from Braydin for this change. The user's
follow-up explicitly requests merging the verified PR, superseding the attachment's
earlier instruction to leave it open. The implementation commit and PR remain
traceable through this document's Git history.
