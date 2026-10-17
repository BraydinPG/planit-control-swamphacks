import type { Alert } from '../../types/api'
import { countdown } from '../../api/contracts'
import { useApplication, useClock } from '../../application/context'
import { Timestamp } from './Status'
import { Action, control } from './Interaction'
export function AlertCard({
  alert,
  detail = false,
}: {
  alert: Alert
  detail?: boolean
}) {
  const { client, persona } = useApplication(),
    now = useClock()
  return (
    <section
      aria-label={`Alert ${alert.id}`}
      className={`rounded-xl border-2 p-4 ${alert.state === 'active' ? 'border-amber-600 bg-amber-50' : 'border-slate-300 bg-white'}`}
    >
      <h2 className="text-xl font-bold">
        {alert.rule === 'lightning_stop_work' && alert.state === 'active'
          ? 'Stop-work alert active'
          : `${alert.rule.replaceAll('_', ' ')} — ${alert.state}`}
      </h2>
      {!detail && (
        <a
          className={control + ' mt-3 inline-flex items-center'}
          href={`#/${persona}/alerts/${encodeURIComponent(alert.id)}`}
        >
          Inspect alert and acknowledge
        </a>
      )}
      <p>
        {client.mode === 'demo' ? 'Simulated alert payload. ' : ''}Status from{' '}
        {client.mode === 'demo' ? 'replay fixture' : 'backend'}:{' '}
        <strong>{alert.state}</strong>
        {alert.is_prototype_rule ? ' · Prototype rule' : ''}
      </p>
      <p className="mt-2 text-sm">
        Latest qualifying event: <Timestamp value={alert.latest_event_at} />
      </p>
      <p role="timer" className="font-semibold">
        {countdown(alert, now)}
      </p>
      <p className="text-xs">
        A zero countdown never clears an alert or authorizes work. Follow the
        authoritative alert and employer procedures.
      </p>
      {detail && (
        <div className="mt-4 space-y-4">
          <p>
            Trigger: <Timestamp value={alert.triggered_at} /> · Supplied
            distance: {alert.distance_miles ?? 'unknown'} mi · Window end:{' '}
            <Timestamp value={alert.clear_after} />
          </p>
          <ul>
            {alert.evidence.map((e) => (
              <li key={e.id}>
                {e.id}: {e.label} · <Timestamp value={e.observed_at} />
              </li>
            ))}
          </ul>
          <p>
            {alert.acknowledgements.length} acknowledgement(s). Acknowledging
            does not clear the alert.
          </p>
          <Action run={() => client.acknowledge(alert.id)}>
            {client.mode === 'demo'
              ? 'Record simulated acknowledgement'
              : 'Acknowledge alert'}
          </Action>
        </div>
      )}
    </section>
  )
}
