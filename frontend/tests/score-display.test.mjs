import { after, test } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

// Server-supplied rules-0.2 score shapes rendered through the real components.
// Controlled inputs only: no backend, Auth0 or Tiger Data request is made.
const server = await createServer({
  configFile: false,
  cacheDir: '.shell-check/score-display-unit-cache',
  logLevel: 'silent',
  server: { middlewareMode: true, hmr: false, watch: null },
  appType: 'custom',
})
after(() => server.close())
const { ScorePanel } = await server.ssrLoadModule(
  '/src/components/data/Status.tsx',
)
const { evidenceOf } = await server.ssrLoadModule(
  '/src/components/data/evidence.ts',
)
const { sortSites } = await server.ssrLoadModule('/src/api/contracts.ts')
const text = (site) =>
  renderToStaticMarkup(React.createElement(ScorePanel, { site, demo: false }))
    .replace(/<[^>]*>/g, ' ')
    .replace(/\s+/g, ' ')

const factor = (overrides) => ({
  factor: 'lightning',
  label: 'Lightning stop-work active',
  contribution: 3,
  value: null,
  unit: null,
  source: 'lightning-replay',
  observed_at: '2026-10-17T18:28:00Z',
  data_state: 'simulated',
  is_prototype: true,
  evidence_id: 'alert-1',
  ...overrides,
})
const site = (overrides) => ({
  id: 'site',
  name: 'Site',
  lat: 25.7,
  lon: -80.4,
  assigned_team: null,
  risk_score: 0,
  risk_level: 'low',
  updated_at: '2026-10-17T18:30:00Z',
  active_alerts: 0,
  top_factors: [],
  data_completeness: 1,
  model_version: 'rules-0.2',
  ...overrides,
})

test('T069 replay: a positive index at 0% coverage shows its number, qualified as incomplete', () => {
  const demo = site({
    risk_score: 7.1,
    risk_level: 'high',
    data_completeness: 0,
    active_alerts: 1,
    top_factors: [
      factor({}),
      factor({ factor: 'flood', label: 'Flood Warning', contribution: 2 }),
    ],
  })
  assert.equal(evidenceOf(demo), 'partial')
  const out = text(demo)
  assert.match(out, /7\.1 \/ 10 · High/)
  assert.match(out, /Evidence incomplete/)
  assert.match(out, /Includes stale or simulated inputs/)
  assert.doesNotMatch(out, /Unknown/)
  assert.match(out, /rules-0\.2/)
})

test('zero with no current evidence reads as unknown, never as a verified low', () => {
  const unknown = site({ data_completeness: 0 })
  assert.equal(evidenceOf(unknown), 'none')
  const out = text(unknown)
  assert.match(out, /Unknown/)
  assert.match(out, /not a low-risk reading/)
  assert.match(out, /Server value 0\.0 \/ 10 · Low/)
})

test('zero from fully observed inputs is shown as the measured index', () => {
  const healthy = site({})
  assert.equal(evidenceOf(healthy), 'full')
  const out = text(healthy)
  assert.match(out, /0\.0 \/ 10 · Low/)
  assert.doesNotMatch(out, /Unknown|Evidence incomplete/)
})

test('partial coverage, feed outage and unscored sites', () => {
  const held = site({
    risk_score: 3,
    risk_level: 'moderate',
    data_completeness: 0.67,
  })
  assert.equal(evidenceOf(held), 'partial')
  assert.match(text(held), /67% of inputs/)
  const unscored = site({
    risk_score: null,
    risk_level: null,
    updated_at: null,
    data_completeness: 0,
    model_version: 'unscored',
  })
  assert.equal(evidenceOf(unscored), null)
  assert.match(text(unscored), /Not scored yet/)
})

test('ranking matches the backend: at equal scores less evidence ranks first', () => {
  const order = sortSites([
    site({ id: 'observed', name: 'A', data_completeness: 1 }),
    site({ id: 'unknown', name: 'B', data_completeness: 0 }),
    site({ id: 'partial', name: 'C', data_completeness: 0.67 }),
    site({
      id: 'unscored',
      name: 'D',
      risk_score: null,
      risk_level: null,
      data_completeness: 0,
    }),
    site({ id: 'higher', name: 'E', risk_score: 2 }),
  ]).map((s) => s.id)
  assert.deepEqual(order, [
    'higher',
    'unknown',
    'partial',
    'observed',
    'unscored',
  ])
})
