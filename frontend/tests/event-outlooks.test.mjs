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
  const checked = validateSiteDetail(structuredClone(detail), detail.id)
  assert.deepEqual(checked.event_outlooks, detail.event_outlooks)
  const html = render(detail.event_outlooks)
  for (const card of detail.event_outlooks)
    assert.match(html, new RegExp(`data-outlook-id="${card.event_id}"`))
  const out = text(html)
  assert.match(out, /Research duration estimate/)
  assert.match(out, /National Hurricane Center forecast/)
  assert.match(out, /U.S. Geological Survey forecast/)
  assert.match(out, /Archived agency forecast, not a current prediction/)
  assert.match(out, /Simulated replay/)
  assert.match(out, /Advisory only. Does not change the score/)
})

const malformed = [
  [
    'historical_duration_research',
    'missing duration',
    (c) => delete c.forecast.remaining_duration_hours,
  ],
  [
    'historical_duration_research',
    'missing persistence',
    (c) => delete c.forecast.persistence,
  ],
  [
    'historical_duration_research',
    'invalid probability',
    (c) => (c.forecast.persistence[0].recorded_event_ongoing_probability = 2),
  ],
  [
    'historical_duration_research',
    'nonnumeric horizon',
    (c) => (c.forecast.persistence[0].horizon_hours = '6'),
  ],
  [
    'historical_duration_research',
    'nonnumeric quantile',
    (c) => (c.forecast.remaining_duration_hours.median = '8'),
  ],
  [
    'official_event_forecast',
    'missing forecast points',
    (c) => delete c.forecast.forecast_points,
  ],
  [
    'official_event_forecast',
    'missing initial position',
    (c) => delete c.forecast.initial_position,
  ],
  [
    'official_event_forecast',
    'null track point',
    (c) => (c.forecast.forecast_points[0] = null),
  ],
  [
    'official_event_forecast',
    'nonnumeric coordinate',
    (c) => (c.forecast.forecast_points[0].lon = 'bad'),
  ],
  [
    'official_event_forecast',
    'unsafe source URL',
    (c) => (c.forecast.source.url = 'javascript:alert(1)'),
  ],
  [
    'official_event_forecast',
    'invalid issue time',
    (c) => (c.forecast.source.issued_at_utc = 'bad'),
  ],
  [
    'official_aftershock_forecast',
    'missing windows',
    (c) => delete c.forecast.windows,
  ],
  [
    'official_aftershock_forecast',
    'missing regional context',
    (c) => delete c.forecast.region,
  ],
  [
    'official_aftershock_forecast',
    'missing mainshock',
    (c) => delete c.forecast.mainshock,
  ],
  [
    'official_aftershock_forecast',
    'null magnitude bin',
    (c) => (c.forecast.windows[0].bins[0] = null),
  ],
  [
    'official_aftershock_forecast',
    'invalid probability',
    (c) => (c.forecast.windows[0].bins[0].probability_at_least_one = -1),
  ],
  [
    'official_aftershock_forecast',
    'reversed validity',
    (c) => (c.forecast.windows[0].end_utc = '2000-01-01T00:00:00Z'),
  ],
  [
    'historical_duration_research',
    'foreign verified site association',
    (c) => {
      c.association.site_id = 'another-site'
      c.association.method = 'site_verified'
    },
  ],
  [
    'historical_duration_research',
    'missing confirmation',
    (c) => (c.confirmation = {}),
  ],
  [
    'historical_duration_research',
    'invalid evidence',
    (c) => (c.evidence = [null]),
  ],
]
for (const [kind, label, damage] of malformed) {
  test(`${kind}: ${label} becomes unavailable and keeps sibling cards`, () => {
    const broken = structuredClone(detail)
    const index = broken.event_outlooks.findIndex(
      (c) => c.forecast.kind === kind,
    )
    damage(broken.event_outlooks[index])
    const checked = validateSiteDetail(broken, broken.id)
    assert.equal(checked.event_outlooks.length, 6)
    assert.equal(checked.event_outlooks[index].forecast.kind, 'unavailable')
    for (let i = 0; i < 6; i++)
      if (i !== index)
        assert.deepEqual(checked.event_outlooks[i], detail.event_outlooks[i])
    assert.match(text(render(checked.event_outlooks)), /Prediction unavailable/)
  })
}

test('duration, storm and aftershock cards show their own uncertainty and times', () => {
  const byType = Object.fromEntries(
    detail.event_outlooks.map((c) => [c.event_type, c]),
  )
  const flood = text(render([byType.Flood]))
  assert.match(flood, /Lower range estimate: 1 hour\. Upper estimate unknown/)
  assert.match(flood, /Still ongoing in 6 hours 54%/)
  assert.match(flood, /not a time to resume work/)
  const storm = text(render([byType['Hurricane (Typhoon)']]))
  assert.match(storm, /HELENE/)
  assert.match(storm, /local wind and event end time are unknown/)
  assert.match(storm, /Archive capture/)
  const quake = text(render([byType.Earthquake]))
  assert.match(quake, /Magnitude 7\.1 mainshock/)
  assert.match(quake, /not this worksite/)
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
  assert.match(text(render([])), /Conditions remain unknown/)
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

test('crew tiles show four outlooks, a View more toggle and one shared evidence disclosure', () => {
  const html = renderToStaticMarkup(
    React.createElement(EventOutlooks, { cards: detail.event_outlooks, tiles: true }),
  )
  const shown = detail.event_outlooks.slice(0, 4)
  for (const card of shown)
    assert.match(html, new RegExp(`data-outlook-id="${card.event_id}"`))
  assert.equal((html.match(/data-outlook-id=/g) ?? []).length, 4)
  const out = text(html)
  assert.ok(out.includes(`View more (${detail.event_outlooks.length - 4})`))
  assert.match(out, /How each outlook was estimated/)
  assert.doesNotMatch(out, /How was this estimated\?/)
  assert.match(out, /Advisory only. Does not change the score/)
})
