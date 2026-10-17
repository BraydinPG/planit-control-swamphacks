import { useState } from 'react'
import type { HazardNotice } from '../../types/api'
import { useApplication } from '../../application/context'
import { Action, control } from './Interaction'
import { Timestamp } from './Status'
export function NoticeCard({ notice }: { notice: HazardNotice }) {
  const { client, persona, principalId } = useApplication()
  const [instruction, setInstruction] = useState(
    notice.suggested_instruction ?? '',
  )
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
        <Action capability="hazards" run={() => client.confirm(notice.id)}>
          Confirm potential hazard
        </Action>
      )}
      {persona === 'supervisor' &&
        notice.status === 'confirmed' &&
        notice.confirmed_by === principalId &&
        !notice.instruction_sent_at && (
          <div className="space-y-2">
            <p>
              {notice.suggested_instruction
                ? 'Gemini suggestion — review before sending:'
                : 'No suggestion available; the confirming supervisor writes the instruction.'}
            </p>
            {notice.suggested_instruction && (
              <blockquote>{notice.suggested_instruction}</blockquote>
            )}
            <label className="block">
              Supervisor instruction
              <textarea
                aria-label="Supervisor instruction"
                maxLength={1000}
                className={control + ' block w-full'}
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
              />
            </label>
            <Action
              capability="hazards"
              disabled={!instruction.trim()}
              run={() => client.instruct(notice.id, instruction)}
            >
              Send approved instruction
            </Action>
          </div>
        )}
    </article>
  )
}
