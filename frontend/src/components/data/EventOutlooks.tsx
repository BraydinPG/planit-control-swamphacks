import { useState, type ReactNode } from 'react'
import type {
  DurationForecast,
  EventOutlookCard,
  OfficialAftershockForecast,
  OfficialEventForecast,
  UnavailableForecast,
} from '../../types/api'
import {
  displayLabel,
  outlookUnavailableLabel,
} from '../../presentation/display'
import { Details } from './Details'
import { Timestamp } from './Status'

// Presentation only: one independent card per backend event, never a site score.
const percent = (p: number) => `${Math.round(p * 100)}%`
const hours = (h: number | null) =>
  h === null
    ? 'Unknown'
    : `${h % 1 === 0 ? h : h.toFixed(1)} ${h === 1 ? 'hour' : 'hours'}`
const presentationText: Record<EventOutlookCard['presentation'], string> = {
  current: 'Current event',
  replay: 'Simulated replay',
  historical_example: 'Historical example',
}
const kindText: Record<EventOutlookCard['forecast']['kind'], string> = {
  historical_duration_research: 'Research duration estimate',
  official_event_forecast: 'National Hurricane Center forecast',
  official_aftershock_forecast: 'U.S. Geological Survey forecast',
  unavailable: 'Prediction unavailable',
}

/** `tiles` uses the crew Weather and conditions layout; the default keeps full cards. */
export function EventOutlooks({
  cards,
  tiles = false,
}: {
  cards: EventOutlookCard[]
  tiles?: boolean
}) {
  return (
    <section className="space-y-3" aria-labelledby="event-outlooks-title">
      <div>
        <h2
          id="event-outlooks-title"
          className={`text-lg font-bold ${tiles ? 'tracking-tight @lg:text-xl' : ''}`}
        >
          Event outlooks
        </h2>
        <p className="text-sm text-ink-2">
          Advisory only. Does not change the score, clear alerts, or authorize
          work.
        </p>
      </div>
      {cards.length && tiles ? (
        <OutlookTiles cards={cards} />
      ) : cards.length ? (
        <div className="grid items-start gap-3 @3xl:grid-cols-2">
          {cards.map((card) => (
            <OutlookCard key={card.event_id} card={card} />
          ))}
        </div>
      ) : (
        <p className="rounded-xl bg-surface p-4 text-sm text-ink-2">
          No confirmed event outlook is available. Conditions remain unknown.
        </p>
      )}
    </section>
  )
}

function OutlookCard({ card }: { card: EventOutlookCard }) {
  const f = card.forecast
  return (
    <article
      data-outlook-id={card.event_id}
      aria-label={`${card.event_type} outlook`}
      className="min-w-0 space-y-3 rounded-2xl border border-line bg-surface p-4 [overflow-wrap:anywhere]"
    >
      <header className="space-y-2">
        <h3 className="text-xl font-bold leading-snug">
          {displayLabel(card.event_type)}
        </h3>
        <div className="flex flex-wrap gap-1.5">
          <span
            className={`chip border ${card.presentation === 'current' ? 'border-line-strong text-ink-2' : 'border-dotted border-sim text-sim'}`}
          >
            {presentationText[card.presentation]}
          </span>
          {f.kind !== 'unavailable' && (
            <span className="chip border border-line-strong text-ink-2">
              {kindText[f.kind]}
            </span>
          )}
        </div>
        {card.presentation === 'historical_example' && (
          <p className="text-sm font-semibold text-sim">
            Archived agency forecast, not a current prediction.
          </p>
        )}
      </header>
      {f.kind === 'historical_duration_research' && <Duration f={f} />}
      {f.kind === 'official_event_forecast' && <Storm f={f} />}
      {f.kind === 'official_aftershock_forecast' && <Aftershock f={f} />}
      {f.kind === 'unavailable' && <Unavailable f={f} />}
      <p className="text-sm text-muted">
        As of <Timestamp value={card.as_of_utc} />
      </p>
      <p className="text-sm font-medium text-ink-2">
        {displayLabel(card.association.method, 'Site link unknown')}
      </p>
      <Details
        title="How was this estimated?"
        label={`${card.event_type}: how was this estimated?`}
      >
        <OutlookEvidence card={card} />
      </Details>
    </article>
  )
}

/** The evidence behind one outlook; shared by full cards and crew tiles. */
function OutlookEvidence({ card }: { card: EventOutlookCard }) {
  const f = card.forecast
  return (
    <>
      <p className="font-semibold">{card.event_name}</p>
      <dl className="divide-y divide-line rounded-xl bg-surface-2">
        <Row label="Event start">
          {card.event_start_utc ? (
            <Timestamp value={card.event_start_utc} />
          ) : (
            'Unknown; warning times are not event starts.'
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
          {displayLabel(card.confirmation.status)} ·{' '}
          {displayLabel(card.confirmation.basis)}
        </Row>
      </dl>
      <p>{card.association.description}</p>
      {f.kind === 'historical_duration_research' && <DurationDetails f={f} />}
      {f.kind === 'official_event_forecast' && <StormDetails f={f} />}
      {f.kind === 'official_aftershock_forecast' && (
        <AftershockDetails f={f} />
      )}
      {f.kind === 'unavailable' && (
        <>
          <p>{f.reason}</p>
          {f.required_inputs.length > 0 && (
            <div>
              <h4 className="font-semibold">Missing requirements</h4>
              <ul className="list-disc space-y-1 pl-5">
                {f.required_inputs.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
      {card.evidence.length > 0 && (
        <div>
          <h4 className="font-semibold">Evidence records</h4>
          <ul className="space-y-2">
            {card.evidence.map((e) => (
              <li key={e.id}>
                <span className="font-mono">{e.id}</span> · {e.source_id}
                <br />
                Valid <Timestamp value={e.valid_time_utc} />
              </li>
            ))}
          </ul>
        </div>
      )}
      <div>
        <h4 className="font-semibold">Limitations</h4>
        <ul className="list-disc space-y-1 pl-5">
          {card.limitations.map((l, i) => (
            <li key={i}>{l}</li>
          ))}
        </ul>
      </div>
    </>
  )
}

const tileLimit = 4

// Same shape as the crew Weather and conditions pane: compact tiles, a
// View more toggle past four, then one shared disclosure for the evidence.
function OutlookTiles({ cards }: { cards: EventOutlookCard[] }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div className="@container space-y-2 rounded-2xl border border-line bg-surface p-3">
      <ul className="grid gap-2 @md:grid-cols-2">
        {(expanded ? cards : cards.slice(0, tileLimit)).map((card) => (
          <OutlookTile key={card.event_id} card={card} />
        ))}
      </ul>
      {cards.length > tileLimit && (
        <button
          type="button"
          aria-expanded={expanded}
          data-outlook-more
          className="inline-flex min-h-11 items-center rounded-xl bg-surface-2 px-4 py-2 text-sm font-semibold text-ink"
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? 'View less' : `View more (${cards.length - tileLimit})`}
        </button>
      )}
      <Details title="How each outlook was estimated">
        <ul className="divide-y divide-line text-sm">
          {cards.map((card) => (
            <li key={card.event_id} className="space-y-2 py-2 leading-relaxed">
              <p className="font-semibold text-ink">
                {displayLabel(card.event_type)}
              </p>
              <p className="font-medium">
                {displayLabel(card.association.method, 'Site link unknown')}
              </p>
              <OutlookEvidence card={card} />
            </li>
          ))}
        </ul>
      </Details>
    </div>
  )
}

function tileReading(f: EventOutlookCard['forecast']): {
  value: string
  unit: string
  note: string
} {
  if (f.kind === 'historical_duration_research') {
    const d = f.remaining_duration_hours
    return {
      value: hours(d.median),
      unit: 'remaining',
      note:
        (d.p10 !== null && d.p90 !== null
          ? `Likely ${hours(d.p10)} to ${hours(d.p90)}. `
          : 'Range partly unknown. ') + 'Not a time to resume work.',
    }
  }
  if (f.kind === 'official_event_forecast')
    return {
      value: String(f.initial_position.max_sustained_wind_kt),
      unit: 'knots at issue',
      note: `${f.storm_name}. Local wind and event end time are unknown.`,
    }
  if (f.kind === 'official_aftershock_forecast') {
    const window = f.windows[0]
    const bin = window?.bins[0]
    return bin
      ? {
          value: percent(bin.probability_at_least_one),
          unit: `chance of M${bin.magnitude_at_least}+`,
          note: `${window.label} · sequence region, not this worksite.`,
        }
      : { value: 'Unknown', unit: '', note: 'Sequence region, not this worksite.' }
  }
  return {
    value: 'Prediction unavailable',
    unit: '',
    note: `${outlookUnavailableLabel(f.reason_code)} No probability is substituted.`,
  }
}

function OutlookTile({ card }: { card: EventOutlookCard }) {
  const f = card.forecast
  const reading = tileReading(f)
  const missing = f.kind === 'unavailable'
  return (
    <li
      data-outlook-id={card.event_id}
      aria-label={`${card.event_type} outlook`}
      className="flex min-w-0 flex-col gap-1.5 rounded-xl bg-surface-2 p-3"
    >
      <p className="text-sm font-semibold text-ink-2 [overflow-wrap:anywhere]">
        {displayLabel(card.event_type)}
      </p>
      <p
        className={`text-xl font-bold leading-snug tracking-tight tabular-nums [overflow-wrap:anywhere] ${missing ? 'text-muted' : ''}`}
      >
        {reading.value}{' '}
        <span className="text-sm font-semibold text-muted">{reading.unit}</span>
      </p>
      <p className="text-sm text-ink-2">{reading.note}</p>
      <p className="flex flex-wrap gap-1.5">
        <span
          className={`chip border ${card.presentation === 'current' ? 'border-line-strong text-ink-2' : 'border-dotted border-sim text-sim'}`}
        >
          {presentationText[card.presentation]}
        </span>
        {f.kind !== 'unavailable' && (
          <span className="chip border border-line-strong text-ink-2">
            {kindText[f.kind]}
          </span>
        )}
      </p>
      {card.presentation === 'historical_example' && (
        <p className="text-xs font-semibold text-sim">
          Archived agency forecast, not a current prediction.
        </p>
      )}
      <p className="mt-auto text-xs text-muted">
        As of <Timestamp value={card.as_of_utc} />
      </p>
    </li>
  )
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1 px-3 py-2">
      <dt className="text-muted">{label}</dt>
      <dd className="font-medium">{children}</dd>
    </div>
  )
}
function Duration({ f }: { f: DurationForecast }) {
  const d = f.remaining_duration_hours
  return (
    <div className="space-y-1">
      <p className="text-sm text-muted">Estimated time remaining</p>
      <p className="text-3xl font-bold tabular-nums">{hours(d.median)}</p>
      <p className="text-sm text-ink-2">
        {d.p10 !== null && d.p90 !== null
          ? `Likely range: ${hours(d.p10)} to ${hours(d.p90)}.`
          : d.p10 !== null
            ? `Lower range estimate: ${hours(d.p10)}. Upper estimate unknown.`
            : d.p90 !== null
              ? `Upper range estimate: ${hours(d.p90)}. Lower estimate unknown.`
              : 'Duration range unknown.'}
      </p>
      <p className="text-sm font-medium">
        Research estimate of the recorded event, not a time to resume work.
      </p>
    </div>
  )
}
function DurationDetails({ f }: { f: DurationForecast }) {
  return (
    <>
      <p>
        The range spans the 10th–90th percentiles of recorded event duration.
        Local severity and trend are unknown.
      </p>
      <ul aria-label="Chance the event is still ongoing" className="space-y-2">
        {f.persistence.map((p) => (
          <li
            key={p.horizon_hours}
            className="flex flex-wrap justify-between gap-2"
          >
            <span>Still ongoing in {p.horizon_hours} hours</span>
            <strong>{percent(p.recorded_event_ongoing_probability)}</strong>
          </li>
        ))}
      </ul>
      <p>
        Model: {f.model_version} · Estimator: {f.estimator}
        {f.training_support_at_event_age !== null &&
          ` · ${f.training_support_at_event_age} historical events at this age`}
      </p>
    </>
  )
}
function Storm({ f }: { f: OfficialEventForecast }) {
  return (
    <div className="space-y-2">
      <p className="text-lg font-semibold">
        {f.storm_name} · {f.initial_position.max_sustained_wind_kt} knots at
        issue
      </p>
      <p className="text-sm text-ink-2">
        Cyclone track and winds; local wind and event end time are unknown.
      </p>
    </div>
  )
}
function StormDetails({ f }: { f: OfficialEventForecast }) {
  return (
    <>
      <p>
        Cyclone {f.cyclone_id} · {displayLabel(f.initial_position.phase)}. Next
        advisory scheduled <Timestamp value={f.next_advisory_at_utc} />.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm tabular-nums">
          <caption className="text-left font-semibold">
            Issued forecast track
          </caption>
          <thead>
            <tr>
              <th className="p-2">Valid</th>
              <th className="p-2">Position</th>
              <th className="p-2">Max wind</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {f.forecast_points.map((p) => (
              <tr key={p.valid_at_utc}>
                <td className="p-2">
                  <Timestamp value={p.valid_at_utc} />
                </td>
                <td className="p-2">
                  {p.lat.toFixed(1)}, {p.lon.toFixed(1)}
                </td>
                <td className="p-2">
                  {p.max_sustained_wind_kt} knots
                  {p.gust_kt !== null && ` (gusts ${p.gust_kt})`}
                  {p.phase && ` · ${displayLabel(p.phase)}`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Source source={f.source} />
    </>
  )
}
function Aftershock({ f }: { f: OfficialAftershockForecast }) {
  const window = f.windows[0]
  const bin = window?.bins[0]
  return (
    <div className="space-y-2">
      {bin && (
        <>
          <p className="text-2xl font-bold">
            {percent(bin.probability_at_least_one)} chance of magnitude{' '}
            {bin.magnitude_at_least}+ aftershock
          </p>
          <p className="text-sm text-ink-2">
            {window.label} · At least one in the sequence region.
          </p>
        </>
      )}
      <p className="text-sm text-ink-2">
        Official aftershock outlook for the {f.region.radius_km} km sequence
        region, not this worksite. No earthquake end-time forecast.
      </p>
      <p className="text-sm text-muted">
        Magnitude {f.mainshock.magnitude} mainshock ·{' '}
        <Timestamp value={f.mainshock.time_utc} />
      </p>
    </div>
  )
}
function AftershockDetails({ f }: { f: OfficialAftershockForecast }) {
  return (
    <>
      <p>Chance of at least one aftershock anywhere in the sequence region:</p>
      <ul className="space-y-3">
        {f.windows.map((w) => (
          <li key={w.label} className="rounded-xl bg-surface-2 p-3">
            <p className="font-semibold">{w.label}</p>
            <p>
              <Timestamp value={w.start_utc} /> to{' '}
              <Timestamp value={w.end_utc} />
            </p>
            <ul className="mt-2 space-y-1">
              {w.bins.map((b) => (
                <li key={b.magnitude_at_least}>
                  Magnitude {b.magnitude_at_least}+:{' '}
                  {percent(b.probability_at_least_one)}
                  {b.count_p95_maximum !== null &&
                    ` (95% range ${b.count_p95_minimum ?? 0}–${b.count_p95_maximum} earthquakes)`}
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
      <p>
        Expires <Timestamp value={f.expires_at_utc} />
      </p>
      <Source source={f.source} />
    </>
  )
}
function Source({ source }: { source: OfficialEventForecast['source'] }) {
  return (
    <p>
      {source.provider} · Issued <Timestamp value={source.issued_at_utc} />
      <br />
      Retrieved <Timestamp value={source.retrieved_at_utc} /> ·{' '}
      {source.vintage === 'archive_capture'
        ? 'Archive capture'
        : 'Captured at the time'}
      <br />
      <a
        className="inline-flex min-h-11 items-center text-link underline"
        href={source.url}
        target="_blank"
        rel="noreferrer noopener"
      >
        View original agency forecast
      </a>
    </p>
  )
}
function Unavailable({ f }: { f: UnavailableForecast }) {
  return (
    <div className="rounded-xl border border-dashed border-line-strong p-3">
      <p className="font-semibold">Prediction unavailable</p>
      <p className="mt-1 text-sm text-ink-2">
        {outlookUnavailableLabel(f.reason_code)} No probability is substituted.
      </p>
    </div>
  )
}
