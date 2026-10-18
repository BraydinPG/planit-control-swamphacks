import { useCallback, useState, type ReactNode } from 'react'
import type { Briefing, SiteSummary } from '../../types/api'
import { useApplication, useResource } from '../../application/context'
import { field, labelText, LoadState } from './Interaction'
import { Timestamp } from './Status'
import { GeminiMark, Icon } from '../shell/Icon'
import { ApiError } from '../../api/contracts'
import { displayLabel } from '../../presentation/display'
import { Details } from './Details'

export const NO_BRIEFING =
  'No briefing yet. Briefings are generated at 6 PM site-local time.'

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="space-y-2">
      <h3 className="kicker">{title}</h3>
      {children}
    </div>
  )
}
const ids = (list: string[]) => (
  <Details title="Evidence references">
    <p className="font-mono">
      {list.join(', ') || 'No evidence reference supplied'}
    </p>
  </Details>
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
          className={`inline-flex items-center gap-1.5 chip border ${fallback ? 'border-dashed border-line-strong text-ink-2' : 'border-sim text-sim'}`}
        >
          {fallback ? (
            <Icon name="doc" className="size-3.5" />
          ) : (
            <GeminiMark className="size-3.5" />
          )}
          {fallback ? 'Template' : 'Gemini'}
        </span>
        <h2 className="text-2xl font-bold tracking-tight">Shift briefing</h2>
        <p className="text-sm text-ink-2">
          Covers <Timestamp value={value.forecast_window_start} /> to{' '}
          <Timestamp value={value.forecast_window_end} />
        </p>
        <p className="text-sm">
          {value.risk_score === null ? (
            <>
              Risk level when written:{' '}
              <strong>{displayLabel(value.risk_level)}</strong>
            </>
          ) : (
            <>
              Score when written:{' '}
              <strong>
                {value.risk_score.toFixed(1)} / 10 ·{' '}
                <span>{displayLabel(value.risk_level)}</span>
              </strong>
              {value.data_completeness !== null &&
                (value.data_completeness === 0 ? (
                  <span className="text-ink-2">
                    {' '}
                    · Evidence incomplete; current conditions unknown
                  </span>
                ) : (
                  <span className="text-ink-2">
                    {' '}
                    · {Math.round(value.data_completeness * 100)}% of inputs
                    available
                  </span>
                ))}
            </>
          )}
        </p>
      </header>
      <p className="text-lg leading-relaxed">{value.summary}</p>
      <div className="grid gap-5 @3xl:grid-cols-2">
        <Section title="Hazards">
          <ul className="space-y-2">
            {value.hazards.map((h, i) => (
              <li key={i} className="rounded-xl bg-surface-2 px-3 py-2">
                <span className="font-semibold">{h.hazard}</span> ·{' '}
                {h.points === null ? (
                  <span className="text-ink-2">not in score</span>
                ) : (
                  <strong>+{h.points.toFixed(1)} pts</strong>
                )}{' '}
                {ids(h.evidence_ids)}
              </li>
            ))}
          </ul>
        </Section>
        <Section title="Suggested actions · review required">
          <ul className="space-y-2">
            {value.recommended_actions.map((a, i) => (
              <li key={i} className="rounded-xl bg-surface-2 px-3 py-2">
                {a.action} {ids(a.evidence_ids)}
              </li>
            ))}
          </ul>
        </Section>
        <Details title="Briefing sources">
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
        </Details>
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
      <footer className="space-y-2 border-t border-line pt-4 text-sm text-muted">
        <p>
          Written <Timestamp value={value.created_at} /> ·{' '}
          {fallback ? 'Template fallback' : 'Gemini draft'}
        </p>
        <p>A briefing does not authorize work or clear alerts.</p>
        <Details title="Briefing record">
          <p>
            Site: {value.site_id ?? 'Organization-wide'} · Organization:{' '}
            {value.organization_id ?? 'Site-scoped'} · Record: {value.id}
          </p>
        </Details>
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
          Choose a worksite or organization
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
            Briefings are scheduled for 6 PM, in the worksite's local time.
            Organization briefings require permission.
          </span>
        </p>
      </div>
      {client.mode === 'demo' && (
        <p className="rounded-xl border border-dotted border-sim px-4 py-3 text-sm text-ink-2">
          <strong className="text-sim">Simulated briefing.</strong> Saved
          example; it does not update after demo changes or represent current
          employer policy.
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
