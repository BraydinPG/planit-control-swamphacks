import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { ApplicationContext } from './context'
import type { Client, Persona } from '../api/contracts'

/** How often a live page reloads its data while the tab is visible. */
export const POLL_MS = 30_000

export function ApplicationProvider({
  client,
  persona,
  children,
  principalId = null,
}: {
  client: Client
  persona: Persona
  children: ReactNode
  principalId?: string | null
}) {
  const [revision, setRevision] = useState(0)
  const refresh = useCallback(() => setRevision((n) => n + 1), [])
  // Live data reloads by itself: every POLL_MS while the tab is visible, and as soon as
  // the reader comes back to it. A poll keeps what is on screen if it fails (useResource).
  const [poll, setPoll] = useState(0)
  useEffect(() => {
    if (client.mode !== 'live') return
    const visible = () => document.visibilityState === 'visible'
    const tick = () => {
      if (visible()) setPoll((n) => n + 1)
    }
    const timer = setInterval(tick, POLL_MS)
    const back = () => {
      if (visible()) tick()
    }
    document.addEventListener('visibilitychange', back)
    window.addEventListener('focus', back)
    return () => {
      clearInterval(timer)
      document.removeEventListener('visibilitychange', back)
      window.removeEventListener('focus', back)
    }
  }, [client])
  return (
    <ApplicationContext.Provider
      value={{
        client,
        persona,
        principalId: client.mode === 'demo' ? `demo-${persona}` : principalId,
        revision,
        poll,
        refresh,
      }}
    >
      {children}
    </ApplicationContext.Provider>
  )
}
