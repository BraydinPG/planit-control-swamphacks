import { Auth0Provider, useAuth0, type AppState } from '@auth0/auth0-react'
import { useCallback, useMemo, useState, type ReactNode } from 'react'
import { auth0Config, devRole, type AuthConfig } from './config'
import { AuthContext, type AuthContextValue } from './context'
import { ROLES_CLAIM, roleFromClaim, type Role } from './roles'

interface AuthProviderProps {
  children: ReactNode
  /** Where Auth0 returns after sign-in. Must be an Allowed Callback URL. Default: site root. */
  redirectUri?: string
}

/**
 * Wrap the app once, near the root. Picks the mode from frontend/.env.local:
 * VITE_DEV_AUTH_ROLE on the dev server, else Auth0 when configured, else unconfigured.
 */
export function AuthProvider({ children, redirectUri }: AuthProviderProps) {
  const role = devRole()
  if (role !== null) return <DevAuthProvider role={role}>{children}</DevAuthProvider>
  const config = auth0Config()
  if (config === null) return <UnconfiguredAuthProvider>{children}</UnconfiguredAuthProvider>
  return (
    <Auth0AuthProvider config={config} redirectUri={redirectUri}>
      {children}
    </Auth0AuthProvider>
  )
}

function Auth0AuthProvider({
  config,
  redirectUri,
  children,
}: {
  config: AuthConfig
  redirectUri?: string
  children: ReactNode
}) {
  const onRedirectCallback = useCallback((appState?: AppState) => {
    // Drop ?code=&state= from the address bar after sign-in.
    const target = appState?.returnTo ?? window.location.pathname
    window.history.replaceState({}, document.title, target)
  }, [])

  return (
    <Auth0Provider
      domain={config.domain}
      clientId={config.clientId}
      authorizationParams={{
        redirect_uri: redirectUri ?? window.location.origin,
        audience: config.audience,
      }}
      // Field crews reload often: keep the session across reloads with refresh-token
      // rotation. Trade-off documented in auth/SETUP.md.
      cacheLocation="localstorage"
      useRefreshTokens
      onRedirectCallback={onRedirectCallback}
    >
      <Auth0Bridge>{children}</Auth0Bridge>
    </Auth0Provider>
  )
}

function Auth0Bridge({ children }: { children: ReactNode }) {
  const auth0 = useAuth0()
  const { user, isAuthenticated, isLoading, error, getAccessTokenSilently } = auth0
  const { loginWithRedirect, logout: auth0Logout } = auth0

  const value = useMemo<AuthContextValue>(() => {
    const getAccessToken = async () =>
      isAuthenticated ? ((await getAccessTokenSilently()) ?? null) : null
    return {
      user:
        isAuthenticated && user?.sub
          ? { sub: user.sub, name: user.name, email: user.email }
          : null,
      role: isAuthenticated ? roleFromClaim(user?.[ROLES_CLAIM]) : null,
      isAuthenticated,
      isLoading,
      error: error ? error.message : null,
      mode: 'auth0',
      login: (options) =>
        loginWithRedirect({
          appState: { returnTo: options?.returnTo ?? window.location.pathname },
        }),
      logout: () => auth0Logout({ logoutParams: { returnTo: window.location.origin } }),
      getAccessToken,
      getAuthHeaders: async (): Promise<Record<string, string>> => {
        const token = await getAccessToken()
        return token ? { Authorization: `Bearer ${token}` } : {}
      },
    }
  }, [user, isAuthenticated, isLoading, error, getAccessTokenSilently, loginWithRedirect, auth0Logout])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

function DevAuthProvider({ role, children }: { role: Role; children: ReactNode }) {
  const [signedIn, setSignedIn] = useState(true)

  const value = useMemo<AuthContextValue>(
    () => ({
      user: signedIn ? { sub: `dev|${role}`, name: `Local ${role} (dev mode)` } : null,
      role: signedIn ? role : null,
      isAuthenticated: signedIn,
      isLoading: false,
      error: null,
      mode: 'dev',
      login: async () => setSignedIn(true),
      logout: async () => setSignedIn(false),
      getAccessToken: async () => null,
      // Accepted only by a local backend with DEV_AUTH_BYPASS=true.
      getAuthHeaders: async (): Promise<Record<string, string>> =>
        signedIn ? { 'X-Dev-Role': role } : {},
    }),
    [role, signedIn],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

function UnconfiguredAuthProvider({ children }: { children: ReactNode }) {
  const value = useMemo<AuthContextValue>(() => {
    const message =
      'Sign-in is not configured. Set VITE_AUTH0_DOMAIN, VITE_AUTH0_CLIENT_ID, and VITE_AUTH0_AUDIENCE (see auth/SETUP.md).'
    return {
      user: null,
      role: null,
      isAuthenticated: false,
      isLoading: false,
      error: message,
      mode: 'unconfigured',
      login: async () => {
        throw new Error(message)
      },
      logout: async () => {},
      getAccessToken: async () => null,
      getAuthHeaders: async () => ({}),
    }
  }, [])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
