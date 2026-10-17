import { useState, type ReactNode } from 'react'
import { ApplicationContext } from './context'
import type { Client, Persona } from '../api/contracts'
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
  return (
    <ApplicationContext.Provider
      value={{
        client,
        persona,
        principalId: client.mode === 'demo' ? `demo-${persona}` : principalId,
        revision,
        refresh: () => setRevision((n) => n + 1),
      }}
    >
      {children}
    </ApplicationContext.Provider>
  )
}
