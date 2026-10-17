/**
 * Auth0 module for PlanIT Control (Braydin). Import from here, not from inner files:
 *
 *   import { AuthProvider, RequireRole, useAuth } from './auth'
 *
 * Setup: auth/SETUP.md.
 */
export { AuthProvider } from './AuthProvider'
export { RequireRole } from './RequireRole'
export { useAuth } from './context'
export type { AuthContextValue, AuthMode, AuthUser } from './context'
export { ROLES, ROLE_LABELS, ROLES_CLAIM, isRole } from './roles'
export type { Role } from './roles'
