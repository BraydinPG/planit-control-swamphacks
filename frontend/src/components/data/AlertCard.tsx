import { useEffect, type ReactNode } from 'react'
import type { Alert } from '../../types/api'
import { countdown } from '../../api/contracts'
import { useApplication, useClock } from '../../application/context'
import { Timestamp } from './Status'
import { Action } from './Interaction'
import { RiskShape, type RiskShapeKind } from './Risk'
import { Icon } from '../shell/Icon'
import { displayLabel } from '../../presentation/display'
import { Details } from './Details'

function remaining(alert: Alert, now: number) {
  if (alert.state !== 'active' || !alert.clear_after) return null
  const end = Date.parse(alert.clear_after)
  if (!Number.isFinite(end)) return null
  return Math.max(0, Math.ceil((end - now) / 1000))
}
const clock = (s: number) =>
  `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

function look(alert: Alert): {
  kind: RiskShapeKind
  band: string
  ring: string
  word: string
} {
  if (alert.state !== 'active')
    return {
      kind: 'clear',
      band: 'bg-surface-2 text-ink',
      ring: 'border-line-strong',
      word: 'Not active',
    }
  if (alert.rule === 'lightning_stop_work')
    return {
      kind: 'stop',
      band: 'bg-stop text-white',
      ring: 'border-stop',
      word: 'Stop work',
    }
  return {
    kind: 'warn',
    band: 'bg-warn text-white',
    ring: 'border-warn',
    word: 'Warning',
  }
}

/** Visual-only progress ring for the server-supplied all-clear window. */
function Ring({
  alert,
  left,
  color,
}: {
  alert: Alert
  left: number
  color: string
}) {
  const start = Date.parse(alert.latest_event_at)
  const end = alert.clear_after ? Date.parse(alert.clear_after) : NaN
  const total =
    Number.isFinite(start) && Number.isFinite(end) ? (end - start) / 1000 : 1800
  const fraction = Math.max(0, Math.min(1, left / Math.max(total, 1)))
  const r = 92,
    c = 2 * Math.PI * r
  return (
    <div className="relative mx-auto size-52 @lg:size-56" aria-hidden="true">
      <svg viewBox="0 0 210 210" className="size-full -rotate-90">
        <circle
          cx="105"
          cy="105"
          r={r}
          fill="none"
          stroke="var(--pc-line)"
          strokeWidth="12"
        />
        <circle
          cx="105"
          cy="105"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - fraction)}
          className="transition-[stroke-dashoffset] duration-700"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-5xl font-bold tabular-nums tracking-tight">
          {clock(left)}
        </span>
        <span className="text-sm text-muted">watch window</span>
      </div>
    </div>
  )
}

export function AlertCard({
  alert,
  detail = false,
}: {
  alert: Alert
  detail?: boolean
}) {
  const { client, persona, refresh } = useApplication(),
    now = useClock()
  const style = look(alert),
    left = remaining(alert, now)
  const name =
    alert.rule === 'lightning_stop_work'
      ? 'Stop-work'
      : displayLabel(alert.rule)
  const title = `${name} alert${alert.state === 'active' ? ' active' : ' cleared'}`
  const simulated = alert.simulated || client.mode === 'demo'
  const acks = alert.acknowledgements.length
  const elapsed = left === 0
  useEffect(() => {
    if (client.mode !== 'live' || !elapsed) return
    // An expired watch window is not clearance. Ask for authoritative state.
    refresh()
    const timer = setInterval(refresh, 15000)
    return () => clearInterval(timer)
  }, [client, elapsed, refresh])
  return (
    <section
      aria-label={`Alert ${alert.id}`}
      data-alert-id={alert.id}
      className={`overflow-hidden rounded-2xl border-[3px] bg-surface ${style.ring}`}
    >
      <div className={`flex items-center gap-3 px-4 py-3 ${style.band}`}>
        <span
          className={
            style.kind === 'stop' && alert.state === 'active'
              ? 'pc-beacon'
              : 'inline-flex'
          }
        >
          <RiskShape
            kind={style.kind}
            className={detail ? 'size-8' : 'size-8 @lg:size-10'}
          />
        </span>
        <h2 className="text-2xl font-bold leading-tight @lg:text-3xl">
          {title}
        </h2>
      </div>
      <div className="space-y-3 p-4">
        {!detail && (
          <a
            className="flex min-h-14 items-center justify-between gap-3 rounded-xl border border-line-strong bg-surface-2 px-4 text-lg font-bold text-ink hover:bg-bg"
            href={`#/${persona}/alerts/${encodeURIComponent(alert.id)}`}
          >
            View alert
            <Icon name="arrow" className="size-5 shrink-0" />
          </a>
        )}
        {!detail && left !== null && left > 0 && (
          <div className="flex items-baseline justify-between gap-3 border-t border-line pt-3">
            <span className="text-base font-semibold">Watch window</span>
            <span
              className="text-4xl font-bold leading-none tabular-nums tracking-tight"
              aria-hidden="true"
            >
              {clock(left)}
            </span>
          </div>
        )}
        {detail && left !== null && left > 0 && (
          <Ring
            alert={alert}
            left={left}
            color={
              style.kind === 'stop'
                ? 'var(--pc-stop-text)'
                : 'var(--pc-warn-text)'
            }
          />
        )}
        <p className="text-sm text-ink-2">
          Status:{' '}
          <strong className="text-ink">{displayLabel(alert.state)}</strong>
          {simulated ? ' · Simulated replay' : ''}
          {alert.is_prototype_rule ? ' · Prototype rule' : ''}
        </p>
        <p className="text-sm text-muted">
          Latest qualifying event: <Timestamp value={alert.latest_event_at} />
        </p>
        <p
          role="timer"
          className={
            left !== null && left > 0 && !detail
              ? 'sr-only'
              : `font-semibold ${detail ? 'text-center text-lg' : 'text-base'}`
          }
        >
          {countdown(alert, now)
            .replace('remaining in server window', 'left in watch window')
            .replace(
              'No countdown supplied by server.',
              'No watch window available.',
            )}
        </p>
        <p className="text-sm text-ink-2">
          The timer does not clear this alert or authorize work.
        </p>
        {elapsed && client.mode === 'live' && (
          <p className="text-sm text-ink-2">Awaiting updated alert status. Checking every 15 seconds.</p>
        )}
        {detail && (
          <div className="space-y-4">
            <Details title="Alert evidence and timing">
              <dl className="divide-y divide-line border-y border-line text-sm">
                {(
                  [
                    [
                      'Triggered',
                      <Timestamp key="t" value={alert.triggered_at} />,
                    ],
                    alert.distance_miles !== null && [
                      'Distance',
                      `${alert.distance_miles} mi`,
                    ],
                    alert.clear_after && [
                      'Watch window ends',
                      <Timestamp key="w" value={alert.clear_after} />,
                    ],
                    [
                      'Rule',
                      alert.is_prototype_rule
                        ? 'Prototype rule, not employer policy'
                        : 'Stop for any strike within 10 mi. Clear after 30 minutes without one.',
                    ],
                    [
                      'Source',
                      simulated
                        ? 'Simulated replay, not a live feed'
                        : 'Live feed',
                    ],
                  ].filter(Boolean) as [string, ReactNode][]
                ).map(([k, v], i) => (
                  <div
                    key={i}
                    className="flex flex-wrap justify-between gap-x-4 gap-y-1 py-2.5"
                  >
                    <dt className="text-muted">{k}</dt>
                    <dd className="text-right font-semibold">{v}</dd>
                  </div>
                ))}
              </dl>
              {/* Crew see trigger, distance, rule and source above; evidence IDs stay on the supervisor view. */}
              {persona === 'supervisor' && alert.evidence.length > 0 && (
                <div>
                  <h3 className="kicker mb-2">Evidence</h3>
                  <ul className="space-y-1.5 text-sm">
                    {alert.evidence.map((e) => (
                      <li
                        key={e.id}
                        className="break-words rounded-lg bg-surface-2 px-3 py-2"
                      >
                        {e.label} ·{' '}
                        <span className="text-muted">
                          <Timestamp value={e.observed_at} />
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </Details>
            <p className="text-sm">
              {acks
                ? `${acks} acknowledgement${acks === 1 ? '' : 's'} so far.`
                : 'No acknowledgements yet.'}{' '}
              Acknowledging does not clear the alert.
            </p>
            <Action
              capability="acknowledge"
              tone="big"
              disabled={alert.state !== 'active'}
              run={() => client.acknowledge(alert.id)}
            >
              {client.mode === 'demo'
                ? 'Acknowledge in demo'
                : 'Acknowledge alert'}
            </Action>
          </div>
        )}
      </div>
    </section>
  )
}
