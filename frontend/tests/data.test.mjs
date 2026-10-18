import { after, test } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
const server = await createServer({
  configFile: false,
  cacheDir: '.shell-check/data-unit-cache',
  logLevel: 'silent',
  server: { middlewareMode: true, hmr: false, watch: null },
  appType: 'custom',
})
after(() => server.close())
const { DemoClient, DEMO_KEY } = await server.ssrLoadModule(
  '/src/demo/client.ts',
)
const { HttpClient } = await server.ssrLoadModule('/src/api/http-client.ts')
const { countdown, sortSites } = await server.ssrLoadModule(
  '/src/api/contracts.ts',
)
const { Advisory } = await server.ssrLoadModule(
  '/src/components/data/Advisory.tsx',
)
const storage = () => {
  const map = new Map()
  return {
    getItem: (k) => map.get(k) ?? null,
    setItem: (k, v) => map.set(k, v),
    removeItem: (k) => map.delete(k),
  }
}
const assigned = 'site-demo-everglades'

test('demo accepts access mat deterioration and preserves the crew assessment', async () => {
  const client = new DemoClient(() => 'crew', storage())
  const report = await client.submit({ site_id: assigned,
    category: 'access_mat_deterioration', hazard_present: true, mat_condition: 'D',
    lat: 25.76, lon: -80.49, note: 'Mat 12: crew stage D.' })
  assert.equal(report.category, 'access_mat_deterioration')
  assert.equal(report.mat_condition, 'D')
  assert.equal(report.note, 'Mat 12: crew stage D.')
  assert.equal(report.review_status, 'pending')
  const notice = (await client.site(assigned)).notices.find(n => n.id === report.notice_id)
  assert.equal(notice.status, 'potential')
  assert.equal(notice.instruction, null)
})

test('access mat grade A is absent with no notice; mismatched grades are rejected', async () => {
  const client = new DemoClient(() => 'crew', storage())
  const base = { site_id: assigned, lat: 25.76, lon: -80.49 }
  const a = await client.submit({ ...base, category: 'access_mat_deterioration',
    hazard_present: false, mat_condition: 'A' })
  assert.equal(a.mat_condition, 'A')
  assert.equal(a.notice_id, null)
  for (const bad of [
    { category: 'access_mat_deterioration', hazard_present: true },
    { category: 'access_mat_deterioration', hazard_present: true, mat_condition: 'A' },
    { category: 'access_mat_deterioration', hazard_present: false, mat_condition: 'C' },
    { category: 'wildlife', hazard_present: true, mat_condition: 'B' },
  ])
    await assert.rejects(() => client.submit({ ...base, ...bad }), (e) => e.status === 422)
})

test('unapproved fixture model scores cannot determine demonstration ranking', async () => {
  const client = new DemoClient(() => 'supervisor', storage())
  const rows = await client.sites()
  // Keep the legacy guard covered without putting obsolete ML terms in canonical fixtures.
  const legacy = { ...rows[0], top_factors: [{ factor: 'model' }] }
  const eligible = {
    ...legacy,
    id: 'eligible',
    name: 'Eligible',
    risk_score: 0.1,
    top_factors: [],
  }
  assert.equal(sortSites([legacy, eligible], true)[0].id, 'eligible')
  assert.notEqual(legacy.risk_score, null)
})

test('reset replaces a saved legacy score with approved fixtures and preserves Auth0 storage', async () => {
  const saved = storage()
  const client = new DemoClient(() => 'supervisor', saved)
  client.reset()
  const old = JSON.parse(saved.getItem(DEMO_KEY))
  const obsolete = { factor: 'model', contribution: 1.6 }
  old.sites.find((s) => s.id === assigned).top_factors = [obsolete]
  old.details[assigned].top_factors = [obsolete]
  old.details[assigned].model_version = 'baseline-0.1'
  old.details[assigned].risk_score = 7.6
  saved.setItem(DEMO_KEY, JSON.stringify(old))
  saved.setItem('@@auth0spajs@@test-session', 'synthetic-session-sentinel')
  const restored = new DemoClient(() => 'supervisor', saved)
  assert.equal((await restored.site(assigned)).model_version, 'baseline-0.1')
  restored.reset()
  const detail = await new DemoClient(() => 'supervisor', saved).site(assigned)
  const row = (await restored.sites()).find((s) => s.id === assigned)
  assert.equal(detail.risk_score, 9.1)
  assert.equal(row.risk_score, detail.risk_score)
  assert.equal(detail.score.risk_score, detail.risk_score)
  assert.equal(detail.model_version, 'rules-0.2')
  assert.equal(detail.data_completeness, 0)
  assert(!detail.score.factor_contributions.some((f) => f.factor === 'model'))
  assert.equal(detail.event_outlooks.length, 6)
  assert.equal(
    saved.getItem('@@auth0spajs@@test-session'),
    'synthetic-session-sentinel',
  )
})

test('unavailable demo storage reports memory-only changes without claiming persistence', async () => {
  const client = new DemoClient(() => 'crew', null)
  await assert.rejects(
    () => client.acknowledge('alert-ltg-demo'),
    /memory only.*will not survive reload/,
  )
  assert(
    (await client.alerts())[0].acknowledgements.some(
      (a) => a.user_id === 'demo-crew',
    ),
  )
})
test('55 typed demo locations, 50 exact reference IDs, assigned first', async () => {
  const client = new DemoClient(() => 'supervisor', storage()),
    rows = await client.sites()
  assert.equal(rows.length, 55)
  assert.equal(rows.filter((s) => s.id.startsWith('eia860m-')).length, 50)
  assert(rows[0].assigned_team)
  assert(rows.slice(4).every((s) => !s.assigned_team))
  assert(
    rows
      .filter((s) => s.id.startsWith('eia860m-'))
      .every((s) => s.risk_score === null && s.updated_at === null),
  )
})
test('crew receives assigned site and cannot access another site or confirm notices', async () => {
  const client = new DemoClient(() => 'crew', storage())
  assert.equal((await client.sites()).length, 1)
  await assert.rejects(() => client.site('site-fixture-b'), /not assigned/)
  await assert.rejects(() => client.confirm('notice-pole-1'), /Supervisor/)
})
test('present report -> notice confirmation -> instruction persists; demo scores and alerts unchanged', async () => {
  let role = 'crew'
  const store = storage(),
    client = new DemoClient(() => role, store)
  const before = await client.site(assigned)
  const report = await client.submit(
    {
      site_id: assigned,
      category: 'broken_pole_downed_line',
      hazard_present: true,
      lat: 25.76,
      lon: -80.49,
    },
    new File(['demo'], 'test.png', { type: 'image/png' }),
  )
  assert.equal(report.review_status, 'pending')
  assert.equal(report.note, null)
  assert(client.photo(report.id)?.startsWith('blob:'))
  let notice = (await client.site(assigned)).notices.find(
    (n) => n.id === report.notice_id,
  )
  assert.equal(notice.status, 'potential')
  assert.equal(notice.instruction, null)
  assert.equal(notice.suggested_instruction, null)
  role = 'supervisor'
  await assert.rejects(
    () => client.instruct(notice.id, 'inspect'),
    /confirming supervisor/,
  )
  await assert.rejects(
    () => client.review(report.id, { decision: 'confirmed' }),
    /through their notice/,
  )
  await client.confirm(notice.id)
  await client.instruct(notice.id, 'Demo supervisor instruction for review.')
  const reloaded = new DemoClient(() => role, store),
    detail = await reloaded.site(assigned)
  notice = detail.notices.find((n) => n.id === report.notice_id)
  assert.equal(notice.instruction, 'Demo supervisor instruction for review.')
  assert(notice.instruction_sent_at)
  assert.equal(
    detail.reports.find((r) => r.id === report.id).review_status,
    'confirmed',
  )
  assert.deepEqual(detail.alerts, before.alerts)
  assert.equal(detail.risk_score, before.risk_score)
  assert.deepEqual(detail.top_factors, before.top_factors)
  assert.equal(reloaded.photo(report.id), null)
})
test('absent/rejected reports do not produce notices, scores or approval', async () => {
  const client = new DemoClient(() => 'supervisor', storage()),
    before = await client.site(assigned)
  const r = await client.submit(
    {
      site_id: assigned,
      category: 'wildlife',
      hazard_present: false,
      lat: 25.76,
      lon: -80.49,
    },
    null,
  )
  assert.equal(r.notice_id, null)
  await client.review(r.id, { decision: 'rejected' })
  const after = await client.site(assigned)
  assert.equal(after.notices.length, before.notices.length)
  assert.equal(after.risk_score, before.risk_score)
})
test('acknowledgement, strike reset and explicit cleared server payload survive reload', async () => {
  const store = storage(),
    client = new DemoClient(() => 'crew', store)
  await client.acknowledge('alert-ltg-demo')
  const before = (await client.alerts())[0]
  client.replay('strike')
  const reloaded = new DemoClient(() => 'crew', store),
    updated = (await reloaded.alerts())[0]
  assert(updated.clear_after > before.clear_after)
  assert(updated.acknowledgements.some((a) => a.user_id === 'demo-crew'))
  assert.match(
    countdown(updated, Date.parse(updated.clear_after) + 1000),
    /Alert remains active/,
  )
  client.replay('cleared')
  assert.match(
    countdown((await client.alerts())[0], Date.now()),
    /Server reports cleared/,
  )
})
test('invalid coordinates, category, photo and note fail before persistence', async () => {
  const client = new DemoClient(() => 'crew', storage()),
    input = {
      site_id: assigned,
      category: 'other',
      hazard_present: true,
      lat: 999,
      lon: 0,
    }
  await assert.rejects(() => client.submit(input, null), /fields/)
  input.lat = 25.76
  await assert.rejects(
    () =>
      client.submit(
        input,
        new File(['bad'], 'a.svg', { type: 'image/svg+xml' }),
      ),
    /Photo/,
  )
  await assert.rejects(
    () => client.submit({ ...input, note: 'x'.repeat(1001) }, null),
    /fields/,
  )
})
test('corrupt local demo storage safely resets and unrelated keys survive', async () => {
  const store = storage()
  store.setItem(DEMO_KEY, 'bad JSON')
  store.setItem('unrelated', 'keep')
  const client = new DemoClient(() => 'crew', store)
  assert.equal((await client.sites()).length, 1)
  client.reset()
  assert.equal(store.getItem('unrelated'), 'keep')
})
test('2.1 replay matches exact site only; wrong site cannot borrow probabilities', async () => {
  const client = new DemoClient(() => 'supervisor', storage())
  const render = (site) =>
    renderToStaticMarkup(React.createElement(Advisory, { site, demo: true }))
  assert.match(
    render(await client.site('eia860m-FL-59611')),
    /Developer\/demo advisory/,
  )
  assert.match(
    render(
      await client.site(
        (await client.sites()).find(
          (s) =>
            s.id.startsWith('eia860m-') &&
            !['eia860m-FL-59611', 'eia860m-AZ-68414'].includes(s.id),
        ).id,
      ),
    ),
    /No duration estimate for this hazard/,
  )
  const compact = render(await client.site(assigned))
  assert.match(
    compact,
    /Simulated replay: .*This flood is likely to continue for about 22 more hours/,
  )
  assert(!compact.includes('Developer/demo advisory'))
})
test('HTTP adapter passes Auth0 token and multipart photo, never a fake dev-role header', async () => {
  const calls = [],
    api = new HttpClient(
      'http://localhost:8000',
      async () => ({ Authorization: 'Bearer test-token' }),
      async (url, options) => {
        calls.push({ url: String(url), options })
        return Response.json({
          ...(await new DemoClient(() => 'crew', storage()).reports())[0],
          id: 'demo',
          site_id: assigned,
          category: 'other',
          hazard_present: false,
          review_status: 'pending',
        })
      },
    )
  await api.submit(
    {
      site_id: assigned,
      category: 'other',
      hazard_present: false,
      lat: 25.76,
      lon: -80.49,
    },
    new File(['test'], 'demo.png', { type: 'image/png' }),
  )
  assert.equal(calls[0].options.headers.Authorization, 'Bearer test-token')
  assert(!('Content-Type' in calls[0].options.headers))
  assert(calls[0].options.body instanceof FormData)
  assert.equal(calls[0].options.body.get('hazard_present'), 'false')
  assert.equal(calls[0].options.body.get('photo').name, 'demo.png')
})
test('published T048 client requests all states, sends authenticated acknowledgement and uses server clock estimate', async () => {
  const demo = new DemoClient(() => 'crew', storage())
  let alerts = await demo.alerts()
  const calls = []
  const serverTime = '2026-10-17T18:00:00Z'
  const api = new HttpClient(
    'http://localhost:8000',
    async () => ({ Authorization: 'Bearer test' }),
    async (url, options) => {
      calls.push(
        `${options.method ?? 'GET'} ${new URL(url).pathname}${new URL(url).search}`,
      )
      if (options.method === 'POST') {
        alerts = alerts.map((a) =>
          a.id === 'alert-ltg-demo'
            ? {
                ...a,
                acknowledgements: [
                  ...a.acknowledgements,
                  {
                    id: 'server-ack',
                    user_id: 'server-user',
                    alert_id: a.id,
                    acknowledged_at: serverTime,
                  },
                ],
              }
            : a,
        )
        return Response.json(alerts[0])
      }
      return Response.json(alerts, {
        headers: { Date: new Date(serverTime).toUTCString() },
      })
    },
  )
  assert(api.capabilities.acknowledge)
  assert(
    api.capabilities.reports &&
      api.capabilities.reviewReports &&
      api.capabilities.hazards &&
      api.capabilities.briefings,
  )
  await api.alerts()
  assert(Math.abs(api.now() - Date.parse(serverTime)) < 1000)
  await api.acknowledge('alert-ltg-demo')
  assert(
    (await api.alerts())[0].acknowledgements.some((a) => a.id === 'server-ack'),
  )
  assert.deepEqual(calls, [
    'GET /api/alerts?state=all',
    'POST /api/alerts/alert-ltg-demo/acknowledge',
    'GET /api/alerts?state=all',
  ])
})
for (const status of [401, 403, 404, 409, 422, 503])
  test(`HTTP ${status} stays an explicit failure without fixtures`, async () => {
    const api = new HttpClient(
      'http://localhost:8000',
      async () => ({ Authorization: 'Bearer test-token' }),
      async () => new Response('', { status }),
    )
    await assert.rejects(
      () => api.sites(),
      (e) => e.status === status,
    )
  })
test('missing token sends no request; token acquisition and network timeouts reject', async () => {
  let calls = 0
  const missing = new HttpClient(
    'http://localhost:8000',
    async () => ({}),
    async () => {
      calls++
      return Response.json([])
    },
  )
  await assert.rejects(
    () => missing.sites(),
    (e) => e.status === 401,
  )
  assert.equal(calls, 0)
  const hung = new HttpClient(
    'http://localhost:8000',
    () => new Promise(() => {}),
    fetch,
    5,
  )
  await assert.rejects(() => hung.sites(), /timed out/)
  const timeout = new HttpClient(
    'http://localhost:8000',
    async () => ({ Authorization: 'Bearer test' }),
    (_url, { signal }) =>
      new Promise((_, reject) =>
        signal.addEventListener('abort', () => reject(new Error('abort'))),
      ),
    5,
  )
  await assert.rejects(() => timeout.sites(), /timed out/)
})
test('malformed/invalid API replies and unsafe destinations reject', async () => {
  const api = new HttpClient(
    'http://localhost:8000',
    async () => ({ Authorization: 'Bearer test' }),
    async () => Response.json({ not: 'sites' }),
  )
  await assert.rejects(() => api.sites(), /Invalid site-list/)
  assert.throws(
    () => new HttpClient('http://remote.example', async () => ({})),
    /HTTPS/,
  )
  assert.throws(
    () => new HttpClient('https://user:password@example.com', async () => ({})),
    /destination/,
  )
})
