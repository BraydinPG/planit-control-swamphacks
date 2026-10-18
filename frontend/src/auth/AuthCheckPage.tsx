import { useState } from 'react'
import { useAuth } from './context'
import { RequireRole } from './RequireRole'
import { ROLE_LABELS, ROLES_CLAIM } from './roles'

/**
 * Isolated sign-in check for T025/T026 and the demo-account setup in auth/SETUP.md.
 * Open http://localhost:5173/auth-check.html while `npm run dev` is running.
 */
export function AuthCheckPage() {
  const auth = useAuth()
  const [tokenStatus, setTokenStatus] = useState<string | null>(null)

  async function checkToken() {
    try {
      const token = await auth.getAccessToken()
      setTokenStatus(token ? describeToken(token) : 'No access token (dev mode or signed out).')
    } catch (error) {
      setTokenStatus(`Token request failed: ${error instanceof Error ? error.message : error}`)
    }
  }

  const rows: [string, string][] = [
    ['Mode', auth.mode],
    ['Loading', auth.isLoading ? 'yes' : 'no'],
    ['Signed in', auth.isAuthenticated ? 'yes' : 'no'],
    ['User', auth.user ? `${auth.user.name ?? ''} (${auth.user.sub})` : '—'],
    ['Role', auth.role ? ROLE_LABELS[auth.role] : 'none'],
  ]

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-6 p-4 text-lg text-neutral-950 dark:text-neutral-50">
      <h1 className="text-3xl font-bold">FORESITE sign-in check</h1>
      {auth.mode === 'dev' && (
        <p className="rounded-md border-2 border-amber-700 p-3 font-medium">
          <span aria-hidden="true">⚠ </span>Dev mode: this is not a real sign-in.
        </p>
      )}
      {auth.error && (
        <p role="alert" className="font-medium text-red-800 dark:text-red-300">
          {auth.error}
        </p>
      )}
      <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="font-semibold">{label}</dt>
            <dd className="break-all">{value}</dd>
          </div>
        ))}
      </dl>
      <div className="flex flex-wrap gap-3">
        <CheckButton onClick={() => void auth.login({ returnTo: '/auth-check.html' })}>
          Sign in
        </CheckButton>
        <CheckButton onClick={() => void auth.logout()}>Sign out</CheckButton>
        <CheckButton onClick={() => void checkToken()}>Get access token</CheckButton>
      </div>
      {tokenStatus && <p role="status">{tokenStatus}</p>}
      <h2 className="text-2xl font-semibold">Role guard</h2>
      <RequireRole role="crew">
        <p>Crew-only content is visible.</p>
      </RequireRole>
      <RequireRole role="supervisor">
        <p>Supervisor-only content is visible.</p>
      </RequireRole>
    </main>
  )
}

/**
 * Shows expiry, the roles claim, and permission names from the token payload, for setup
 * checks. Never displays the token itself.
 */
function describeToken(token: string): string {
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
    const expires = new Date(payload.exp * 1000).toLocaleTimeString()
    const permissions: string[] = Array.isArray(payload.permissions) ? payload.permissions : []
    const roles = payload[ROLES_CLAIM]
    const roleText = Array.isArray(roles)
      ? `roles claim: [${roles.join(', ')}]`
      : 'roles claim: missing (the post-login Action did not run)'
    return `Access token received. Expires ${expires}. ${roleText}. ${permissions.length} permissions: ${permissions.sort().join(', ')}.`
  } catch {
    return 'Access token received.'
  }
}

function CheckButton({ onClick, children }: { onClick: () => void; children: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="min-h-11 min-w-11 rounded-md border-2 border-neutral-900 px-4 py-2 font-semibold hover:bg-neutral-100 focus-visible:outline-4 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:border-neutral-100 dark:hover:bg-neutral-800"
    >
      {children}
    </button>
  )
}
