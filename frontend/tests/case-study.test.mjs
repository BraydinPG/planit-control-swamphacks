import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import test from 'node:test'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const detail = JSON.parse(read('../src/fixtures/site-detail.json'))
const reports = JSON.parse(read('../src/fixtures/reports.json'))
const notices = JSON.parse(read('../src/fixtures/hazard-notices.json'))
const html = read('../public/case-study.html')
const stage = number => html.split(`id="stage-${number}"`)[1].split('</article>')[0]

test('case study score and factor evidence match the canonical frozen fixture', () => {
  const score = detail.score
  assert.equal(score.model_version, 'rules-0.2')
  assert.equal(score.risk_score, 7.9)
  assert.equal(score.data_completeness, 0)
  assert.equal(Math.round(score.factor_contributions.reduce((sum, factor) => sum + factor.contribution, 0) * 10) / 10, score.risk_score)
  assert.deepEqual(score.factor_contributions.map(f => [f.factor, f.contribution]), [['lightning', 3], ['heat_index', 2.91], ['flood', 1], ['crew_report', 1]])
  for (const factor of score.factor_contributions) assert(stage(2).includes(`<strong>${factor.contribution.toFixed(2)}</strong>`))
  for (const id of ['obs-ltg-2', 'obs-wx-3', 'obs-flood-1']) {
    const observation = detail.observations.find(o => o.id === id)
    assert.equal(observation.simulated, true)
    assert(stage(1).includes(id) && stage(1).includes(`datetime="${observation.observed_at}"`))
    assert(stage(1).includes(String(observation.value)))
  }
  assert(html.includes('Zero verified live coverage.') && stage(2).includes('ML and Gemini contribute no score points'))
  assert.equal(detail.id, 'site-demo-everglades')
  assert.deepEqual([detail.lat, detail.lon], [25.76, -80.49])
  assert(html.includes('25.7600° N / 80.4900° W') && html.includes('fictional, not an EIA reference site'))
})

test('case study preserves report review states and exact human-approved instruction', () => {
  const pole = reports.find(r => r.id === 'report-pole-1')
  const wildlife = reports.find(r => r.id === 'report-wildlife-1')
  const notice = notices.find(n => n.id === 'notice-wildlife-1')
  assert.equal(pole.review_status, 'pending')
  assert.equal(pole.reviewed_at, null)
  assert.equal(pole.location_accuracy_m, 12)
  assert(stage(4).includes(pole.id) && stage(4).includes(`datetime="${pole.created_at}"`))
  assert.equal(wildlife.review_status, 'confirmed')
  assert.equal(notice.status, 'confirmed')
  assert(stage(5).includes(notice.instruction) && stage(5).includes(notice.instruction_sent_at))
  assert(stage(5).includes('not the pending pole report being auto-approved'))
  assert(html.includes('This page submits nothing.') && html.includes('No backend transaction was performed'))
})

test('case study does not promote synthetic duration or a different historical site to an Everglades forecast', () => {
  assert(detail.event_outlook.limitations.some(l => l.includes('synthetic example values')))
  assert.notEqual(detail.event_outlooks[0].association.site_id, detail.id)
  assert(stage(6).includes('explicitly synthetic') && stage(6).includes('does not reuse them as site predictions'))
  assert(!stage(6).includes('22 hours') && !stage(6).includes('8 hours') && !stage(6).includes('9 hours'))
  assert(html.includes('Simulated scenario — not live worksite conditions.'))
  assert(html.includes('The guest\'s supervisor perspective is still read-only'))
  assert(html.includes('not a navigation map') || html.includes('navigation map'))
})

test('case study captures are tied to fixture hashes and public navigation stays consistent', () => {
  const provenance = JSON.parse(read('../public/case-study/capture-provenance.json'))
  assert.equal(provenance.fixture_hash_encoding, 'UTF-8, CRLF normalized to LF')
  for (const [path, hash] of Object.entries(provenance.fixture_sha256)) {
    assert.equal(createHash('sha256').update(read(`../${path}`).replaceAll('\r\n', '\n')).digest('hex'), hash, `${path}: recapture and review the fixed narrative after fixture changes`)
  }
  for (const [path, hash] of Object.entries(provenance.image_sha256)) assert.equal(createHash('sha256').update(readFileSync(new URL(`../public/case-study/${path}`, import.meta.url))).digest('hex'), hash)
  for (const file of ['landing.html', 'platform.html', 'data.html', 'case-study.html']) {
    const document = read(`../public/${file}`)
    const nav = document.split('<nav class="public-nav"')[1].split('</nav>')[0]
    assert(nav.includes('/platform.html') && nav.includes('/data.html') && nav.includes('/case-study.html'))
    assert(!nav.includes('>Home<'))
    assert(document.includes('class="brand" href="/landing.html"'))
  }
})
