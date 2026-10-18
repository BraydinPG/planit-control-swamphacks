import { after, test } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
const server = await createServer({
  configFile: false,
  cacheDir: '.shell-check/masonry-unit-cache',
  logLevel: 'silent',
  server: { middlewareMode: true, hmr: false, watch: null },
})
after(() => server.close())
const { Masonry } = await server.ssrLoadModule(
  '/src/components/data/Masonry.tsx',
)

test('masonry keeps every item, in order, as a labeled list', () => {
  const items = ['a', 'b', 'c', 'd'].map((key) => ({
    key,
    node: React.createElement('p', null, `card-${key}`),
  }))
  const html = renderToStaticMarkup(
    React.createElement(Masonry, { items, label: 'Submitted reports' }),
  )
  assert.match(html, /role="list" aria-label="Submitted reports"/)
  assert.equal((html.match(/role="listitem"/g) ?? []).length, 4)
  const order = [...html.matchAll(/card-(\w)/g)].map((m) => m[1])
  assert.deepEqual(order, ['a', 'b', 'c', 'd'])
})
