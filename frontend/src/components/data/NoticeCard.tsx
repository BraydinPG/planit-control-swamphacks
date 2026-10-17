import { useState } from 'react'
import type { HazardNotice } from '../../types/api'
import { useApplication } from '../../application/context'
import { Action, field, labelText } from './Interaction'
import { Timestamp } from './Status'
import { RiskShape } from './Risk'
export function NoticeCard({ notice }: { notice: HazardNotice }) {
  const { client, persona, principalId } = useApplication()
  const [instruction, setInstruction] = useState(
    notice.suggested_instruction ?? '',
  )
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
        <div className="rounded-xl border-l-4 border-ink bg-surface-2 p-3">
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
      {persona === 'supervisor' && potential && (
        <Action
          capability="hazards"
          tone="primary"
          run={() => client.confirm(notice.id)}
        >
          Confirm potential hazard
        </Action>
      )}
      {persona === 'supervisor' &&
        notice.status === 'confirmed' &&
        notice.confirmed_by === principalId &&
        !notice.instruction_sent_at && (
          <div className="space-y-3 rounded-xl border border-line bg-surface-2 p-3">
            <p className="text-sm font-semibold">
              {notice.suggested_instruction
                ? 'Gemini suggestion — review before sending:'
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
                maxLength={1000}
                rows={3}
                className={field}
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
              />
            </label>
            <Action
              capability="hazards"
              tone="primary"
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
