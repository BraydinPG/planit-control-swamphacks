import { after, test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createServer } from 'vite'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

const server = await createServer({
  configFile: false,
  logLevel: 'silent',
  cacheDir: '.shell-check/display-cache',
  server: { middlewareMode: true, hmr: false, watch: null },
  appType: 'custom',
})
after(() => server.close())
const {
  displayLabel,
  factorLabel,
  reportCategories,
  formatTimestamp,
  unitLabel,
  errorSummary,
  outlookUnavailableLabel,
} = await server.ssrLoadModule('/src/presentation/display.ts')
const { ApplicationContext } = await server.ssrLoadModule(
  '/src/application/context.tsx',
)
const { NoticeCard } = await server.ssrLoadModule(
  '/src/components/data/NoticeCard.tsx',
)
const { AlertCard } = await server.ssrLoadModule(
  '/src/components/data/AlertCard.tsx',
)
const { Observations } = await server.ssrLoadModule(
  '/src/components/data/Status.tsx',
)
const { EventOutlooks } = await server.ssrLoadModule(
  '/src/components/data/EventOutlooks.tsx',
)
const { BriefingCard } = await server.ssrLoadModule(
  '/src/components/data/StoredBriefings.tsx',
)
const { ReportAnalysis } = await server.ssrLoadModule(
  '/src/components/data/ReportAnalysis.tsx',
)
const load = async (name) =>
  JSON.parse(
    await readFile(new URL(`../src/fixtures/${name}.json`, import.meta.url)),
  )
const site = await load('site-detail')
const reports = await load('reports')
const briefings = await load('briefings')
const render = (Component, props) =>
  renderToStaticMarkup(
    React.createElement(
      ApplicationContext.Provider,
      {
        value: {
          client: {
            mode: 'demo',
            capabilities: { hazards: true, acknowledge: true },
            now: () => Date.parse(site.updated_at),
          },
          persona: 'crew',
          principalId: 'demo-crew',
          refresh() {},
        },
      },
      React.createElement(Component, props),
    ),
  )
const primary = (html) =>
  html.replace(/<details\b[^>]*>[\s\S]*?<\/details>/g, '')
const plain = (html) => html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ')

test('controlled enums have deliberate labels; all report categories include access mats', () => {
  assert.equal(displayLabel('flash_flood_warning'), 'Flash Flood Warning')
  assert.equal(displayLabel('site_verified'), 'Verified for this site')
  assert.equal(displayLabel('crew_report'), 'Crew report')
  assert.equal(displayLabel('new_status'), 'New status')
  assert.equal(displayLabel(null), 'Unknown')
  assert.equal(factorLabel('heat_index'), 'Heat index')
  assert.equal(
    reportCategories.access_mat_deterioration,
    'Access mat deterioration',
  )
  assert.equal(Object.keys(reportCategories).length, 6)
})
test('dates show local timezone and handle null/invalid; units are labels without conversion', () => {
  assert.equal(formatTimestamp(null), 'Time unavailable')
  assert.equal(formatTimestamp('invalid'), 'Time unavailable')
  assert.match(
    formatTimestamp('2026-10-17T17:57:00Z', 'America/New_York'),
    /Oct 17, 2026, 1:57 PM EDT/,
  )
  assert.match(
    formatTimestamp('2026-01-17T17:57:00Z', 'America/New_York'),
    /12:57 PM EST/,
  )
  assert.equal(unitLabel('degF'), '°F')
  assert.equal(unitLabel('kt'), 'kn')
  assert.equal(unitLabel('mm'), 'mm')
  assert.equal(
    errorSummary('Invalid stored briefing response'),
    'This information could not be verified. Try again.',
  )
  assert.equal(errorSummary('Permission denied'), 'Permission denied')
  assert.equal(errorSummary('Session expired'), 'Session expired')
  assert.equal(
    outlookUnavailableLabel('event_start_missing'),
    'The event start time is unknown.',
  )
  assert.equal(
    outlookUnavailableLabel('official_forecast_stale'),
    'The agency forecast is out of date.',
  )
  assert.equal(
    outlookUnavailableLabel('site_association_unverified'),
    'The event could not be linked to this worksite.',
  )
})
test('outlooks with an estimate keep replay/research/archive labels; unavailable ones are hidden', () => {
  const html = render(EventOutlooks, { cards: site.event_outlooks })
  const main = plain(primary(html))
  const shown = site.event_outlooks.filter((c) => c.status === 'available')
  assert.equal((html.match(/data-outlook-id=/g) ?? []).length, shown.length)
  for (const text of [
    'Flood',
    'Flash Flood',
    'High Wind',
    'Hurricane',
    'Earthquake',
    'Research duration estimate',
    'not a time to resume work',
    'Archived agency forecast, not a current prediction',
    'not this worksite',
  ])
    assert(main.includes(text), text)
  // The unavailable Wildfire outlook draws no box at all.
  assert(!main.includes('Wildfire'))
  assert(!main.includes('Prediction unavailable'))
  assert(!main.includes(site.event_outlooks[0].forecast.model_version))
  assert(html.includes(site.event_outlooks[0].forecast.model_version))
  assert.equal(
    (html.match(/How was this estimated\?/g) ?? []).length,
    shown.length,
  )
})
test('pending notices never imply confirmation or supply an instruction; approved prose stays primary and verbatim', () => {
  const notice =
    site.notices.find((n) => n.status === 'potential') ?? site.notices[0]
  const pending = render(NoticeCard, {
    notice: {
      ...notice,
      status: 'potential',
      instruction: null,
      instruction_sent_at: null,
    },
  })
  assert(
    plain(primary(pending)).includes(
      'No instruction: supervisor confirmation is pending',
    ),
  )
  const instruction =
    'Supervisor text: retain wording, underscores_in_a_note, and punctuation.'
  const approved = render(NoticeCard, {
    notice: {
      ...notice,
      status: 'confirmed',
      instruction,
      instruction_sent_at: site.updated_at,
    },
  })
  assert(primary(approved).includes(instruction))
  assert(primary(approved).includes('Supervisor-approved instruction'))
})
test('active and elapsed timers never promise an automatic all-clear; acknowledgements stay independent', () => {
  const active = site.alerts.find((a) => a.rule === 'lightning_stop_work')
  const html = render(AlertCard, { alerts: [active], detail: true })
  assert(
    plain(primary(html)).includes('Acknowledging does not clear the alert'),
  )
  assert(html.includes('The timer does not clear this alert or authorize work'))
  assert(!html.includes('until all-clear') && !html.includes('All-clear in'))
  const elapsed = render(AlertCard, {
    alerts: [{ ...active, clear_after: '2000-01-01T00:00:00Z' }],
  })
  assert(plain(primary(elapsed)).includes('Alert remains active'))
})
test('a merged same-tier card names every event and waits for a warning in effect', () => {
  const lightning = site.alerts.find((a) => a.rule === 'lightning_stop_work')
  const storm = {
    ...lightning,
    id: 'svr-1',
    rule: 'severe_thunderstorm',
    event_label: 'Severe Thunderstorm Warning',
    clear_after: null,
    is_prototype_rule: true,
    acknowledgements: [],
  }
  const html = plain(render(AlertCard, { alerts: [lightning, storm], detail: true }))
  assert(html.includes('Stop work alert - Lightning + Severe Thunderstorm'))
  assert(html.includes('Tier 2 · Severe danger'))
  assert(html.includes(lightning.event_label) && html.includes('Severe Thunderstorm Warning'))
  // A warning still in effect has no all-clear time, so the group shows no countdown.
  assert(html.includes('Warning still in effect'))
  assert(!/\d\dm \d+s left/.test(html))
})
test('unknown/stale observations remain explicit and preserve original timing under source details', () => {
  const row = {
    ...site.observations[0],
    value: null,
    data_state: 'stale',
    simulated: false,
  }
  const html = render(Observations, { rows: [row] })
  assert(plain(primary(html)).includes('Stale'))
  assert(plain(primary(html)).includes('Unknown'))
  assert(html.includes('Source and timing'))
  assert(html.includes(row.fetched_at))
  assert(!plain(primary(html)).includes(row.source_ref))
})
test('Gemini and briefing prose is retained verbatim while evidence remains accessible', () => {
  const briefing = briefings[0]
  const html = render(BriefingCard, { value: briefing })
  assert(html.includes(briefing.summary.replaceAll('&', '&amp;')))
  for (const action of briefing.recommended_actions)
    assert(html.includes(action.action.replaceAll('&', '&amp;')))
  const report = reports.find((r) => r.enrichment?.status === 'complete')
  const analysis = render(ReportAnalysis, { report })
  assert(analysis.includes(report.enrichment.summary.replaceAll('&', '&amp;')))
  assert(primary(analysis).includes('Supervisor review required'))
  assert(analysis.includes('Analysis evidence and suggestions'))
})
