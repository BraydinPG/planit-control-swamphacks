/** Synthetic browser positions only. No actual geolocation, Auth0, DB, or T053A acceptance. */
import { after, test } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'
const server = await createServer({
  configFile: false, logLevel: 'silent', cacheDir: '.shell-check/location-unit-cache',
  server: { middlewareMode: true, hmr: false, watch: null },
})
after(() => server.close())
const { createReportLocationController, REPORT_LOCATION_TIMEOUT_MS } = await server.ssrLoadModule('/src/application/report-location.ts')
const { HttpClient } = await server.ssrLoadModule('/src/api/http-client.ts')
const { DemoClient, DEMO_KEY } = await server.ssrLoadModule('/src/demo/client.ts')
const { createMockService } = await server.ssrLoadModule('/tests/mock-service.ts')
const site = Object.freeze({ id: 'site-demo-everglades', lat: 25.76, lon: -80.49 })
const other = Object.freeze({ id: 'site-fixture-b', lat: 28.1, lon: -81.1 })
const fix = (latitude = 26.1, longitude = -80.8, accuracy = 12) => ({ coords: { latitude, longitude, accuracy } })
function setup(providerOverride) {
  const requests = [], timers = new Set(), delays = [], updates = []
  const provider = { getCurrentPosition(success, error, options) {
    requests.push({ success, error, options })
  }, watchPosition() { assert.fail('Continuous tracking is forbidden') } }
  const controller = createReportLocationController({
    geolocation: providerOverride ?? (() => provider),
    schedule(callback, ms) {
      timers.add(callback)
      delays.push(ms)
      return () => timers.delete(callback)
    },
  })
  controller.subscribe(() => updates.push(controller.getSnapshot()))
  return { controller, requests, timers, delays, updates }
}
function approximate(controller, reason) {
  const state = controller.getSnapshot()
  assert.equal(state.status, 'site')
  assert.equal(state.reason, reason)
  assert.deepEqual(state.location, { lat: site.lat, lon: site.lon, source: 'site', accuracyM: null })
  assert.match(state.message, /approximate/i)
}

test('no request at construction/outside report; opening is one-shot, high accuracy and immediately usable', () => {
  const { controller, requests, timers, delays } = setup()
  assert.equal(controller.getSnapshot().status, 'closed')
  assert.equal(controller.getSnapshot().location, null)
  assert.equal(controller.setPin(20, 30), false)
  assert.equal(requests.length, 0)
  controller.open(site, 'live')
  controller.open({ ...site }, 'live')
  assert.equal(requests.length, 1)
  assert.equal(timers.size, 1)
  assert.deepEqual(delays, [8000])
  assert.equal(REPORT_LOCATION_TIMEOUT_MS, 8000)
  assert.deepEqual(requests[0].options, { enableHighAccuracy: true, maximumAge: 0, timeout: 8000 })
  assert.equal(controller.getSnapshot().status, 'locating')
  assert.equal(controller.getSnapshot().location.source, 'site')
  assert.equal(controller.getSnapshot().location.accuracyM, null)
  assert.match(controller.getSnapshot().message, /no need to wait/)
})

test('permission-granted valid fix retains finite accuracy, including zero coordinates and accuracy', () => {
  for (const position of [fix(), fix(0, 0, 0), fix(-90, 180, 12345)]) {
    const { controller, requests, timers } = setup()
    controller.open(site, 'live')
    requests[0].success(position)
    const state = controller.getSnapshot()
    assert.equal(state.status, 'device')
    assert.deepEqual(state.location, { lat: position.coords.latitude, lon: position.coords.longitude,
      source: 'device', accuracyM: position.coords.accuracy })
    assert.equal(timers.size, 0)
    requests[0].error({ code: 1 })
    assert.strictEqual(controller.getSnapshot(), state)
  }
})
for (const [code, reason] of [[1, 'denied'], [2, 'unavailable'], [3, 'timeout'], [9, 'unavailable']])
  test(`geolocation error ${code} falls back to approximate site, no invented accuracy`, () => {
    const { controller, requests, timers } = setup()
    controller.open(site, 'live')
    requests[0].error({ code, message: 'Do not display arbitrary provider messages/coordinates' })
    approximate(controller, reason)
    assert.equal(timers.size, 0)
    requests[0].success(fix())
    approximate(controller, reason)
  })

test('unsupported browser and throwing provider/request remain usable', () => {
  for (const [provider, reason] of [
    [() => null, 'unsupported'],
    [() => { throw new Error('policy unavailable') }, 'unavailable'],
    [() => ({ getCurrentPosition() { throw new Error('blocked') } }), 'unavailable'],
  ]) {
    const { controller, timers } = setup(provider)
    controller.open(site, 'live')
    approximate(controller, reason)
    assert.equal(timers.size, 0)
  }
})

test('own deadline covers unanswered permission prompt and ignores a later fix', () => {
  const { controller, requests, timers } = setup()
  controller.open(site, 'live')
  ;[...timers][0]()
  approximate(controller, 'timeout')
  assert.equal(timers.size, 0)
  requests[0].success(fix())
  approximate(controller, 'timeout')
})

test('invalid device coordinates are rejected without number/string/null coercion', () => {
  for (const position of [null, {}, { coords: null }, fix(NaN), fix(91), fix(-91),
    fix(Infinity), fix('25'), fix(null), fix(25, 181), fix(25, -181), fix(25, '0')]) {
    const { controller, requests } = setup()
    controller.open(site, 'live')
    requests[0].success(position)
    approximate(controller, 'invalid_device')
  }
})

test('negative, missing, nonnumeric and infinite accuracy cannot become device evidence', () => {
  for (const accuracy of [-1, NaN, Infinity, null, undefined, '12']) {
    const { controller, requests } = setup()
    controller.open(site, 'live')
    const position = fix()
    position.coords.accuracy = accuracy
    requests[0].success(position)
    approximate(controller, 'invalid_device')
  }
})

test('manual pin wins over late success/error/timeout and clears device accuracy', () => {
  const { controller, requests, timers } = setup()
  controller.open(site, 'live')
  const timeout = [...timers][0]
  assert.equal(controller.setPin(27, -82), true)
  const pin = controller.getSnapshot()
  assert.deepEqual(pin.location, { lat: 27, lon: -82, source: 'pin', accuracyM: null })
  requests[0].success(fix()); requests[0].error({ code: 2 }); timeout()
  assert.strictEqual(controller.getSnapshot(), pin)
  assert.equal(timers.size, 0)
  controller.close(); controller.open(site, 'live')
  requests[1].success(fix())
  controller.setPin(26.2, -80.9)
  assert.equal(controller.getSnapshot().location.source, 'pin')
  assert.equal(controller.getSnapshot().location.accuracyM, null)
})

test('invalid/incomplete manual edit stops GPS and exposes no stale coordinates for submission', () => {
  const { controller, requests, timers } = setup()
  controller.open(site, 'live')
  assert.equal(controller.setPin(NaN, -82), false)
  requests[0].success(fix())
  assert.equal(controller.getSnapshot().location, null)
  assert.equal(controller.getSnapshot().reason, 'invalid_pin')
  assert.equal(timers.size, 0)
  assert.equal(controller.setPin(27, -82), true)
  assert.equal(controller.getSnapshot().location.source, 'pin')
})

test('switching sites resets device/manual state, invalidates prior callbacks and handles moved same-ID site', () => {
  const { controller, requests, timers } = setup()
  controller.open(site, 'live')
  controller.setPin(25, -80)
  controller.open(other, 'live')
  requests[0].success(fix())
  assert.deepEqual(controller.getSnapshot().location, { lat: other.lat, lon: other.lon, source: 'site', accuracyM: null })
  requests[1].success(fix())
  controller.open({ ...other, lat: 29 }, 'live')
  assert.equal(requests.length, 3)
  assert.equal(controller.getSnapshot().location.lat, 29)
  assert.equal(timers.size, 1)
})

test('closing clears coordinates/timers, ignores outstanding callback and reopening creates one new request', () => {
  const { controller, requests, timers, updates } = setup()
  controller.open(site, 'live')
  const timeout = [...timers][0]
  controller.close()
  const count = updates.length
  requests[0].success(fix()); requests[0].error({ code: 1 }); timeout()
  assert.equal(updates.length, count)
  assert.equal(controller.getSnapshot().status, 'closed')
  assert.equal(controller.getSnapshot().location, null)
  assert.equal(controller.getSnapshot().site, null)
  assert.equal(timers.size, 0)
  controller.close()
  controller.open(site, 'live')
  assert.equal(requests.length, 2)
})

test('malformed site cannot trigger geolocation, reuse prior fix or invent fallback coordinates', () => {
  for (const badSite of [{ ...site, id: '' }, { ...site, lat: NaN },
    { ...site, lat: null }, { ...site, lon: 181 }]) {
    const { controller, requests } = setup()
    controller.open(badSite, 'live')
    assert.equal(controller.getSnapshot().reason, 'invalid_site')
    assert.equal(controller.getSnapshot().location, null)
    assert.equal(controller.setPin(25, -80), false)
    assert.equal(requests.length, 0)
  }
})

test('demo never acquires private GPS; mode change clears an earlier live fix', () => {
  const { controller, requests, timers } = setup()
  controller.open(site, 'demo')
  approximate(controller, 'demo')
  assert.equal(requests.length, 0)
  controller.open(site, 'live')
  requests[0].success(fix())
  controller.open(site, 'demo')
  approximate(controller, 'demo')
  assert.equal(timers.size, 0)
})

test('location state is immutable and unsubscribing stops notifications', () => {
  const { controller } = setup()
  let calls = 0
  const unsubscribe = controller.subscribe(() => calls++)
  controller.open(site, 'live')
  const state = controller.getSnapshot()
  assert(Object.isFrozen(state) && Object.isFrozen(state.location) && Object.isFrozen(state.site))
  assert.throws(() => { state.location.lat = 90 })
  unsubscribe(); controller.close()
  assert.equal(calls, 1)
})

test('existing mocked live transport stays canonical: no new metadata sent, no-note/photo rules preserved', async () => {
  const service = createMockService(), bodies = []
  const client = new HttpClient('http://localhost:8000', async () => ({ Authorization: 'Bearer mock-crew' }),
    async (url, options) => { bodies.push(options.body); return service.request(url, options, 'crew') })
  const { controller, requests } = setup()
  controller.open(site, 'live') // Intentionally never resolve the permission prompt.
  const location = controller.getSnapshot().location
  // Current legacy site-coordinate submission only; device metadata integration is BLOCKED by T053A.
  const input = { site_id: site.id, category: 'wildlife', hazard_present: true, lat: location.lat, lon: location.lon }
  await assert.rejects(() => client.submit(input, null), (e) => e.status === 422)
  const report = await client.submit(input, new File(['synthetic'], 'fixture.png', { type: 'image/png' }))
  assert.equal(report.note, null)
  assert.equal(requests.length, 1)
  assert.equal(controller.getSnapshot().status, 'locating')
  assert.deepEqual([...bodies[1].keys()].sort(), ['category', 'hazard_present', 'lat', 'lon', 'photo', 'site_id'])
  controller.close()
})

test('existing simulated submission uses fixture site fallback only, never device fix or new metadata', async () => {
  const stored = new Map()
  const client = new DemoClient(() => 'crew', {
    getItem: (k) => stored.get(k) ?? null, setItem: (k, v) => stored.set(k, v), removeItem: (k) => stored.delete(k),
  })
  const { controller, requests } = setup()
  controller.open(site, 'demo')
  const location = controller.getSnapshot().location
  const report = await client.submit({ site_id: site.id, category: 'wildlife', hazard_present: false,
    lat: location.lat, lon: location.lon }, null)
  assert.equal(report.note, null)
  assert.equal(requests.length, 0)
  assert.equal(report.lat, site.lat)
  const saved = JSON.parse(stored.get(DEMO_KEY)).reports.find((row) => row.id === report.id)
  assert.equal(saved.lat, site.lat)
  assert.equal(saved.lon, site.lon)
})
