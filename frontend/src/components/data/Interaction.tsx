import { useRef, useState, type ReactNode } from 'react'
import { useApplication } from '../../application/context'
import { ApiError, type Client } from '../../api/contracts'
import { Details } from './Details'
import { errorSummary } from '../../presentation/display'

const base =
  'pc-press inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50'
/** Secondary button / link. */
export const control = base + ' bg-control text-ink hover:bg-control-hover'
/** Primary action: system blue fill with white text. */
export const primary =
  base + ' bg-accent-fill text-white hover:bg-accent-fill-hover'
/** Large field action for gloved use (acknowledge, report). */
// Important modifiers so these win over the base size when concatenated.
export const big =
  ' min-h-[72px]! w-full rounded-2xl! px-6! text-lg! font-bold!'
/** Text inputs, selects and textareas. */
export const field =
  'mt-1.5 block min-h-11 w-full rounded-xl border border-line bg-surface px-3 py-2 text-base text-ink placeholder:text-faint'
/** Form label text. */
export const labelText = 'block text-sm font-medium text-ink-2'
/** Card surface used across pages. */
export const card = 'rounded-2xl bg-surface'

export function LoadState({ error }: { error: string | null }) {
  const { refresh } = useApplication()
  return error ? (
    <div
      role="alert"
      className="flex flex-col gap-3 rounded-2xl border-2 border-stop bg-surface p-5 @lg:flex-row @lg:items-center @lg:justify-between"
    >
      <div>
        <p className="text-lg font-bold text-stop-text">
          Information unavailable
        </p>
        <p className="mt-1 text-base text-ink">{errorSummary(error)}</p>
        <p className="mt-2 text-sm text-ink-2">
          Try again. If access is denied, ask your supervisor to check your
          account.
        </p>
        <Details title="Error details">
          {errorSummary(error) !== error && <p>{error}</p>}
          <p>
            No demo data replaces a failed live request. Previously shown
            information may be out of date.
          </p>
        </Details>
      </div>
      <button type="button" className={control} onClick={refresh}>
        Retry loading
      </button>
    </div>
  ) : (
    <div className="space-y-3">
      <p role="status" aria-live="polite" className="kicker">
        Loading your workspace…
      </p>
      <div className="pc-skeleton h-24 rounded-2xl" aria-hidden="true" />
      <div className="grid gap-3 @lg:grid-cols-2" aria-hidden="true">
        <div className="pc-skeleton h-20 rounded-2xl" />
        <div className="pc-skeleton h-20 rounded-2xl" />
      </div>
    </div>
  )
}

export function Action({
  run,
  children,
  disabled = false,
  capability = 'reviewReports',
  tone = 'default',
}: {
  run: () => Promise<unknown>
  children: ReactNode
  disabled?: boolean
  capability?: keyof Client['capabilities']
  tone?: 'default' | 'primary' | 'big'
}) {
  const { refresh, client } = useApplication()
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const inFlight = useRef(false)
  const className =
    tone === 'big' ? primary + big : tone === 'primary' ? primary : control
  return (
    <div className={tone === 'big' ? 'w-full' : undefined}>
      <button
        type="button"
        className={className}
        disabled={busy || disabled || !client.capabilities[capability]}
        onClick={async () => {
          if (inFlight.current) return
          inFlight.current = true
          setBusy(true)
          setMessage('')
          try {
            await run()
            refresh()
            setMessage('Action recorded.')
          } catch (e) {
            setMessage(e instanceof Error ? e.message : 'Action unavailable')
            if (e instanceof ApiError && [403, 409, 502].includes(e.status))
              refresh()
          } finally {
            inFlight.current = false
            setBusy(false)
          }
        }}
      >
        {busy ? 'Working…' : children}
      </button>
      {!client.capabilities[capability] && (
        <p className="mt-2 text-sm text-muted">
          {client.readOnlyMessage ??
            'This action is not available yet. No change has been made.'}
        </p>
      )}
      {message && (
        <p
          role="status"
          className="mt-2 inline-flex items-center gap-1.5 text-sm font-semibold text-ink-2"
        >
          {message}
        </p>
      )}
    </div>
  )
}
