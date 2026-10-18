import { useEffect, useMemo, useState } from 'react'
import { RequireRole, useAuth } from '../auth'
import { HttpClient } from '../api/http-client'
import { ApplicationProvider } from './Provider'
import { AppShell } from '../components/shell/AppShell'
import { ConnectedPages } from '../pages/ConnectedPages'
import { control } from '../components/data/Interaction'
import {
  cameFromLanding,
  installBackToLanding,
  isBareEntry,
  resetBackToLanding,
  showLanding,
} from './landing'

export function LiveApplication() {
  const auth = useAuth()
  const { mode, isAuthenticated, isLoading, error, login, getAccessToken } = auth
  // Read once: Sign in on the landing page starts Auth0 straight away instead of
  // showing the old sign-in card. If that fails, the card stays as the fallback.
  const [fromLanding] = useState(cameFromLanding)
  const [loginFailed, setLoginFailed] = useState(false)
  const startSignIn = fromLanding && mode === 'auth0' && !loginFailed
  // An Auth0 sign-in error (for example a failed callback) stays on the sign-in card.
  const toLanding = !fromLanding && !(mode === 'auth0' && error) && isBareEntry()
  const leaving = !isLoading && !isAuthenticated && (startSignIn || toLanding)
  useEffect(() => {
    if (!leaving) return
    if (startSignIn) login({ returnTo: '/' }).catch(() => setLoginFailed(true))
    else showLanding()
  }, [leaving, startSignIn, login])
  // Once fully signed in, Back from the app returns to the landing page.
  const signedIn = !isLoading && isAuthenticated
  useEffect(() => {
    if (signedIn) return installBackToLanding()
    if (!isLoading) resetBackToLanding()
  }, [signedIn, isLoading])
  const client = useMemo(
    () =>
      new HttpClient(
        new URL(
          import.meta.env.VITE_API_BASE_URL || '/',
          window.location.origin,
        ).href,
        async (): Promise<Record<string, string>> => {
          if (mode !== 'auth0' || !isAuthenticated) return {}
          const token = await getAccessToken()
          return token ? { Authorization: `Bearer ${token}` } : {}
        },
      ),
    [mode, isAuthenticated, getAccessToken],
  )
  if (leaving) return null
  return (
    <RequireRole role={['crew', 'supervisor']}>
      <LiveSession client={client} />
    </RequireRole>
  )
}
function LiveSession({ client }: { client: HttpClient }) {
  const auth = useAuth()
  if (auth.mode !== 'auth0' || !auth.role)
    return (
      <main className="p-6">
        <h1>Real Auth0 session required</h1>
        <p>
          Development bypass roles are not accepted by this application. No live
          requests were sent.
        </p>
      </main>
    )
  return (
    <ApplicationProvider
      key={`${auth.user?.sub}:${auth.role}`}
      client={client}
      persona={auth.role}
      principalId={auth.user?.sub ?? null}
    >
      <AppShell
        workspaceOverride={auth.role}
        badge="Authenticated API"
        hideConnectionInfo
        headerControls={
          <button type="button" className={control} onClick={() => void auth.logout()}>
            Sign out
          </button>
        }
      >
        <ConnectedPages />
      </AppShell>
    </ApplicationProvider>
  )
}
