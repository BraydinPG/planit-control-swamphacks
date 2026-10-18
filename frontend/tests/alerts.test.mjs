import { after, test } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'

const server = await createServer({
  configFile: false,
  logLevel: 'silent',
  cacheDir: '.shell-check/alerts-cache',
  server: { middlewareMode: true, hmr: false, watch: null },
  appType: 'custom',
})
after(() => server.close())
const { alertTitle, alertTone } = await server.ssrLoadModule(
  '/src/presentation/alerts.ts',
)

test('only lightning is titled as stop work, naming its event', () => {
  assert.equal(
    alertTitle({ rule: 'lightning_stop_work' }),
    'Stop work alert - Lightning',
  )
  assert.equal(alertTitle({ rule: 'heat' }), 'Heat advisory')
  assert.equal(alertTitle({ rule: 'flood' }), 'Flood advisory')
  assert.equal(alertTitle({ rule: 'hurricane' }), 'Hurricane advisory')
  assert.equal(alertTitle({ rule: 'earthquake' }), 'Earthquake advisory')
})

test('heat is the only orange alert', () => {
  assert.equal(alertTone({ rule: 'heat' }), 'heat')
  for (const rule of ['lightning_stop_work', 'flood', 'hurricane', 'earthquake'])
    assert.equal(alertTone({ rule }), 'stop')
})
