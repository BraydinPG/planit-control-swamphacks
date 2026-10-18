import { useContext, useState } from 'react'
import type { SiteRecord } from '../../api/contracts'
import { siteHazards } from '../../presentation/site-hazards'
import { Details } from './Details'
import { RiskShape } from './Risk'
import { Status, Timestamp } from './Status'
import { NoticeCard } from './NoticeCard'
import { Icon } from '../shell/Icon'
import { displayLabel } from '../../presentation/display'
import { ApplicationContext } from '../../application/context'

/** One hazard row holds its alerts, score evidence, confirmations and instructions.
 * Every row, confirmed or still potential, starts folded to save space. */
export function SiteHazards({ site }: { site: SiteRecord }) {
  // Confirmation can move a notice from pending to its merged hazard row during
  // a GET refresh. Preserve an in-flight supervisor draft across that move.
  const [drafts] = useState(() => new Map<string, string>())
  const application = useContext(ApplicationContext)
  // A folded row still says when this supervisor has an instruction to review and send.
  const toSend = (notices: SiteRecord['notices']) =>
    application?.persona === 'supervisor' &&
    notices.some(
      (n) =>
        n.status === 'confirmed' &&
        n.confirmed_by === application.principalId &&
        !n.instruction_sent_at,
    )
  const hazards = siteHazards(site)
  const pending = site.notices.filter((n) => n.status === 'potential')
  return (
    <>
    {hazards.length > 0 && <section aria-label="Confirmed hazards"
      className="scroll-mt-20 overflow-hidden rounded-2xl border border-line-strong bg-surface">
      <div className="flex items-center gap-3 border-b border-line px-4 py-3">
        <RiskShape kind="warn" className="size-6" />
        <h3 className="flex-1 text-lg font-bold">Confirmed hazards</h3>
        <span className="chip border border-line-strong">{hazards.length} {hazards.length === 1 ? 'hazard' : 'hazards'}</span>
      </div>
      <ul className="divide-y divide-line">
        {hazards.map((hazard) => (
          <li key={hazard.id} data-site-hazard={hazard.id} className="min-w-0">
            <details data-hazard-row className="group/hazard">
            <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 [&::-webkit-details-marker]:hidden">
              <span className="flex min-w-0 flex-wrap items-center gap-2">
                <h4 className="text-lg font-bold">{hazard.label}</h4>
                {toSend(hazard.notices) && <span className="chip border border-caution text-warn-text">Instruction to review</span>}
              </span>
              <Icon name="back" className="size-5 shrink-0 -rotate-90 transition-transform group-open/hazard:rotate-90" />
            </summary>
            <div className="space-y-2.5 px-4 pb-4">
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
                  <Status state={factor.data_state} />{' '}
                  <span className="font-semibold tabular-nums">{factor.contribution} score {factor.contribution === 1 ? 'point' : 'points'}</span>
                </div>
                <p className="text-muted [overflow-wrap:anywhere]">{factor.source} · <Timestamp value={factor.observed_at} /></p>
              </div>
            ))}
            {hazard.notices.map((notice) => (
              <NoticeCard key={notice.id} notice={notice} embedded drafts={drafts} outlook={site.event_outlook} />
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
            </div>
            </details>
          </li>
        ))}
      </ul>
    </section>}
    {pending.length > 0 && <section aria-label="Potential hazards"
      className="scroll-mt-20 overflow-hidden rounded-2xl border-2 border-dashed border-caution bg-surface">
      <ul className="divide-y divide-line">
        {pending.map((notice) => (
          <li key={notice.id} className="min-w-0">
            <details data-hazard-row className="group/hazard">
            <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 [&::-webkit-details-marker]:hidden">
              <span className="flex min-w-0 items-center gap-3">
                <RiskShape kind="caution" className="size-5 shrink-0" />
                <h4 className="text-lg font-bold">{displayLabel(notice.hazard_label)}</h4>
              </span>
              <Icon name="back" className="size-5 shrink-0 -rotate-90 transition-transform group-open/hazard:rotate-90" />
            </summary>
            <div className="px-4 pb-4">
              <NoticeCard notice={notice} embedded drafts={drafts} outlook={site.event_outlook} />
            </div>
            </details>
          </li>
        ))}
      </ul>
    </section>}
    {!hazards.length && !pending.length && <p className="text-sm text-muted">No confirmed hazards supplied. Unmeasured conditions remain unknown.</p>}
    </>
  )
}
