import { after, test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createServer } from 'vite'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
const server = await createServer({
  configFile: false,
  cacheDir: '.shell-check/briefings-unit-cache',
  logLevel: 'silent',
  server: { middlewareMode: true, hmr: false, watch: null },
})
after(() => server.close())
const { HttpClient } = await server.ssrLoadModule('/src/api/http-client.ts')
const { DemoClient } = await server.ssrLoadModule('/src/demo/client.ts')
const { validateBriefing } = await server.ssrLoadModule('/src/api/validate.ts')
const { BriefingCard } = await server.ssrLoadModule(
  '/src/components/data/StoredBriefings.tsx',
)
const fixtures = JSON.parse(
  await readFile(new URL('../src/fixtures/briefings.json', import.meta.url)),
)
const client = (fetcher) =>
  new HttpClient(
    'http://localhost:8000',
    async () => ({ Authorization: 'Bearer test-only' }),
    fetcher,
  )

test('stored site and organization DTOs use GET only, exact IDs and forecast windows', async () => {
  const requests = []
  const api = client(async (url, options) => {
    requests.push([url.pathname, options.method ?? 'GET'])
    return Response.json(
      url.pathname === '/api/briefings' ? fixtures : fixtures[0],
    )
  })
  assert.deepEqual(await api.briefing(fixtures[0].site_id), fixtures[0])
  assert.deepEqual(await api.briefings(), fixtures)
  assert.deepEqual(requests, [
    [`/api/sites/${fixtures[0].site_id}/briefing`, 'GET'],
    ['/api/briefings', 'GET'],
  ])
})
test('missing site briefing is empty; permission/auth/service errors never substitute samples', async () => {
  assert.equal(
    await client(async () => new Response('', { status: 404 })).briefing(
      'missing',
    ),
    null,
  )
  for (const status of [401, 403, 503]) {
    for (const method of ['briefing', 'briefings']) {
      await assert.rejects(
        () =>
          client(async () => new Response('', { status }))[method]('missing'),
        (e) => e.status === status,
      )
    }
  }
})
test("backend reasons pass through; only a 'not generated' 404 is the plain empty state", async () => {
  const reply = (status, reason, message) => async () =>
    Response.json({ detail: { reason, message } }, { status })
  assert.equal(
    await client(
      reply(404, 'not_generated', 'No briefing yet. Briefings are generated at 6 PM site-local time.'),
    ).briefing('site-a'),
    null,
  )
  const cases = [
    [404, 'no_supervisor', 'No supervisor is assigned to this organization, so no briefing is generated.'],
    [404, 'no_team', 'This site has no assigned team, so no briefing is generated for it.'],
    [403, 'not_linked', "Your account isn't linked to an organization yet, so briefings can't be shown."],
  ]
  for (const [status, reason, message] of cases) {
    await assert.rejects(
      () => client(reply(status, reason, message)).briefing('site-a'),
      (e) => e.status === status && e.reason === reason && e.detail === message,
    )
  }
  await assert.rejects(
    () => client(reply(403, 'not_linked', 'not linked')).briefings(),
    (e) => e.status === 403 && e.reason === 'not_linked',
  )
  // Without a reason the generic message stays and nothing is attached.
  await assert.rejects(
    () => client(async () => new Response('', { status: 403 })).briefing('x'),
    (e) => e.status === 403 && e.reason === undefined && e.detail === undefined,
  )
})
test('invalid DTO, wrong site, contradictory forecast dates and invalid JSON fail closed', async () => {
  for (const value of [
    {},
    null,
    { ...fixtures[0], site_id: 'unrelated' },
    { ...fixtures[0], forecast_window_end: fixtures[0].forecast_window_start },
    { ...fixtures[0], generated_by: 'browser' },
    { ...fixtures[0], hazards: [null] },
  ]) {
    await assert.rejects(
      () =>
        client(async () => Response.json(value)).briefing(fixtures[0].site_id),
      (e) => e.status === 502,
    )
  }
  await assert.rejects(
    () => client(async () => Response.json({})).briefings(),
    (e) => e.status === 502,
  )
  await assert.rejects(
    () => client(async () => new Response('bad')).briefings(),
    (e) => e.status === 502,
  )
})
test('stored Gemini/template cards retain hazards, source times, evidence and unknowns', () => {
  for (const fixture of fixtures) {
    const html = renderToStaticMarkup(
      React.createElement(BriefingCard, { value: fixture }),
    )
    assert(
      html.includes(
        fixture.generated_by === 'fallback'
          ? 'Deterministic template fallback'
          : 'Gemini output',
      ),
    )
    for (const time of [
      fixture.created_at,
      fixture.forecast_window_start,
      fixture.forecast_window_end,
    ])
      assert(html.includes(time))
    assert(
      html.includes('Evidence references') &&
        html.includes('Unknowns') &&
        html.includes('Hazards'),
    )
    assert(!html.includes('<button'))
  }
})
test('demo stored fixtures are read-only and unavailable reference sites stay empty', async () => {
  const api = new DemoClient(() => 'supervisor', null)
  assert.equal((await api.briefing(fixtures[0].site_id)).id, fixtures[0].id)
  assert.deepEqual(await api.briefings(), fixtures)
  assert.equal(await api.briefing('eia860m-FL-59611'), null)
  const first = await api.briefings()
  first[0].summary = 'mutated'
  assert.notEqual((await api.briefings())[0].summary, 'mutated')
})
test('briefings show the 0–10 index and each hazard’s points, never a level per hazard', () => {
  const gemini = fixtures.find((f) => f.generated_by === 'gemini')
  const text = renderToStaticMarkup(
    React.createElement(BriefingCard, { value: gemini }),
  ).replace(/<[^>]+>/g, '')
  assert(text.includes('Site hazard index at generation: 6.1 / 10 · high'))
  assert(text.includes('Not enough current data to score'))
  assert(text.includes('Lightning stop-work (simulated) · +3.0 pts'))
  assert(text.includes('Afternoon thunderstorms · not in score'))
  const empty = renderToStaticMarkup(
    React.createElement(BriefingCard, {
      value: { ...gemini, risk_score: 0, data_completeness: 0 },
    }),
  ).replace(/<[^>]+>/g, '')
  assert(empty.includes('Not enough current data to score'))
  const legacy = renderToStaticMarkup(
    React.createElement(BriefingCard, {
      value: { ...gemini, risk_score: null, data_completeness: null },
    }),
  ).replace(/<[^>]+>/g, '')
  assert(legacy.includes('Risk level at generation: high'))
})
test('briefing index and points are validated', () => {
  const gemini = fixtures.find((f) => f.generated_by === 'gemini')
  assert.equal(validateBriefing(gemini).risk_score, 6.1)
  for (const bad of [
    { risk_score: 11 },
    { data_completeness: 1.5 },
    { hazards: [{ hazard: 'Heat', points: -1, evidence_ids: ['x'] }] },
    { hazards: [{ hazard: 'Heat', risk_level: 'high', evidence_ids: ['x'] }] },
  ])
    assert.throws(() => validateBriefing({ ...gemini, ...bad }), (e) => e.status === 502)
})
