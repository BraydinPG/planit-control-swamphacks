/** Canonical read/ack contracts using isolated HTTP mocks, never live acceptance. */
import { after, test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createServer } from 'vite'
const server = await createServer({
  configFile: false,
  logLevel: 'silent',
  cacheDir: '.shell-check/live-read-unit-cache',
  server: { middlewareMode: true, hmr: false, watch: null },
})
after(() => server.close())
const { HttpClient } = await server.ssrLoadModule('/src/api/http-client.ts')
const fixtures = async (name) =>
  JSON.parse(
    await readFile(new URL(`../src/fixtures/${name}.json`, import.meta.url)),
  )
const sites = await fixtures('sites'),
  detail = await fixtures('site-detail'),
  alerts = await fixtures('alerts')
const client = (value) =>
  new HttpClient(
    'http://localhost:8000',
    async () => ({ Authorization: 'Bearer mock-only' }),
    async () => Response.json(value),
  )

test('canonical site/detail/alert reads retain nulls, source/time metadata, research flags and server state without mutation', async () => {
  assert.deepEqual(await client(sites).sites(), sites)
  assert.deepEqual(await client(detail).site(detail.id), detail)
  assert.deepEqual(await client(alerts).alerts(), alerts)
  const unscored = {
    ...sites[0],
    risk_score: null,
    risk_level: null,
    updated_at: null,
  }
  assert.deepEqual((await client([unscored]).sites())[0], unscored)
})
test('out-of-range/coerced site fields and duplicate identifiers cannot become a valid site view', async () => {
  for (const row of [
    { ...sites[0], lat: 91 },
    { ...sites[0], lon: -181 },
    { ...sites[0], risk_score: '0' },
    { ...sites[0], risk_score: 11 },
    { ...sites[0], risk_level: 'safe' },
    { ...sites[0], data_completeness: -1 },
    { ...sites[0], active_alerts: 1.5 },
    { ...sites[0], updated_at: 'not-a-time' },
    { ...sites[0], assigned_team: {} },
    { ...sites[0], top_factors: [{}] },
  ])
    await assert.rejects(
      () => client([row]).sites(),
      (e) => e.status === 502,
    )
  await assert.rejects(
    () => client([sites[0], sites[0]]).sites(),
    (e) => e.status === 502,
  )
})
test('site details reject foreign-site observations/reports/alerts and malformed nested source/score fields', async () => {
  for (const override of [
    { id: 'wrong-site' },
    { observations: [{ ...detail.observations[0], site_id: 'other' }] },
    { observations: [{ ...detail.observations[0], observed_at: 'yesterday' }] },
    { alerts: [{ ...detail.alerts[0], site_id: 'other' }] },
    { reports: [{ ...detail.reports[0], site_id: 'other' }] },
    { score: { ...detail.score, risk_score: 99 } },
    { event_outlook: { ...detail.event_outlook, production_eligible: true } },
  ])
    await assert.rejects(
      () => client({ ...detail, ...override }).site(detail.id),
      (e) => e.status === 502,
    )
})
test('invalid alert states, timestamps, flags, acknowledgement identities and duplicate IDs reject without a cleared fallback', async () => {
  for (const override of [
    { state: 'safe' },
    { rule: 'ai_clearance' },
    { latest_event_at: 'bad' },
    { clear_after: 0 },
    { distance_miles: -1 },
    { simulated: 'true' },
    { acknowledgements: [{}] },
    {
      acknowledgements: [
        {
          id: 'ack',
          alert_id: 'wrong',
          user_id: 'mock',
          acknowledged_at: '2026-10-17T18:00:00Z',
        },
      ],
    },
  ])
    await assert.rejects(
      () => client([{ ...alerts[0], ...override }]).alerts(),
      (e) => e.status === 502,
    )
  await assert.rejects(
    () => client([alerts[0], alerts[0]]).alerts(),
    (e) => e.status === 502,
  )
})
test('one site payload cannot mix headline and nested stored-score versions', async () => {
  for (const override of [
    { risk_score: detail.risk_score - 1 },
    { risk_level: 'critical' },
    { model_version: 'different-server-version' },
    { data_completeness: detail.data_completeness === 0 ? 1 : 0 },
    {
      updated_at: new Date(Date.parse(detail.updated_at) + 1000).toISOString(),
    },
    { score: null },
  ])
    await assert.rejects(
      () => client({ ...detail, ...override }).site(detail.id),
      (e) => e.status === 502,
    )
  // A genuine unscored response remains null; equivalent timezone notation is valid.
  const unscored = {
    ...detail,
    risk_score: null,
    risk_level: null,
    updated_at: null,
    score: null,
    model_version: 'unscored',
    data_completeness: 0,
    top_factors: [],
  }
  assert.deepEqual(await client(unscored).site(detail.id), unscored)
  const equivalent = {
    ...detail,
    updated_at: new Date(detail.updated_at).toISOString(),
  }
  assert.deepEqual(await client(equivalent).site(detail.id), equivalent)
})
test('acknowledgement must return the matching complete canonical alert and a server acknowledgement', async () => {
  for (const value of [
    { id: alerts[0].id },
    { ...alerts[0], id: 'wrong' },
    { ...alerts[0], acknowledgements: [] },
  ])
    await assert.rejects(
      () => client(value).acknowledge(alerts[0].id),
      (e) => e.status === 502,
    )
  const expected = {
    ...alerts[0],
    acknowledgements: [
      {
        id: 'mock-ack',
        alert_id: alerts[0].id,
        user_id: 'mock-user',
        acknowledged_at: '2026-10-17T18:00:00Z',
      },
    ],
  }
  assert.deepEqual(await client(expected).acknowledge(expected.id), expected)
})
test('a concurrent server state change is retained; client never derives clearance from acknowledgement or elapsed time', async () => {
  const expected = {
    ...alerts[0],
    state: 'cleared',
    clear_after: '2026-01-01T00:00:00Z',
    acknowledgements: [
      {
        id: 'ack',
        alert_id: alerts[0].id,
        user_id: 'mock',
        acknowledged_at: '2026-10-17T18:00:00Z',
      },
    ],
  }
  assert.deepEqual(await client(expected).acknowledge(expected.id), expected)
  expected.state = 'active'
  await assert.rejects(
    () => client(expected).alerts(),
    (e) => e.status === 502,
  )
  assert.equal((await client([expected]).alerts())[0].state, 'active')
})
