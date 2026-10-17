/** Mocked HTTP contract/workflow tests. Never real Auth0 or database acceptance. */
import { after, test } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'
const server = await createServer({
  configFile: false,
  logLevel: 'silent',
  cacheDir: '.shell-check/lifecycle-unit-cache',
  server: { middlewareMode: true, hmr: false, watch: null },
})
after(() => server.close())
const { HttpClient } = await server.ssrLoadModule('/src/api/http-client.ts')
const { createMockService } = await server.ssrLoadModule(
  '/tests/mock-service.ts',
)
const site = 'site-demo-everglades'
const input = {
  site_id: site,
  category: 'broken_pole_downed_line',
  hazard_present: true,
  lat: 25.76,
  lon: -80.49,
}
const photo = () =>
  new File(['mock photo only'], 'mock.png', { type: 'image/png' })
function setup() {
  const service = createMockService(),
    requests = []
  const client = (role) =>
    new HttpClient(
      'http://localhost:8000',
      async () => ({ Authorization: `Bearer mock-${role}` }),
      async (url, options) => {
        requests.push([role, options.method ?? 'GET', url.pathname])
        return service.request(url, options, role)
      },
    )
  return {
    service,
    requests,
    client,
    crew: client('crew'),
    supervisor: client('supervisor'),
  }
}

test('mock HTTP present lifecycle: photo -> pending/no instruction -> notice confirmation -> edited send -> independent read-back', async () => {
  const { crew, supervisor, client, requests } = setup()
  const before = await crew.site(site)
  await assert.rejects(
    () => crew.submit(input, null),
    (e) => e.status === 422,
  )
  const report = await crew.submit(input, photo())
  assert.equal(report.review_status, 'pending')
  assert.equal(report.note, null)
  const pending = await crew.site(site)
  assert.equal(pending.risk_score, before.risk_score)
  assert.deepEqual(pending.alerts, before.alerts)
  let notice = pending.notices.find((n) => n.id === report.notice_id)
  assert.equal(notice.status, 'potential')
  assert.equal(notice.instruction, null)
  assert.equal(notice.suggested_instruction, null)
  await assert.rejects(
    () => supervisor.review(report.id, { decision: 'confirmed' }),
    (e) => e.status === 409,
  )
  const confirmation = await supervisor.confirm(notice.id)
  assert.equal(confirmation.notice.confirmed_by, 'mock-supervisor')
  assert.equal(confirmation.generated_by, 'gemini')
  assert.equal(confirmation.notice.instruction, null)
  assert.equal(requests.filter((r) => r[2].endsWith('/instruction')).length, 0)
  assert(
    (await supervisor.site(site)).reports.find((r) => r.id === report.id)
      .review_status === 'confirmed',
  )
  assert.equal((await supervisor.site(site)).risk_score, 8.25) // supplied mock server DTO
  const sent = await supervisor.instruct(
    notice.id,
    '  Edited by supervisor: request field inspection.  ',
  )
  assert.equal(
    sent.instruction,
    'Edited by supervisor: request field inspection.',
  )
  notice = (await client('crew').site(site)).notices.find(
    (n) => n.id === notice.id,
  )
  assert.equal(notice.instruction, sent.instruction)
  assert(notice.instruction_sent_at)
  assert.equal(notice.suggested_instruction, null)
  assert.deepEqual((await crew.site(site)).alerts, before.alerts)
})
test('mock HTTP absent/rejected review: no required photo, no notice or score mutation, new client reads reviewed state', async () => {
  const { crew, supervisor, client, service } = setup()
  const noticeCount = service.notices.length
  for (const decision of ['confirmed', 'rejected']) {
    const report = await crew.submit({ ...input, hazard_present: false }, null)
    assert.equal(report.notice_id, null)
    await supervisor.review(report.id, { decision })
    assert.equal(
      (await client('crew').reports()).find((r) => r.id === report.id)
        .review_status,
      decision,
    )
  }
  assert.equal(service.notices.length, noticeCount)
  assert.equal(service.confirmed, false)
})
test('mock HTTP manual draft fallback requires explicit nonblank instruction, never auto sends', async () => {
  const { crew, supervisor, service, requests } = setup()
  service.draft = null
  const report = await crew.submit(input, photo())
  const result = await supervisor.confirm(report.notice_id)
  assert.equal(result.suggested_instruction, null)
  assert.equal(result.generated_by, null)
  const count = requests.length
  for (const value of ['', '  ', 'a'.repeat(501)])
    await assert.rejects(
      () => supervisor.instruct(report.notice_id, value),
      (e) => e.status === 422,
    )
  assert.equal(requests.length, count)
  assert.equal(
    (await supervisor.instruct(report.notice_id, 'Manual supervisor text'))
      .instruction,
    'Manual supervisor text',
  )
})
test('mock policy denials and conflicts remain backend-authoritative with no ownership takeover', async () => {
  const { crew, supervisor, service } = setup()
  await assert.rejects(
    () => crew.submit({ ...input, site_id: 'site-fixture-b' }, photo()),
    (e) => e.status === 403,
  )
  const report = await crew.submit(input, photo())
  await assert.rejects(
    () => crew.confirm(report.notice_id),
    (e) => e.status === 403,
  )
  service.denyMutation = true
  await assert.rejects(
    () => supervisor.confirm(report.notice_id),
    (e) => e.status === 403,
  )
  service.denyMutation = false
  await supervisor.confirm(report.notice_id)
  await assert.rejects(
    () => supervisor.confirm(report.notice_id),
    (e) => e.status === 409,
  )
  const notice = service.notices.find((n) => n.id === report.notice_id)
  notice.confirmed_by = 'other-supervisor'
  await assert.rejects(
    () => supervisor.instruct(notice.id, 'No takeover'),
    (e) => e.status === 403,
  )
  assert.equal(notice.instruction, null)
  assert.equal(notice.confirmed_by, 'other-supervisor')
  await assert.rejects(
    () => supervisor.confirm('missing'),
    (e) => e.status === 404,
  )
})
for (const status of [401, 403, 404, 409, 422, 503])
  test(`mock HTTP lifecycle ${status}: no automatic mutation retries or success substitution`, async () => {
    let calls = 0
    const api = new HttpClient(
      'http://localhost:8000',
      async () => ({ Authorization: 'Bearer mock' }),
      async () => {
        calls++
        return new Response('', { status })
      },
    )
    for (const action of [
      () => api.submit(input, photo()),
      () => api.review('id', { decision: 'confirmed' }),
      () => api.confirm('id'),
      () => api.instruct('id', 'Text'),
    ])
      await assert.rejects(action, (e) => e.status === status)
    assert.equal(calls, 4)
  })
test('malformed confirmation/delivery/report replies cannot become a successful local state', async () => {
  const { crew, service } = setup()
  const report = await crew.submit(input, photo())
  const potential = service.notices.find((n) => n.id === report.notice_id)
  for (const value of [
    {},
    { notice: potential, suggested_instruction: null, generated_by: null },
    {
      notice: { ...potential, status: 'confirmed', confirmed_by: null },
      suggested_instruction: null,
      generated_by: null,
    },
  ]) {
    const api = new HttpClient(
      'http://localhost:8000',
      async () => ({ Authorization: 'Bearer mock' }),
      async () => Response.json(value),
    )
    await assert.rejects(
      () => api.confirm(potential.id),
      (e) => e.status === 502,
    )
  }
  const api = new HttpClient(
    'http://localhost:8000',
    async () => ({ Authorization: 'Bearer mock' }),
    async () => Response.json(potential),
  )
  await assert.rejects(
    () => api.instruct(potential.id, 'Text'),
    (e) => e.status === 502,
  )
  await assert.rejects(
    () => api.submit(input, photo()),
    (e) => e.status === 502,
  )
})
test('network failure and abort timeout leave mutation outcome unknown without fallback or retry', async () => {
  for (const fetcher of [
    async () => {
      throw new Error('private provider failure')
    },
    (_url, options) =>
      new Promise((_resolve, reject) =>
        options.signal.addEventListener('abort', () =>
          reject(new Error('abort')),
        ),
      ),
  ]) {
    const api = new HttpClient(
      'http://localhost:8000',
      async () => ({ Authorization: 'Bearer mock' }),
      fetcher,
      5,
    )
    await assert.rejects(
      () => api.submit(input, photo()),
      (e) => e.status === 0 && !e.message.includes('private provider'),
    )
  }
})
