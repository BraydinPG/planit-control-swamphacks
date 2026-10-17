import { isRole, type Role } from './roles'

/** Public Auth0 SPA settings from frontend/.env.local. None of these are secrets. */
export interface AuthConfig {
  domain: string
  clientId: string
  audience: string
}

function read(name: string): string {
  const value: unknown = import.meta.env[name]
  return typeof value === 'string' ? value.trim() : ''
}

/** Auth0 settings, or null when any of the three values is missing. */
export function auth0Config(): AuthConfig | null {
  const domain = read('VITE_AUTH0_DOMAIN').replace(/^https?:\/\//, '').replace(/\/$/, '')
  const clientId = read('VITE_AUTH0_CLIENT_ID')
  const audience = read('VITE_AUTH0_AUDIENCE')
  return domain && clientId && audience ? { domain, clientId, audience } : null
}

/**
 * Local development role (VITE_DEV_AUTH_ROLE). Only honored by the Vite dev server,
 * never in a production build. Pairs with DEV_AUTH_BYPASS on the backend.
 */
export function devRole(): Role | null {
  if (!import.meta.env.DEV) return null
  const role = read('VITE_DEV_AUTH_ROLE').toLowerCase()
  return isRole(role) ? role : null
}
