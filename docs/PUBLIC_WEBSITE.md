# FORESITE public website

User-authorized scope, 2026-10-18: complete About, documentation access, shared
public navigation/footer and metadata, change mapped-location copy to **250**,
and **remove Case Study**. The user's later removal instruction supersedes the
attachment's five-page navigation and Case Study resource request. The direct
message authorizes merge after verification, superseding its original merge hold.
Branch: `feature/cache-about-public-completion`, base main `5b27687`.

## Current public documents

- `/landing.html`: existing hero, three features and demo/sign-in destinations;
  mapped-infrastructure statistic now reads 250, including its animation target.
- `/platform.html`: existing interactive architecture; content unchanged.
- `/data.html`: existing research dashboard; content/exports unchanged.
- `/about.html`: project narrative, documented team contributions, engineering
  process, eight resource cards, safety context and technical data-handling overview.

The logo remains the Home link. Desktop header: logo/Home, Platform, Data, About,
Sign In. A non-modal phone disclosure retains 44px controls, focuses the first
link on opening, closes on Escape with focus restored, closes when focus leaves
or the visitor clicks outside, and resets at the desktop breakpoint. Without JS,
the complete navigation remains visible in two header rows. Footer groups are
Explore, Resources and FORESITE, identical on all four documents.

The Case Study narrative, script, CSS, public captures and scenario-only tests are
removed. `/case-study.html` is only a noindex static redirect to About, so an old
link does not fall through to the authenticated SPA. Historical implementation
details remain in archived `CASE_STUDY.md` and PR94; no active page links there.

## One source for public chrome

`frontend/scripts/public-chrome.mjs` owns the four page definitions, exact header,
footer and metadata. `prepare-public-chrome.mjs` writes marked blocks in the static
HTML. The built documents remain complete without JS or a backend; no runtime
HTML fetch or second app/server is introduced.

```powershell
Set-Location C:\Users\cache\planit-control-functional\frontend
node scripts/prepare-public-chrome.mjs
node scripts/prepare-public-chrome.mjs --check
```

The script is idempotent, and tests compare every marked block against its source.
Use it after public navigation/metadata changes; no package/lockfile/build-hook
change is needed. Page-specific content/styles remain independent. Metadata
includes unique titles/descriptions, canonical URLs, Open Graph fields and the
existing approved 1200×630 `foresite-social.png`; Twitter uses a large-image card.
The browser-only `public-navigation.js` has no API, auth or storage dependencies.

## Claims and sources

| Public description | Inspected source / boundary |
|---|---|
| SwampHacks 2026 project and supporting question | User's approved About brief; no award, track qualification or external endorsement claimed |
| Cache: duration research, simulations, evaluation, multi-disaster models, deterministic algorithm | `AGENTS.md` current ownership; `tasks.md` ML lane, T051A and T071; historical frontend contributions remain credited in the backlog |
| Rudra: backend, contracts, alert orchestration, persistence, current frontend/integration responsibility | `AGENTS.md` current ownership; backend/integration task lane |
| Braydin: identity, Tiger Data, services, Gemini, storage provisioning, deployment | `AGENTS.md`; T078–T082; `deploy/README.md` |
| Nick: app shell and completed confirmation/instruction/report-score work | Unchanged completed attribution in T030, T054, T054A, T055; not reassigned current frontend work |
| Feature branches, reviewable PRs, contracts, tests and repeatable research | `AGENTS.md`, `tasks.md`, existing PR history, frontend/backend tests and research reports; no claim that every task or deployed acceptance gate is complete |
| Auth0 plus backend permissions/membership checks | `backend/app/security/dependencies.py`, `membership.py`, `roles.py`; frontend guards do not authorize requests |
| Tiger Data stores site/report/review state | `backend/app/db/models.py`, report/hazard services and protected API routes |
| Private production photo objects / private local development storage | `backend/app/storage/photos.py`; `backend/app/api/reports.py` authorizes report-photo reads |
| Report analysis can send photo, category, present/absent answer, note and site context to Gemini; report location excluded | `backend/app/gemini/report_analysis.py`; generated enrichment never confirms a report or modifies scoring |
| 250 mapped infrastructure locations | Explicit user-provided current public display figure; not a new remote database audit, live-coverage count or active-work-order claim |

Only documented first names and contributions are published. Initials are designed
monograms, not fabricated portraits. No private contact data, biographies,
credentials, full names, certifications or professional titles are invented.

### Location count versus research sample

The old public marketing statistic was `50+`. It is now **250**, with no `+` suffix.
The dedicated research export's `reference_sites: 50` is an archived research-sample
count and stays intact, as do all model statistics, Monte Carlo draws, chart data,
historical acceptance counts and backlog minimums. These are different quantities.
No database, EIA selector, research corpus or fixture inventory is altered to make
the display number true. Unit/browser checks guard the new statistic and preserved
historical export separately.

## Working resources and scope

All 14 unique GitHub links on About returned HTTP 200 during this run (repository,
task/ownership records, merged PR list, frontend tests, deployment guide,
methodology, multi-disaster evaluation, Flood evaluation, offline Monte Carlo
artifact, multi-event integration guide, authorization, photo storage and report
analysis). Tests also resolve local resources and fragments and verify that
repository file/tree destinations exist in this checkout.

Methodology and Flood evaluation explicitly preserve the baseline scope and link
to extensions. The Monte Carlo resource is a raw offline artifact; it is not an
operational simulation UI. Technical setup/deployment guides are developer
references, not polished end-user manuals or fresh production-acceptance reports.

No final Devpost URL was found in the approved repository documentation. It is
omitted from the footer; About says it will be added after team publication. Rudra
can supply the final public URL separately. Formal privacy policy/terms, retention
and provider/data-sharing disclosures need team review. The page labels its
data-handling text as a technical overview and makes no legal-completeness,
retention, certification, guaranteed-safety or independent-operational-skill claims.

## Reproduce the checks

Existing Node 24, frontend dependencies and installed Edge; no service credentials:

```powershell
Set-Location C:\Users\cache\planit-control-functional\frontend
node scripts/prepare-public-chrome.mjs --check
node --test tests/*.test.mjs
npm.cmd run lint
.\node_modules\.bin\tsc.cmd -b
npm.cmd run build
# Serve the built files in a separate terminal on an available owned port:
npm.cmd run preview -- --host 127.0.0.1 --port 5182 --strictPort
# From the first terminal:
node scripts/check-public-pages.mjs http://127.0.0.1:5182/
```

For the existing fixture-mode demonstration, set `$env:VITE_USE_FIXTURES='true'`
in a dedicated build/dev terminal; use `--fixtures` with the browser command.
Live and fixture builds serve the same static public documents. Guest-demo entry
is checked in fixture mode without claiming authenticated or database acceptance.
Keep other checkouts, environment files, servers and browser sessions untouched.

## Team handoff

Initial feature verification at base `5b27687`: 203 frontend tests, lint,
TypeScript, development and live/fixture production public-browser checks pass
at 1440/768/390/320 with no exceptions, clipping or API requests. The existing
SPA chunk-size warning remains. Teammate main `66902bd` is being reconciled and
the final combined tree will be checked before publication.

Cache's explicit public-site scope touches public HTML/CSS/JS, the existing public
browser harness, static-document tests, shared-chrome generator and coordination
docs only. Rudra maintains those files and can provide the final Devpost URL.
Braydin's identity/database/services/deployment behavior is unchanged; no new route
or infrastructure is needed to serve these existing static build outputs. Models,
scoring, canonical API contracts/fixtures, application components, dependencies,
credentials and task states remain untouched. This does not complete live
T063–T068, T070, T081/T083 or the team's remaining acceptance tasks.
