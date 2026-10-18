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
const { alertTitle, alertTone, stopWorkTitle, tierLabel, topTier, visibleAlertGroups } =
  await server.ssrLoadModule('/src/presentation/alerts.ts')

// Tiers as the server sets them (backend DANGER_TIERS, a prototype ranking).
const tiers = {
  tornado: 1,
  hurricane: 1,
  flash_flood: 1,
  earthquake: 2,
  lightning_stop_work: 2,
  severe_thunderstorm: 2,
  tropical_storm: 3,
  flood: 3,
  heat: 4,
}
const alert = (rule, extra = {}) => ({
  id: `${rule}-${extra.site_id ?? 'a'}-${extra.state ?? 'active'}`,
  site_id: 'a',
  state: 'active',
  rule,
  danger_tier: tiers[rule],
  ...extra,
})

test('stop-work alerts name their event; heat stays an advisory', () => {
  assert.equal(alertTitle(alert('lightning_stop_work')), 'Stop work alert - Lightning')
  assert.equal(alertTitle(alert('flash_flood')), 'Stop work alert - Flash Flood')
  assert.equal(alertTitle(alert('earthquake')), 'Stop work alert - Earthquake')
  assert.equal(alertTitle(alert('heat')), 'Heat advisory')
  assert.equal(tierLabel(alert('tornado')), 'Tier 1 · Extreme danger')
  assert.equal(tierLabel(alert('heat')), 'Advisory')
})

test('same-tier alerts merge into one title naming every event', () => {
  const group = [alert('severe_thunderstorm'), alert('lightning_stop_work')]
  assert.equal(stopWorkTitle(group), 'Stop work alert - Lightning + Severe Thunderstorm')
  assert.deepEqual(
    topTier([...group, alert('flood')]).map((a) => a.rule),
    ['severe_thunderstorm', 'lightning_stop_work'],
  )
})

test('a higher tier hides every lower active tier', () => {
  const all = [alert('flood'), alert('lightning_stop_work'), alert('tornado'), alert('heat')]
  assert.deepEqual(topTier(all).map((a) => a.rule), ['tornado'])
  // When the tornado clears, lightning (tier 2) shows; nothing was lost.
  const cleared = all.map((a) => (a.rule === 'tornado' ? { ...a, state: 'cleared' } : a))
  assert.deepEqual(topTier(cleared).map((a) => a.rule), ['lightning_stop_work'])
})

test('heat shows only when no stop-work tier is active', () => {
  assert.deepEqual(topTier([alert('heat'), alert('flood')]).map((a) => a.rule), ['flood'])
  assert.deepEqual(topTier([alert('heat')]).map((a) => a.rule), ['heat'])
  assert.deepEqual(topTier([alert('heat', { state: 'cleared' })]), [])
})

test('visible groups: one merged top tier per site, cleared alerts kept as history', () => {
  const groups = visibleAlertGroups([
    alert('lightning_stop_work'),
    alert('flood'),
    alert('severe_thunderstorm'),
    alert('flood', { state: 'cleared' }),
    alert('tropical_storm', { site_id: 'b' }),
  ])
  assert.deepEqual(
    groups.map((g) => g.map((a) => `${a.site_id}:${a.rule}:${a.state}`)),
    [
      ['a:lightning_stop_work:active', 'a:severe_thunderstorm:active'],
      ['a:flood:cleared'],
      ['b:tropical_storm:active'],
    ],
  )
})

test('heat is the only orange alert', () => {
  assert.equal(alertTone({ rule: 'heat' }), 'heat')
  for (const rule of ['lightning_stop_work', 'flood', 'hurricane', 'earthquake', 'tornado'])
    assert.equal(alertTone({ rule }), 'stop')
})
