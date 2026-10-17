import type { ReactNode } from 'react'
import type {
  DurationForecast,
  EventOutlookCard,
  OfficialAftershockForecast,
  OfficialEventForecast,
  UnavailableForecast,
} from '../../types/api'
import { Timestamp } from './Status'

/**
 * T050A event outlooks: one card per confirmed event, as the backend supplied it.
 * Advisory only: nothing here changes the score, alerts, the lightning timer or
 * work authorization. "Prediction unavailable" is a visible reason, never 0%.
 */
const percent = (p: number) => `${Math.round(p * 100)}%`
const hours = (h: number | null) =>
  h === null ? 'not identified' : `${h % 1 === 0 ? h : h.toFixed(1)} h`

const presentationText: Record<EventOutlookCard['presentation'], string> = {
  current: 'Current event',
  replay: 'Simulated replay',
  historical_example: 'Historical example, not a current prediction',
}
const kindText: Record<EventOutlookCard['forecast']['kind'], string> = {
  historical_duration_research: 'Research duration estimate',
  official_event_forecast: 'Issued NHC forecast',
  official_aftershock_forecast: 'Issued USGS aftershock forecast',
  unavailable: 'Prediction unavailable',
}
const basisText: Record<EventOutlookCard['confirmation']['basis'], string> = {
  independent_observation: 'independent observation',
  confirmed_worksite_report: 'supervisor-confirmed notice',
  historical_record: 'historical record',
  hypothetical_activation: 'hypothetical activation (replay)',
  official_event_record: 'official event record',
  warning_only: 'warning only',
  none: 'none',
}
const associationText: Record<
  EventOutlookCard['association']['method'],
  string
> = {
  site_verified: 'Verified at this site',
  regional_context: 'Regional context only',
  reference_replay: 'Replay at a reference location',
  unknown: 'Site link unknown',
}

export function EventOutlooks({ cards }: { cards: EventOutlookCard[] }) {
  return (
    <section className="space-y-1.5" aria-labelledby="event-outlooks-title">
      <div className="flex flex-wrap items-end justify-between gap-2 px-4">
        <h2 id="event-outlooks-title" className="kicker">
          Event outlooks
        </h2>
        <p className="text-xs text-muted">
          Advisory only. Does not change the score, clear alerts, or authorize
          work.
        </p>
      </div>
      {cards.length ? (
        <div className="grid gap-3 @3xl:grid-cols-2 @3xl:items-start">
          {cards.map((card) => (
            <OutlookCard key={card.event_id} card={card} />
          ))}
        </div>
      ) : (
        <p className="rounded-xl bg-surface px-4 py-3 text-sm text-ink-2">
          No confirmed event at this site, so there is no outlook. This does not
          mean the site is safe.
        </p>
      )}
    </section>
  )
}

function OutlookCard({ card }: { card: EventOutlookCard }) {
  const f = card.forecast
  const unavailable = f.kind === 'unavailable'
  return (
    <article
      data-outlook-id={card.event_id}
      aria-label={`${card.event_type} outlook`}
      className={`space-y-3 rounded-2xl bg-surface p-4 ${unavailable ? 'ring-1 ring-line-strong ring-dashed' : ''}`}
    >
      <header className="space-y-1.5">
        <div className="flex flex-wrap items-center gap-1.5">
          <span
            className={`chip border ${card.presentation === 'current' ? 'border-line-strong text-ink-2' : 'border-dotted border-sim text-sim'}`}
          >
            {presentationText[card.presentation]}
          </span>
          <span
            className={`chip border ${unavailable ? 'border-dashed border-line-strong text-muted' : 'border-accent text-accent'}`}
          >
            {kindText[f.kind]}
          </span>
        </div>
        <h3 className="text-lg leading-snug font-semibold">
          {card.event_type}
        </h3>
        <p className="text-[13px] text-muted">{card.event_name}</p>
      </header>

      {f.kind === 'historical_duration_research' && <Duration f={f} />}
      {f.kind === 'official_event_forecast' && <Storm f={f} />}
      {f.kind === 'official_aftershock_forecast' && <Aftershock f={f} />}
      {f.kind === 'unavailable' && <Unavailable f={f} />}

      <dl className="divide-y divide-line rounded-xl bg-surface-2 text-[13px]">
        <Row label="As of">
          <Timestamp value={card.as_of_utc} />
        </Row>
        <Row label="Event start">
          {card.event_start_utc ? (
            <Timestamp value={card.event_start_utc} />
          ) : (
            'Unknown (notice and warning times are not used)'
          )}
        </Row>
        {card.last_forecast_issued_at_utc && (
          <Row label="Forecast issued">
            <Timestamp value={card.last_forecast_issued_at_utc} />
          </Row>
        )}
        {card.last_observation_at_utc && (
          <Row label="Latest local evidence">
            <Timestamp value={card.last_observation_at_utc} />
          </Row>
        )}
        <Row label="Confirmation">
          {card.confirmation.status.replaceAll('_', ' ')} ·{' '}
          {basisText[card.confirmation.basis]}
        </Row>
        <Row label="Site link">{associationText[card.association.method]}</Row>
      </dl>
      <p className="text-[13px] text-ink-2">{card.association.description}</p>

      {card.evidence.length > 0 && (
        <div>
          <h4 className="kicker mb-1">Evidence</h4>
          <ul className="space-y-1 text-[13px]">
            {card.evidence.map((e) => (
              <li key={e.id}>
                <span className="font-mono text-xs text-muted">{e.id}</span> ·{' '}
                {e.source_id.replaceAll('-', ' ')} · observed{' '}
                <Timestamp value={e.valid_time_utc} />
              </li>
            ))}
          </ul>
        </div>
      )}

      <details className="group text-[13px]">
        <summary className="flex min-h-11 cursor-pointer list-none items-center font-semibold text-link">
          Limitations ({card.limitations.length})
        </summary>
        <ul className="list-disc space-y-1 pl-5 text-ink-2">
          {card.limitations.map((l, i) => (
            <li key={i}>{l}</li>
          ))}
        </ul>
      </details>
    </article>
  )
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-wrap justify-between gap-x-4 gap-y-0.5 px-3 py-2">
      <dt className="text-muted">{label}</dt>
      <dd className="text-right font-medium">{children}</dd>
    </div>
  )
}

function Duration({ f }: { f: DurationForecast }) {
  const d = f.remaining_duration_hours
  return (
    <div className="space-y-3">
      <div>
        <p className="text-[13px] text-muted">
          Estimated remaining duration of the recorded event
        </p>
        <p className="text-3xl leading-tight font-bold tabular-nums">
          {d.median === null ? 'Not identified' : hours(d.median)}
        </p>
        <p className="text-[13px] text-ink-2">
          Likely range {hours(d.p10)} to {hours(d.p90)} (10th–90th percentile).
          Not a time when work can resume.
        </p>
      </div>
      <ul
        className="space-y-1.5"
        aria-label="Chance the event is still ongoing"
      >
        {f.persistence.map((p) => (
          <li key={p.horizon_hours} className="text-[13px]">
            <div className="flex justify-between">
              <span>Still ongoing in {p.horizon_hours} h</span>
              <span className="font-semibold tabular-nums">
                {percent(p.recorded_event_ongoing_probability)}
              </span>
            </div>
            <span
              className="mt-0.5 block h-1.5 overflow-hidden rounded-full bg-surface-2"
              aria-hidden="true"
            >
              <span
                className="block h-full rounded-full bg-accent"
                style={{
                  width: percent(p.recorded_event_ongoing_probability),
                }}
              />
            </span>
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted">
        {f.model_version} · {f.estimator}
        {f.training_support_at_event_age !== null &&
          ` · ${f.training_support_at_event_age} historical events at this age`}{' '}
        · Trend unknown
      </p>
    </div>
  )
}

function Storm({ f }: { f: OfficialEventForecast }) {
  return (
    <div className="space-y-2">
      <p className="text-[15px]">
        <strong>{f.storm_name}</strong> ({f.cyclone_id}) · now{' '}
        {f.initial_position.max_sustained_wind_kt} kt
        {f.initial_position.phase
          ? `, ${f.initial_position.phase.toLowerCase()}`
          : ''}
      </p>
      <p className="text-[13px] text-ink-2">
        Next advisory <Timestamp value={f.next_advisory_at_utc} />. Cyclone
        track and winds, not wind at this site or when the event ends.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-[13px] tabular-nums">
          <caption className="sr-only">Issued forecast track</caption>
          <thead className="text-muted">
            <tr>
              <th className="py-1 font-medium">Valid</th>
              <th className="py-1 font-medium">Position</th>
              <th className="py-1 font-medium">Max wind</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {f.forecast_points.map((p) => (
              <tr key={p.valid_at_utc}>
                <td className="py-1 pr-2">
                  <Timestamp value={p.valid_at_utc} />
                </td>
                <td className="py-1 pr-2">
                  {p.lat.toFixed(1)}, {p.lon.toFixed(1)}
                </td>
                <td className="py-1">
                  {p.max_sustained_wind_kt} kt
                  {p.gust_kt !== null && ` (gusts ${p.gust_kt})`}
                  {p.phase && ` · ${p.phase.toLowerCase()}`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Source source={f.source} />
    </div>
  )
}

function Aftershock({ f }: { f: OfficialAftershockForecast }) {
  return (
    <div className="space-y-2">
      <p className="text-[15px]">
        Mainshock <strong>M{f.mainshock.magnitude}</strong> ·{' '}
        <Timestamp value={f.mainshock.time_utc} />
      </p>
      <p className="text-[13px] text-ink-2">
        Chances of at least one aftershock anywhere in the {f.region.radius_km}{' '}
        km sequence region, not at this site. Earthquakes have no end-time
        forecast.
      </p>
      <ul className="space-y-2">
        {f.windows.map((w) => (
          <li key={w.label} className="rounded-xl bg-surface-2 px-3 py-2">
            <p className="text-[13px] font-semibold">
              {w.label}: <Timestamp value={w.start_utc} /> to{' '}
              <Timestamp value={w.end_utc} />
            </p>
            <ul className="mt-1 text-[13px] tabular-nums">
              {w.bins.map((b) => (
                <li key={b.magnitude_at_least}>
                  M{b.magnitude_at_least}+:{' '}
                  {percent(b.probability_at_least_one)}
                  {b.count_p95_maximum !== null &&
                    ` (95% range ${b.count_p95_minimum ?? 0}–${b.count_p95_maximum} quakes)`}
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted">
        Expires <Timestamp value={f.expires_at_utc} />
      </p>
      <Source source={f.source} />
    </div>
  )
}

function Source({ source }: { source: OfficialEventForecast['source'] }) {
  return (
    <p className="text-xs text-muted">
      {source.provider} product issued{' '}
      <Timestamp value={source.issued_at_utc} />
      , retrieved <Timestamp value={source.retrieved_at_utc} /> (
      {source.vintage === 'archive_capture'
        ? 'archive capture'
        : 'captured at the time'}
      ) ·{' '}
      <a
        className="text-link underline"
        href={source.url}
        target="_blank"
        rel="noreferrer noopener"
      >
        original product
      </a>
    </p>
  )
}

function Unavailable({ f }: { f: UnavailableForecast }) {
  return (
    <div className="space-y-1.5 rounded-xl border border-dashed border-line-strong px-3 py-2.5">
      <p className="font-semibold">Prediction unavailable</p>
      <p className="text-[13px] text-ink-2">{f.reason}</p>
      {f.required_inputs.length > 0 && (
        <p className="text-xs text-muted">
          Needs: {f.required_inputs.join('; ')}
        </p>
      )}
      <p className="text-xs text-muted">
        No probability is shown in its place.
      </p>
    </div>
  )
}
