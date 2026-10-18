import { after, test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createServer } from 'vite'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

const server = await createServer({
  configFile: false, logLevel: 'silent', cacheDir: '.shell-check/site-hazards-cache',
  server: { middlewareMode: true, hmr: false, watch: null }, appType: 'custom',
})
after(() => server.close())
const { siteHazards } = await server.ssrLoadModule('/src/presentation/site-hazards.ts')
const { SiteHazards } = await server.ssrLoadModule('/src/components/data/SiteHazards.tsx')
const fixture = JSON.parse(await readFile(new URL('../src/fixtures/site-detail.json', import.meta.url), 'utf8'))
const fresh = () => structuredClone(fixture)
const bare = () => ({ ...fresh(), alerts: [], notices: [], reports: [],
  score: { ...fresh().score, factor_contributions: [] } })
const heat = fixture.score.factor_contributions.find(f => f.factor === 'heat_index')
const reportFactor = fixture.score.factor_contributions.find(f => f.factor === 'crew_report')

test('lightning appears once with its active alert and stored score factor; lower tiers stay visible', () => {
  const site = fresh()
  const rows = siteHazards(site)
  const lightning = rows.filter(r => r.id === 'lightning')
  assert.equal(lightning.length, 1)
  assert.equal(lightning[0].alerts[0].rule, 'lightning_stop_work')
  assert.equal(lightning[0].factors[0].contribution, 3)
  assert(rows.some(r => r.id === 'heat_index'))
  assert(rows.some(r => r.id === 'flood'))
  assert(rows.some(r => r.id === 'severe_thunderstorm'))
  assert.deepEqual(site, fixture, 'projection cannot mutate score, alerts or notices')
})

test('positive evidence keeps forecast, stale and simulated qualifications without a confirmation claim', () => {
  for (const state of ['observed', 'forecast', 'stale', 'simulated']) {
    const site = bare()
    site.score.factor_contributions = [{ ...heat, data_state: state }]
    const html = renderToStaticMarkup(React.createElement(SiteHazards, { site }))
    assert.match(html, new RegExp(state[0].toUpperCase() + state.slice(1)))
    assert.match(html, new RegExp(`${heat.contribution} score points`))
    assert.doesNotMatch(html, /Supervisor-confirmed|Confirmed hazards/)
  }
})

test('zero, unavailable, invalid and legacy model factors do not become hazards', () => {
  const site = bare()
  site.score.factor_contributions = [
    { ...heat, contribution: 0 }, { ...heat, contribution: -1 },
    { ...heat, contribution: NaN }, { ...heat, contribution: Infinity },
    { ...heat, data_state: 'unavailable' }, { ...heat, factor: 'model' },
  ]
  assert.deepEqual(siteHazards(site), [])
  assert.equal(renderToStaticMarkup(React.createElement(SiteHazards, { site })), '')
})

test('unavailable feeds and elapsed windows cannot remove an active server alert', () => {
  const site = bare()
  const alert = { ...fixture.alerts[0], clear_after: '2000-01-01T00:00:00Z' }
  site.alerts = [alert]
  site.score.factor_contributions = [{ ...heat, data_state: 'unavailable' }]
  assert.equal(siteHazards(site)[0].alerts[0].id, alert.id)
  site.alerts[0].state = 'cleared'
  assert.deepEqual(siteHazards(site), [])
})

test('all supported positive environmental score factors are represented without merging Flood and Flash Flood', () => {
  const site = bare()
  site.score.factor_contributions = ['lightning', 'heat_index', 'flood', 'hurricane', 'earthquake']
    .map(factor => ({ ...heat, factor }))
  site.alerts = [{ ...fixture.alerts[2], rule: 'flash_flood' }]
  assert.deepEqual(new Set(siteHazards(site).map(r => r.id)),
    new Set(['lightning', 'heat_index', 'flood', 'flash_flood', 'hurricane', 'earthquake']))
})

test('confirmed present report without a notice appears; pending, absent, rejected and missing reports do not', () => {
  for (const change of [null, { review_status: 'pending' }, { review_status: 'rejected' },
    { hazard_present: false }, { site_id: 'another-site' }]) {
    const site = bare()
    site.score.factor_contributions = [reportFactor]
    site.reports = [{ ...fixture.reports.find(r => r.id === reportFactor.evidence_id), ...change }]
    const rows = siteHazards(site)
    assert.equal(rows.length, change ? 0 : 1)
    if (!change) {
      assert.equal(rows[0].label, 'Wildlife')
      assert.match(renderToStaticMarkup(React.createElement(SiteHazards, { site })), /Supervisor-confirmed report/)
    }
  }
  const missing = bare()
  missing.score.factor_contributions = [reportFactor]
  assert.deepEqual(siteHazards(missing), [])
})

test('confirmed notice already represents its scored report; potential notice cannot hide it', () => {
  const site = bare()
  site.score.factor_contributions = [reportFactor]
  site.reports = [fixture.reports.find(r => r.id === reportFactor.evidence_id)]
  site.notices = [fixture.notices.find(n => n.id === site.reports[0].notice_id)]
  assert.deepEqual(siteHazards(site), [])
  site.notices[0] = { ...site.notices[0], status: 'potential' }
  assert.equal(siteHazards(site).length, 1)
})

test('wrong-site alerts and score snapshots are ignored; missing score uses supplied top factors', () => {
  const site = fresh()
  site.alerts = site.alerts.map(a => ({ ...a, site_id: 'another-site' }))
  site.score.site_id = 'another-site'
  assert.deepEqual(siteHazards(site), [])
  site.score = null
  assert(siteHazards(site).some(r => r.id === 'lightning'))
})
