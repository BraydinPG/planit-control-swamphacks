import { useCallback, useState, type ReactNode } from 'react'
import type { Briefing, SiteSummary } from '../../types/api'
import { useApplication, useResource } from '../../application/context'
import { field, labelText, LoadState } from './Interaction'
import { Timestamp } from './Status'
import { Icon } from '../shell/Icon'
import { ApiError } from '../../api/contracts'

export const NO_BRIEFING =
  'No briefing yet. Briefings are generated at 6 PM site-local time.'

function Section({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <div className="space-y-2">
      <h3 className="kicker">{title}</h3>
      {children}
    </div>
  )
}
const ids = (list: string[]) => (
  <span className="font-mono text-xs text-muted">
    evidence: {list.join(', ')}
  </span>
)

export function BriefingCard({ value }: { value: Briefing }) {
  const fallback = value.generated_by === 'fallback'
  return (
    <article
      className="space-y-5 rounded-2xl border border-line bg-surface p-5 @lg:p-6"
      data-briefing-id={value.id}
    >
      <header className="space-y-3 border-b border-line pb-4">
        <span
          className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 font-mono text-[11px] font-semibold uppercase tracking-wider ${fallback ? 'border-dashed border-line-strong text-ink-2' : 'border-sim text-sim'}`}
        >
          <Icon name={fallback ? 'doc' : 'spark'} className="size-3.5" />
          {fallback ? 'Template' : 'Gemini'}
        </span>
        <h2 className="text-2xl font-bold tracking-tight">
          Stored briefing ·{' '}
          {fallback ? 'Deterministic template fallback' : 'Gemini output'}
        </h2>
        <p className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-2">
          <span>
            Site: {value.site_id ?? 'Organization briefing'} · Organization:{' '}
            {value.organization_id ?? 'Site-scoped'}
          </span>
        </p>
        <p className="text-sm text-ink-2">
          Forecast window: <Timestamp value={value.forecast_window_start} /> to{' '}
          <Timestamp value={value.forecast_window_end} />
        </p>
        <p className="text-sm">
          Risk level at generation:{' '}
          <strong className="capitalize">{value.risk_level}</strong>
        </p>
      </header>
      <p className="text-lg leading-relaxed">{value.summary}</p>
      <div className="grid gap-5 @3xl:grid-cols-2">
        <Section title="Hazards">
          <ul className="space-y-2">
            {value.hazards.map((h, i) => (
              <li key={i} className="rounded-xl bg-surface-2 px-3 py-2">
                <span className="font-semibold">{h.hazard}</span> ·{' '}
                {h.risk_level} · {ids(h.evidence_ids)}
              </li>
            ))}
          </ul>
        </Section>
        <Section title="Actions supplied for human review">
          <ul className="space-y-2">
            {value.recommended_actions.map((a, i) => (
              <li key={i} className="rounded-xl bg-surface-2 px-3 py-2">
                {a.action} · {ids(a.evidence_ids)}
              </li>
            ))}
          </ul>
        </Section>
        <Section title="Evidence references">
          <ul className="divide-y divide-line text-sm">
            {value.evidence.map((e) => (
              <li key={e.id} className="break-words py-2">
                <span className="font-mono text-xs text-muted">{e.id}</span> ·{' '}
                {e.label} · <Timestamp value={e.observed_at} />
              </li>
            ))}
          </ul>
        </Section>
        <Section title="Unknowns">
          <ul className="space-y-1.5 text-sm">
            {value.unknowns.map((u, i) => (
              <li key={i} className="flex gap-2">
                <span
                  className="mt-1.5 size-2 shrink-0 rounded-full border border-dashed border-faint"
                  aria-hidden="true"
                />
                {u}
              </li>
            ))}
          </ul>
        </Section>
      </div>
      <footer className="space-y-1 border-t border-line pt-4 text-xs text-muted">
        <p>
          Created <Timestamp value={value.created_at} /> · generated_by:{' '}
          {value.generated_by}
        </p>
        <p>
          Stored advisory text cannot authorize work or clear alerts. The
          backend owns the generation schedule.
        </p>
      </footer>
    </article>
  )
}

type Loaded = { briefings: Briefing[]; unavailable: string | null }

export function StoredBriefings({ sites }: { sites: SiteSummary[] }) {
  const { client } = useApplication()
  const [selection, setSelection] = useState(sites[0]?.id ?? '')
  const result = useResource(
    `briefings:${selection}`,
    useCallback(async (): Promise<Loaded> => {
      try {
        if (selection === 'organization')
          return { briefings: await client.briefings(), unavailable: null }
        const value = await client.briefing(selection)
        return { briefings: value ? [value] : [], unavailable: null }
      } catch (error) {
        // The backend explained why there is no briefing (no team, no supervisor,
        // account not linked, ...): an empty state, not a load failure.
        if (error instanceof ApiError && error.reason && error.detail)
          return { briefings: [], unavailable: error.detail }
        throw error
      }
    }, [client, selection]),
  )
  return (
    <section className="space-y-5" aria-label="Stored briefings">
      <div className="grid gap-4 rounded-2xl border border-line bg-surface p-4 @lg:grid-cols-[minmax(0,22rem)_1fr] @lg:items-end">
        <label className={labelText}>
          Briefing site or organization
          <select
            className={field}
            value={selection}
            onChange={(e) => setSelection(e.target.value)}
          >
            {sites.map((site) => (
              <option key={site.id} value={site.id}>
                {site.name}
              </option>
            ))}
            <option value="organization">Organization briefings</option>
          </select>
        </label>
        <p className="flex items-start gap-2 text-sm text-ink-2">
          <Icon name="clock" className="mt-0.5 size-4 shrink-0" />
          <span>
            Read-only stored briefings. Briefings are generated at 6 PM
            site-local time. Organization access requires the backend's
            read:org_briefings permission.
          </span>
        </p>
      </div>
      {client.mode === 'demo' && (
        <p className="rounded-xl border border-dotted border-sim px-4 py-3 text-sm text-ink-2">
          <span className="kicker text-sim!">Simulated</span>{' '}
          SIMULATED / ARCHIVED FIXTURES — prerecorded examples, including a
          template fallback. Text is not regenerated after demo mutations and is
          not current employer policy.
        </p>
      )}
      {result.data === null ? (
        <LoadState error={result.error} />
      ) : result.data.briefings.length ? (
        result.data.briefings.map((value) => (
          <BriefingCard key={value.id} value={value} />
        ))
      ) : (
        <p
          role="status"
          className="rounded-2xl border border-dashed border-line-strong p-5 text-ink-2"
        >
          {result.data.unavailable ?? NO_BRIEFING}
        </p>
      )}
    </section>
  )
}
