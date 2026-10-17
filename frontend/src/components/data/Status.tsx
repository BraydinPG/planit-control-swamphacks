import type {
  DataState,
  SiteSummary,
  FactorContribution,
  Observation,
} from '../../types/api'

const stateLabels: Record<DataState, string> = {
  observed: 'Observed',
  forecast: 'Forecast',
  crew_reported: 'Crew reported',
  simulated: 'Simulated',
  stale: 'Stale',
  unavailable: 'Unavailable',
}
export function Status({ state }: { state: DataState }) {
  return (
    <span
      className={`inline-block rounded border px-2 py-1 text-xs font-semibold ${state === 'stale' || state === 'unavailable' ? 'border-amber-300 bg-amber-50 text-amber-950' : 'border-slate-300 bg-slate-50 text-slate-800'}`}
    >
      {stateLabels[state]}
    </span>
  )
}
export function Timestamp({ value }: { value: string | null }) {
  return value && Number.isFinite(Date.parse(value)) ? (
    <time dateTime={value}>
      {new Date(value).toISOString().replace('T', ' ').replace('.000Z', ' UTC')}
    </time>
  ) : (
    <span>Timestamp unavailable</span>
  )
}
export function Factors({ factors }: { factors: FactorContribution[] }) {
  return (
    <ul className="space-y-3">
      {factors.map((factor, i) => (
        <li
          key={`${factor.factor}-${i}`}
          className="rounded-lg border border-slate-200 p-3 text-sm"
        >
          <strong>
            {factor.factor === 'model'
              ? 'Unapproved legacy ML factor — value withheld'
              : factor.label}
          </strong>
          <p>
            {factor.source} · <Status state={factor.data_state} />
          </p>
          <p className="text-xs">
            <Timestamp value={factor.observed_at} /> ·{' '}
            {factor.is_prototype
              ? 'Prototype setting, not employer policy'
              : 'Source-provided factor'}{' '}
            · Evidence: {factor.evidence_id ?? 'not supplied'}
          </p>
          {factor.factor !== 'model' && (
            <p>
              Contribution: {factor.contribution}; source value:{' '}
              {factor.value ?? 'unknown'} {factor.unit}
            </p>
          )}
        </li>
      ))}
    </ul>
  )
}
export function ScorePanel({
  site,
  demo,
}: {
  site: SiteSummary
  demo: boolean
}) {
  const legacy =
    demo && site.top_factors.some((factor) => factor.factor === 'model')
  return (
    <section
      aria-label="Site score"
      className="rounded-xl border border-slate-200 bg-white p-4"
    >
      <h2 className="text-lg font-semibold">Site score</h2>
      <p className="mt-2 text-xl font-semibold">
        {legacy
          ? 'Score withheld'
          : site.risk_score === null
            ? 'Not scored yet'
            : `${site.risk_score.toFixed(1)} / 10 · ${site.risk_level ?? 'level unavailable'}`}
      </p>
      {legacy && (
        <p className="text-sm">
          This legacy fixture includes an unapproved ML score component. The
          original payload is preserved; no score is recomputed here.
        </p>
      )}
      <p className="mt-2 text-xs">
        {demo
          ? 'Historical demonstration payload, not live scoring.'
          : 'Server-provided score; never calculated by the frontend.'}{' '}
        Completeness: {Math.round(site.data_completeness * 100)}%. Model:{' '}
        {site.model_version}
      </p>
      <p className="text-xs">
        Updated: <Timestamp value={site.updated_at} />
      </p>
    </section>
  )
}
export function Observations({ rows }: { rows: Observation[] }) {
  if (!rows.length)
    return <p>No observations supplied. Conditions remain unknown.</p>
  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {rows.map((row, index) => (
        <li
          key={row.id ?? index}
          className="rounded-xl border border-slate-200 bg-white p-4"
        >
          <p className="font-semibold">{row.label ?? row.hazard_type}</p>
          <p>
            {row.value ?? 'Unknown'} {row.unit}
          </p>
          <p>
            <Status state={row.data_state} />{' '}
            {row.simulated && <Status state="simulated" />}
          </p>
          <p className="mt-2 text-xs">
            Source: {row.source} ·{' '}
            {row.source_ref ?? 'record reference unavailable'}
            <br />
            Observed: <Timestamp value={row.observed_at} />
            <br />
            Valid: <Timestamp value={row.valid_at} />
            <br />
            Fetched: <Timestamp value={row.fetched_at} />
          </p>
        </li>
      ))}
    </ul>
  )
}
