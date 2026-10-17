import { createContext, useContext } from 'react'
import type { Role } from './roles'

/** Minimal profile. The app needs no more personal data than this. */
export interface AuthUser {
  sub: string
  name?: string
  email?: string
}

/**
 * `auth0`: real Auth0 sign-in.
 * `dev`: VITE_DEV_AUTH_ROLE on the local dev server. Not a real sign-in.
 * `unconfigured`: Auth0 settings are missing, so nobody can sign in.
 */
export type AuthMode = 'auth0' | 'dev' | 'unconfigured'

export interface AuthContextValue {
  user: AuthUser | null
  /** Null when signed out, or signed in without a FORESITE role. */
  role: Role | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  mode: AuthMode
  login: (options?: { returnTo?: string }) => Promise<void>
  logout: () => Promise<void>
  /** Access token for the FastAPI backend, or null when there is none (dev mode). */
  getAccessToken: () => Promise<string | null>
  /** Headers for API calls: a Bearer token, or the local dev-role header in dev mode. */
  getAuthHeaders: () => Promise<Record<string, string>>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (value === null) {
    throw new Error('useAuth() must be used inside <AuthProvider>')
  }
  return value
}
