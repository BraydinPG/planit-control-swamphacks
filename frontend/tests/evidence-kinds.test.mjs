import { after, test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createServer } from 'vite'
const server = await createServer({
  configFile: false,
  cacheDir: '.shell-check/evidence-kinds-unit-cache',
  logLevel: 'silent',
  server: { middlewareMode: true, hmr: false, watch: null },
})
after(() => server.close())
const { evidence } = await server.ssrLoadModule('/src/api/validate.ts')

// The runtime validator must accept every canonical EvidenceKind, or a valid site
// detail is rejected as "Invalid hazard notice response".
test('validator accepts every backend EvidenceKind and nothing else', async () => {
  const source = await readFile(
    new URL('../../backend/app/schemas/common.py', import.meta.url),
    'utf8',
  )
  const block = source
    .split('class EvidenceKind(StrEnum):')[1]
    .split('\nclass ')[0]
  const kinds = [...block.matchAll(/= "(\w+)"/g)].map((m) => m[1])
  assert.ok(kinds.includes('event_start'))
  const item = (kind) => ({ id: 'e', kind, label: 'x', observed_at: null })
  for (const kind of kinds) assert.ok(evidence([item(kind)]), kind)
  assert.equal(evidence([item('invented')]), false)
})
