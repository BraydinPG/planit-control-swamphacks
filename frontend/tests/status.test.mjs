import { after, test } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'
import React from 'react'
import { readFileSync } from 'node:fs'
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
const { AlertCard } = await server.ssrLoadModule('/src/components/data/AlertCard.tsx')
const { ApplicationContext } = await server.ssrLoadModule('/src/application/context.tsx')
const alert = JSON.parse(readFileSync(new URL('../src/fixtures/alerts.json', import.meta.url), 'utf8'))[0]
function alertMarkup(value, user = 'crew-current', now = Date.parse(alert.clear_after) - 60000) {
  return renderToStaticMarkup(React.createElement(ApplicationContext.Provider, {
    value: { client: { mode: 'live', capabilities: { acknowledge: true }, now: () => now },
      persona: 'crew', principalId: user, refresh() {}, revision: 0 },
  }, React.createElement(AlertCard, { alert: value, detail: true })))
}

test('expired live windows do not display a stuck zero or claim clearance', () => {
  const html = alertMarkup(alert, 'crew-current', Date.parse(alert.clear_after) + 1000)
  assert.doesNotMatch(html, /00:00/)
  assert.match(html, /Alert remains active/)
  assert.match(html, /Awaiting updated alert status/)
  assert.match(alertMarkup(alert), /01:00/)
  const reset = { ...alert, clear_after: new Date(Date.parse(alert.clear_after) + 1800000).toISOString() }
  assert.match(alertMarkup(reset), /31:00/)
})
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
