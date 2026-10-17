import { after, test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createServer } from 'vite'
import {
  origin,
  routeInventory,
  tokenIdentity,
  runAcceptance,
} from '../scripts/integration/acceptance.mjs'

const server = await createServer({
  cacheDir: '.shell-check/integration-unit-cache',
  logLevel: 'silent',
  configFile: false,
  server: { middlewareMode: true, hmr: false },
  appType: 'custom',
})
after(() => server.close())
const { HttpClient } = await server.ssrLoadModule('/src/api/http-client.ts')
const config = {
  issuer: 'https://tenant.example/',
  audience: 'https://api.example',
  rolesClaim: 'https://planit-control/roles',
}
const secret = 'private-value-must-not-reach-report'
const jwt = (role, extra = {}, header = { alg: 'RS256' }) =>
  [
    header,
    {
      iss: config.issuer,
      aud: config.audience,
      sub: `private-${role}-subject`,
      exp: Math.floor(Date.now() / 1000) + 3600,
      [config.rolesClaim]: [role],
      ...extra,
    },
  ]
    .map((x) => Buffer.from(JSON.stringify(x)).toString('base64url'))
    .join('.') + '.unit-signature'
const readiness = {
  auth: {
    configured: true,
    dev_auth_bypass: false,
    domain_matches_spa: true,
    audience_matches_spa: true,
  },
  database: { status: 'passed' },
}
const fixtures = JSON.parse(
  await readFile(new URL('../src/fixtures/sites.json', import.meta.url)),
)
const detail = JSON.parse(
  await readFile(new URL('../src/fixtures/site-detail.json', import.meta.url)),
)
const initialAlerts = JSON.parse(
  await readFile(new URL('../src/fixtures/alerts.json', import.meta.url)),
)
const reportsFixture = JSON.parse(
  await readFile(new URL('../src/fixtures/reports.json', import.meta.url)),
)
function harness(overrides = {}, sourceAlerts = initialAlerts) {
  const accounts = { crew: jwt('crew'), supervisor: jwt('supervisor') },
    calls = []
  let alerts = structuredClone(sourceAlerts)
  const fetcher = async (url, options = {}) => {
    const { pathname, search } = new URL(url, 'http://localhost:8000')
    const role = Object.entries(accounts).find(
      ([, token]) => options.headers?.Authorization === `Bearer ${token}`,
    )?.[0]
    calls.push({
      path: pathname + search,
      method: options.method ?? 'GET',
      role,
    })
    if (!role) return new Response('', { status: 401 })
    if (pathname === '/api/sites')
      return Response.json(role === 'crew' ? [fixtures[0]] : fixtures)
    if (pathname === '/api/reports')
      return Response.json(
        reportsFixture.filter(
          (r) => role === 'supervisor' || r.site_id === fixtures[0].id,
        ),
      )
    if (pathname === '/api/alerts')
      return Response.json(
        alerts.filter(
          (a) => role === 'supervisor' || a.site_id === fixtures[0].id,
        ),
      )
    if (pathname.endsWith('/acknowledge')) {
      const alert = alerts.find(
        (a) => a.id === decodeURIComponent(pathname.split('/')[3]),
      )
      if (!alert) return new Response('', { status: 404 })
      alert.acknowledgements.push({
        id: 'unit-ack',
        user_id: `private-${role}-subject`,
        alert_id: alert.id,
        acknowledged_at: new Date().toISOString(),
      })
      return Response.json(alert)
    }
    if (pathname.endsWith('/review'))
      return new Response('', { status: role === 'crew' ? 403 : 404 })
    const id = decodeURIComponent(pathname.split('/')[3])
    if (role === 'crew' && id !== fixtures[0].id)
      return new Response('', { status: 403 })
    return Response.json(detail)
  }
  const makeClient = (token) =>
    new HttpClient(
      'http://localhost:8000',
      async () => ({ Authorization: `Bearer ${token}` }),
      fetcher,
    )
  const request = async (path, options) => {
    const r = await fetcher(path, options)
    return { status: r.status, data: null }
  }
  return {
    calls,
    options: {
      accounts,
      makeClient,
      request,
      config,
      readiness,
      inventory: routeInventory({ '/api/reports/{id}/review': { post: {} } }),
      evidenceType: 'mocked_transport',
      ...overrides,
    },
  }
}
const byId = (result, id) => result.report.checks.find((c) => c.id === id)

test('published T053 report reads use existing client and remain distinct from absent review and live creation acceptance', async () => {
  const h = harness({
    inventory: routeInventory({ '/api/reports': { get: {}, post: {} } }),
  })
  const result = await runAcceptance(h.options)
  assert.equal(byId(result, 'anonymous_reports').status, 'passed')
  assert.equal(byId(result, 'crew_report_list').status, 'passed')
  assert.equal(byId(result, 'supervisor_report_list').status, 'passed')
  assert.equal(byId(result, 'crew_review_denied').status, 'blocked')
  assert(result.snapshots.reports.length > 0)
  assert(!h.calls.some((c) => c.path === '/api/reports' && c.method === 'POST'))
  assert.equal(result.report.live_acceptance_complete, false)
})

test('local origins reject remote destinations, credentials and query token leakage', () => {
  assert.equal(origin('http://localhost:8000'), 'http://localhost:8000')
  for (const input of [
    'https://remote.example',
    'http://u:p@localhost:8000',
    'http://localhost:8000/?token=' + secret,
    'file:///tmp',
  ])
    assert.throws(() => origin(input))
})
test('route inventory compares canonical path shape and never calls missing services', () => {
  const rows = routeInventory({
    '/api/sites/{id}': { get: {} },
    '/api/reports/{id}/review': { get: {} },
  })
  assert(rows.find((r) => r.path === '/api/sites/{site_id}').available)
  assert(
    !rows.find((r) => r.path === '/api/reports/{report_id}/review').available,
  )
})
test('token inspection refuses wrong roles, audience, issuer, expiry and algorithm without claiming signature validation', () => {
  assert.equal(tokenIdentity(jwt('crew'), 'crew', config).role, 'crew')
  for (const token of [
    jwt('supervisor'),
    jwt('crew', { exp: 1 }),
    jwt('crew', { aud: 'wrong' }),
    jwt('crew', { iss: 'wrong' }),
    jwt('crew', {}, { alg: 'none' }),
    secret,
  ])
    assert.throws(
      () => tokenIdentity(token, 'crew', config),
      (e) => !e.message.includes(secret),
    )
})
test('read-only acceptance uses actual app client, cross-role denial and new typed reads; never acknowledges by default', async () => {
  const h = harness(),
    r = await runAcceptance(h.options)
  assert.equal(byId(r, 'crew_unrelated_site').status, 'passed')
  assert.equal(byId(r, 'crew_review_denied').status, 'passed')
  assert.equal(byId(r, 'acknowledgement_persistence').status, 'not_run')
  assert(!h.calls.some((c) => c.role && c.path.endsWith('/acknowledge')))
  assert.equal(r.report.evidence_type, 'mocked_transport')
  assert.equal(r.report.live_acceptance_complete, false)
  assert(!JSON.stringify(r.report).includes('private-crew-subject'))
  assert(!JSON.stringify(r.report).includes(h.options.accounts.crew))
})
test('missing credentials leave real account checks blocked; no mock account is substituted', async () => {
  const h = harness({ accounts: {} }),
    r = await runAcceptance(h.options)
  assert.equal(byId(r, 'crew_session').status, 'blocked')
  assert.equal(r.snapshots.details.length, 0)
  assert(!h.calls.some((c) => c.role))
})
test('configured development bypass blocks token use and writes', async () => {
  const h = harness({
    readiness: {
      ...readiness,
      auth: { ...readiness.auth, dev_auth_bypass: true },
    },
    allowAcknowledge: true,
    alertId: 'alert-ltg-demo',
  })
  const r = await runAcceptance(h.options)
  assert.equal(byId(r, 'acknowledgement_persistence').status, 'blocked')
  assert(!h.calls.some((c) => c.role))
})
test('missing report route is blocked rather than counted as supervisor authorization', async () => {
  const h = harness({ inventory: [] }),
    r = await runAcceptance(h.options)
  assert.equal(byId(r, 'crew_review_denied').status, 'blocked')
  assert(!h.calls.some((c) => c.path.endsWith('/review')))
})
test('explicit acknowledgement is observed by independent crew and supervisor clients, without claiming browser or real DB acceptance', async () => {
  const h = harness({ allowAcknowledge: true, alertId: 'alert-ltg-demo' }),
    r = await runAcceptance(h.options)
  assert.equal(byId(r, 'acknowledgement_persistence').status, 'passed')
  assert.equal(byId(r, 'real_browser_roles').status, 'not_run')
  assert.equal(r.report.evidence_type, 'mocked_transport')
  assert.equal(
    h.calls.filter((c) => c.role && c.path.endsWith('/acknowledge')).length,
    1,
  )
  assert.deepEqual(r.report.task_checkboxes_changed, [])
})
test('missing database verification or unassigned/unknown alert prevents acknowledgement writes', async () => {
  for (const overrides of [
    { readiness: { ...readiness, database: { status: 'blocked' } } },
    { alertId: 'not-assigned' },
  ]) {
    const h = harness({
        allowAcknowledge: true,
        alertId: 'alert-ltg-demo',
        ...overrides,
      }),
      r = await runAcceptance(h.options)
    assert.equal(byId(r, 'acknowledgement_persistence').status, 'blocked')
    assert(!h.calls.some((c) => c.role && c.path.endsWith('/acknowledge')))
  }
})
test('backend failure messages and private subjects/tokens never appear in saved acceptance report', async () => {
  const h = harness({
      makeClient: () => ({
        sites: async () => {
          throw new Error(secret)
        },
      }),
    }),
    r = await runAcceptance(h.options)
  assert.equal(byId(r, 'crew_sites').status, 'failed')
  const text = JSON.stringify(r.report)
  assert(!text.includes(secret))
  assert(!text.includes(h.options.accounts.crew))
})
test('actual authentication unavailability is blocked, not described as a tested invalid token', async () => {
  const h = harness({
      accounts: {},
      request: async (_p, o) => ({
        status: o?.headers?.Authorization ? 503 : 401,
      }),
    }),
    r = await runAcceptance(h.options)
  assert.equal(byId(r, 'invalid_token').status, 'blocked')
})

test('unexpected anonymous success prevents sending real account tokens to an unprotected service', async () => {
  const h = harness({
    request: async () => ({ status: 200 }),
    allowAcknowledge: true,
    alertId: 'alert-ltg-demo',
  })
  const r = await runAcceptance(h.options)
  assert.equal(byId(r, 'anonymous_sites').status, 'failed')
  assert.equal(byId(r, 'acknowledgement_persistence').status, 'blocked')
  assert(!h.calls.some((c) => c.role))
})

test('a successful acknowledgement echo without independent server persistence fails acceptance', async () => {
  const h = harness({ allowAcknowledge: true, alertId: 'alert-ltg-demo' })
  const makeClient = h.options.makeClient
  h.options.makeClient = (token) => {
    const client = makeClient(token)
    client.acknowledge = async () => ({ id: 'non-persistent-echo' })
    return client
  }
  const r = await runAcceptance(h.options)
  assert.equal(byId(r, 'acknowledgement_persistence').status, 'failed')
})

test('cleared or operational alerts are ineligible for this test acknowledgement write', async () => {
  for (const change of [{ state: 'cleared' }, { simulated: false }]) {
    const alerts = structuredClone(initialAlerts)
    Object.assign(
      alerts.find((a) => a.id === 'alert-ltg-demo'),
      change,
    )
    const h = harness(
      { allowAcknowledge: true, alertId: 'alert-ltg-demo' },
      alerts,
    )
    const r = await runAcceptance(h.options)
    assert.equal(byId(r, 'acknowledgement_persistence').status, 'blocked')
    assert(!h.calls.some((c) => c.role && c.path.endsWith('/acknowledge')))
  }
})

test('accepting an invalid bearer token prevents sending real account credentials even when anonymous reads are denied', async () => {
  const h = harness({
    request: async (_path, options) => ({
      status: options?.headers?.Authorization ? 200 : 401,
    }),
  })
  const result = await runAcceptance(h.options)
  assert.equal(byId(result, 'invalid_token').status, 'failed')
  assert.equal(byId(result, 'crew_session').status, 'blocked')
  assert(!h.calls.some((c) => c.role))
})
