import type { ReactNode } from 'react'
import { useAuth } from './context'
import { ROLE_LABELS, type Role } from './roles'
import { Brand } from '../components/shell/Brand'

interface RequireRoleProps {
  /** Role or roles allowed to see `children`. */
  role: Role | readonly Role[]
  children: ReactNode
  /** Replaces the default access state for a signed-in user with the wrong role. */
  fallback?: ReactNode
  /** A standalone screen shows its brand once; embedded guard examples may omit it. */
  showBrand?: boolean
}

/**
 * Shows `children` only to signed-in users with an allowed role. This guard is for the
 * interface only: the backend checks every request on its own.
 */
export function RequireRole({ role, children, fallback, showBrand = true }: RequireRoleProps) {
  const auth = useAuth()
  const allowed: readonly Role[] = typeof role === 'string' ? [role] : role

  if (auth.isLoading) {
    return (
      <AccessPanel title="Checking sign-in" showBrand={showBrand}>
        <p role="status" aria-live="polite">
          Checking your sign-in…
        </p>
      </AccessPanel>
    )
  }

  if (!auth.isAuthenticated) {
    return (
      <AccessPanel title="Sign in required" showBrand={showBrand}>
        <p>Sign in to see this screen.</p>
        {auth.error && <ErrorText message={auth.error} />}
        {auth.mode !== 'unconfigured' && (
          <ActionButton onClick={() => void auth.login()}>Sign in</ActionButton>
        )}
      </AccessPanel>
    )
  }

  if (auth.role === null) {
    return (
      <AccessPanel title="No role assigned" showBrand={showBrand}>
        <p>
          You are signed in, but your account has no FORESITE role. Ask the project admin
          to assign Crew or Supervisor, then sign in again.
        </p>
        <ActionButton onClick={() => void auth.logout()}>Sign out</ActionButton>
      </AccessPanel>
    )
  }

  if (!allowed.includes(auth.role)) {
    if (fallback !== undefined) return <>{fallback}</>
    const needed = allowed.map((name) => ROLE_LABELS[name]).join(' or ')
    return (
      <AccessPanel title="Not available for your role" showBrand={showBrand}>
        <p>
          This screen is for {needed}. You are signed in as{' '}
          <strong>{ROLE_LABELS[auth.role]}</strong>.
        </p>
        <ActionButton onClick={() => void auth.logout()}>Sign out</ActionButton>
      </AccessPanel>
    )
  }

  return <>{children}</>
}

function AccessPanel({ title, children, showBrand }: { title: string; children: ReactNode; showBrand: boolean }) {
  return (
    <section
      aria-labelledby="access-panel-title"
      className="mx-auto my-8 flex max-w-md flex-col gap-4 rounded-lg bg-white p-6 text-lg text-neutral-950 shadow-[0_8px_32px_rgba(0,0,0,0.12)]"
    >
      {showBrand && <Brand variant="full" />}
      <h2 id="access-panel-title" className="text-2xl font-semibold">
        {title}
      </h2>
      {children}
    </section>
  )
}

function ActionButton({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="min-h-11 min-w-11 self-start rounded-md bg-neutral-900 px-5 py-2 text-lg font-semibold text-white hover:bg-neutral-700 focus-visible:outline-4 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
    >
      {children}
    </button>
  )
}

function ErrorText({ message }: { message: string }) {
  return (
    <p role="alert" className="font-medium text-red-800">
      <span aria-hidden="true">⚠ </span>
      {message}
    </p>
  )
}
