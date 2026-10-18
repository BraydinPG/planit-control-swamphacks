import type { SiteRecord } from '../../api/contracts'
import { siteHazards } from '../../presentation/site-hazards'
import { Details } from './Details'
import { RiskShape } from './Risk'
import { Status, Timestamp } from './Status'

/** Environmental evidence and confirmed reports supplement, never replace, notice workflows. */
export function SiteHazards({ site }: { site: SiteRecord }) {
  const hazards = siteHazards(site)
  if (!hazards.length) return null
  return (
    <section aria-label="Environmental hazards and score contributors"
      className="@container overflow-hidden rounded-2xl border border-line-strong bg-surface">
      <div className="flex items-center gap-3 border-b border-line px-4 py-3">
        <RiskShape kind="warn" className="size-6" />
        <h3 className="text-base font-bold">Active alerts and score contributors</h3>
      </div>
      <ul className="grid @xl:grid-cols-2">
        {hazards.map((hazard) => (
          <li key={hazard.id} data-site-hazard={hazard.id} className="min-w-0 space-y-2.5 border-b border-line p-4">
            <h4 className="text-lg font-bold">{hazard.label}</h4>
            {hazard.alerts.map((alert) => (
              <div key={alert.id} className="space-y-1 text-sm">
                <p className="font-semibold">Active {alert.rule === 'heat' ? 'advisory' : 'alert'} · {alert.event_label}</p>
                {!hazard.factors.length && <p className="text-muted">Latest qualifying event: <Timestamp value={alert.latest_event_at} /></p>}
                {alert.simulated && !hazard.factors.some((f) => f.data_state === 'simulated') && <Status state="simulated" />}
              </div>
            ))}
            {hazard.report && <p className="text-sm font-semibold">Supervisor-confirmed report</p>}
            {hazard.factors.map((factor, i) => (
              <div key={`${factor.evidence_id}-${i}`} className="space-y-1 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Status state={factor.data_state} />
                  <span className="font-semibold tabular-nums">{factor.contribution} score {factor.contribution === 1 ? 'point' : 'points'}</span>
                </div>
                <p className="text-muted [overflow-wrap:anywhere]">{factor.source} · <Timestamp value={factor.observed_at} /></p>
              </div>
            ))}
            <Details title="Hazard evidence">
              {hazard.alerts.map((alert) => (
                <p key={alert.id} className="text-sm [overflow-wrap:anywhere]">
                  Alert: {alert.id}. {alert.evidence.map((e) => `${e.label} (${e.id})`).join('; ')}
                </p>
              ))}
              {hazard.factors.map((factor, i) => (
                <p key={i} className="text-sm [overflow-wrap:anywhere]">
                  {factor.label}<br />
                  Score evidence: {factor.evidence_id ?? 'reference not supplied'}.
                  {factor.is_prototype && ' Prototype scoring setting, not employer policy.'}
                </p>
              ))}
              <p className="text-sm text-muted">Source evidence does not confirm unmeasured worksite conditions. Alerts and supervisor instructions still apply.</p>
            </Details>
          </li>
        ))}
      </ul>
    </section>
  )
}
