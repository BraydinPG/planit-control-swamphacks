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
const React = (await import('react')).default
const { renderToStaticMarkup } = await import('react-dom/server')
const { ApplicationContext } = await server.ssrLoadModule(
  '/src/application/context.tsx',
)
const { ReportAnalysis } = await server.ssrLoadModule(
  '/src/components/data/ReportAnalysis.tsx',
)
const { ExpectedDuration } = await server.ssrLoadModule(
  '/src/components/data/Duration.tsx',
)
const { durationSentence } = await server.ssrLoadModule(
  '/src/components/data/duration-text.ts',
)
const { ReportForm } = await server.ssrLoadModule(
  '/src/pages/ConnectedPages.tsx',
)
const detail = JSON.parse(
  readFileSync(
    new URL('../src/fixtures/site-detail.json', import.meta.url),
    'utf8',
  ),
)
const text = (html) =>
  html
    .replace(/<[^>]+>/g, '')
    .replaceAll('&#x27;', "'")
    .replaceAll('&quot;', '"')
    .replaceAll('&amp;', '&')
function panel(
  report,
  mode = 'live',
  now = Date.parse(report.created_at) + 1000,
) {
  const value = {
    client: { mode, now: () => now },
    persona: 'supervisor',
    principalId: null,
    revision: 0,
    refresh: () => {},
  }
  return text(
    renderToStaticMarkup(
      React.createElement(
        ApplicationContext.Provider,
        { value },
        React.createElement(ReportAnalysis, { report }),
      ),
    ),
  )
}

const reports = JSON.parse(
  readFileSync(
    new URL('../src/fixtures/reports.json', import.meta.url),
    'utf8',
  ),
)
const byVerdict = (status, verdict) =>
  reports.find(
    (r) => r.enrichment?.status === status && r.enrichment.verdict === verdict,
  )
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
    () =>
      validateReport({
        ...report,
        enrichment: { ...report.enrichment, verdict: 'supports' },
      }),
    invalid,
  )
})

test('location source, accuracy, and site distance are validated', () => {
  const report = byVerdict('complete', 'supports')
  assert.equal(validateReport(report).location_source, 'device')
  assert.equal(
    validateReport({ ...report, location_source: null }).location_source,
    null,
  )
  for (const bad of [
    { location_source: 'gps' },
    { location_accuracy_m: -1 },
    { site_distance_miles: 'near' },
  ])
    assert.throws(() => validateReport({ ...report, ...bad }), invalid)
})

// ---- T036A side panel ----

test('a supporting analysis shows its verdict, reasons with evidence labels, and suggestions', () => {
  const html = panel(byVerdict('complete', 'supports'))
  assert(html.includes('Supports the report'))
  assert(html.includes('Backs up the report'))
  assert(html.includes("Based on: Crew member's photo"))
  assert(html.includes('Also visible in the photo'))
  assert(html.includes('Suggested category: Broken pole or downed line'))
  assert(html.includes('Supervisor review required'))
})

test('contradicts, inconclusive, analyzing, and unavailable render distinctly', () => {
  const base = byVerdict('complete', 'supports')
  const contradicts = panel({
    ...base,
    enrichment: {
      ...base.enrichment,
      verdict: 'contradicts',
      supporting: [],
      contradicting: [
        { statement: 'The ground is dry.', evidence_ids: ['photo'] },
      ],
    },
  })
  assert(contradicts.includes('Contradicts the report'))
  assert(contradicts.includes('Points against the report'))
  assert(panel(byVerdict('complete', 'inconclusive')).includes('Inconclusive'))
  const unavailable = panel(byVerdict('unavailable', null))
  assert(unavailable.includes('Photo analysis unavailable'))
  assert(unavailable.includes('Gemini did not answer in time'))
  const fresh = { ...base, enrichment: null }
  assert(panel(fresh).includes('Analyzing the photo and site data'))
  const old = panel(fresh, 'live', Date.parse(base.created_at) + 10 * 60 * 1000)
  assert(old.includes('No analysis recorded'))
  assert(panel(fresh, 'demo').includes('No new photo analysis'))
})

// ---- T036B expected duration ----

const outlook = (patch = {}) => ({ ...detail.event_outlook, ...patch })

test('the duration reads as one plain sentence and never as zero', () => {
  assert.equal(
    durationSentence(
      outlook({
        remaining_hours_p10: 2,
        remaining_hours_median: 6.2,
        remaining_hours_p90: 14,
      }),
    ),
    'This flood is likely to continue for about 6 more hours (likely range 2 hours to 14 hours).',
  )
  const short = durationSentence(
    outlook({
      remaining_hours_p10: 0.2,
      remaining_hours_median: 0.4,
      remaining_hours_p90: 3,
    }),
  )
  assert(
    short.includes('less than an hour more') &&
      short.includes('under 1 hour to 3 hours'),
  )
  assert(!short.includes('0 hours'))
  assert.equal(
    durationSentence(outlook({ remaining_hours_median: null })),
    null,
  )
  assert.equal(durationSentence(outlook({ status: 'unavailable' })), null)
  assert.equal(durationSentence(null), null)
})

test('the duration card labels replays and disappears without an estimate', () => {
  const card = (o) =>
    text(
      renderToStaticMarkup(
        React.createElement(ExpectedDuration, { outlook: o }),
      ),
    )
  const replay = card(outlook())
  assert(
    replay.includes(
      'Simulated replay: This flood is likely to continue for about 22 more hours',
    ),
  )
  assert(replay.includes('Not an all-clear'))
  assert(replay.includes('How this is estimated'))
  // No estimate: no box at all.
  assert.equal(
    card(outlook({ status: 'unavailable', limitations: ['model unavailable'] })),
    '',
  )
})

// ---- T034A report location in the form ----

const site = { id: 'site-a', lat: 25.76, lon: -80.49, name: 'Alpha' }
function form(mode) {
  const value = {
    client: { mode, capabilities: { reports: true } },
    persona: 'crew',
    principalId: null,
    revision: 0,
    refresh: () => {},
  }
  return renderToStaticMarkup(
    React.createElement(
      ApplicationContext.Provider,
      { value },
      React.createElement(ReportForm, { site }),
    ),
  )
}

test('live reports start from the site while asking for the device location', () => {
  const html = form('live')
  assert(text(html).includes('Finding your location…'))
  assert(
    text(html).includes('The site’s location is used if this takes too long.'),
  )
  // Clean UI: no coordinates unless the crew member enters a different spot.
  assert(!text(html).includes('Latitude') && !html.includes('value="25.76"'))
  assert(text(html).includes('Enter a different spot'))
  assert(text(html).includes('only with your permission'))
})

test('demo reports never request device location and say they are approximate', () => {
  const html = text(form('demo'))
  assert(html.includes('Using the site’s location (approximate)'))
  assert(html.includes('Simulated report: device location is not requested.'))
  assert(!html.includes('Finding your location'))
  assert(!html.includes('Latitude'))
})

test('present/absent is a pair of large choices, not a dropdown', () => {
  const html = form('live')
  assert(text(html).includes('2 · Is the hazard present? (required)'))
  assert.equal((html.match(/name="presence"/g) ?? []).length, 2)
  assert(
    text(html).includes('Hazard present') &&
      text(html).includes('Hazard absent'),
  )
  assert(!html.includes('<select required'))
})

test('access mat deterioration is selectable and accepted when reading reports', () => {
  const html = form('live')
  assert(html.includes('value="access_mat_deterioration"'))
  assert(text(html).includes('Access mat deterioration'))
  const report = { ...detail.reports[0], category: 'access_mat_deterioration',
    note: 'Mat 12: crew stage D, broken timber.' }
  assert.equal(validateReport(report).note, report.note)
})
