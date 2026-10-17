/** T030 browser acceptance using installed Edge/Chrome and Node 24. No npm test dependencies. */
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { createServer } from 'node:net'
import { join } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'
import { fileURLToPath } from 'node:url'
import { checkReportLocation } from './integration/location-browser.mjs'

const root = fileURLToPath(new URL('..', import.meta.url))
const output = join(root, '.shell-check')
const base = new URL(process.argv[2] ?? 'http://localhost:5173/')
const production = process.argv.includes('--production')
const restartCheck = process.argv.includes('--restart-check')
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
const failedRequests = []
const inFlightRequests = new Map()
let id = 0
let documentGeneration = 0
const pending = new Map()

async function until(getValue, label) {
  // Isolated Vite graphs measured 13-15s cold; keep assertions intact with a 30s startup allowance.
  for (let attempt = 0; attempt < 300; attempt++) {
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
        `document.readyState === 'complete' && document.body.innerText.toLowerCase().replace(/[^a-z0-9]/g,'').includes(${JSON.stringify(text.toLowerCase().replaceAll(/[^a-z0-9]/g, ''))})`,
      ),
    text,
  )
}
async function navigate(url, text) {
  const before = documentGeneration
  const result = await send('Page.navigate', { url })
  if (result.loaderId)
    await until(() => documentGeneration > before, 'new document context')
  await loaded(text)
}
async function reload(text) {
  const before = documentGeneration
  await send('Page.reload')
  await until(() => documentGeneration > before, 'reloaded context')
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
      '--input-type=module',
      '--eval',
      // These fixed-source helpers do not need file watchers (including old browser profiles).
      `import {createServer} from 'vite'; const server=await createServer({root:${JSON.stringify(root)},cacheDir:${JSON.stringify(join(output, `mode-${setting}-${Date.now()}`))},server:{host:'127.0.0.1',port:${port},strictPort:true,watch:null}});await server.listen();`,
    ],
    {
      cwd: root,
      env: {
        ...process.env,
        VITE_USE_FIXTURES: setting,
        VITE_AUTH0_DOMAIN: '',
        VITE_AUTH0_CLIENT_ID: '',
        VITE_AUTH0_AUDIENCE: '',
        VITE_DEV_AUTH_ROLE: '',
      },
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
    } else if (message.method === 'Runtime.executionContextsCleared')
      documentGeneration++
    else if (message.method === 'Runtime.exceptionThrown')
      errors.push(message.params.exceptionDetails.text)
    else if (message.method === 'Network.requestWillBeSent') {
      network.push(message.params.request.url)
      inFlightRequests.set(message.params.requestId, message.params.request.url)
    } else if (message.method === 'Network.loadingFinished')
      inFlightRequests.delete(message.params.requestId)
    else if (message.method === 'Network.loadingFailed')
      failedRequests.push({
        error: message.params.errorText,
        blocked: message.params.blockedReason,
      })
    else if (
      message.method === 'Network.responseReceived' &&
      message.params.response.status >= 400
    )
      failedRequests.push({
        url: message.params.response.url,
        status: message.params.response.status,
      })
  })
  await send('Page.enable')
  await send('Runtime.enable')
  await send('Network.enable')
  await send('Network.setCacheDisabled', { cacheDisabled: true })
  async function click(text) {
    await until(
      () =>
        evaluate(
          `Array.from(document.querySelectorAll('button,a')).some(e=>e.getClientRects().length && e.textContent.trim()===${JSON.stringify(text)})`,
        ),
      'click target ' + text,
    )
    await evaluate(
      `Array.from(document.querySelectorAll('button,a')).find(e=>e.getClientRects().length && e.textContent.trim()===${JSON.stringify(text)})?.click()`,
    )
  }
  async function hash(value, text) {
    await evaluate(`location.hash=${JSON.stringify(value)}`)
    await loaded(text)
  }
  async function set(selector, value) {
    await evaluate(
      `(()=>{const e=document.querySelector(${JSON.stringify(selector)});const prototype=e.tagName==='SELECT'?HTMLSelectElement.prototype:e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(prototype,'value').set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event(e.tagName==='SELECT'?'change':'input',{bubbles:true}))})()`,
    )
  }
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
      'Stop-work alert active',
    )
    await screenshot(name)
    assert(
      await evaluate('document.documentElement.scrollWidth <= innerWidth'),
      `Overflow at ${width}`,
    )
    const bounds = await evaluate(
      "(()=>{const a=Array.from(document.querySelectorAll('a')).find(e=>e.textContent.includes('Inspect alert and acknowledge'));const r=a.getBoundingClientRect();return {top:r.top,bottom:r.bottom}})()",
    )
    assert(
      bounds.top >= 0 && bounds.bottom <= height - 64,
      `Crew primary action below viewport at ${width}: ${JSON.stringify(bounds)}`,
    )
    assert(
      await evaluate(
        "Array.from(document.querySelectorAll('nav a')).filter(a=>a.getClientRects().length).every(a=>{const r=a.getBoundingClientRect();return r.width>=44&&r.height>=44})",
      ),
    )
    results.push({
      viewport: `${width}x${height}`,
      primary_action_visible: true,
      overflow: false,
      nav_targets: '>=44px',
    })
  }
  await click('Inspect alert and acknowledge')
  await loaded('acknowledgement(s)')
  await click('Record simulated acknowledgement')
  await loaded('Action recorded.')
  await reload('acknowledgement(s)')
  assert(
    await evaluate(
      "JSON.parse(localStorage.getItem('planit:frontend-demo:v1')).alerts[0].acknowledgements.some(a=>a.user_id==='demo-crew')",
    ),
  )
  const oldWindow = await evaluate(
    "JSON.parse(localStorage.getItem('planit:frontend-demo:v1')).alerts[0].clear_after",
  )
  await click('Replay additional qualifying strike')
  assert(
    await evaluate(
      `JSON.parse(localStorage.getItem('planit:frontend-demo:v1')).alerts[0].clear_after > ${JSON.stringify(oldWindow)}`,
    ),
  )
  await click('Replay server-cleared payload')
  await loaded('Server reports cleared')
  await click('Replay additional qualifying strike')
  await loaded('Stop-work alert active')
  const demoReportOpened = performance.now()
  await hash('/crew/reports', 'Report a hazard')
  await set('form select[required]', 'present')
  await writeFile(
    join(output, 'demo-photo.png'),
    Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a3ioAAAAASUVORK5CYII=',
      'base64',
    ),
  )
  const { root: documentNode } = await send('DOM.getDocument')
  const { nodeId } = await send('DOM.querySelector', {
    nodeId: documentNode.nodeId,
    selector: 'input[type=file]',
  })
  await send('DOM.setFileInputFiles', {
    nodeId,
    files: [join(output, 'demo-photo.png')],
  })
  await click('Submit simulated report')
  await loaded('Simulated report stored')
  const demoReportMs = Math.round(performance.now() - demoReportOpened)
  assert(demoReportMs < 30000, 'Existing no-note demo report must finish in under 30 seconds')
  results.push({ existing_report_no_note_no_gps_ms: demoReportMs,
    scope: 'Automated existing simulated form only; T034A form/metadata acceptance remains blocked by T053A' })
  const reportId = await evaluate(
    "JSON.parse(localStorage.getItem('planit:frontend-demo:v1')).reports[0].id",
  )
  const noticeId = await evaluate(
    "JSON.parse(localStorage.getItem('planit:frontend-demo:v1')).reports[0].notice_id",
  )
  assert(
    await evaluate(
      "!document.body.innerText.includes('Confirm report classification')",
    ),
  )
  await reload(reportId)
  await click('Supervisor')
  await loaded('55 sample/reference')
  await until(
    () =>
      evaluate(
        "document.querySelectorAll('.leaflet-overlay-pane path.leaflet-interactive').length===55",
      ),
    '55 map markers',
  )
  const firstSite = await evaluate(
    'document.querySelector(\'ol[aria-label="Ranked locations"] li\').innerText',
  )
  assert(
    !firstSite.includes('No team assigned') && /crew/i.test(firstSite),
    'Assigned sites not first',
  )
  await send('Emulation.setDeviceMetricsOverride', {
    width: 1440,
    height: 1000,
    deviceScaleFactor: 1,
    mobile: false,
  })
  await screenshot('supervisor-desktop')
  await evaluate(
    "document.querySelector('.leaflet-overlay-pane path.leaflet-interactive').dispatchEvent(new MouseEvent('click',{bubbles:true}))",
  )
  await until(
    () =>
      evaluate(
        "document.querySelector('.leaflet-popup-content button') !== null",
      ),
    'map point popup',
  )
  assert(
    await evaluate(
      "document.querySelector('.leaflet-popup-content button').textContent.length>0",
    ),
  )
  await evaluate(
    "document.querySelector('.leaflet-popup-content button').click()",
  )
  await loaded('Potential notices and approved instructions')
  await hash('/supervisor/overview', '55 sample/reference')
  await until(
    () =>
      evaluate(
        "document.querySelectorAll('.leaflet-overlay-pane path.leaflet-interactive').length===55",
      ),
    'restored map',
  )
  results.push({
    map: '55 geographic Leaflet points; point popup navigation and equivalent location list passed; online basemap optional',
  })
  await click('Flood advisory replay')
  await loaded('Developer/demo advisory')
  assert(
    await evaluate(
      "document.body.innerText.includes('eia860m-FL-59611') && document.body.innerText.includes('Recorded event end is not worksite clearance')",
    ),
  )
  await hash(
    '/supervisor/sites/site-demo-everglades',
    'Potential notices and approved instructions',
  )
  assert(
    await evaluate(
      `document.querySelector('[data-report-id="${reportId}"]').innerText.includes('Present report remains pending') && !document.querySelector('[data-report-id="${reportId}"] button')`,
    ),
    'Present report must use its notice, not absent-review controls',
  )
  assert(
    await evaluate(
      `document.querySelector('[data-notice-id="${noticeId}"]').innerText.includes('No instruction: supervisor confirmation is pending')`,
    ),
  )
  await evaluate(
    `document.querySelector('[data-notice-id="${noticeId}"] button').click()`,
  )
  await loaded(
    'No suggestion available; the confirming supervisor writes the instruction',
  )
  await set(
    `[data-notice-id="${noticeId}"] textarea`,
    'Demo reviewed instruction: await qualified field inspection.',
  )
  await evaluate(
    `document.querySelector('[data-notice-id="${noticeId}"] button').click()`,
  )
  await loaded('Demo reviewed instruction: await qualified field inspection.')
  await hash('/supervisor/briefings', 'Read-only stored briefings')
  await set('main select', 'site-demo-everglades')
  await loaded('Gemini output')
  await set('main select', 'organization')
  await loaded('Deterministic template fallback')
  await click('Crew')
  await loaded('Demo reviewed instruction: await qualified field inspection.')
  await hash('/crew/briefings', 'Gemini output')
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
      "document.activeElement.id==='main-content' && location.hash==='#/crew/briefings'",
    ),
  )
  await send('Input.dispatchKeyEvent', {
    type: 'keyDown',
    key: 'Tab',
    code: 'Tab',
    windowsVirtualKeyCode: 9,
  })
  await send('Input.dispatchKeyEvent', {
    type: 'keyUp',
    key: 'Tab',
    code: 'Tab',
    windowsVirtualKeyCode: 9,
  })
  assert(
    await evaluate(
      "(()=>{const e=document.activeElement;return ['INPUT','SELECT','BUTTON','TEXTAREA','A'].includes(e.tagName)&&e.matches(':focus-visible')&&parseFloat(getComputedStyle(e).outlineWidth)>0})()",
    ),
    'Keyboard focus must visibly reach an interactive control',
  )
  results.push({
    crew: 'assigned site -> alert acknowledgement/reset/reload -> photo report without note -> approved instruction',
    supervisor:
      '55 ranked/map locations -> exact-site ML advisory -> review -> confirm -> send instruction',
    briefings: 'read-only archived Gemini/template fixtures with citations',
    persistence: 'local demo namespace only; no server writes',
    keyboard: 'skip navigation and Tab to visible focused control passed',
  })
  for (const [width, height] of [
    [1440, 1000],
    [390, 844],
    [320, 740],
  ]) {
    await send('Emulation.setDeviceMetricsOverride', {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: width < 600,
    })
    for (const persona of ['crew', 'supervisor'])
      for (const page of [
        'overview',
        'sites',
        'alerts',
        'reports',
        'briefings',
      ]) {
        await hash(
          `/${persona}/${page}`,
          page === 'briefings'
            ? 'Read-only stored briefings'
            : page === 'reports'
              ? 'Hazard present or absent'
              : page === 'alerts'
                ? 'acknowledgement(s)'
                : persona === 'supervisor'
                  ? '55 sample/reference'
                  : page === 'sites'
                    ? 'Score factors and source evidence'
                    : 'Inspect alert and acknowledge',
        )
        if (persona === 'supervisor' && ['overview', 'sites'].includes(page))
          await until(
            () =>
              evaluate(
                "document.querySelectorAll('.leaflet-overlay-pane path.leaflet-interactive').length===55",
              ),
            'geographic markers',
          )
        assert(
          await evaluate('document.documentElement.scrollWidth <= innerWidth'),
          `Page overflow: ${width}/${persona}/${page}`,
        )
        assert(
          await evaluate(
            "Array.from(document.querySelectorAll('input,select,textarea')).every(e=>e.closest('label')||e.getAttribute('aria-label')||(e.id&&document.querySelector('label[for=\"'+e.id+'\"]')))",
          ),
          `Unlabelled control: ${page}`,
        )
        assert(
          await evaluate(
            "Array.from(document.querySelectorAll('button')).every(e=>e.textContent.trim()||e.getAttribute('aria-label'))",
          ),
          `Unnamed button: ${page}`,
        )
        assert(
          await evaluate(
            "Array.from(document.querySelectorAll('main button,main select,main textarea,main summary,main input:not([type=checkbox]),.leaflet-control-zoom a')).filter(e=>e.getClientRects().length).every(e=>{const r=e.getBoundingClientRect();return r.width>=44&&r.height>=44})",
          ),
          `Small primary control: ${width}/${persona}/${page}`,
        )
      }
  }
  results.push({
    accessibility:
      'all ten demo destinations at three viewports; no horizontal overflow, labels/names present, primary controls and map zoom >=44px, visible keyboard focus; full T068 live acceptance still blocked',
  })
  if (restartCheck) {
    const saved = await evaluate("localStorage.getItem('planit:frontend-demo:v1')")
    console.log(`RESTART CHECK: restart only your demo server at ${base.origin}, on the same port. Leave this browser running, then press Enter here. This checker never stops a server.`)
    await new Promise((done, reject) => {
      const timer = setTimeout(() => finish(new Error('Restart confirmation timed out after five minutes')), 300000)
      const finish = (error) => {
        clearTimeout(timer)
        process.stdin.off('data', ready)
        process.stdin.off('end', ended)
        process.stdin.pause()
        if (error) reject(error)
        else done()
      }
      const ready = () => finish()
      const ended = () => finish(new Error('Restart check needs an interactive stdin'))
      process.stdin.once('data', ready)
      process.stdin.once('end', ended)
      process.stdin.resume()
    })
    await until(async () => (await fetch(base)).ok, 'restarted demo server')
    await reload('Read-only stored briefings')
    assert.equal(await evaluate("localStorage.getItem('planit:frontend-demo:v1')"), saved, 'Restart must retain exactly the same isolated demo state')
    await hash('/supervisor/reports', reportId)
    await hash('/supervisor/sites/site-demo-everglades', 'Demo reviewed instruction: await qualified field inspection.')
    assert(await evaluate(`document.querySelector('[data-notice-id="${noticeId}"]').innerText.toLowerCase().includes('confirmed')`), 'Confirmed notice must survive restart')
    await hash('/crew/overview', 'Demo reviewed instruction: await qualified field inspection.')
    await hash('/crew/briefings', 'Gemini output')
    results.push({ restart: 'Operator restarted the same-origin demo server; exact demo state/report, supervisor confirmation, approved crew instruction, navigation and stored briefing survived. Browser-local simulation only; photos are memory-only.' })
  }
  if (!production) {
    results.push(await checkReportLocation({ base, navigate, evaluate, until }))
    await navigate(
      new URL('/tests/browser.html', base).href,
      'Sign in required',
    )
    await evaluate('window.harness.reset()')
    await evaluate("window.harness.mount('loading')")
    await loaded('Checking sign-in')
    await evaluate("window.harness.mount('no-role')")
    await loaded('No role assigned')
    await evaluate("window.harness.mount('dev')")
    await loaded('Development bypass roles are not accepted')
    await evaluate("window.harness.mount('crew')")
    await loaded('Stop-work alert active')
    await hash(
      '/supervisor/sites/site-fixture-b',
      'outside the sites returned for your session',
    )
    assert(
      await evaluate("!document.body.innerText.includes('Preview workspace')"),
      'Live role selector leaked',
    )
    await hash('/crew/overview', 'Stop-work alert active')
    await click('Inspect alert and acknowledge')
    await loaded('Acknowledge alert')
    await click('Acknowledge alert')
    await loaded('Action recorded.')
    assert(
      await evaluate(
        "window.harness.requests.some(r=>r==='POST /api/alerts/alert-ltg-demo/acknowledge')",
      ),
    )
    await hash('/crew/briefings', 'Gemini output')
    await set('main select', 'organization')
    await loaded('Deterministic template fallback')
    for (const [code, message] of [
      [
        404,
        'No briefing yet. Briefings are generated at 6 PM site-local time.',
      ],
      [401, 'Session expired'],
      [403, 'Permission denied'],
      [503, 'service or database is unavailable'],
    ]) {
      await evaluate(`window.harness.briefingStatus=${code}`)
      await set('main select', 'site-demo-everglades')
      await loaded(message)
      await set('main select', 'organization')
      await loaded('Deterministic template fallback')
    }
    await evaluate(
      'window.harness.briefingStatus=200; window.harness.invalidBriefing=true',
    )
    await set('main select', 'site-demo-everglades')
    await loaded('Invalid stored briefing response')
    await evaluate('window.harness.invalidBriefing=false')
    assert(
      await evaluate(
        "window.harness.requests.filter(r=>r.includes('brief')).every(r=>r.startsWith('GET '))",
      ),
      'Stored briefings must only use GET',
    )
    await hash('/crew/reports', 'Hazard present or absent')
    await set('form select[required]', 'present')
    assert(
      await evaluate(
        "document.querySelector('form input[type=file]').required && document.querySelector('form button[type=submit]').disabled",
      ),
      'Live present report must require photo',
    )
    await set('form select[required]', 'absent')
    assert(
      await evaluate(
        "!document.querySelector('form input[type=file]').required && !document.querySelector('form button[type=submit]').disabled",
      ),
      'Live absent report does not require a photo',
    )
    // These requests stay inside the browser's explicit mock fetch, never FastAPI.
    await click('Submit report')
    await loaded('Report accepted by backend')
    const absentId = await evaluate('window.harness.snapshot().reports[0].id')
    for (const [code, text] of [
      [401, 'Session expired'],
      [403, 'Permission denied'],
      [409, 'server state changed'],
      [422, 'backend rejected'],
      [503, 'service or database is unavailable'],
    ]) {
      await evaluate(`window.harness.settings({mutationStatus:${code}})`)
      await click('Submit report')
      await loaded(text)
      assert(
        await evaluate(
          `window.harness.snapshot().reports[0].id===${JSON.stringify(absentId)}`,
        ),
        'Failed submit must not claim a saved report',
      )
    }
    await evaluate('window.harness.settings({mutationStatus:200})')
    await set('form select[required]', 'present')
    async function attachMockPhoto() {
      const { root } = await send('DOM.getDocument')
      const { nodeId } = await send('DOM.querySelector', {
        nodeId: root.nodeId,
        selector: 'form input[type=file]',
      })
      await send('DOM.setFileInputFiles', {
        nodeId,
        files: [join(output, 'demo-photo.png')],
      })
    }
    await attachMockPhoto()
    await click('Submit report')
    await loaded('Report accepted by backend')
    const created = await evaluate('window.harness.snapshot().reports[0]')
    assert.equal(created.review_status, 'pending')
    const mockNotice = created.notice_id
    await evaluate("window.harness.mount('supervisor')")
    await hash(
      '/supervisor/sites/site-demo-everglades',
      'Potential notices and approved instructions',
    )
    assert(
      await evaluate(
        `!document.querySelector('[data-report-id="${created.id}"] button')`,
      ),
      'Present report has no absent-review action',
    )
    await evaluate(
      `document.querySelector('[data-report-id="${absentId}"] button').click()`,
    )
    await until(
      () =>
        evaluate(
          `document.querySelector('[data-report-id="${absentId}"] h3').innerText.includes('confirmed')`,
        ),
      'mock absent reviewed',
    )
    assert(
      await evaluate(
        `document.querySelector('[data-notice-id="${mockNotice}"]').innerText.includes('No instruction: supervisor confirmation is pending')`,
      ),
    )
    await evaluate('window.harness.settings({denyMutation:true})')
    await evaluate(
      `document.querySelector('[data-notice-id="${mockNotice}"] button').click()`,
    )
    await loaded('Permission denied')
    assert(
      await evaluate(
        `!document.querySelector('[data-notice-id="${mockNotice}"] textarea')`,
      ),
    )
    await evaluate('window.harness.settings({denyMutation:false})')
    await evaluate(
      `document.querySelector('[data-notice-id="${mockNotice}"] button').click()`,
    )
    await loaded('Suggested instruction')
    assert(
      await evaluate(
        `document.querySelector('[data-notice-id="${mockNotice}"] textarea').value.includes('Mocked Gemini draft')`,
      ),
      'Returned draft must populate the editor after confirmation',
    )
    assert(
      await evaluate(
        "!window.harness.requests.some(r=>r.endsWith('/instruction'))",
      ),
      'Draft must not send automatically',
    )
    await loaded('8.3 / 10')
    await set(
      `[data-notice-id="${mockNotice}"] textarea`,
      'Edited mock supervisor instruction: request field inspection.',
    )
    const readsBeforeRefresh = await evaluate('window.harness.requests.length')
    await click('Refresh server state')
    await until(
      () => evaluate(`window.harness.requests.length > ${readsBeforeRefresh}`),
      'shared server refresh requested',
    )
    await evaluate(
      'new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))',
    )
    assert(
      await evaluate(
        `document.querySelector('[data-notice-id="${mockNotice}"] textarea').value==='Edited mock supervisor instruction: request field inspection.'`,
      ),
      'Refreshing the same notice must preserve the edited draft',
    )
    await evaluate(
      `document.querySelector('[data-notice-id="${mockNotice}"] button').click()`,
    )
    await loaded(
      'Edited mock supervisor instruction: request field inspection.',
    )
    await send('Page.reload', { ignoreCache: true })
    await loaded('Sign in required')
    await evaluate("window.harness.mount('crew')")
    await hash(
      '/crew/overview',
      'Edited mock supervisor instruction: request field inspection.',
    )
    assert(
      await evaluate('!document.querySelector("main textarea")'),
      'Crew cannot edit supervisor instruction',
    )
    // A second report exercises a null suggestion and a manual final instruction.
    await hash('/crew/reports', 'Hazard present or absent')
    await set('form select[required]', 'present')
    await attachMockPhoto()
    await click('Submit report')
    await loaded('Report accepted by backend')
    const manualId = await evaluate(
      'window.harness.snapshot().reports[0].notice_id',
    )
    await evaluate(
      "window.harness.settings({manual:true}); window.harness.mount('supervisor')",
    )
    await hash(
      '/supervisor/sites/site-demo-everglades',
      'Potential notices and approved instructions',
    )
    await evaluate(
      `document.querySelector('[data-notice-id="${manualId}"] button').click()`,
    )
    await loaded(
      'No suggestion available; the confirming supervisor writes the instruction',
    )
    assert(
      await evaluate(
        `document.querySelector('[data-notice-id="${manualId}"] textarea').value==='' && document.querySelector('[data-notice-id="${manualId}"] button').disabled`,
      ),
    )
    await set(
      `[data-notice-id="${manualId}"] textarea`,
      'Manual mock instruction approved by supervisor.',
    )
    await evaluate(
      `document.querySelector('[data-notice-id="${manualId}"] button').click()`,
    )
    await loaded('Manual mock instruction approved by supervisor.')
    // Competing confirmation: backend conflict refreshes owner, no editor/takeover.
    const raceId = await evaluate(
      "window.harness.snapshot().notices.find(n=>n.status==='potential').id",
    )
    await evaluate(
      `window.harness.settings({foreignOwner:${JSON.stringify(raceId)}}); document.querySelector('[data-notice-id="${raceId}"] button').click()`,
    )
    await loaded('Another supervisor confirmed this hazard')
    assert(
      await evaluate(
        `!document.querySelector('[data-notice-id="${raceId}"] textarea')`,
      ),
    )
    results.push({
      reports:
        'MOCK HTTP ONLY: present/photo and absent/no-photo, 401/403/409/422/503 submission failures, absent review, notice confirmation/draft/edit/send, manual fallback, reload/crew delivery, server score refresh and competing owner all pass',
      alerts:
        'Mock server state and acknowledgement preserved; no ML/React score or alert engine',
    })
    await evaluate("window.harness.mount('supervisor')")
    await hash('/supervisor/overview', '5 backend-authorized locations')
    await until(
      () =>
        evaluate(
          "document.querySelectorAll('.leaflet-overlay-pane path.leaflet-interactive').length===5",
        ),
      'mock live map',
    )
    for (const [status, text] of [
      [401, 'Session expired'],
      [403, 'Permission denied'],
      [503, 'service or database is unavailable'],
    ]) {
      await evaluate(`window.harness.mount('crew',${status})`)
      await loaded(text)
      assert(
        await evaluate("!document.body.innerText.includes('Line Crew A')"),
        'Error substituted fixture data',
      )
    }
    await evaluate("window.harness.mount('logged-out')")
    await loaded('Sign in required')
    results.push({
      auth: 'mocked existing provider: loading/logged out/no role/dev rejection/crew/supervisor/session transitions',
      api: 'mocked HTTP 200/401/403/503 rendered; no demo fallback or live preview persona escalation',
      real_auth: 'not verified; tenant credentials unavailable',
    })
    for (const setting of ['false', 'typo']) {
      const started = Date.now()
      const url = await offModeServer(setting)
      await navigate(
        url,
        setting === 'false'
          ? 'Sign-in is not configured.'
          : 'Fixture configuration is invalid.',
      )
      assert(await evaluate("!document.body.innerText.includes('Line Crew A')"))
      results.push({
        fixture_setting: setting,
        cold_start_ms: Date.now() - started,
        status: 'explicit configuration/auth state; no silent samples',
      })
    }
  } else {
    const response = await fetch(new URL('/tests/browser.html', base))
    assert(
      !(await response.text()).includes('id="auth-test"'),
      'Test harness must not be published in production output',
    )
    results.push({
      production:
        'full demo lifecycle exercised from clean built bundle; mocked provider and compile-time mode tests are development-only',
    })
  }
  assert.equal(errors.length, 0, `Browser exceptions: ${errors.join(', ')}`)
  assert(
    !network.some((url) => new URL(url).pathname.startsWith('/api/')),
    'Unexpected backend API call',
  )
  const report = {
    task: production
      ? 'Clean production-bundle demo acceptance (not real login/persistence)'
      : 'T032-T038 demo acceptance and mocked live integration (not real login/persistence)',
    checked_at: new Date().toISOString(),
    url: base.href,
    browser: 'Installed headless Edge/Chrome via CDP',
    results,
    browser_exceptions: errors,
    backend_api_requests: 0,
    screenshots: '.shell-check/*.png (ignored)',
  }
  await writeFile(
    join(output, production ? 'production-acceptance.json' : 'acceptance.json'),
    JSON.stringify(report, null, 2) + '\n',
  )
  console.log(JSON.stringify(report, null, 2))
} catch (error) {
  if (ws?.readyState === WebSocket.OPEN) {
    const diagnostic = await evaluate(
      "({url:location.href,ready:document.readyState,text:document.body.innerText.slice(0,5000),map:document.querySelectorAll('.leaflet-interactive').length,hash:location.hash})",
    ).catch(() => null)
    await writeFile(
      join(output, 'failure.json'),
      JSON.stringify(
        {
          error: String(error),
          completed_results: results,
          errors,
          failedRequests,
          pending_requests: [...inFlightRequests.values()],
          diagnostic,
        },
        null,
        2,
      ),
    )
    await screenshot('failure').catch(() => {})
    console.error(
      JSON.stringify({
        errors,
        failedRequests,
        pending_requests: [...inFlightRequests.values()],
        diagnostic,
      }),
    )
  }
  throw error
} finally {
  for (const child of extraServers) child.kill()
  if (ws?.readyState === WebSocket.OPEN) {
    await send('Browser.close').catch(() => {})
    ws.close()
  }
  browser.kill()
}
