import { after, test } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
const server = await createServer({
  configFile: false,
  cacheDir: '.shell-check/status-unit-cache',
  logLevel: 'silent',
  server: { middlewareMode: true, hmr: false, watch: null },
  appType: 'custom',
})
after(() => server.close())
const { Status, ScorePanel, Timestamp } = await server.ssrLoadModule(
  '/src/components/data/Status.tsx',
)
const render = (type, props) =>
  renderToStaticMarkup(React.createElement(type, props))
test('all source states have explicit text, independent of color', () => {
  for (const [state, label] of Object.entries({
    observed: 'Observed',
    forecast: 'Forecast',
    crew_reported: 'Crew report',
    simulated: 'Simulated',
    stale: 'Stale',
    unavailable: 'Unavailable',
  }))
    assert.match(render(Status, { state }), new RegExp(label))
})
test('null score and unavailable timestamp never become safe/zero', () => {
  const site = {
    risk_score: null,
    risk_level: null,
    top_factors: [],
    data_completeness: 0,
    model_version: 'unscored',
    updated_at: null,
  }
  assert.match(render(ScorePanel, { site, demo: false }), /Not scored yet/)
  assert.doesNotMatch(
    render(ScorePanel, { site, demo: false }),
    /0.0 \/ 10|low risk/,
  )
  assert.match(render(Timestamp, { value: null }), /Time unavailable/)
})
test('legacy model-onset score component is withheld without mutating fixture', () => {
  const site = {
    risk_score: 7.6,
    top_factors: [{ factor: 'model' }],
    data_completeness: 0.71,
    model_version: 'legacy',
    updated_at: null,
  }
  assert.match(render(ScorePanel, { site, demo: true }), /Score withheld/)
  assert.equal(site.risk_score, 7.6)
})
