/** PlanIT Control roles. They match backend/app/security/roles.py and auth/SETUP.md. */
export type Role = 'crew' | 'supervisor'

export const ROLES: readonly Role[] = ['crew', 'supervisor']

/** Custom claim the Auth0 post-login Action adds to ID and access tokens. */
export const ROLES_CLAIM = 'https://planit-control/roles'

export const ROLE_LABELS: Record<Role, string> = {
  crew: 'Crew',
  supervisor: 'Supervisor',
}

export function isRole(value: unknown): value is Role {
  return value === 'crew' || value === 'supervisor'
}

/** Supervisor wins when both are assigned, matching the backend. */
export function roleFromClaim(value: unknown): Role | null {
  const names = Array.isArray(value) ? value : []
  if (names.includes('supervisor')) return 'supervisor'
  if (names.includes('crew')) return 'crew'
  return null
}
