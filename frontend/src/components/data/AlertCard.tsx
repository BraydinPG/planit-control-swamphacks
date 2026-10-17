import type { Alert } from '../../types/api'
import { countdown } from '../../api/contracts'
import { useApplication, useClock } from '../../application/context'
import { Timestamp } from './Status'
import { Action } from './Interaction'
import { RiskShape, type RiskShapeKind } from './Risk'
import { Icon } from '../shell/Icon'

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
    band: 'bg-warn text-[#1a1e24]',
    ring: 'border-warn',
    word: 'Warning',
  }
}

/** Visual-only progress ring for the server-supplied all-clear window. */
function Ring({ alert, left }: { alert: Alert; left: number | null }) {
  const start = Date.parse(alert.latest_event_at)
  const end = alert.clear_after ? Date.parse(alert.clear_after) : NaN
  const total = Number.isFinite(start) && Number.isFinite(end) ? (end - start) / 1000 : 1800
  const fraction = left === null ? 0 : Math.max(0, Math.min(1, left / Math.max(total, 1)))
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
          stroke="var(--pc-stop-text)"
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - fraction)}
          className="transition-[stroke-dashoffset] duration-700"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-5xl font-bold tabular-nums tracking-tight">
          {left === null ? '--:--' : clock(left)}
        </span>
        <span className="text-sm text-muted">until all-clear</span>
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
  const { client, persona } = useApplication(),
    now = useClock()
  const style = look(alert),
    left = remaining(alert, now)
  const title =
    alert.rule === 'lightning_stop_work' && alert.state === 'active'
      ? 'Stop-work alert active'
      : `${alert.rule.replaceAll('_', ' ')} — ${alert.state}`
  const source = `${client.mode === 'demo' ? 'Simulated alert payload. ' : ''}Status from ${client.mode === 'demo' ? 'replay fixture' : 'backend'}`
  return (
    <section
      aria-label={`Alert ${alert.id}`}
      className={`overflow-hidden rounded-2xl border-[3px] bg-surface ${style.ring}`}
    >
      <div className={`flex items-center gap-3 px-4 py-3 ${style.band}`}>
        <RiskShape
          kind={style.kind}
          className={detail ? 'size-8' : 'size-8 @lg:size-10'}
        />
        <h2
          className={`font-condensed uppercase leading-[0.95] ${detail ? 'text-3xl' : 'text-[2rem] @lg:text-4xl'}`}
        >
          {title}
        </h2>
      </div>
      <div className="space-y-3 p-4">
        {!detail && (
          <a
            className="flex min-h-14 items-center justify-between gap-3 rounded-xl border border-line-strong bg-surface-2 px-4 text-lg font-bold text-ink hover:bg-bg"
            href={`#/${persona}/alerts/${encodeURIComponent(alert.id)}`}
          >
            Inspect alert and acknowledge
            <Icon name="arrow" className="size-5 shrink-0" />
          </a>
        )}
        {!detail && left !== null && (
          <div className="flex items-baseline justify-between gap-3 border-t border-line pt-3">
            <span className="text-base font-semibold">All-clear in</span>
            <span
              className="text-4xl font-bold leading-none tabular-nums tracking-tight"
              aria-hidden="true"
            >
              {clock(left)}
            </span>
          </div>
        )}
        {detail && <Ring alert={alert} left={left} />}
        <p className="text-sm text-ink-2">
          {source}: <strong className="text-ink">{alert.state}</strong>
          {alert.is_prototype_rule ? ' · Prototype rule' : ''}
        </p>
        <p className="text-sm text-muted">
          Latest qualifying event: <Timestamp value={alert.latest_event_at} />
        </p>
        <p
          role="timer"
          className={`font-semibold ${detail ? 'text-center text-lg' : 'text-base'}`}
        >
          {countdown(alert, now)}
        </p>
        <p className="text-xs leading-relaxed text-muted">
          Countdown is a display estimate. A zero countdown never clears an alert
          or authorizes work. Follow the authoritative alert and employer
          procedures.
        </p>
        {detail && (
          <div className="space-y-4">
            <dl className="divide-y divide-line border-y border-line text-sm">
              {[
                ['Trigger', <Timestamp key="t" value={alert.triggered_at} />],
                [
                  'Supplied distance',
                  `${alert.distance_miles ?? 'unknown'} mi`,
                ],
                ['Window end', <Timestamp key="w" value={alert.clear_after} />],
                [
                  'Rule',
                  alert.is_prototype_rule
                    ? 'Prototype rule, not employer policy'
                    : 'Stop for any strike within 10 mi. Clear after 30 minutes without one.',
                ],
                [
                  'Source',
                  alert.simulated
                    ? 'Simulated replay, not a live feed'
                    : 'Server evidence',
                ],
              ].map(([k, v], i) => (
                <div
                  key={i}
                  className="flex flex-wrap justify-between gap-x-4 gap-y-1 py-2.5"
                >
                  <dt className="text-muted">{k}</dt>
                  <dd className="text-right font-semibold">{v}</dd>
                </div>
              ))}
            </dl>
            {alert.evidence.length > 0 && (
              <div>
                <h3 className="kicker mb-2">Evidence</h3>
                <ul className="space-y-1.5 text-sm">
                  {alert.evidence.map((e) => (
                    <li
                      key={e.id}
                      className="break-words rounded-lg bg-surface-2 px-3 py-2"
                    >
                      <span className="font-mono text-xs text-muted">
                        {e.id}
                      </span>
                      : {e.label} · <Timestamp value={e.observed_at} />
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <p className="text-sm">
              {alert.acknowledgements.length} acknowledgement(s). Acknowledging
              does not clear the alert.
            </p>
            <Action
              capability="acknowledge"
              tone="big"
              disabled={alert.state !== 'active'}
              run={() => client.acknowledge(alert.id)}
            >
              {client.mode === 'demo'
                ? 'Record simulated acknowledgement'
                : 'Acknowledge alert'}
            </Action>
          </div>
        )}
      </div>
    </section>
  )
}
