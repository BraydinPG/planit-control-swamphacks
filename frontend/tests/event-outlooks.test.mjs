import { after, test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createServer } from 'vite'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

// T050A cards rendered from the generated fixture (Cache's PR #39 example output).
// Controlled inputs only: no backend, Auth0 or Tiger Data request is made.
const server = await createServer({
  configFile: false,
  cacheDir: '.shell-check/event-outlooks-unit-cache',
  logLevel: 'silent',
  server: { middlewareMode: true, hmr: false, watch: null },
  appType: 'custom',
})
after(() => server.close())
const { EventOutlooks } = await server.ssrLoadModule(
  '/src/components/data/EventOutlooks.tsx',
)
const { validateSiteDetail } = await server.ssrLoadModule(
  '/src/api/live-read-validation.ts',
)
const detail = JSON.parse(
  await readFile(new URL('../src/fixtures/site-detail.json', import.meta.url)),
)
const render = (cards) =>
  renderToStaticMarkup(React.createElement(EventOutlooks, { cards }))
const text = (html) => html.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ')

test('each event renders as its own card, keyed by event id', () => {
  const html = render(detail.event_outlooks)
  for (const card of detail.event_outlooks)
    assert.match(html, new RegExp(`data-outlook-id="${card.event_id}"`))
  const out = text(html)
  assert.match(out, /Research duration estimate/)
  assert.match(out, /Issued NHC forecast/)
  assert.match(out, /Issued USGS aftershock forecast/)
  assert.match(out, /Historical example, not a current prediction/)
  assert.match(out, /Simulated replay/)
  assert.match(out, /Advisory only. Does not change the score/)
})

test('duration, storm and aftershock cards show their own uncertainty and times', () => {
  const byType = Object.fromEntries(
    detail.event_outlooks.map((c) => [c.event_type, c]),
  )
  const flood = text(render([byType.Flood]))
  assert.match(flood, /Likely range 1 h to not identified/)
  assert.match(flood, /Still ongoing in 6 h 54%/)
  assert.match(flood, /Not a time when work can resume/)
  const storm = text(render([byType['Hurricane (Typhoon)']]))
  assert.match(storm, /HELENE/)
  assert.match(storm, /not wind at this site/)
  assert.match(storm, /archive capture/)
  const quake = text(render([byType.Earthquake]))
  assert.match(quake, /Mainshock M7\.1/)
  assert.match(quake, /not at this site/)
})

test('unavailable is a visible reason, never a probability', () => {
  const wildfire = detail.event_outlooks.find(
    (c) => c.forecast.kind === 'unavailable',
  )
  const out = text(render([wildfire]))
  assert.match(out, /Prediction unavailable/)
  assert.match(out, new RegExp(wildfire.forecast.reason.slice(0, 30)))
  assert.doesNotMatch(out, /\d+%/)
})

test('no confirmed event says so without implying safety', () => {
  assert.match(text(render([])), /This does not mean the site is safe/)
})

test('a malformed card does not break the site page; a missing field means none', () => {
  const broken = structuredClone(detail)
  broken.event_outlooks[0] = { event_id: 'x', status: 'available' }
  const checked = validateSiteDetail(broken, broken.id)
  assert.equal(checked.event_outlooks[0].status, 'unavailable')
  assert.match(checked.event_outlooks[0].forecast.reason, /could not verify/)
  assert.equal(
    checked.event_outlooks.length,
    detail.event_outlooks.length,
    'other cards survive',
  )
  const legacy = structuredClone(detail)
  delete legacy.event_outlooks
  assert.deepEqual(validateSiteDetail(legacy, legacy.id).event_outlooks, [])
})
