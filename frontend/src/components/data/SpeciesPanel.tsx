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
const isPlant = (s: SpeciesEntry) => /plant|fern|lichen/i.test(s.group ?? '')
const nameOf = (s: {
  common_name: string | null
  scientific_name: string | null
}) => s.common_name ?? s.scientific_name ?? 'Unnamed species'

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
  const guided = context.species.filter((s) => s.encounter)
  const otherAnimals = context.species.filter(
    (s) => !s.encounter && !isPlant(s),
  )
  const plants = context.species.filter((s) => !s.encounter && isPlant(s))
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

      <div className={`${card} space-y-2 p-4 text-sm text-ink-2`}>
        <p className="flex flex-wrap items-center gap-2">
          <Status state={context.data_state} />
          <span className="font-semibold text-ink">{context.source}</span>
          {context.api_version && <span>v{context.api_version}</span>}
          {context.simulated && (
            <span className="chip border border-dotted border-sim text-sim">
              Recorded demo snapshot
            </span>
          )}
        </p>
        <p>
          Retrieved <Timestamp value={context.fetched_at} />
        </p>
        <Details title="Species sources and coverage">
          <p>{context.caveat}</p>
          <p>{context.footprint_description}</p>
          <p>
            Wording:{' '}
            {context.generated_by === 'gemini'
              ? 'Gemini, checked line by line against the sources below'
              : 'deterministic template'}
            . Statuses and guidance are shown exactly as sourced.
          </p>
        </Details>
      </div>

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
          {guided.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-base font-bold">
                Encounter guidance ({guided.length})
              </h3>
              <ul className="grid gap-3 @3xl:grid-cols-2">
                {guided.map((s) => (
                  <li key={s.id}>
                    <SpeciesCard species={s} />
                  </li>
                ))}
              </ul>
            </div>
          )}
          <SpeciesGroup title="Other listed animals" rows={otherAnimals} />
          <SpeciesGroup title="Listed plants" rows={plants} />
        </>
      )}

      <Habitat context={context} site={site} />

      {context.field_office && (
        <p className={`${card} p-4 text-sm text-ink-2`}>
          <span className="font-semibold text-ink">USFWS field office:</span>{' '}
          {context.field_office.name}
          {context.field_office.phone && ` · ${context.field_office.phone}`}
          {context.field_office.email && ` · ${context.field_office.email}`}
        </p>
      )}

      {context.unknowns.length > 0 && (
        <div className={`${card} p-4`}>
          <Details title="What this does not tell you">
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink-2">
              {context.unknowns.map((u) => (
                <li key={u}>{u}</li>
              ))}
            </ul>
          </Details>
        </div>
      )}
    </div>
  )
}

function WildlifeReports({ reports }: { reports: WildlifeReportRef[] }) {
  return (
    <div className="space-y-2">
      <h3 className="text-base font-bold">
        Crew wildlife reports at this site
      </h3>
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

export function SpeciesCard({ species: s }: { species: SpeciesEntry }) {
  return (
    <article
      className={`${card} h-full space-y-3 border border-line p-4`}
      aria-label={nameOf(s)}
    >
      <header>
        <h4 className="text-base font-bold">{nameOf(s)}</h4>
        <p className="text-sm text-muted">
          {s.common_name && s.scientific_name && (
            <i className="mr-1">{s.scientific_name}</i>
          )}
          {s.group && `· ${s.group}`}
        </p>
        <p className="mt-1.5 chip inline-flex border border-dashed border-line-strong text-ink-2">
          {matchLabels[s.match_basis]} · not a sighting
        </p>
      </header>
      <p className="text-sm text-ink">
        {s.summary}{' '}
        <span className="text-sm text-muted">
          ({s.summary_by === 'gemini' ? 'Gemini wording' : 'template'})
        </span>
      </p>
      <Encounter species={s} />
      <Details title="Protection status and sources">
        <Protection species={s} />
      </Details>
    </article>
  )
}

function Protection({ species: s }: { species: SpeciesEntry }) {
  const p = s.protection
  return (
    <section className="rounded-xl bg-surface-2 p-3 text-sm">
      <h5 className="kicker mb-1">Protection status</h5>
      {p ? (
        <>
          <p className="font-semibold text-ink">
            {p.status ?? 'Protection status unknown'}
          </p>
          <p className="text-ink-2">{p.jurisdiction}</p>
          <p className="text-ink-2">
            Critical habitat at this location:{' '}
            {p.critical_habitat_here === null
              ? 'unknown'
              : p.critical_habitat_here
                ? 'yes, per IPaC'
                : 'not per IPaC'}
          </p>
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

function Encounter({ species: s }: { species: SpeciesEntry }) {
  const e = s.encounter
  return (
    <section className="rounded-xl bg-surface-2 p-3 text-sm">
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

function Habitat({
  context,
  site,
}: {
  context: SiteSpeciesContext
  site: Pick<SiteDetail, 'id' | 'name' | 'lat' | 'lon'> & Partial<SiteDetail>
}) {
  const areas = context.critical_habitat
  const drawn = areas.filter((a) => a.geometry)
  return (
    <div className="space-y-2">
      <h3 className="flex flex-wrap items-center gap-2 text-base font-bold">
        Critical habitat near the site
        <Status state={context.critical_habitat_state} />
      </h3>
      <p className="text-sm text-muted">
        {context.critical_habitat_source}, within about 3 km. A boundary is
        legal habitat designation, not a sighting.
      </p>
      {context.critical_habitat_state === 'unavailable' ? (
        <p role="alert" className="text-sm font-semibold">
          Critical habitat boundaries are unavailable. This does not mean there
          is none.
        </p>
      ) : areas.length ? (
        <ul className="space-y-2">
          {areas.map((a) => (
            <HabitatRow key={a.id} area={a} />
          ))}
        </ul>
      ) : (
        <Muted>
          The map service returned no critical habitat within about 3 km.
        </Muted>
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
    </div>
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
