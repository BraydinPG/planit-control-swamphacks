/** Local integration diagnostics. Credentials only through private stdin, never argv/logs/files. */
import { execFile } from 'node:child_process'
import { readFile } from 'node:fs/promises'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { loadEnv, createServer } from 'vite'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import {
  origin,
  routeInventory,
  runAcceptance,
} from './integration/acceptance.mjs'

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const args = process.argv.slice(2)
const value = (key, fallback) =>
  args.includes(key) ? args[args.indexOf(key) + 1] : fallback
const flags = new Set([
  '--python',
  '--api-origin',
  '--frontend-origin',
  '--mode',
  '--check-database',
  '--tokens-stdin',
  '--acknowledge',
])
if (args.some((a) => a.startsWith('--') && !flags.has(a))) {
  console.error(
    'Unknown option. Tokens must never be passed as command-line arguments.',
  )
  process.exit(1)
}

export async function boundedRequest(base, path, options = {}) {
  try {
    const response = await fetch(new URL(path, base), {
      ...options,
      redirect: 'error',
      credentials: 'omit',
      signal: AbortSignal.timeout(6000),
    })
    const chunks = [],
      reader = response.body?.getReader()
    let size = 0
    if (reader)
      while (true) {
        const { done, value: chunk } = await reader.read()
        if (done) break
        size += chunk.length
        if (size > 8 * 1024 * 1024) {
          await reader.cancel()
          return { status: 0, data: null }
        }
        chunks.push(chunk)
      }
    let data = null
    try {
      data = JSON.parse(Buffer.concat(chunks).toString('utf8'))
    } catch {
      /* HTML/error bodies are never logged. */
    }
    return { status: response.status, data }
  } catch {
    return { status: 0, data: null }
  }
}

async function privateInput() {
  if (!args.includes('--tokens-stdin')) return {}
  let size = 0,
    text = ''
  for await (const chunk of process.stdin) {
    size += chunk.length
    if (size > 65536) throw new Error('Private input exceeds limit')
    text += chunk.toString('utf8')
  }
  try {
    const result = JSON.parse(text)
    if (!result || typeof result !== 'object' || Array.isArray(result))
      throw new Error()
    return result
  } catch {
    throw new Error(
      'Private stdin must contain an object; input was not logged',
    )
  }
}

async function backendProbe(python, input, flags = []) {
  const child = execFile(
    python,
    [resolve(frontend, 'scripts/probe-integration.py'), ...flags],
    {
      cwd: resolve(frontend, '../backend'),
      timeout: 25000,
      maxBuffer: 512 * 1024,
      windowsHide: true,
    },
    () => {},
  )
  // execFile arguments contain no credentials. The pipe never becomes a saved report.
  child.stdin.on('error', () => {})
  child.stdin.end(JSON.stringify(input))
  return await new Promise((resolveResult) => {
    let output = ''
    child.stdout.on('data', (chunk) => {
      output += chunk
    })
    child.on('error', () =>
      resolveResult({
        status: 'blocked',
        reason:
          'Backend Python unavailable; use --python with the installed backend environment',
      }),
    )
    child.on('close', (code) => {
      try {
        resolveResult(
          code === 0
            ? JSON.parse(output)
            : { status: 'blocked', reason: 'Backend inspection unavailable' },
        )
      } catch {
        resolveResult({
          status: 'blocked',
          reason:
            'Backend dependencies/inspection unavailable; error output suppressed',
        })
      }
    })
  })
}

async function main() {
  const apiOrigin = origin(value('--api-origin', 'http://127.0.0.1:8000'))
  const frontendOrigin = origin(
    value('--frontend-origin', 'http://localhost:5173'),
  )
  const mode = value('--mode', 'development')
  if (!['development', 'production'].includes(mode))
    throw new Error('Mode must be development or production')
  const env = loadEnv(mode, frontend, 'VITE_')
  // Public SPA values stay in memory; summaries record state/matches only.
  const keys = [
    'VITE_AUTH0_DOMAIN',
    'VITE_AUTH0_CLIENT_ID',
    'VITE_AUTH0_AUDIENCE',
  ]
  const state = (value) =>
    !value?.trim()
      ? 'missing'
      : /[<>]|your-tenant|your-client/i.test(value)
        ? 'placeholder'
        : 'set'
  const configState = Object.fromEntries(
    keys.map((key) => [key, state(env[key])]),
  )
  const fixture =
    env.VITE_USE_FIXTURES === undefined || env.VITE_USE_FIXTURES === 'true'
      ? 'demo'
      : env.VITE_USE_FIXTURES === 'false'
        ? 'live'
        : 'invalid'
  const pythonOption = value(
    '--python',
    process.platform === 'win32' ? 'python' : 'python3',
  )
  const python = /[\\/]/.test(pythonOption)
    ? resolve(process.cwd(), pythonOption)
    : pythonOption
  const backend = await backendProbe(
    python,
    Object.fromEntries(keys.map((k) => [k, env[k]?.trim()])),
    args.includes('--check-database') ? ['--check-database'] : [],
  )
  const frontendStatus = {
    mode: fixture,
    configuration: configState,
    unsafe_public_credential_keys: Object.keys(env).filter((k) =>
      /TOKEN|SECRET|PASSWORD|API_KEY|PRIVATE_KEY/i.test(k),
    ),
    development_role_configured: Boolean(env.VITE_DEV_AUTH_ROLE?.trim()),
    api_base: env.VITE_API_BASE_URL
      ? 'explicit_configured'
      : 'same_origin_proxy',
    note: 'Environment inspection does not prove what a previously started server/build loaded; restart after configuration changes',
  }
  const health = await boundedRequest(apiOrigin, '/health')
  const schema = await boundedRequest(apiOrigin, '/openapi.json')
  const inventory = routeInventory(schema.data?.paths)
  const sourceInventory = routeInventory(
    Object.fromEntries(
      Object.entries(backend.routes_in_checkout ?? {}).map(
        ([path, methods]) => [
          path,
          Object.fromEntries(
            methods.map((method) => [method.toLowerCase(), {}]),
          ),
        ],
      ),
    ),
  )
  const proxy = await boundedRequest(frontendOrigin, '/api/sites')
  const network = {
    health: { status: health.status, expected: 200 },
    openapi: {
      status: schema.status,
      available: schema.status === 200 && Boolean(schema.data?.paths),
    },
    vite_proxy_unauthenticated: { status: proxy.status, expected: 401 },
    routes: inventory,
    checkout_routes_missing_from_running: sourceInventory
      .filter(
        (source) =>
          source.available &&
          !inventory.some(
            (r) =>
              r.path === source.path &&
              r.method === source.method &&
              r.available,
          ),
      )
      .map(({ path, method }) => ({ path, method })),
  }
  let discovery = {
    status: 'not_run',
    reason: 'Auth0 SPA domain not configured',
  }
  if (configState.VITE_AUTH0_DOMAIN === 'set') {
    try {
      const bare = env.VITE_AUTH0_DOMAIN.replace(/^https?:\/\//, '').replace(
        /\/$/,
        '',
      )
      const url = new URL(`https://${bare}`)
      if (
        url.username ||
        url.password ||
        url.pathname !== '/' ||
        url.search ||
        url.hash
      )
        throw new Error()
      const response = await boundedRequest(
        url.origin,
        '/.well-known/openid-configuration',
      )
      discovery = {
        status:
          response.status === 200 && response.data?.issuer === `${url.origin}/`
            ? 'passed'
            : 'blocked',
        reason:
          'Public tenant discovery only; SPA settings, role assignments and accounts need owner verification',
      }
    } catch {
      discovery = {
        status: 'blocked',
        reason: 'Invalid/unreachable Auth0 public discovery configuration',
      }
    }
  }
  const input = await privateInput()
  const server = await createServer({
    root: frontend,
    cacheDir: resolve(frontend, '.shell-check/live-integration-cache'),
    logLevel: 'silent',
    configFile: false,
    server: { middlewareMode: true, hmr: false },
    appType: 'custom',
  })
  let result, canonical, rendering
  try {
    const { HttpClient } = await server.ssrLoadModule('/src/api/http-client.ts')
    const { ScorePanel, Factors, Observations } = await server.ssrLoadModule(
      '/src/components/data/Status.tsx',
    )
    const config = {
      issuer: `https://${(env.VITE_AUTH0_DOMAIN ?? '').replace(/^https?:\/\//, '').replace(/\/$/, '')}/`,
      audience: env.VITE_AUTH0_AUDIENCE,
      rolesClaim: 'https://planit-control/roles',
    }
    const request = (path, options) => boundedRequest(apiOrigin, path, options)
    const makeClient = (token) =>
      new HttpClient(apiOrigin, async () => ({
        Authorization: `Bearer ${token}`,
      }))
    result = await runAcceptance({
      request,
      makeClient,
      accounts: { crew: input.crew, supervisor: input.supervisor },
      config,
      readiness: backend,
      inventory,
      allowAcknowledge: args.includes('--acknowledge'),
      alertId: input.alert_id,
    })
    canonical = await backendProbe(python, result.snapshots, ['--validate'])
    if (!result.snapshots.details.length)
      canonical = {
        status: 'not_run',
        reason:
          'No real authorized data available; no fixture validation substituted',
      }
    try {
      const fixtureDetail = JSON.parse(
        await readFile(
          resolve(frontend, 'src/fixtures/site-detail.json'),
          'utf8',
        ),
      )
      for (const [site, demo] of [
        [fixtureDetail, true],
        ...result.snapshots.details.map((s) => [s, false]),
      ]) {
        renderToStaticMarkup(
          React.createElement(
            React.Fragment,
            null,
            React.createElement(ScorePanel, { site, demo }),
            React.createElement(Factors, { factors: site.top_factors }),
            React.createElement(Observations, { rows: site.observations }),
          ),
        )
      }
      rendering = {
        status: result.snapshots.details.length ? 'passed' : 'partial',
        method:
          'Same existing ScorePanel/Factors/Observations components; no snapshot payload/HTML saved',
        real_details: result.snapshots.details.length,
        fixture_details: 1,
        full_browser:
          'not_run; real Auth0 browser-role/reload acceptance remains required',
      }
    } catch {
      rendering = {
        status: 'failed',
        reason: 'Canonical view rendering failed; private payload omitted',
      }
    }
  } finally {
    await server.close()
  }
  const ready =
    fixture === 'live' &&
    keys.every((k) => configState[k] === 'set') &&
    !frontendStatus.unsafe_public_credential_keys.length &&
    !frontendStatus.development_role_configured &&
    backend.auth?.configured &&
    !backend.auth.dev_auth_bypass &&
    backend.auth.domain_matches_spa &&
    backend.auth.audience_matches_spa &&
    backend.database?.status === 'passed' &&
    !network.checkout_routes_missing_from_running.length
  const failed =
    result.report.status === 'failed' ||
    canonical.status === 'failed' ||
    rendering.status === 'failed' ||
    network.health.status !== 200 ||
    network.vite_proxy_unauthenticated.status !== 401
  const report = {
    checked_at: new Date().toISOString(),
    status: failed
      ? 'failed'
      : ready && result.report.status === 'passed'
        ? 'passed'
        : 'blocked',
    scope:
      'local real-integration readiness and API acceptance; never task auto-completion',
    frontend: frontendStatus,
    backend,
    auth0_discovery: discovery,
    network,
    acceptance: result.report,
    canonical_responses: canonical,
    shared_rendering: rendering,
    privacy:
      'No tokens, user IDs, credentials, response bodies or private site names retained',
    task_checkboxes_changed: [],
  }
  console.log(JSON.stringify(report, null, 2))
  process.exitCode = failed ? 1 : report.status === 'passed' ? 0 : 2
}

main().catch(() => {
  console.error(
    JSON.stringify({
      status: 'failed',
      reason:
        'Integration runner input/dependency/configuration failed; private details suppressed',
      task_checkboxes_changed: [],
    }),
  )
  process.exitCode = 1
})
