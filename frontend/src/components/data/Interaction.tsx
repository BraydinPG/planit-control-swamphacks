import { useRef, useState, type ReactNode } from 'react'
import { useApplication } from '../../application/context'
import { ApiError, type Client } from '../../api/contracts'
export const control =
  'min-h-11 min-w-11 rounded-lg border border-slate-400 bg-white px-3 py-2 text-sm text-slate-950 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700 disabled:cursor-not-allowed disabled:opacity-60'
export const primary = control + ' bg-teal-800! text-white! border-teal-800!'
export function LoadState({ error }: { error: string | null }) {
  const { refresh } = useApplication()
  return error ? (
    <div role="alert" className="rounded border border-red-400 bg-red-50 p-4">
      <p>{error}</p>
      <button type="button" className={control} onClick={refresh}>
        Retry loading
      </button>
    </div>
  ) : (
    <p role="status" aria-live="polite">
      Loading workspace data…
    </p>
  )
}
export function Action({
  run,
  children,
  disabled = false,
  capability = 'reviewReports',
}: {
  run: () => Promise<unknown>
  children: ReactNode
  disabled?: boolean
  capability?: keyof Client['capabilities']
}) {
  const { refresh, client } = useApplication()
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const inFlight = useRef(false)
  return (
    <div>
      <button
        type="button"
        className={control}
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
        <p className="text-sm">
          This action is unavailable on the current live backend.
        </p>
      )}
      {message && (
        <p role="status" className="mt-2 text-sm">
          {message}
        </p>
      )}
    </div>
  )
}
