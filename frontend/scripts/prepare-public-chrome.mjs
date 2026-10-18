import { readFile, writeFile } from 'node:fs/promises'
import { pages, header, footer, metadata } from './public-chrome.mjs'

const check = process.argv.includes('--check')
for (const page of pages) {
  const path = new URL(`../public${page.path}`, import.meta.url)
  const original = (await readFile(path, 'utf8')).replaceAll('\r\n', '\n')
  let html = original
  html = html.replace(/<!-- public-metadata:start -->[\s\S]*?<!-- public-metadata:end -->|<title>[\s\S]*?<meta name="description"[^>]*>/, `<!-- public-metadata:start -->\n${metadata(page)}\n<!-- public-metadata:end -->`)
  html = html.replace(/<!-- public-header:start -->[\s\S]*?<!-- public-header:end -->|<header class="top"[\s\S]*?<\/header>/, `<!-- public-header:start -->\n${header(page.path)}\n<!-- public-header:end -->`)
  const footerBlock = `<!-- public-footer:start -->\n${footer()}\n<!-- public-footer:end -->`
  if (html.includes('<footer class="public-footer"')) html = html.replace(/<!-- public-footer:start -->[\s\S]*?<!-- public-footer:end -->|<footer class="public-footer"[\s\S]*?<\/footer>/, footerBlock)
  else html = html.replace('</main>', `</main>\n${footerBlock}`)
  if (!html.includes('src="/public-navigation.js"')) html = html.replace('<script src="/public-atmosphere.js"', '<script src="/public-navigation.js" defer></script>\n<script src="/public-atmosphere.js"')
  if (page.path === '/landing.html') html = html.replace('<b data-to="50" data-suffix="+">50+</b><span>Mapped infrastructure locations</span>', '<b data-to="250">250</b><span>Mapped infrastructure locations</span>')
  if (check && html !== original) throw new Error(`Public chrome is stale: ${page.path}. Run node scripts/prepare-public-chrome.mjs`)
  if (!check && html !== original) await writeFile(path, html)
}
console.log(check ? 'Public headers, footers, metadata and location copy are current.' : 'Prepared four public documents from the shared source.')
