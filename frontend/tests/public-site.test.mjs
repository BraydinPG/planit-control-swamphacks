import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import test from 'node:test'
import { pages, header, footer, metadata, repository } from '../scripts/public-chrome.mjs'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8').replaceAll('\r\n', '\n')
test('all four public documents use identical canonical chrome, correct active links and unique SEO metadata', () => {
  assert.equal(pages.length, 4)
  assert.equal(new Set(pages.map(p => p.title)).size, 4)
  assert.equal(new Set(pages.map(p => p.description)).size, 4)
  for (const page of pages) {
    const html = read(`../public${page.path}`)
    assert(html.includes(header(page.path)) && html.includes(footer()) && html.includes(metadata(page)))
    assert.equal((html.match(/<header class="top"/g) ?? []).length, 1)
    assert.equal((html.match(/<footer class="public-footer"/g) ?? []).length, 1)
    assert.equal((html.match(/<link rel="canonical"/g) ?? []).length, 1)
    assert(!html.includes('href="/case-study.html"'))
  }
})
test('public documentation, local resources and anchor destinations exist', () => {
  for (const page of pages) {
    const html = read(`../public${page.path}`)
    for (const [, value] of html.matchAll(/(?:href|src)="([^"]+)"/g)) {
      const target = new URL(value.replaceAll('&amp;', '&'), `https://foresiteoperations.org${page.path}`)
      if (target.origin === 'https://foresiteoperations.org') {
        if (target.pathname === '/') continue // Existing Auth0/demo app, not a static document.
        const file = new URL(`../public${target.pathname}`, import.meta.url)
        assert(existsSync(file), `${page.path}: ${target.pathname}`)
        if (target.hash) assert(readFileSync(file, 'utf8').includes(`id="${target.hash.slice(1)}"`), `${page.path}: ${target.href}`)
      } else if (target.href.startsWith(`${repository}/blob/main/`) || target.href.startsWith(`${repository}/tree/main/`)) {
        const path = target.pathname.split('/main/')[1]
        assert(existsSync(new URL(`../../${path}`, import.meta.url)), `Missing repository resource: ${path}`)
      }
      assert(!target.href.includes('devpost.com'), 'No unverified submission destination')
    }
  }
})
test('public team attribution and data handling have source-backed, limited scope', () => {
  const about = read('../public/about.html'), tasks = read('../../tasks.md')
  for (const [name, ids] of [['Cache', ['T051A', 'T071']], ['Rudra', ['T063', 'T068']], ['Braydin', ['T078', 'T082']], ['Nick', ['T030', 'T054', 'T054A', 'T055']]]) {
    assert(about.includes(`<h3>${name}</h3>`))
    for (const id of ids) assert(tasks.includes(`**${id} | `))
  }
  assert(about.includes('not a legally complete privacy policy') && about.includes('require the team\'s review before publication'))
  assert(about.includes('location is excluded from that analysis payload'))
  assert(read('../../backend/app/gemini/report_analysis.py').includes("The report's location is not"))
  assert(about.includes('AI cannot change a score or clear an alert'))
})
test('mapped-location copy is 250, research sample counts are preserved, and Case Study is retired', () => {
  const home = read('../public/landing.html')
  assert(home.includes('<b data-to="250">250</b><span>Mapped infrastructure locations</span>'))
  assert(!home.includes('50+'))
  assert.equal(JSON.parse(read('../public/research/evidence.json')).reference_sites, 50)
  assert(!existsSync(new URL('../public/case-study.js', import.meta.url)))
  assert(!existsSync(new URL('../public/case-study.css', import.meta.url)))
  const retired = read('../public/case-study.html')
  assert(retired.includes('http-equiv="refresh" content="0;url=/about.html"') && retired.includes('content="noindex"'))
})
