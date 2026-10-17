import { useCallback, useState } from 'react'
import type { Briefing, SiteSummary } from '../../types/api'
import { useApplication, useResource } from '../../application/context'
import { control, LoadState } from './Interaction'
import { Timestamp } from './Status'

export const NO_BRIEFING =
  'No briefing yet. Briefings are generated at 6 PM site-local time.'

export function BriefingCard({ value }: { value: Briefing }) {
  return (
    <article
      className="space-y-3 rounded border bg-white p-4"
      data-briefing-id={value.id}
    >
      <h2 className="text-xl font-semibold">
        Stored briefing ·{' '}
        {value.generated_by === 'fallback'
          ? 'Deterministic template fallback'
          : 'Gemini output'}
      </h2>
      <p>
        Site: {value.site_id ?? 'Organization briefing'} · Organization:{' '}
        {value.organization_id ?? 'Site-scoped'}
      </p>
      <p>
        Forecast window: <Timestamp value={value.forecast_window_start} /> to{' '}
        <Timestamp value={value.forecast_window_end} />
      </p>
      <p>Risk level at generation: {value.risk_level}</p>
      <p>{value.summary}</p>
      <h3 className="font-semibold">Hazards</h3>
      <ul>
        {value.hazards.map((h, i) => (
          <li key={i}>
            {h.hazard} · {h.risk_level} · evidence: {h.evidence_ids.join(', ')}
          </li>
        ))}
      </ul>
      <h3 className="font-semibold">Actions supplied for human review</h3>
      <ul>
        {value.recommended_actions.map((a, i) => (
          <li key={i}>
            {a.action} · evidence: {a.evidence_ids.join(', ')}
          </li>
        ))}
      </ul>
      <h3 className="font-semibold">Evidence references</h3>
      <ul>
        {value.evidence.map((e) => (
          <li key={e.id}>
            {e.id} · {e.label} · <Timestamp value={e.observed_at} />
          </li>
        ))}
      </ul>
      <h3 className="font-semibold">Unknowns</h3>
      <ul>
        {value.unknowns.map((u, i) => (
          <li key={i}>{u}</li>
        ))}
      </ul>
      <p>
        Created <Timestamp value={value.created_at} /> · generated_by:{' '}
        {value.generated_by}
      </p>
      <p className="text-xs">
        Stored advisory text cannot authorize work or clear alerts. The backend
        owns the generation schedule.
      </p>
    </article>
  )
}

export function StoredBriefings({ sites }: { sites: SiteSummary[] }) {
  const { client } = useApplication()
  const [selection, setSelection] = useState(sites[0]?.id ?? '')
  const result = useResource(
    `briefings:${selection}`,
    useCallback(async () => {
      if (selection === 'organization') return client.briefings()
      const value = await client.briefing(selection)
      return value ? [value] : []
    }, [client, selection]),
  )
  return (
    <section className="space-y-4" aria-label="Stored briefings">
      <label className="block">
        Briefing site or organization
        <select
          className={control + ' block w-full'}
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
      <p>
        Read-only stored briefings. Briefings are generated at 6 PM site-local
        time. Organization access requires the backend's read:org_briefings
        permission.
      </p>
      {client.mode === 'demo' && (
        <p>
          SIMULATED / ARCHIVED FIXTURES — prerecorded examples, including a
          template fallback. Text is not regenerated after demo mutations and is
          not current employer policy.
        </p>
      )}
      {result.data === null ? (
        <LoadState error={result.error} />
      ) : result.data.length ? (
        result.data.map((value) => (
          <BriefingCard key={value.id} value={value} />
        ))
      ) : (
        <p role="status">{NO_BRIEFING}</p>
      )}
    </section>
  )
}
