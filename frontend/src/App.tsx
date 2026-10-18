import { useEffect, useState } from 'react'
import { AuthProvider } from './auth'
import { AppShell } from './components/shell/AppShell'
import { shellMode } from './api/shell-fixtures'
import { DemoClient } from './demo/client'
import { useRoute } from './application/context'
import { ConnectedPages, DemoClock } from './pages/ConnectedPages'
import { control } from './components/data/Interaction'
import { Details } from './components/data/Details'
import { LiveApplication } from './application/LiveApplication'
import { ApplicationProvider } from './application/Provider'
import type { Persona } from './api/contracts'
import { cameFromLanding, clearSignInParam, isBareEntry, showLanding } from './application/landing'
import './styles/map.css'

function DemoApplication() {
  const route = useRoute(),
    persona: Persona = route[0] === 'supervisor' ? 'supervisor' : 'crew'
  const [client] = useState(
    () =>
      new DemoClient(() =>
        window.location.hash.startsWith('#/supervisor/')
          ? 'supervisor'
          : 'crew',
      ),
  )
  const [reset, setReset] = useState(0)
  const [resetError, setResetError] = useState('')
  return (
    <ApplicationProvider
      client={client}
      persona={persona}
      key={`${persona}:${reset}`}
    >
      <AppShell
        workspaceOverride={persona}
        badge="Simulated demo"
        message="Practice only. Changes stay in this browser; no live sign-in or backend writes."
        controls={
          <div
            className="flex flex-wrap gap-2"
            role="group"
            aria-label="Demo workspace"
          >
            <button
              className={control}
              aria-pressed={persona === 'crew'}
              onClick={() => {
                location.hash = '/crew/overview'
              }}
            >
              Crew
            </button>
            <button
              className={control}
              aria-pressed={persona === 'supervisor'}
              onClick={() => {
                location.hash = '/supervisor/overview'
              }}
            >
              Supervisor
            </button>
            <button
              className={control}
              onClick={() => {
                setResetError('')
                try {
                  client.reset()
                } catch (error) {
                  setResetError(
                    error instanceof Error
                      ? error.message
                      : 'Demo reset is memory-only.',
                  )
                }
                setReset((n) => n + 1)
              }}
            >
              Reset demo
            </button>
          </div>
        }
      >
        {resetError && <p role="alert">{resetError}</p>}
        <div className="mb-3">
          <Details title="Demo time and details">
            <DemoClock />
            <p>
              All events and changes are simulated. Reset demo restores the
              saved examples and preserves sign-in sessions.
            </p>
          </Details>
        </div>
        <ConnectedPages />
      </AppShell>
    </ApplicationProvider>
  )
}
/** The bare address opens the landing page; its Sign in button opens the crew demo. */
function DemoEntry() {
  const [leaving] = useState(() => {
    if (cameFromLanding()) {
      clearSignInParam('#/crew/overview')
      return false
    }
    return isBareEntry()
  })
  useEffect(() => {
    if (leaving) showLanding()
  }, [leaving])
  return leaving ? null : <DemoApplication />
}
export default function App() {
  if (shellMode === 'invalid')
    return (
      <main className="p-6">
        <h1 className="text-2xl font-bold">The app could not start</h1>
        <p>
          Demo mode is not configured correctly. No worksite data has loaded.
        </p>
        <Details title="Configuration details">
          Set VITE_USE_FIXTURES to true or false, then restart the frontend.
        </Details>
      </main>
    )
  return shellMode === 'fixture' ? (
    <DemoEntry />
  ) : (
    <AuthProvider>
      <LiveApplication />
    </AuthProvider>
  )
}
