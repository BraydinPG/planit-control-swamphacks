import { useState } from 'react'
import type { HazardNotice } from '../../types/api'
import { useApplication } from '../../application/context'
import { Action, control } from './Interaction'
import { Timestamp } from './Status'
export function NoticeCard({ notice }: { notice: HazardNotice }) {
  return <NoticeWorkflow key={notice.id} initial={notice} />
}
function NoticeWorkflow({ initial }: { initial: HazardNotice }) {
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
  return (
    <article
      data-notice-id={notice.id}
      className="space-y-3 rounded-xl border border-slate-300 bg-white p-4"
    >
      <h3 className="text-lg font-semibold">
        {notice.status === 'potential' ? 'potential ' : ''}
        {notice.hazard_label}
      </h3>
      <p>
        Status: {notice.status} · Radius: {notice.radius_miles} mi (
        {notice.radius_source}
        {notice.radius_source === 'default' ? ' prototype default' : ''})
      </p>
      <p className="text-xs">
        {notice.source} · {notice.source_ref} · Created{' '}
        <Timestamp value={notice.created_at} />
      </p>
      {notice.status === 'potential' ? (
        <p>No instruction: supervisor confirmation is pending.</p>
      ) : notice.instruction_sent_at && notice.instruction ? (
        <div className="rounded bg-teal-50 p-3">
          <strong>Supervisor-approved instruction</strong>
          <p>{notice.instruction}</p>
          <p className="text-xs">
            Sent <Timestamp value={notice.instruction_sent_at} />
          </p>
        </div>
      ) : (
        <p>Confirmed; no approved instruction has been sent.</p>
      )}
      {persona === 'supervisor' && notice.status === 'potential' && (
        <Action
          capability="hazards"
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
          <p>
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
    <div className="space-y-2">
      <p>
        {notice.suggested_instruction
          ? 'Suggested instruction — review before sending (server draft):'
          : 'No suggestion available; the confirming supervisor writes the instruction.'}
      </p>
      {notice.suggested_instruction && (
        <blockquote>{notice.suggested_instruction}</blockquote>
      )}
      <label className="block">
        Supervisor instruction
        <textarea
          aria-label="Supervisor instruction"
          maxLength={500}
          className={control + ' block w-full'}
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
        />
      </label>
      <p className="text-xs">
        1–500 characters. Sending explicitly approves this text for backend
        delivery. No suggestion is sent automatically.
      </p>
      <Action
        capability="hazards"
        disabled={!instruction.trim() || instruction.trim().length > 500}
        run={async () => sent(await client.instruct(notice.id, instruction))}
      >
        Send approved instruction
      </Action>
    </div>
  )
}
