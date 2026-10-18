import { lazy, Suspense, useCallback, type ReactNode } from 'react'
import type {
  CriticalHabitatArea,
  MatchBasis,
  SiteDetail,
  SiteSpeciesContext,
  SpeciesEntry,
  WildlifeReportRef,
} from '../../types/api'
import { useApplication, useResource } from '../../application/context'
import { card } from './Interaction'
import { RiskShape } from './Risk'
import { Status, Timestamp } from './Status'
import { Icon } from '../shell/Icon'
import { arrangeWildlife, type Relevance, type WildlifeRow } from './wildlife'
import { Details } from './Details'
const SiteMap = lazy(() =>
  import('./SiteMap').then((m) => ({ default: m.SiteMap })),
)

// Read-only field awareness. Nothing here feeds the score, alerts or clearance, and
// a regional range is never shown as a sighting.

const matchLabels: Record<MatchBasis, string> = {
  regional_range: 'Known regional range/habitat',
  possible_regional_context: 'Possible regional context',
  confirmed_report: 'Confirmed crew report',
  unknown: 'Unknown',
}
const confirmationLabels: Record<WildlifeReportRef['confirmation'], string> = {
  confirmed: 'Confirmed by supervisor review',
  pending: 'Pending review — not confirmed',
  rejected: 'Rejected in review',
}
const nameOf = (s: {
  common_name: string | null
  scientific_name: string | null
}) => (s.common_name ?? s.scientific_name ?? 'Unnamed species').replace(/=\s*/g, '')

/** Loads and shows species context for a site with an assigned team. */
export function SpeciesSection({ site }: { site: SiteDetail }) {
  const { client } = useApplication()
  const result = useResource(
    `species:${site.id}`,
    useCallback(
      () => client.species(site.id).then((context) => ({ context })),
      [client, site.id],
    ),
  )
  if (!site.assigned_team) return null
  return (
    <section className="space-y-3" aria-labelledby="species-title">
      <div>
        <p className="kicker mb-1">Regional wildlife and habitat</p>
        <h2 id="species-title" className="text-lg font-bold tracking-tight">
          Local species
        </h2>
      </div>
      {result.error ? (
        <p
          role="alert"
          className="rounded-2xl border-2 border-stop bg-surface p-4 text-sm"
        >
          Species information could not be loaded: {result.error}. This does not
          mean no species are present.
        </p>
      ) : !result.data ? (
        <p role="status" aria-live="polite" className="kicker">
          Loading species context…
        </p>
      ) : result.data.context ? (
        <SpeciesPanel context={result.data.context} site={site} />
      ) : (
        <Muted>Species context is shown only for sites with a team.</Muted>
      )}
    </section>
  )
}

export function SpeciesPanel({
  context,
  site,
}: {
  context: SiteSpeciesContext
  site: Pick<SiteDetail, 'id' | 'name' | 'lat' | 'lon'> & Partial<SiteDetail>
}) {
  const { animals, plants, otherHabitat } = arrangeWildlife(context)
  const unavailable = context.data_state === 'unavailable'
  return (
    <div className="space-y-4">
      <p
        className="flex items-start gap-2.5 rounded-2xl border-2 border-warn bg-warn/10 p-4 text-sm font-medium text-ink"
        data-testid="species-caveat"
      >
        <RiskShape kind="caution" className="mt-0.5 size-4 shrink-0" />
        <span>
          Regional context, not a sighting. Local wildlife remains unverified;
          this does not clear work.
        </span>
      </p>

      <WildlifeReports reports={context.wildlife_reports} />

      {unavailable ? (
        <p
          role="alert"
          className="rounded-2xl border-2 border-stop bg-surface p-4 text-sm font-semibold"
        >
          Species information is unavailable right now. This does not mean no
          species are present. Follow your site's wildlife procedures.
        </p>
      ) : !context.species.length ? (
        <Muted>
          IPaC listed no federally listed species for this area. Species that
          are not federally listed are never included, so this does not mean no
          wildlife is present.
        </Muted>
      ) : (
        <>
          <Wildlife rows={animals} context={context} />
          <SpeciesGroup title="Listed plants" rows={plants} />
        </>
      )}

      <HabitatMap context={context} site={site} other={otherHabitat} />

      <footer className="border-t border-line pt-3 text-xs text-muted">
        <p className="flex flex-wrap items-center gap-2">
          <Status state={context.data_state} />
          <span>Source: {context.source}</span>
          {context.simulated && <span>Recorded demo snapshot</span>}
          <span>Retrieved <Timestamp value={context.fetched_at} /></span>
        </p>
        <Details title="Species sources and coverage">
          <p>{context.caveat}</p>
          <p>{context.footprint_description}</p>
          <p>Wording: {context.generated_by === 'gemini'
            ? (context.simulated ? 'recorded Gemini response, checked line by line against the sources below' : 'Gemini, checked line by line against the sources below')
            : 'deterministic template'}.</p>
        </Details>
      </footer>
    </div>
  )
}

function WildlifeReports({ reports }: { reports: WildlifeReportRef[] }) {
  return (
    <div className="space-y-2">
      <p className="text-sm text-muted">
        Crew reports are separate from regional habitat records. Species
        identity is unverified.
      </p>
      {reports.length ? (
        <ul className="space-y-2">
          {reports.map((r) => (
            <li
              key={r.report_id}
              className={`${card} flex flex-wrap items-start gap-x-3 gap-y-1 border p-3 text-sm ${
                r.confirmation === 'confirmed'
                  ? 'border-ink'
                  : 'border-dashed border-line-strong'
              }`}
            >
              <span className="inline-flex items-center gap-1.5 font-semibold">
                <Icon
                  name={r.confirmation === 'confirmed' ? 'check' : 'clock'}
                  className="size-4"
                />
                {confirmationLabels[r.confirmation]}
              </span>
              <span className="text-ink-2">
                {r.hazard_present
                  ? 'Hazard marked present'
                  : 'Marked no hazard'}{' '}
                · <Timestamp value={r.reported_at} />
              </span>
              {r.note && <span className="w-full text-ink-2">“{r.note}”</span>}
            </li>
          ))}
        </ul>
      ) : (
        <Muted>No crew wildlife reports supplied for this site.</Muted>
      )}
    </div>
  )
}

const relevanceLabels: Record<
  Relevance,
  { label: string; shape: 'stop' | 'caution' | 'nodata' }
> = {
  crew_hazard: { label: 'Direct crew hazard', shape: 'stop' },
  work_impact: { label: 'Affects work at this site', shape: 'caution' },
  background: { label: 'Listed for the area', shape: 'nodata' },
}

/** Every listed animal in one list, most relevant to the job site first. */
function Wildlife({
  rows,
  context,
}: {
  rows: WildlifeRow[]
  context: SiteSpeciesContext
}) {
  if (!rows.length) return null
  const hazards = rows.filter((r) => r.relevance === 'crew_hazard').length
  return (
    <details className={`${card} group`}>
      <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-3 px-4 text-base font-bold">
        <span>
          Wildlife ({rows.length})
          {hazards > 0 && (
            <span className="ml-2 text-sm font-semibold text-stop-text">
              {hazards} direct crew {hazards === 1 ? 'hazard' : 'hazards'}
            </span>
          )}
        </span>
        <Icon
          name="back"
          className="size-5 -rotate-90 transition-transform group-open:rotate-90"
        />
      </summary>
      <p className="border-t border-line px-4 pt-3 text-sm text-muted">
        Ordered by relevance to this job site: direct crew hazards first, then
        animals whose habitat or guidance affects work here, then the rest.
      </p>
      <ol className="space-y-2 p-3">
        {rows.map((row) => (
          <li key={row.species.id}>
            <WildlifePane
              row={row}
              habitatState={context.critical_habitat_state}
            />
          </li>
        ))}
      </ol>
    </details>
  )
}

export function WildlifePane({
  row: { species: s, habitat, relevance, reasons },
  habitatState,
}: {
  row: WildlifeRow
  habitatState: SiteSpeciesContext['critical_habitat_state']
}) {
  const level = relevanceLabels[relevance]
  const red = relevance === 'crew_hazard'
  return (
    <article
      aria-label={`${nameOf(s)}: ${level.label}`}
      data-relevance={relevance}
      className={`space-y-3 rounded-xl p-3 text-sm ${
        red ? 'border-2 border-stop bg-stop/5' : 'border border-line'
      }`}
    >
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h4 className="text-base font-bold text-ink">{nameOf(s)}</h4>
          <p className="text-muted">
            {s.common_name && s.scientific_name && (
              <i className="mr-1">{s.scientific_name}</i>
            )}
            {s.group && `· ${s.group}`}
          </p>
        </div>
        <p
          className={`chip inline-flex items-center gap-1.5 border font-semibold ${
            red ? 'border-stop text-stop-text' : 'border-line-strong text-ink-2'
          }`}
        >
          <RiskShape kind={level.shape} className="size-3.5" />
          {level.label}
        </p>
      </header>
      {reasons.length > 0 && (
        <p className="text-ink-2">Why: {reasons.join(' · ')}</p>
      )}
      <p className="text-ink">
        {s.summary}{' '}
        <span className="text-sm text-muted">
          ({s.summary_by === 'gemini' ? 'Gemini wording' : 'template'})
        </span>
      </p>
      <div className="grid gap-2 @3xl:grid-cols-3">
        <Protection species={s} />
        <Habitat species={s} areas={habitat} state={habitatState} />
        <Encounter species={s} />
      </div>
    </article>
  )
}

function Protection({ species: s }: { species: SpeciesEntry }) {
  const p = s.protection
  return (
    <section className="rounded-lg bg-surface-2 p-3">
      <h5 className="kicker mb-1">Protection status</h5>
      {p ? (
        <>
          <p className="font-semibold text-ink">
            {p.status ?? 'Protection status unknown'}
          </p>
          <p className="text-ink-2">{p.jurisdiction}</p>
          <SourceLink href={p.source_url} label={p.source}>
            As of <Timestamp value={p.as_of} />
          </SourceLink>
        </>
      ) : (
        <p className="text-ink-2">Unknown: no protection record supplied.</p>
      )}
    </section>
  )
}

function Habitat({
  species: s,
  areas,
  state,
}: {
  species: SpeciesEntry
  areas: CriticalHabitatArea[]
  state: SiteSpeciesContext['critical_habitat_state']
}) {
  const here = s.protection?.critical_habitat_here
  return (
    <section className="rounded-lg bg-surface-2 p-3">
      <h5 className="kicker mb-1">Habitat</h5>
      <p className="text-ink">{matchLabels[s.match_basis]}, not a sighting.</p>
      <p className="text-ink-2">
        Critical habitat at this location:{' '}
        {here === null || here === undefined
          ? 'unknown'
          : here
            ? 'yes, per IPaC'
            : 'not per IPaC'}
      </p>
      {areas.map((a) => (
        <div key={a.id} className="mt-1.5">
          <p className="font-semibold text-ink">
            {a.status ?? 'Status unknown'} critical habitat within about 3 km
          </p>
          <p className="text-ink-2">
            {a.federal_register
              ? `Federal Register ${a.federal_register}`
              : 'Citation not supplied'}{' '}
            · published {a.published ?? 'date unknown'}
          </p>
          {a.geometry_note && <p className="text-muted">{a.geometry_note}</p>}
          <SourceLink href={a.source_url} label={a.source} />
        </div>
      ))}
      {state === 'unavailable' && (
        <p className="mt-1.5 text-ink-2">
          Critical habitat map unavailable; nearby boundaries unknown.
        </p>
      )}
    </section>
  )
}

function Encounter({ species: s }: { species: SpeciesEntry }) {
  const e = s.encounter
  return (
    <section className="rounded-lg bg-surface-2 p-3">
      <h5 className="kicker mb-1">Encounter guidance</h5>
      {e ? (
        <>
          <p className="text-ink">
            {e.hazard ?? 'The cited source does not describe a worker hazard.'}
          </p>
          <ul className="mt-1.5 list-disc space-y-1 pl-5 text-ink">
            {e.actions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
          {e.contact && (
            <p className="mt-1.5 font-semibold text-ink">
              Contact: {e.contact}
            </p>
          )}
          <p className="mt-1.5 text-sm text-muted">
            {e.review_status === 'pending_review'
              ? 'Curated from the cited source; pending safety-lead review. Your site procedures come first.'
              : `Reviewed by ${e.reviewed_by ?? 'safety lead'}.`}
          </p>
          <SourceLink href={e.source_url} label={e.source} />
        </>
      ) : (
        <p className="text-ink-2">
          Not reviewed. Unknown — this does not mean the species is harmless.
        </p>
      )}
    </section>
  )
}

function SpeciesGroup({
  title,
  rows,
}: {
  title: string
  rows: SpeciesEntry[]
}) {
  if (!rows.length) return null
  return (
    <details className={`${card} group`}>
      <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-3 px-4 text-base font-bold">
        {title} ({rows.length})
        <Icon
          name="back"
          className="size-5 -rotate-90 transition-transform group-open:rotate-90"
        />
      </summary>
      <ul className="divide-y divide-line border-t border-line px-4">
        {rows.map((s) => (
          <li key={s.id} className="py-3 text-sm">
            <p className="font-semibold text-ink">
              {nameOf(s)}{' '}
              {s.common_name && s.scientific_name && (
                <i className="font-normal text-muted">{s.scientific_name}</i>
              )}
            </p>
            <p className="text-ink-2">
              Protection: {s.protection?.status ?? 'unknown'} (
              {s.protection?.jurisdiction ?? 'jurisdiction unknown'}) ·{' '}
              {matchLabels[s.match_basis]}, not a sighting · Encounter guidance:
              not reviewed
            </p>
            {s.protection?.source_url && (
              <SourceLink href={s.protection.source_url} label="ECOS profile" />
            )}
          </li>
        ))}
      </ul>
    </details>
  )
}

/** The boundary map. Animal habitat details live in each Wildlife pane. */
function HabitatMap({
  context,
  site,
  other,
}: {
  context: SiteSpeciesContext
  site: Pick<SiteDetail, 'id' | 'name' | 'lat' | 'lon'> & Partial<SiteDetail>
  other: CriticalHabitatArea[]
}) {
  const drawn = context.critical_habitat.filter((a) => a.geometry)
  return (
    <section
      aria-labelledby="critical-habitat-map"
      className={`${card} space-y-3 border-2 border-line-strong p-4`}
    >
      <h3
        id="critical-habitat-map"
        className="flex flex-wrap items-center gap-2 text-xl font-bold tracking-tight"
      >
        <Icon name="layers" className="size-6 text-accent" />
        Critical habitat map
        <Status state={context.critical_habitat_state} />
      </h3>
      <p className="text-sm text-muted">
        {context.critical_habitat_source}, within about 3 km. A boundary is
        legal habitat designation, not a sighting. Each animal's habitat is
        listed in its Wildlife pane.
      </p>
      {context.critical_habitat_state === 'unavailable' ? (
        <p role="alert" className="text-sm font-semibold">
          Critical habitat boundaries are unavailable. This does not mean there
          is none.
        </p>
      ) : !context.critical_habitat.length ? (
        <Muted>
          The map service returned no critical habitat within about 3 km.
        </Muted>
      ) : (
        other.length > 0 && (
          <ul className="space-y-2" aria-label="Other critical habitat nearby">
            {other.map((a) => (
              <HabitatRow key={a.id} area={a} />
            ))}
          </ul>
        )
      )}
      {drawn.length > 0 && (
        <Suspense
          fallback={
            <p role="status" className="kicker">
              Loading map…
            </p>
          }
        >
          <SiteMap
            sites={[toSummary(site)]}
            select={() => {}}
            habitat={drawn}
          />
        </Suspense>
      )}
    </section>
  )
}

function HabitatRow({ area: a }: { area: CriticalHabitatArea }) {
  return (
    <li className={`${card} border border-line p-3 text-sm`}>
      <p className="font-semibold text-ink">
        {nameOf(a)} · {a.status ?? 'status unknown'} critical habitat
      </p>
      <p className="text-ink-2">
        Species listed {a.listing_status ?? 'status unknown'} ·{' '}
        {a.federal_register
          ? `Federal Register ${a.federal_register}`
          : 'citation not supplied'}{' '}
        · published {a.published ?? 'date unknown'}
      </p>
      {a.geometry_note && <p className="text-muted">{a.geometry_note}</p>}
      <SourceLink href={a.source_url} label={a.source} />
    </li>
  )
}

function SourceLink({
  href,
  label,
  children,
}: {
  href: string | null
  label: string
  children?: ReactNode
}) {
  return (
    <p className="mt-1 text-sm text-muted">
      Source:{' '}
      {href ? (
        <a
          href={href}
          target="_blank"
          rel="noreferrer noopener"
          className="inline-flex min-h-11 items-center font-semibold text-ink underline"
        >
          {label}
        </a>
      ) : (
        label
      )}
      {children && <> · {children}</>}
    </p>
  )
}

function Muted({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-2xl border border-dashed border-line-strong p-4 text-sm text-ink-2">
      {children}
    </p>
  )
}

function toSummary(
  site: Pick<SiteDetail, 'id' | 'name' | 'lat' | 'lon'> & Partial<SiteDetail>,
) {
  return {
    id: site.id,
    name: site.name,
    lat: site.lat,
    lon: site.lon,
    assigned_team: site.assigned_team ?? null,
    risk_score: site.risk_score ?? null,
    risk_level: site.risk_level ?? null,
    updated_at: site.updated_at ?? null,
    active_alerts: site.active_alerts ?? 0,
    top_factors: site.top_factors ?? [],
    data_completeness: site.data_completeness ?? 0,
    model_version: site.model_version ?? 'unscored',
  }
}
