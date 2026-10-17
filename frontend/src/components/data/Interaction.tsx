import { useState, type ReactNode } from 'react'
import { useApplication } from '../../application/context'
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
}: {
  run: () => Promise<unknown>
  children: ReactNode
  disabled?: boolean
}) {
  const { refresh, client } = useApplication()
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  return (
    <div>
      <button
        type="button"
        className={control}
        disabled={busy || disabled || !client.writesAvailable}
        onClick={async () => {
          setBusy(true)
          setMessage('')
          try {
            await run()
            refresh()
            setMessage('Action recorded.')
          } catch (e) {
            setMessage(e instanceof Error ? e.message : 'Action unavailable')
          } finally {
            setBusy(false)
          }
        }}
      >
        {busy ? 'Working…' : children}
      </button>
      {!client.writesAvailable && (
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
