import { useState } from 'react'
import { AuthProvider } from './auth'
import { AppShell } from './components/shell/AppShell'
import { shellMode } from './api/shell-fixtures'
import { DemoClient } from './demo/client'
import { useRoute } from './application/context'
import { ConnectedPages, DemoClock } from './pages/ConnectedPages'
import { control } from './components/data/Interaction'
import { LiveApplication } from './application/LiveApplication'
import { ApplicationProvider } from './application/Provider'
import type { Persona } from './api/contracts'
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
        message="Local demo changes only; no sign-in or backend writes. Workspaces are previews, never authorization."
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
        <p className="mb-3 text-xs text-slate-600">
          <DemoClock /> | All activations and mutations simulated.
        </p>
        <ConnectedPages />
      </AppShell>
    </ApplicationProvider>
  )
}
export default function App() {
  if (shellMode === 'invalid')
    return (
      <main className="p-6">
        <h1>Fixture configuration is invalid.</h1>
        <p>
          No site data loaded. Use VITE_USE_FIXTURES=true or false; no data is
          substituted.
        </p>
      </main>
    )
  return shellMode === 'fixture' ? (
    <DemoApplication />
  ) : (
    <AuthProvider>
      <LiveApplication />
    </AuthProvider>
  )
}
