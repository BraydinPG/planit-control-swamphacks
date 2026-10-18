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
const { SpeciesPanel, WildlifePane } = await server.ssrLoadModule(
  '/src/components/data/SpeciesPanel.tsx',
)
const { arrangeWildlife, relevanceOf } = await server.ssrLoadModule(
  '/src/components/data/wildlife.ts',
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
  assert.match(text, /Known regional range\/habitat, not a sighting/)
  assert.doesNotMatch(text, /Crew wildlife reports at this site/)
  assert.match(text, /Confirmed by supervisor review/)
  assert.doesNotMatch(text, /What this does not tell you/)
  assert.doesNotMatch(text, /USFWS field office:/)
})

test('protection, habitat and encounter render independently; unknown never reads as harmless', () => {
  const byName = (name) => fixture.species.find((s) => s.common_name === name)
  const pane = (species) =>
    html(
      React.createElement(WildlifePane, {
        row: { species, habitat: [], ...relevanceOf(species, []) },
        habitatState: 'observed',
      }),
    )
  const indigo = pane(byName('Eastern indigo snake'))
  assert.match(indigo, /Protection status.*Habitat.*Encounter guidance/s)
  assert.match(indigo, /Threatened/)
  assert.match(indigo, /does not describe a worker hazard/)
  assert.match(indigo, /pending safety-lead review/)

  const manatee = pane(byName('West Indian Manatee'))
  assert.match(manatee, /does not mean the species is harmless/)

  const statusless = structuredClone(byName('American alligator'))
  statusless.protection.status = null
  const gator = pane(statusless)
  assert.match(gator, /Protection status unknown/)
  assert.match(gator, /Keep your distance/)
})

test('wildlife is one list ranked by relevance to the job site', () => {
  const { animals, plants, otherHabitat } = arrangeWildlife(fixture)
  const names = animals.map((r) => r.species.common_name)
  assert.ok(animals.every((r) => !/plant/i.test(r.species.group ?? '')))
  assert.ok(plants.length > 0)
  const order = { crew_hazard: 0, work_impact: 1, background: 2 }
  const ranks = animals.map((r) => order[r.relevance])
  assert.deepEqual(
    ranks,
    [...ranks].sort((a, b) => a - b),
  )
  for (const name of [
    'American alligator',
    'American crocodile',
    'Florida panther',
    'Florida bonneted bat',
  ])
    assert.equal(animals[names.indexOf(name)].relevance, 'crew_hazard', name)
  const manatee = animals[names.indexOf('West Indian Manatee')]
  assert.equal(manatee.relevance, 'work_impact')
  assert.equal(manatee.habitat[0].status, 'Proposed')
  assert.equal(
    animals[names.indexOf('Eastern indigo snake')].relevance,
    'work_impact',
  )
  assert.equal(
    animals[names.indexOf('Everglade snail kite')].relevance,
    'background',
  )
  // The manatee's boundary lives in its pane, not a separate habitat list.
  assert.equal(otherHabitat.length, 0)
})

test('only direct crew hazards are highlighted red, with a text label', () => {
  const text = panel(fixture)
  assert.match(text, /Wildlife \(\d+\)/)
  assert.doesNotMatch(
    text,
    /Species with encounter guidance|Other listed animals/,
  )
  const panes = [
    ...text.matchAll(
      /<article[^>]*data-relevance="(\w+)"[^>]*class="([^"]*)"/g,
    ),
  ]
  assert.ok(panes.length > 0)
  for (const [, relevance, cls] of panes)
    assert.equal(
      cls.includes('border-stop'),
      relevance === 'crew_hazard',
      relevance,
    )
  assert.match(text, /Direct crew hazard/)
  assert.ok(
    text.indexOf('American alligator') < text.indexOf('West Indian Manatee'),
  )
  assert.ok(
    text.indexOf('West Indian Manatee') < text.indexOf('Everglade snail kite'),
  )
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

test('demo shows recorded Gemini wording, labeled and still sourced', () => {
  assert.equal(fixture.generated_by, 'gemini')
  assert.ok(fixture.species.every((s) => s.summary_by === 'gemini'))
  const text = panel(fixture)
  assert.match(text, /recorded Gemini response, checked line by line/)
  assert.match(text, /Gemini wording/)
  assert.ok(text.includes('Similarity of Appearance (Threatened)'))
})

test('critical habitat lists status, citation and date', () => {
  const text = panel(fixture)
  assert.match(text, /Proposed critical habitat within about 3 km/)
  assert.match(text, /Federal Register 89FR78134 78198/)
  assert.match(text, /2024-09-24/)
})
