import assert from 'node:assert/strict'

/** Uses the existing installed-browser runner; does not add another server/test framework. */
export async function checkReportLocation({ base, navigate, evaluate, until }) {
  await navigate(new URL('/tests/location.html', base).href, 'MOCKED LOCATION HOOK ONLY')
  const state = () => evaluate('window.locationHarness.snapshot()')
  const calls = () => evaluate('window.locationHarness.requests()')
  const configure = async (settings, status) => {
    await evaluate(`window.locationHarness.configure(${JSON.stringify(settings)})`)
    await until(async () => (await state()).status === status, `location status ${status}`)
  }
  const storedBefore = await evaluate('JSON.stringify({...localStorage})')
  assert.equal((await state()).status, 'closed')
  assert.equal((await calls()).length, 0)
  await configure({ open: true }, 'locating')
  assert.equal((await calls()).length, 1, 'StrictMode must not make duplicate requests')
  assert.equal((await state()).location.source, 'site')
  await evaluate('window.locationHarness.grant(0)')
  await until(async () => (await state()).status === 'device', 'device fix')
  assert.equal((await state()).location.accuracyM, 9)
  assert.equal((await calls())[0].enableHighAccuracy, true)
  await evaluate('window.locationHarness.pin(27,-82)')
  await until(async () => (await state()).status === 'pin', 'manual pin')
  await evaluate('window.locationHarness.grant(0,28,-83,2)')
  assert.equal((await state()).location.lat, 27)
  assert.equal((await state()).location.accuracyM, null)
  await evaluate('window.locationHarness.retainPin()')
  const other = { id: 'synthetic-site-b', lat: 29, lon: -84 }
  await configure({ site: other }, 'locating')
  assert.equal((await state()).location.lat, 29)
  assert.equal((await calls()).length, 2)
  assert.equal(await evaluate('window.locationHarness.oldPin()'), false, 'Old-site handler cannot change the new report')
  await evaluate('window.locationHarness.pin(30,-85);window.locationHarness.grant(1)')
  await until(async () => (await state()).status === 'pin', 'late fix cannot replace pin')
  assert.equal((await state()).location.lat, 30)
  await configure({ open: false }, 'closed')
  assert.equal(await evaluate('window.locationHarness.oldPin()'), false, 'Closed form cannot restart location')
  await evaluate('window.locationHarness.grant(1)')
  assert.equal((await state()).location, null)
  assert.equal((await state()).site, null)
  for (const [code, reason] of [[1, 'denied'], [2, 'unavailable'], [3, 'timeout']]) {
    await configure({ open: true }, 'locating')
    const index = (await calls()).length - 1
    await evaluate(`window.locationHarness.fail(${index},${code})`)
    await until(async () => (await state()).reason === reason, reason)
    assert.equal((await state()).location.source, 'site')
    assert.equal((await state()).location.accuracyM, null)
    await configure({ open: false }, 'closed')
  }
  await configure({ open: true, supported: false }, 'site')
  assert.equal((await state()).reason, 'unsupported')
  await configure({ open: false }, 'closed')
  const requestCount = (await calls()).length
  await configure({ open: true, supported: true, mode: 'demo' }, 'site')
  await evaluate('window.locationHarness.retainPin()')
  assert.equal((await state()).reason, 'demo')
  assert.equal((await calls()).length, requestCount, 'Demo must not acquire real GPS for localStorage')
  assert.equal(await evaluate('JSON.stringify({...localStorage})'), storedBefore)
  await configure({ open: false }, 'closed')
  await configure({ open: true }, 'site')
  assert.equal(await evaluate('window.locationHarness.oldPin()'), false, 'Old handler cannot change a reopened same-site report')
  await configure({ open: false }, 'closed')
  await evaluate('window.locationHarness.unmount()')
  assert.equal(await evaluate('window.locationHarness.oldPin()'), false, 'Unmounted form cannot change state')
  assert.equal((await calls()).length, requestCount)
  return { report_location_hook: 'Synthetic StrictMode live/demo, granted/denied/unavailable/timeout/unsupported, pin/late fix, site switch and close pass. No form/backend acceptance or real GPS.' }
}
