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
const { ApplicationContext } = await server.ssrLoadModule('/src/application/context.tsx')
const render = (site) => renderToStaticMarkup(React.createElement(ApplicationContext.Provider,
  { value: { client: { mode: 'demo', capabilities: { hazards: true } },
    persona: 'crew', principalId: 'demo-crew', refresh() {} } },
  React.createElement(SiteHazards, { site })))
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

test('one list keeps forecast, stale and simulated qualifications without claiming supervisor confirmation', () => {
  for (const state of ['observed', 'forecast', 'stale', 'simulated']) {
    const site = bare()
    site.score.factor_contributions = [{ ...heat, data_state: state }]
    const html = render(site)
    assert.match(html, new RegExp(state[0].toUpperCase() + state.slice(1)))
    assert.match(html, new RegExp(`${heat.contribution} score points`))
    assert.doesNotMatch(html, /Supervisor-confirmed/)
    assert.equal((html.match(/aria-label="Confirmed hazards"/g) ?? []).length, 1)
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
  assert.match(render(site), /No confirmed hazards supplied. Unmeasured conditions remain unknown/)
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

test('confirmed notice and its scored report share one row; potential notice is excluded from that row', () => {
  const site = bare()
  site.score.factor_contributions = [reportFactor]
  site.reports = [fixture.reports.find(r => r.id === reportFactor.evidence_id)]
  site.notices = [fixture.notices.find(n => n.id === site.reports[0].notice_id)]
  const rows = siteHazards(site)
  assert.equal(rows.length, 1)
  assert.equal(rows[0].notices[0].id, site.notices[0].id)
  assert.equal(rows[0].factors[0].evidence_id, reportFactor.evidence_id)
  site.notices[0] = { ...site.notices[0], status: 'potential' }
  assert.equal(siteHazards(site).length, 1)
  assert.equal(siteHazards(site)[0].notices.length, 0)
})

test('wrong-site alerts and score snapshots are ignored; missing score uses supplied top factors', () => {
  const site = fresh()
  site.alerts = site.alerts.map(a => ({ ...a, site_id: 'another-site' }))
  site.score.site_id = 'another-site'
  site.notices = []
  assert.deepEqual(siteHazards(site), [])
  site.score = null
  assert(siteHazards(site).some(r => r.id === 'lightning'))
})

test('Flood and Flooding merge score points, confirmation, duration and instruction in the single list', () => {
  const site = fresh()
  const rows = siteHazards(site)
  const flood = rows.filter(r => r.id === 'flood')
  assert.equal(flood.length, 1)
  assert.equal(flood[0].factors.length, 1)
  assert.equal(flood[0].notices[0].id, 'notice-flood-1')
  const html = render(site)
  assert.equal((html.match(/aria-label="Confirmed hazards"/g) ?? []).length, 1)
  assert.equal((html.match(/data-site-hazard="flood"/g) ?? []).length, 1)
  assert.equal((html.match(/data-site-hazard="wildlife"/g) ?? []).length, 1)
  assert.doesNotMatch(html, /Active alerts and score contributors|View more/)
  assert.match(html, /Supervisor-approved instruction/)
  assert(html.includes(site.notices.find(n => n.id === 'notice-wildlife-1').instruction))
  assert.match(html, /Estimated duration/)
  const confirmed = html.split('aria-label="Confirmed hazards"')[1].split('</section>')[0]
  assert(!confirmed.includes('notice-pole-1'), 'pending notice remains outside confirmed list')
})

test('multiple confirmations retain every distinct instruction; Flash Flood is a separate hazard', () => {
  const site = bare()
  const notice = fresh().notices.find(n => n.id === 'notice-flood-1')
  site.notices = [notice, { ...notice, id: 'flood-2', instruction: 'Second instruction.' },
    { ...notice, id: 'flash-1', hazard_label: 'Flash Flood', instruction: 'Flash flood instruction.' }]
  const rows = siteHazards(site)
  assert.equal(rows.length, 2)
  assert.equal(rows.find(r => r.id === 'flood').notices.length, 2)
  assert.equal(rows.find(r => r.id === 'flash_flood').notices.length, 1)
  const html = render(site)
  assert(html.includes(notice.instruction))
  assert.match(html, /Second instruction\.|Flash flood instruction\./)
})

test('unrecognized notices stay distinct; other-category report joins only its exact notice', () => {
  const site = bare()
  const report = { ...fresh().reports.find(r => r.id === reportFactor.evidence_id), category: 'other', confirmed_category: 'other' }
  const notice = { ...fresh().notices.find(n => n.id === report.notice_id), hazard_label: 'Chemical spill' }
  site.reports = [report]
  site.score.factor_contributions = [reportFactor]
  site.notices = [notice, { ...notice, id: 'chemical-2', source_ref: 'another-report' },
    { ...notice, id: 'chemical-3', source_ref: 'third-report' }]
  const rows = siteHazards(site)
  assert.equal(rows.length, 3)
  assert.equal(rows.find(r => r.id === `report:${report.id}`).notices[0].id, notice.id)
})
