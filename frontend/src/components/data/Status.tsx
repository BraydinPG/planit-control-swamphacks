import type {
  DataState,
  SiteSummary,
  FactorContribution,
  Observation,
  HazardScore,
} from '../../types/api'
import { RiskBadge, RiskShape, ScoreBar } from './Risk'
import { evidenceLabel, evidenceOf, hasStaleOrReplay } from './evidence'
import {
  displayLabel,
  factorLabel,
  formatTimestamp,
  unitLabel,
} from '../../presentation/display'
import { Details } from './Details'
import { CountUp } from './CountUp'

const stateLabels: Record<DataState, string> = {
  observed: 'Observed',
  forecast: 'Forecast',
  crew_reported: 'Crew report',
  simulated: 'Simulated',
  stale: 'Stale',
  unavailable: 'Unavailable',
}
/* Each state has its own mark so it never depends on colour alone. */
function StateMark({ state }: { state: DataState }) {
  const p = {
    viewBox: '0 0 12 12',
    className: 'size-3 shrink-0',
    'aria-hidden': true,
  } as const
  switch (state) {
    case 'observed':
      return (
        <svg {...p}>
          <circle cx="6" cy="6" r="4" fill="currentColor" />
        </svg>
      )
    case 'forecast':
      return (
        <svg {...p}>
          <circle
            cx="6"
            cy="6"
            r="4"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeDasharray="2 1.6"
          />
        </svg>
      )
    case 'crew_reported':
      return (
        <svg {...p}>
          <circle cx="6" cy="4" r="2.2" fill="currentColor" />
          <path d="M1.8 11a4.2 4.2 0 0 1 8.4 0z" fill="currentColor" />
        </svg>
      )
    case 'simulated':
      return (
        <svg {...p}>
          <circle
            cx="6"
            cy="6"
            r="4"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeDasharray="0.1 2.2"
            strokeLinecap="round"
          />
        </svg>
      )
    case 'stale':
      return (
        <svg {...p}>
          <circle
            cx="6"
            cy="6"
            r="4.6"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.4"
          />
          <path
            d="M6 3.4V6l1.8 1.2"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
          />
        </svg>
      )
    case 'unavailable':
      return (
        <svg {...p}>
          <circle
            cx="6"
            cy="6"
            r="4.6"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.4"
          />
          <path d="M2.8 9.2 9.2 2.8" stroke="currentColor" strokeWidth="1.4" />
        </svg>
      )
  }
}
const stateTone: Record<DataState, string> = {
  observed: 'border-line-strong text-ink-2',
  forecast: 'border-dashed border-line-strong text-ink-2',
  crew_reported: 'border-line-strong text-ink-2',
  simulated: 'border-dotted border-sim text-sim',
  stale: 'border-warn bg-warn/10 text-warn-text',
  unavailable: 'border-line-strong text-muted',
}
export function Status({ state }: { state: DataState }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap chip border ${stateTone[state]}`}
    >
      <StateMark state={state} />
      {stateLabels[state]}
    </span>
  )
}
export function Timestamp({ value }: { value: string | null }) {
  return value && Number.isFinite(Date.parse(value)) ? (
    <time dateTime={value} title={value} className="tabular-nums">
      {formatTimestamp(value)}
    </time>
  ) : (
    <span>Time unavailable</span>
  )
}
export function Factors({ factors }: { factors: FactorContribution[] }) {
  const max = Math.max(1, ...factors.map((f) => Math.abs(f.contribution)))
  return (
    <ul className="divide-y divide-line">
      {factors.map((factor, i) => (
        <li
          key={`${factor.factor}-${i}`}
          className="grid gap-2 py-3 text-sm @lg:grid-cols-[minmax(0,1fr)_auto] @lg:items-start"
        >
          <div className="min-w-0 space-y-1.5">
            <strong className="block text-base text-ink">
              {factor.factor === 'model'
                ? 'Unapproved legacy ML factor — value withheld'
                : factorLabel(factor.factor)}
            </strong>
            <p className="flex flex-wrap items-center gap-2 text-ink-2">
              <Status state={factor.data_state} />
            </p>
            <Details title="Factor evidence">
              <p>{factor.label}</p>
              <p>Source: {factor.source}</p>
              <p>
                <Timestamp value={factor.observed_at} /> ·{' '}
                {factor.is_prototype
                  ? 'Prototype setting, not employer policy'
                  : 'Source-provided factor'}{' '}
                · Evidence: {factor.evidence_id ?? 'not supplied'}
              </p>
            </Details>
          </div>
          {factor.factor !== 'model' && (
            <div className="space-y-1.5 @lg:w-48 @lg:text-right">
              <p className="text-ink-2">
                Score contribution:{' '}
                <span className="font-bold tabular-nums text-ink">
                  {factor.contribution}
                </span>
                {' points'}
              </p>
              <p className="text-sm text-muted">
                Reading:{' '}
                {typeof factor.value === 'string'
                  ? displayLabel(factor.value)
                  : (factor.value ?? 'Unknown')}{' '}
                {unitLabel(factor.unit)}
              </p>
              <span
                className="block h-1.5 overflow-hidden rounded-full bg-surface-2"
                aria-hidden="true"
              >
                <span
                  className="block h-full rounded-full bg-ink-2"
                  style={{
                    width: `${(Math.abs(factor.contribution) / max) * 100}%`,
                  }}
                />
              </span>
            </div>
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
  site: SiteSummary & { score?: HazardScore | null }
  demo: boolean
}) {
  const legacy =
    demo && site.top_factors.some((factor) => factor.factor === 'model')
  const score = legacy ? null : site.risk_score
  const evidence = legacy ? null : evidenceOf(site)
  const percent = Math.round(site.data_completeness * 100)
  const inputFactors = site.score?.factor_contributions ?? site.top_factors
  const supplied =
    site.risk_score === null
      ? null
      : `${site.risk_score.toFixed(1)} / 10 · ${displayLabel(site.risk_level, 'Level unavailable')}`
  return (
    <section
      aria-label="Site score"
      className={`rounded-2xl border bg-surface p-5 ${evidence === 'none' || evidence === 'partial' ? 'border-dashed border-caution' : 'border-line'}`}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="kicker">Site score</h2>
        <RiskBadge
          level={site.risk_level}
          withheld={legacy}
          evidence={evidence}
        />
      </div>
      <p className="mt-3 flex flex-wrap items-baseline gap-x-2 gap-y-1">
        {legacy ? (
          <span className="text-2xl font-bold">Score withheld</span>
        ) : site.risk_score === null ? (
          <span className="text-2xl font-bold">Not scored yet</span>
        ) : evidence === 'none' ? (
          <>
            <span className="font-condensed text-5xl leading-none">
              Unknown
            </span>
            <span className="text-base text-muted">
              Server value {supplied}
            </span>
          </>
        ) : (
          <>
            <span className="font-condensed text-6xl leading-none tabular-nums">
              <CountUp value={site.risk_score} decimals={1} />
            </span>
            <span className="text-lg text-muted">
              / 10 · {displayLabel(site.risk_level, 'Level unavailable')}
            </span>
          </>
        )}
      </p>
      <div className="mt-4">
        <ScoreBar
          score={score}
          level={legacy ? null : site.risk_level}
          evidence={evidence}
        />
      </div>
      {(evidence === 'none' || evidence === 'partial') && (
        <div
          role="note"
          className="mt-4 flex gap-3 rounded-xl bg-surface-2 p-3 text-sm"
        >
          <RiskShape
            kind={evidence === 'none' ? 'nodata' : 'caution'}
            className="mt-0.5 size-5"
          />
          <p className="text-ink-2">
            <strong className="block text-ink">
              {evidenceLabel[evidence]}
            </strong>
            {evidence === 'none'
              ? 'Conditions are unknown. No scoring inputs are available; a zero is not a low-risk reading.'
              : 'Missing inputs remain unknown. The score may understate conditions.'}
          </p>
        </div>
      )}
      {!legacy && site.risk_score !== null && hasStaleOrReplay(site) && (
        <p className="mt-3 flex items-center gap-2 text-sm text-ink-2">
          {inputFactors.some((f) => f.data_state === 'stale') && (
            <Status state="stale" />
          )}
          {(demo || inputFactors.some((f) => f.data_state === 'simulated')) && (
            <Status state="simulated" />
          )}
          {demo ? 'No live readings.' : 'Includes stale or simulated inputs.'}
        </p>
      )}
      {legacy && (
        <p className="mt-3 text-sm text-ink-2">
          This legacy fixture includes an unapproved ML score component. The
          original payload is preserved; no score is recomputed here.
        </p>
      )}
      <p className="mt-4 text-sm text-muted">
        Updated <Timestamp value={site.updated_at} />
      </p>
      <Details title="How the score is calculated">
        <p>
          {demo
            ? 'Simulated demo score, not live conditions.'
            : 'Calculated by the backend from deterministic rules and confirmed reports.'}{' '}
          Completeness: {percent}% of inputs. Scoring version:{' '}
          {site.model_version}.
        </p>
        <p>
          ML predictions do not contribute to this score. The score does not
          clear alerts or authorize work.
        </p>
      </Details>
    </section>
  )
}
export function Observations({ rows }: { rows: Observation[] }) {
  if (!rows.length)
    return (
      <p className="rounded-2xl border border-dashed border-line-strong p-4 text-ink-2">
        No observations supplied. Conditions remain unknown.
      </p>
    )
  const name = (row: Observation) => row.label ?? displayLabel(row.hazard_type)
  const when = (row: Observation) =>
    row.data_state === 'forecast' ? row.valid_at : row.observed_at
  // One compact tile per reading, then one shared disclosure for every
  // reading's source and timestamps.
  return (
    <div className="@container space-y-2 rounded-2xl border border-line bg-surface p-3">
      <ul className="grid gap-2 @md:grid-cols-2 @3xl:grid-cols-3">
        {rows.map((row, index) => {
          const missing = row.value === null || row.data_state === 'unavailable'
          return (
            <li
              key={row.id ?? index}
              className="flex min-w-0 flex-col gap-1.5 rounded-xl bg-surface-2 p-3"
            >
              <p className="text-sm font-semibold text-ink-2 [overflow-wrap:anywhere]">
                {name(row)}
              </p>
              <p
                className={`text-xl font-bold leading-snug tracking-tight tabular-nums [overflow-wrap:anywhere] ${missing ? 'text-muted' : ''}`}
              >
                {typeof row.value === 'string'
                  ? displayLabel(row.value)
                  : (row.value ?? 'Unknown')}{' '}
                <span className="text-sm font-semibold text-muted">
                  {unitLabel(row.unit)}
                </span>
              </p>
              <p className="flex flex-wrap gap-1.5">
                <Status state={row.data_state} />{' '}
                {row.simulated && row.data_state !== 'simulated' && (
                  <Status state="simulated" />
                )}
              </p>
              <p className="mt-auto text-xs text-muted">
                {row.data_state === 'forecast' ? 'Valid' : 'Observed'}{' '}
                <Timestamp value={when(row)} />
              </p>
            </li>
          )
        })}
      </ul>
      <Details title="Source and timing for each reading">
        <ul className="divide-y divide-line text-sm">
          {rows.map((row, index) => (
            <li key={row.id ?? index} className="py-2 leading-relaxed">
              <p className="font-semibold text-ink">{name(row)}</p>
              <p className="grid gap-x-4 text-ink-2 @lg:grid-cols-2">
                <span className="[overflow-wrap:anywhere]">
                  Source: {row.source} ·{' '}
                  {row.source_ref ?? 'record reference unavailable'}
                </span>
                <span>
                  Observed: <Timestamp value={row.observed_at} />
                </span>
                <span>
                  Valid: <Timestamp value={row.valid_at} />
                </span>
                <span>
                  Fetched: <Timestamp value={row.fetched_at} />
                </span>
              </p>
            </li>
          ))}
        </ul>
      </Details>
    </div>
  )
}
