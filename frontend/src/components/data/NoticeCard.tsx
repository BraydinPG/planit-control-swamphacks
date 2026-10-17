import { useState } from 'react'
import type { EventOutlook, HazardNotice } from '../../types/api'
import { useApplication } from '../../application/context'
import { Action, field, labelText } from './Interaction'
import { Timestamp } from './Status'
import { RiskShape } from './Risk'
import { ExpectedDuration } from './Duration'
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
      className={`space-y-3 rounded-2xl border-2 bg-surface p-4 ${potential ? 'border-dashed border-caution' : 'border-line-strong'}`}
    >
      <div className="flex items-start gap-3">
        <RiskShape
          kind={potential ? 'caution' : 'warn'}
          className="mt-0.5 size-6"
        />
        <div className="min-w-0 flex-1">
          <p className="kicker">
            {potential ? 'Potential notice' : 'Confirmed notice'}
          </p>
          <h3 className="text-xl font-bold">
            {potential ? 'potential ' : ''}
            {notice.hazard_label}
          </h3>
        </div>
      </div>
      <p className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-2">
        <span>
          Status: <strong className="text-ink">{notice.status}</strong>
        </span>
        <span>
          Radius: {notice.radius_miles} mi ({notice.radius_source}
          {notice.radius_source === 'default' ? ' prototype default' : ''})
        </span>
      </p>
      <p className="break-words text-xs text-muted">
        {notice.source} · {notice.source_ref} · Created{' '}
        <Timestamp value={notice.created_at} />
      </p>
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
          <p className="mt-1 text-xs text-muted">
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
          Confirm potential hazard
        </Action>
      )}
      {persona === 'supervisor' &&
        notice.status === 'confirmed' &&
        notice.confirmed_by !== principalId &&
        !notice.instruction_sent_at && (
          <p className="rounded-xl border border-dashed border-line-strong px-3 py-2.5 text-sm text-ink-2">
            Another supervisor confirmed this hazard. Only that supervisor may
            send the instruction. Refresh for current server state.
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
    </article>
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
          ? 'Suggested instruction — review before sending (server draft):'
          : 'No suggestion available; the confirming supervisor writes the instruction.'}
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
      <p className="text-xs text-muted">
        1–500 characters. Sending explicitly approves this text for backend
        delivery. No suggestion is sent automatically.
      </p>
      <Action
        capability="hazards"
        tone="primary"
        disabled={!instruction.trim() || instruction.trim().length > 500}
        run={async () => sent(await client.instruct(notice.id, instruction))}
      >
        Send approved instruction
      </Action>
    </div>
  )
}
