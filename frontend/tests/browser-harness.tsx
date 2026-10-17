/** Test-only entry, not a production build input or authentication mechanism. */
import { createRoot } from 'react-dom/client'
import { AuthContext, type AuthContextValue } from '../src/auth/context'
import { LiveApplication } from '../src/application/LiveApplication'
import sitesJSON from '../src/fixtures/sites.json'
import detailJSON from '../src/fixtures/site-detail.json'
import alertsJSON from '../src/fixtures/alerts.json'
import '../src/index.css'
const root = createRoot(document.getElementById('auth-test')!)
let role: 'crew' | 'supervisor' | null = 'crew',
  status = 200
const requests: string[] = []
const alerts = structuredClone(alertsJSON)
window.fetch = async (input, options) => {
  const url = new URL(String(input), location.origin)
  requests.push(`${options?.method ?? 'GET'} ${url.pathname}`)
  if (!url.pathname.startsWith('/api/'))
    throw new Error('Unexpected test request')
  if (status !== 200) return new Response('', { status })
  if (
    !new Headers(options?.headers)
      .get('Authorization')
      ?.startsWith('Bearer mock-')
  )
    return new Response('', { status: 401 })
  if (url.pathname === '/api/sites')
    return Response.json(role === 'crew' ? [sitesJSON[0]] : sitesJSON)
  if (url.pathname === '/api/alerts')
    return Response.json(
      alerts.filter(
        (a) => role === 'supervisor' || a.site_id === sitesJSON[0].id,
      ),
    )
  if (url.pathname.endsWith('/acknowledge')) {
    const alert = alerts.find(
      (a) => a.id === decodeURIComponent(url.pathname.split('/')[3]),
    )
    if (!alert) return new Response('', { status: 404 })
    if (alert.state !== 'active') return new Response('', { status: 409 })
    if (!alert.acknowledgements.some((a) => a.user_id === `mock-${role}`))
      alert.acknowledgements.push({
        id: 'mock-ack',
        alert_id: alert.id,
        user_id: `mock-${role}`,
        acknowledged_at: new Date().toISOString(),
      })
    return Response.json(alert)
  }
  const id = decodeURIComponent(url.pathname.split('/')[3] ?? '')
  if (role === 'crew' && id !== sitesJSON[0].id)
    return new Response('', { status: 403 })
  if (id === detailJSON.id)
    return Response.json({
      ...detailJSON,
      alerts: alerts.filter((a) => a.site_id === id),
    })
  const summary = sitesJSON.find((s) => s.id === id)
  return summary
    ? Response.json({
        ...summary,
        location_type: 'power_plant',
        source: 'Mocked HTTP fixture',
        region: null,
        observations: [],
        score: null,
        alerts: [],
        reports: [],
        notices: [],
        event_outlook: null,
      })
    : new Response('', { status: 404 })
}
const controls = {
  requests,
  mount(
    kind: 'crew' | 'supervisor' | 'logged-out' | 'loading' | 'no-role' | 'dev',
    httpStatus = 200,
  ) {
    role =
      kind === 'supervisor'
        ? 'supervisor'
        : kind === 'crew' || kind === 'dev'
          ? 'crew'
          : null
    status = httpStatus
    const value: AuthContextValue = {
      user: role ? { sub: `mock-${role}` } : { sub: 'mock-user' },
      role,
      isAuthenticated: !['logged-out', 'loading'].includes(kind),
      isLoading: kind === 'loading',
      error: null,
      mode: kind === 'dev' ? 'dev' : 'auth0',
      login: async () => {},
      logout: async () => controls.mount('logged-out'),
      getAccessToken: async () => `mock-${role}`,
      getAuthHeaders: async () => ({ Authorization: `Bearer mock-${role}` }),
    }
    root.render(
      <AuthContext.Provider value={value}>
        <p>MOCKED AUTH/API TEST ONLY — not a real login</p>
        <LiveApplication />
      </AuthContext.Provider>,
    )
  },
}
Object.assign(window, { harness: controls })
controls.mount('logged-out')
