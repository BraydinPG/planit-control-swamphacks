import { useState } from 'react'
import type { EventOutlook, HazardNotice } from '../../types/api'
import { useApplication } from '../../application/context'
import { Action, field, labelText } from './Interaction'
import { Timestamp } from './Status'
import { RiskShape } from './Risk'
import { ExpectedDuration } from './Duration'
import { displayLabel } from '../../presentation/display'
import { Details } from './Details'
/** `outlook` is the site's event outlook; it shows on the confirmed notice it belongs to. */
export function NoticeCard({
  notice,
  outlook = null,
}: {
  notice: HazardNotice
  outlook?: EventOutlook | null
}) {
  return <NoticeWorkflow key={notice.id} initial={notice} outlook={outlook} />
}
function NoticeWorkflow({
  initial,
  outlook,
}: {
  initial: HazardNotice
  outlook: EventOutlook | null
}) {
  const [responseNotice, setNotice] = useState<HazardNotice | null>(null)
  // Keep the returned server confirmation while its GET refresh is in flight.
  // Equivalent refreshes must not remount the editor and erase a supervisor's draft.
  // A different owner or delivered instruction in a newer GET takes precedence.
  const notice =
    responseNotice &&
    (initial.status === 'potential' ||
      (initial.confirmed_by === responseNotice.confirmed_by &&
        !initial.instruction_sent_at))
      ? responseNotice
      : initial
  const { client, persona, principalId } = useApplication()
  const potential = notice.status === 'potential'
  return (
    <article
      data-notice-id={notice.id}
      className={`scroll-mt-20 space-y-3 rounded-2xl border-2 bg-surface p-4 ${potential ? 'border-dashed border-caution' : 'border-line-strong'}`}
    >
      <div className="flex items-start gap-3">
        <RiskShape
          kind={potential ? 'caution' : 'warn'}
          className="mt-0.5 size-6"
        />
        <div className="min-w-0 flex-1">
          <p className="kicker">
            {potential
              ? 'Potential hazard · awaiting confirmation'
              : 'Confirmed hazard'}
          </p>
          <h3 className="text-xl font-bold">
            {displayLabel(notice.hazard_label)}
          </h3>
        </div>
      </div>
      {potential ? (
        <p className="rounded-xl border border-dashed border-line-strong px-3 py-2.5 text-sm font-semibold">
          No instruction: supervisor confirmation is pending.
        </p>
      ) : notice.instruction_sent_at && notice.instruction ? (
        <div className="rounded-xl bg-surface-2 p-3 ring-1 ring-line-strong">
          <strong className="kicker text-ink!">
            Supervisor-approved instruction
          </strong>
          <p className="mt-1 text-lg font-semibold">{notice.instruction}</p>
          <p className="mt-1 text-sm text-muted">
            Sent <Timestamp value={notice.instruction_sent_at} />
          </p>
        </div>
      ) : (
        <p className="text-sm">
          Confirmed; no approved instruction has been sent.
        </p>
      )}
      {!potential && outlook?.event_id === notice.id && (
        <ExpectedDuration outlook={outlook} />
      )}
      {persona === 'supervisor' && potential && (
        <Action
          capability="hazards"
          tone="primary"
          run={async () => {
            const response = await client.confirm(notice.id)
            setNotice(response.notice)
          }}
        >
          Confirm for your organization
        </Action>
      )}
      {persona === 'supervisor' &&
        notice.status === 'confirmed' &&
        notice.confirmed_by !== principalId &&
        !notice.instruction_sent_at && (
          <p className="rounded-xl border border-dashed border-line-strong px-3 py-2.5 text-sm text-ink-2">
            Only the supervisor who confirmed this hazard for your
            organization can send its instruction.
          </p>
        )}
      {persona === 'supervisor' &&
        notice.status === 'confirmed' &&
        notice.confirmed_by === principalId &&
        !notice.instruction_sent_at && (
          <InstructionEditor
            key={notice.suggested_instruction}
            notice={notice}
            sent={setNotice}
          />
        )}
      <NoticeSource notice={notice} />
    </article>
  )
}

function NoticeSource({ notice }: { notice: HazardNotice }) {
  return (
    <Details title="Notice source and coverage">
      <p className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-2">
        <span>
          Status:{' '}
          <strong className="text-ink">{displayLabel(notice.status)}</strong>
        </span>
        <span>
          Radius: {notice.radius_miles} mi ({displayLabel(notice.radius_source)}
          {notice.radius_source === 'default' ? ' prototype default' : ''})
        </span>
      </p>
      <p className="break-words text-sm text-muted">
        {notice.source} · {notice.source_ref} · Created{' '}
        <Timestamp value={notice.created_at} />
      </p>
    </Details>
  )
}

/**
 * Every settled confirmed hazard in one card, one row each. Potential notices and
 * a confirmed notice the viewer still has to instruct keep their own NoticeCard.
 */
export function ConfirmedHazards({
  notices,
  outlook = null,
}: {
  notices: HazardNotice[]
  outlook?: EventOutlook | null
}) {
  if (!notices.length) return null
  return (
    <section
      aria-label="Confirmed hazards"
      className="overflow-hidden rounded-2xl border-2 border-line-strong bg-surface"
    >
      <div className="flex items-center gap-3 border-b border-line px-4 py-3">
        <RiskShape kind="warn" className="size-6" />
        <div>
          <p className="kicker">Confirmed hazards</p>
          <h3 className="text-xl font-bold">
            {notices.length} confirmed{' '}
            {notices.length === 1 ? 'hazard' : 'hazards'}
          </h3>
        </div>
      </div>
      <ul className="divide-y divide-line">
        {notices.map((notice) => (
          <li
            key={notice.id}
            data-notice-id={notice.id}
            className="scroll-mt-20 space-y-2.5 p-4"
          >
            <h4 className="text-lg font-bold">
              {displayLabel(notice.hazard_label)}
            </h4>
            <Details title="View more" label={`View more about ${displayLabel(notice.hazard_label)}`}>
            {notice.instruction_sent_at && notice.instruction ? (
              <div className="rounded-xl bg-surface-2 p-3 ring-1 ring-line-strong">
                <strong className="kicker text-ink!">
                  Supervisor-approved instruction
                </strong>
                <p className="mt-1 text-base font-semibold">
                  {notice.instruction}
                </p>
                <p className="mt-1 text-sm text-muted">
                  Sent <Timestamp value={notice.instruction_sent_at} />
                </p>
              </div>
            ) : (
              <p className="text-sm">
                Confirmed; no approved instruction has been sent.
              </p>
            )}
            {outlook?.event_id === notice.id && (
              <ExpectedDuration outlook={outlook} />
            )}
            <NoticeSource notice={notice} />
            </Details>
          </li>
        ))}
      </ul>
    </section>
  )
}

function InstructionEditor({
  notice,
  sent,
}: {
  notice: HazardNotice
  sent: (notice: HazardNotice) => void
}) {
  const { client } = useApplication()
  const [instruction, setInstruction] = useState(
    notice.suggested_instruction ?? '',
  )
  return (
    <div className="space-y-3 rounded-xl border border-line bg-surface-2 p-3">
      <p className="text-sm font-semibold">
        {notice.suggested_instruction
          ? 'Suggested instruction · not yet approved'
          : 'Write an instruction for the crew.'}
      </p>
      {notice.suggested_instruction && (
        <blockquote className="border-l-2 border-sim pl-3 text-sm italic text-ink-2">
          {notice.suggested_instruction}
        </blockquote>
      )}
      <label className={labelText}>
        Supervisor instruction
        <textarea
          aria-label="Supervisor instruction"
          maxLength={500}
          rows={3}
          className={field}
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
        />
      </label>
      <p className="text-sm text-muted">
        Review before sending. Your action approves this instruction. Maximum
        500 characters.
      </p>
      <Action
        capability="hazards"
        tone="primary"
        disabled={!instruction.trim() || instruction.trim().length > 500}
        run={async () => sent(await client.instruct(notice.id, instruction))}
      >
        Send to your organization's teams
      </Action>
    </div>
  )
}
