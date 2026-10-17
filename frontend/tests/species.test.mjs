import { after, test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createServer } from 'vite'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
const server = await createServer({
  configFile: false,
  cacheDir: '.shell-check/species-unit-cache',
  logLevel: 'silent',
  server: { middlewareMode: true, hmr: false, watch: null },
})
after(() => server.close())
const { HttpClient } = await server.ssrLoadModule('/src/api/http-client.ts')
const { DemoClient } = await server.ssrLoadModule('/src/demo/client.ts')
const { SpeciesPanel, SpeciesCard } = await server.ssrLoadModule(
  '/src/components/data/SpeciesPanel.tsx',
)
const read = async (name) =>
  JSON.parse(
    await readFile(new URL(`../src/fixtures/${name}`, import.meta.url)),
  )
const fixture = await read('species-context.json')
const detail = await read('site-detail.json')
const SITE = fixture.site_id
const client = (fetcher) =>
  new HttpClient(
    'http://localhost:8000',
    async () => ({ Authorization: 'Bearer test-only' }),
    fetcher,
  )
const html = (element) => renderToStaticMarkup(element)
const panel = (context) =>
  html(React.createElement(SpeciesPanel, { context, site: detail }))
const copy = () => structuredClone(fixture)

test('species context is a GET of the exact site path and validates', async () => {
  const requests = []
  const api = client(async (url, options) => {
    requests.push([url.pathname, options.method ?? 'GET'])
    return Response.json(fixture)
  })
  assert.deepEqual(await api.species(SITE), fixture)
  assert.deepEqual(requests, [[`/api/sites/${SITE}/species`, 'GET']])
})

test('only no_team is an empty state; every other failure surfaces', async () => {
  const noTeam = Response.json(
    { detail: { reason: 'no_team', message: 'No team' } },
    { status: 404 },
  )
  assert.equal(await client(async () => noTeam).species(SITE), null)
  for (const status of [401, 403, 404, 429, 503]) {
    await assert.rejects(
      () => client(async () => new Response('', { status })).species(SITE),
      (e) => e.status === status,
    )
  }
})

test('responses that blur sightings, sites or states are rejected', async () => {
  const claimsReport = copy()
  claimsReport.species[0].match_basis = 'confirmed_report'
  const otherSite = { ...copy(), site_id: 'site-other' }
  const badState = { ...copy(), data_state: 'safe' }
  const noCaveat = { ...copy(), caveat: null }
  for (const body of [claimsReport, otherSite, badState, noCaveat]) {
    await assert.rejects(
      () => client(async () => Response.json(body)).species(SITE),
      (e) => e.status === 502,
    )
  }
})

test('demo client serves the labeled recorded snapshot for the team site only', async () => {
  const api = new DemoClient(() => 'supervisor', null)
  const context = await api.species(SITE)
  assert.equal(context.simulated, true)
  assert.equal(context.data_state, 'simulated')
  assert.match(context.unknowns[0], /recorded IPaC/)
  const sites = await api.sites()
  const unassigned = sites.find((s) => !s.assigned_team)
  assert.equal(await api.species(unassigned.id), null)
  await assert.rejects(
    () => new DemoClient(() => 'crew', null).species(unassigned.id),
    (e) => e.status === 403,
  )
})

test('fixture keeps regional context and crew reports apart', () => {
  assert.ok(fixture.species.length > 0)
  assert.ok(
    fixture.species.every((s) =>
      ['regional_range', 'possible_regional_context'].includes(s.match_basis),
    ),
  )
  assert.ok(
    fixture.wildlife_reports.every((r) =>
      detail.reports.some((report) => report.id === r.report_id),
    ),
  )
  assert.ok(!JSON.stringify(fixture).toLowerCase().includes('moccasin"'))
})

test('panel always shows the caveat, source, date, and match labels', () => {
  const text = panel(fixture)
  assert.match(text, /Regional context, not a sighting/)
  assert.match(text, /USFWS IPaC Location API/)
  assert.match(text, /Recorded demo snapshot/)
  assert.match(text, /Known regional range\/habitat · not a sighting/)
  assert.match(text, /Crew wildlife reports at this site/)
  assert.match(text, /Confirmed by supervisor review/)
  assert.match(text, /What this does not tell you/)
  assert.match(text, /water moccasin/)
})

test('protection and encounter render independently, unknown never reads as harmless', () => {
  const byName = (name) => fixture.species.find((s) => s.common_name === name)
  const indigo = html(
    React.createElement(SpeciesCard, { species: byName('Eastern indigo snake') }),
  )
  assert.match(indigo, /Threatened/)
  assert.match(indigo, /does not describe a worker hazard/)
  assert.match(indigo, /pending safety-lead review/)

  const manatee = byName('West Indian Manatee')
  assert.equal(manatee.encounter, null)
  const text = panel(fixture)
  assert.match(text, /Encounter guidance: not reviewed/)

  const statusless = structuredClone(byName('American alligator'))
  statusless.protection.status = null
  const gator = html(React.createElement(SpeciesCard, { species: statusless }))
  assert.match(gator, /Protection status unknown/)
  assert.match(gator, /Keep your distance/)
})

test('unavailable lookups never read as "no species"', () => {
  const down = {
    ...copy(),
    data_state: 'unavailable',
    species: [],
    critical_habitat: [],
    critical_habitat_state: 'unavailable',
    fetched_at: null,
  }
  const text = panel(down)
  assert.match(text, /unavailable right now\. This does not mean no species/)
  assert.match(text, /boundaries are unavailable\. This does not mean/)
  assert.doesNotMatch(text, /no federally listed species/)
})

test('critical habitat lists status, citation and date', () => {
  const text = panel(fixture)
  assert.match(text, /West Indian Manatee · Proposed critical habitat/)
  assert.match(text, /Federal Register 89FR78134 78198/)
  assert.match(text, /2024-09-24/)
})
