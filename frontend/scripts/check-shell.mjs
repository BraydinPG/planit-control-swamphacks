/** T030 browser acceptance using installed Edge/Chrome and Node 24. No npm test dependencies. */
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { createServer } from 'node:net'
import { join } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('..', import.meta.url))
const output = join(root, '.shell-check')
const base = new URL(process.argv[2] ?? 'http://localhost:5173/')
assert(
  ['localhost', '127.0.0.1', '[::1]'].includes(base.hostname) &&
    base.protocol === 'http:' &&
    !base.username &&
    !base.password,
  'Use a loopback Vite URL',
)
const browserPath =
  process.env.SHELL_BROWSER ??
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const profile = join(output, `browser-${Date.now()}`)
await mkdir(profile, { recursive: true })
const browser = spawn(
  browserPath,
  [
    '--headless=new',
    '--disable-gpu',
    '--disable-extensions',
    '--disable-background-networking',
    '--no-first-run',
    '--no-default-browser-check',
    '--remote-debugging-port=0',
    `--user-data-dir=${profile}`,
    'about:blank',
  ],
  { stdio: 'ignore', windowsHide: true },
)
const extraServers = []
let ws
const results = []
const errors = []
const network = []
let id = 0
const pending = new Map()

async function until(getValue, label) {
  for (let attempt = 0; attempt < 100; attempt++) {
    try {
      const value = await getValue()
      if (value) return value
    } catch {
      /* Page or browser still starting. */
    }
    await delay(100)
  }
  throw new Error(`Timed out: ${label}`)
}
function send(method, params = {}) {
  return new Promise((resolveCall, reject) => {
    const requestId = ++id
    const timeout = setTimeout(() => {
      pending.delete(requestId)
      reject(new Error(`CDP timeout: ${method}`))
    }, 10000)
    pending.set(requestId, { resolveCall, reject, timeout })
    ws.send(JSON.stringify({ id: requestId, method, params }))
  })
}
async function evaluate(expression) {
  const result = await send('Runtime.evaluate', {
    expression,
    returnByValue: true,
    awaitPromise: true,
  })
  assert(!result.exceptionDetails, JSON.stringify(result.exceptionDetails))
  return result.result.value
}
async function loaded(text) {
  await until(
    () =>
      evaluate(
      `document.readyState === 'complete' && document.body.innerText.toLowerCase().includes(${JSON.stringify(text.toLowerCase())})`,
      ),
    text,
  )
}
async function navigate(url, text) {
  await send('Page.navigate', { url })
  await loaded(text)
}
async function screenshot(name) {
  await delay(250) // Let the existing CSS color transitions finish before capture.
  const { data } = await send('Page.captureScreenshot', {
    format: 'png',
    captureBeyondViewport: false,
  })
  await writeFile(join(output, `${name}.png`), Buffer.from(data, 'base64'))
}
async function offModeServer(setting) {
  const listener = createServer()
  await new Promise((done) => listener.listen(0, '127.0.0.1', done))
  const port = listener.address().port
  await new Promise((done) => listener.close(done))
  const child = spawn(
    process.execPath,
    [
      join(root, 'node_modules/vite/bin/vite.js'),
      '--host',
      '127.0.0.1',
      '--port',
      String(port),
      '--strictPort',
    ],
    {
      cwd: root,
      env: { ...process.env, VITE_USE_FIXTURES: setting },
      stdio: 'ignore',
      windowsHide: true,
    },
  )
  extraServers.push(child)
  const url = `http://127.0.0.1:${port}/`
  await until(async () => (await fetch(url)).ok, `Vite ${setting}`)
  return url
}

try {
  const portText = await until(
    () => readFile(join(profile, 'DevToolsActivePort'), 'utf8'),
    'browser debug port',
  )
  const port = portText.split('\n')[0]
  const targets = await (
    await fetch(`http://127.0.0.1:${port}/json/list`)
  ).json()
  ws = new WebSocket(
    targets.find((target) => target.type === 'page').webSocketDebuggerUrl,
  )
  await new Promise((done, reject) => {
    ws.addEventListener('open', done, { once: true })
    ws.addEventListener('error', reject, { once: true })
  })
  ws.addEventListener('message', ({ data }) => {
    const message = JSON.parse(data)
    if (message.id) {
      const request = pending.get(message.id)
      if (!request) return
      pending.delete(message.id)
      clearTimeout(request.timeout)
      if (message.error)
        request.reject(new Error(JSON.stringify(message.error)))
      else request.resolveCall(message.result)
    } else if (message.method === 'Runtime.exceptionThrown')
      errors.push(message.params.exceptionDetails.text)
    else if (message.method === 'Network.requestWillBeSent')
      network.push(message.params.request.url)
  })
  await send('Page.enable')
  await send('Runtime.enable')
  await send('Network.enable')
  await send('Network.setCacheDisabled', { cacheDisabled: true })
  for (const [width, height, name] of [
    [1440, 1000, 'desktop'],
    [390, 844, 'phone'],
    [320, 740, 'small-phone'],
  ]) {
    await send('Emulation.setDeviceMetricsOverride', {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: width < 600,
    })
    await navigate(
      new URL('#/crew/overview', base).href,
      'Fixed fixture timestamp',
    )
    await screenshot(name)
    for (const workspace of ['crew', 'supervisor']) {
      await evaluate(
        `document.querySelector('button[aria-pressed]${workspace === 'crew' ? '' : ':last-child'}').click()`,
      )
      await loaded(
        workspace === 'crew' ? 'Crew workspace' : 'Supervisor workspace',
      )
      for (const [page, title] of [
        ['sites', 'Worksite context'],
        ['alerts', 'Crew alerts'],
        ['reports', 'Hazard reports'],
        ['briefings', 'Shift briefings'],
        ['overview', 'Field overview'],
      ]) {
        await evaluate(
          `Array.from(document.querySelectorAll('nav a')).find(a => a.getClientRects().length && a.hash === '#/${workspace}/${page}').click()`,
        )
        await until(
          () =>
            evaluate(
              `document.querySelector('h1')?.innerText === ${JSON.stringify(title)}`,
            ),
          title,
        )
        assert(
          await evaluate('document.documentElement.scrollWidth <= innerWidth'),
          `Horizontal overflow at ${width}/${workspace}/${page}`,
        )
        assert(
          await evaluate(
            "Array.from(document.querySelectorAll('nav a')).filter(a => a.getClientRects().length).every(a => {const r=a.getBoundingClientRect(); return r.width >= 44 && r.height >= 44})",
          ),
          'Navigation targets below 44px',
        )
        assert(
          await evaluate(
            "document.querySelector('nav a[aria-current=page]') !== null",
          ),
        )
        assert(
          await evaluate(
            "document.body.innerText.includes('Sign-in is not connected')",
          ),
        )
      }
    }
    results.push({
      viewport: `${width}x${height}`,
      navigation: '10 workspace destinations passed',
      overflow: false,
      navigation_targets: '>=44px',
    })
  }
  await navigate(new URL('#/supervisor/reports', base).href, 'Hazard reports')
  await send('Page.reload')
  await loaded('Hazard reports')
  assert(
    await evaluate("location.hash === '#/supervisor/reports'"),
    'Deep link lost on reload',
  )
  await evaluate('document.querySelector(\'a[href="#main-content"]\').focus()')
  await send('Input.dispatchKeyEvent', {
    type: 'keyDown',
    key: 'Enter',
    code: 'Enter',
    windowsVirtualKeyCode: 13,
  })
  await send('Input.dispatchKeyEvent', {
    type: 'keyUp',
    key: 'Enter',
    code: 'Enter',
    windowsVirtualKeyCode: 13,
  })
  assert(
    await evaluate(
      "document.activeElement.id === 'main-content' && location.hash === '#/supervisor/reports'",
    ),
    'Skip link lost focus or route',
  )
  await evaluate("location.hash = '/supervisor/overview'")
  await loaded('Fixed fixture timestamp')
  await evaluate('history.back()')
  await until(
    () =>
      evaluate("document.querySelector('h1')?.innerText === 'Hazard reports'"),
    'browser back',
  )
  await navigate(
    new URL('#/crew/overview', base).href,
    'Fixed fixture timestamp',
  )
  await evaluate(
    "(async () => { const { shellContext } = await import('/src/api/shell-fixtures.ts'); shellContext('fixture').site.risk_score = null; location.hash = '/crew/reports' })()",
  )
  await loaded('Hazard reports')
  await evaluate("location.hash = '/crew/overview'")
  await loaded('Not scored yet')
  results.push({
    null_score: 'Not scored yet; never zero or low risk',
    fixture_mutation: 'browser memory only; no fixture file changed',
    deep_links_reload_back_skip_link: 'passed',
  })
  for (const setting of ['false', 'typo']) {
    const url = await offModeServer(setting)
    await navigate(
      url,
      setting === 'false'
        ? 'Live connection unavailable.'
        : 'Fixture configuration is invalid.',
    )
    assert(
      await evaluate(
        "!document.body.innerText.includes('Line Crew A') && document.body.innerText.includes('No site data loaded')",
      ),
      'Samples leaked into disabled/invalid mode',
    )
    assert(await evaluate('document.documentElement.scrollWidth <= innerWidth'))
    results.push({
      fixture_setting: setting,
      status: 'explicit unavailable; no silent fixture fallback',
    })
    await screenshot(`mode-${setting}`)
  }
  assert.equal(errors.length, 0, `Browser exceptions: ${errors.join(', ')}`)
  assert(
    !network.some((url) => new URL(url).pathname.startsWith('/api/')),
    'Unexpected backend API call',
  )
  const report = {
    task: 'T030',
    checked_at: new Date().toISOString(),
    url: base.href,
    browser: 'Installed headless Edge/Chrome via CDP',
    results,
    browser_exceptions: errors,
    backend_api_requests: 0,
    screenshots: '.shell-check/*.png (ignored)',
  }
  await writeFile(
    join(output, 'acceptance.json'),
    JSON.stringify(report, null, 2) + '\n',
  )
  console.log(JSON.stringify(report, null, 2))
} finally {
  for (const child of extraServers) child.kill()
  if (ws?.readyState === WebSocket.OPEN) {
    await send('Browser.close').catch(() => {})
    ws.close()
  }
  browser.kill()
}
