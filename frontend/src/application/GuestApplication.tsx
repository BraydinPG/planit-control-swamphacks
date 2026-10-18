import { useMemo } from 'react'
import { HttpClient } from '../api/http-client'
import type { Persona } from '../api/contracts'
import { ApplicationProvider } from './Provider'
import { useRoute } from './context'
import { AppShell } from '../components/shell/AppShell'
import { ConnectedPages } from '../pages/ConnectedPages'
import { control } from '../components/data/Interaction'

/**
 * Try demo (`/?demo`): the server's demo sites, read-only, with no sign-in. The visitor
 * switches between Crew and Supervisor here; the backend scopes each to its guest account
 * and refuses every write.
 */
export function GuestApplication() {
  const route = useRoute(),
    persona: Persona = route[0] === 'supervisor' ? 'supervisor' : 'crew'
  const client = useMemo(
    () =>
      HttpClient.guest(
        new URL(
          import.meta.env.VITE_API_BASE_URL || '/',
          window.location.origin,
        ).href,
        persona,
      ),
    [persona],
  )
  return (
    <ApplicationProvider
      key={persona}
      client={client}
      persona={persona}
      principalId={`demo-guest|${persona}`}
    >
      <AppShell
        workspaceOverride={persona}
        badge="Demo (read-only)"
        message="Live demo worksites. Look around as a crew member or a supervisor; sign in to report hazards, acknowledge alerts or manage a team."
        headerControls={
          <a className={control} href="/?signin">
            Sign in
          </a>
        }
        controls={
          <div
            className="flex flex-wrap gap-2"
            role="group"
            aria-label="Demo workspace"
          >
            <button
              type="button"
              className={control}
              aria-pressed={persona === 'crew'}
              onClick={() => {
                location.hash = '/crew/overview'
              }}
            >
              Crew
            </button>
            <button
              type="button"
              className={control}
              aria-pressed={persona === 'supervisor'}
              onClick={() => {
                location.hash = '/supervisor/overview'
              }}
            >
              Supervisor
            </button>
          </div>
        }
      >
        <ConnectedPages />
      </AppShell>
    </ApplicationProvider>
  )
}
