/** Test-only entry, not a production build input or authentication mechanism. */
import { createRoot } from 'react-dom/client'
import { AuthContext, type AuthContextValue } from '../src/auth/context'
import { LiveApplication } from '../src/application/LiveApplication'
import { createMockService } from './mock-service'
import briefingsJSON from '../src/fixtures/briefings.json'
import '../src/index.css'
const root = createRoot(document.getElementById('auth-test')!)
let role: 'crew' | 'supervisor' | null = 'crew',
  status = 200
const requests: string[] = []
let service = createMockService()
const testKey = 'planit:mock-http-browser-test'
try {
  const stored = JSON.parse(sessionStorage.getItem(testKey) ?? 'null')
  if (stored) Object.assign(service, stored)
} catch {
  /* Isolated public test fixtures only. */
}
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
  if (url.pathname === '/api/briefings') return Response.json(briefingsJSON)
  if (url.pathname.endsWith('/briefing')) {
    if (controls.briefingStatus !== 200)
      return new Response('', { status: controls.briefingStatus })
    return Response.json(controls.invalidBriefing ? {} : briefingsJSON[0])
  }
  const response = await service.request(url, options, role ?? '')
  sessionStorage.setItem(
    testKey,
    JSON.stringify({
      reports: service.reports,
      notices: service.notices,
      alerts: service.alerts,
      confirmed: service.confirmed,
    }),
  )
  return response
}
const controls = {
  requests,
  snapshot: () => ({ reports: service.reports, notices: service.notices }),
  reset() {
    service = createMockService()
    sessionStorage.removeItem(testKey)
  },
  settings(input: {
    mutationStatus?: number
    manual?: boolean
    denyMutation?: boolean
    conflict?: boolean
    foreignOwner?: string
  }) {
    if (input.mutationStatus !== undefined)
      service.mutationStatus = input.mutationStatus
    if (input.manual !== undefined)
      service.draft = input.manual
        ? null
        : 'Mocked Gemini draft: request qualified inspection before proceeding.'
    if (input.denyMutation !== undefined)
      service.denyMutation = input.denyMutation
    if (input.conflict !== undefined) service.conflict = input.conflict
    if (input.foreignOwner) {
      const notice = service.notices.find((n) => n.id === input.foreignOwner)
      if (notice) {
        notice.status = 'confirmed'
        notice.confirmed_by = 'other-supervisor'
        notice.confirmed_at = '2026-10-17T20:00:00Z'
      }
    }
  },
  briefingStatus: 200,
  invalidBriefing: false,
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
