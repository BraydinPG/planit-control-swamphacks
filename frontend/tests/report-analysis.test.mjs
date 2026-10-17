// T060 report analysis and T053A location fields, as the live client validates them.
import { after, test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createServer } from 'vite'

const server = await createServer({
  configFile: false,
  cacheDir: '.shell-check/report-analysis-cache',
  logLevel: 'silent',
  server: { middlewareMode: true, hmr: false, watch: null },
  appType: 'custom',
})
after(() => server.close())
const { validateReport } = await server.ssrLoadModule('/src/api/validate.ts')

const reports = JSON.parse(
  readFileSync(new URL('../src/fixtures/reports.json', import.meta.url), 'utf8'),
)
const byVerdict = (status, verdict) =>
  reports.find((r) => r.enrichment?.status === status && r.enrichment.verdict === verdict)
const invalid = (e) => e.status === 502

test('generated fixtures cover supports, inconclusive, and unavailable analyses', () => {
  for (const report of [
    byVerdict('complete', 'supports'),
    byVerdict('complete', 'inconclusive'),
    byVerdict('unavailable', null),
  ]) {
    assert.ok(report)
    assert.equal(validateReport(report).id, report.id)
  }
})

test('a report still being analyzed has a null analysis', () => {
  const pending = { ...byVerdict('complete', 'supports'), enrichment: null }
  assert.equal(validateReport(pending).enrichment, null)
})

test('a complete analysis needs a known verdict and a summary', () => {
  const report = byVerdict('complete', 'supports')
  for (const enrichment of [
    { ...report.enrichment, verdict: 'safe' },
    { ...report.enrichment, verdict: null },
    { ...report.enrichment, summary: null },
    { ...report.enrichment, needs_review: false },
    { ...report.enrichment, supporting: [{ statement: 'x' }] },
  ])
    assert.throws(() => validateReport({ ...report, enrichment }), invalid)
})

test('an unavailable analysis carries no verdict', () => {
  const report = byVerdict('unavailable', null)
  assert.throws(
    () => validateReport({ ...report, enrichment: { ...report.enrichment, verdict: 'supports' } }),
    invalid,
  )
})

test('location source, accuracy, and site distance are validated', () => {
  const report = byVerdict('complete', 'supports')
  assert.equal(validateReport(report).location_source, 'device')
  assert.equal(validateReport({ ...report, location_source: null }).location_source, null)
  for (const bad of [
    { location_source: 'gps' },
    { location_accuracy_m: -1 },
    { site_distance_miles: 'near' },
  ])
    assert.throws(() => validateReport({ ...report, ...bad }), invalid)
})
