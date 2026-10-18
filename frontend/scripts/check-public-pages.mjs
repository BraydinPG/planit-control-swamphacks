/** Public-document acceptance with installed Edge/Chrome and Node 24. No service credentials. */
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { createHash } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('..', import.meta.url))
const output = join(root, '.shell-check')
const base = new URL(process.argv[2] ?? 'http://localhost:5177/')
assert(['localhost', '127.0.0.1', '[::1]'].includes(base.hostname) && base.protocol === 'http:' && !base.username && !base.password)
const fixtures = process.argv.includes('--fixtures')
const captureFixtures = process.argv.includes('--capture-fixtures')
assert(!captureFixtures || fixtures, 'Capture only the explicitly simulated fixture app')
const profile = join(output, `public-pages-${Date.now()}`)
await mkdir(profile, { recursive: true })
const browser = spawn(process.env.SHELL_BROWSER ?? 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', [
  '--headless=new', '--disable-gpu', '--disable-extensions', '--disable-background-networking',
  '--no-first-run', '--no-default-browser-check', '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank',
], { stdio: 'ignore', windowsHide: true })
const pending = new Map(), errors = [], requests = [], results = []
let ws, sequence = 0
async function until(fn, label) {
  for (let n = 0; n < 300; n++) {
    try { const result = await fn(); if (result) return result } catch { /* navigation can replace the context */ }
    await delay(100)
  }
  throw new Error(`Timed out: ${label}`)
}
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++sequence, timeout = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)) }, 10000)
    pending.set(id, { resolve, reject, timeout })
    ws.send(JSON.stringify({ id, method, params }))
  })
}
async function evaluate(expression) {
  const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  assert(!result.exceptionDetails, JSON.stringify(result.exceptionDetails))
  return result.result.value
}
async function loaded(path) {
  const heading = path === '/data.html' ? '#data-title' : path === '/platform.html' ? '#platform-title' : path === '/case-study.html' ? '#case-title' : '.hero h1'
  await until(() => evaluate(`location.pathname===${JSON.stringify(path)}&&document.readyState==='complete'&&!!document.querySelector(${JSON.stringify(heading)})`), path)
  await evaluate('document.fonts.ready')
  await until(() => evaluate("document.querySelector('.brand img').complete&&document.querySelector('.brand img').naturalWidth>0"), 'logo')
}
async function shot(name, full = true) {
  await evaluate('scrollTo(0,0)')
  const clip = full ? await evaluate('({x:0,y:0,width:document.documentElement.clientWidth,height:document.documentElement.scrollHeight,scale:1})') : undefined
  const { data } = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: full, ...(clip ? { clip } : {}) })
  await writeFile(join(output, name + '.png'), Buffer.from(data, 'base64'))
  // Edge's full-page compositor can leave content beyond 16K pixels blank.
  // Preserve full-resolution tiles for review of this unusually long document.
  if (clip?.height > 14000) {
    for (let y = 0, index = 0; y < clip.height; y += 6000, index++) {
      await evaluate(`scrollTo(0,${y});document.querySelector('header.top').style.visibility=${JSON.stringify(y ? 'hidden' : 'visible')}`)
      const tile = { ...clip, y, height: Math.min(6000, clip.height - y) }
      const result = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, clip: tile })
      await writeFile(join(output, `${name}-tile-${index}.png`), Buffer.from(result.data, 'base64'))
    }
    await evaluate("document.querySelector('header.top').style.visibility='';scrollTo(0,0)")
  }
}
const storage = "JSON.stringify([Object.entries(localStorage).sort(),Object.entries(sessionStorage).sort()])"
const layout = `(()=>{
  const links=Array.from(document.querySelectorAll('header a')),rects=links.map(e=>e.getBoundingClientRect());
  const clipped=Array.from(document.querySelectorAll('main h1,main h2,main h3,main h4,main p,main li,main td,main th')).flatMap(e=>{const range=document.createRange();range.selectNodeContents(e);return Array.from(range.getClientRects()).filter(r=>r.width&&(r.left< -1||r.right>document.documentElement.clientWidth+1)).map(()=>e.textContent)});
  return {overflow:document.documentElement.scrollWidth>innerWidth,clipped,headerFits:rects.every(r=>r.left>=0&&r.right<=document.documentElement.clientWidth&&r.width>=44&&r.height>=44),headerOverlaps:rects.some((a,i)=>rects.some((b,j)=>j>i&&Math.min(a.right,b.right)-Math.max(a.left,b.left)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1))};
})()`
try {
  const port = await until(() => readFile(join(profile, 'DevToolsActivePort'), 'utf8'), 'browser port')
  const targets = await (await fetch(`http://127.0.0.1:${port.split('\n')[0]}/json/list`)).json()
  ws = new WebSocket(targets.find(t => t.type === 'page').webSocketDebuggerUrl)
  await new Promise((resolve, reject) => { ws.addEventListener('open', resolve, { once: true }); ws.addEventListener('error', reject, { once: true }) })
  ws.addEventListener('message', ({ data }) => {
    const event = JSON.parse(data)
    if (event.id) {
      const task = pending.get(event.id)
      if (!task) return
      pending.delete(event.id); clearTimeout(task.timeout)
      if (event.error) task.reject(new Error(JSON.stringify(event.error))); else task.resolve(event.result)
    } else if (event.method === 'Runtime.exceptionThrown') errors.push(event.params.exceptionDetails)
    else if (event.method === 'Runtime.consoleAPICalled' && event.params.type === 'error') errors.push(event.params.args.map(a => a.value ?? a.description))
    else if (event.method === 'Network.requestWillBeSent') requests.push(new URL(event.params.request.url).pathname)
  })
  await send('Page.enable'); await send('Runtime.enable'); await send('Network.enable')
  await send('Page.addScriptToEvaluateOnNewDocument', { source: 'window.__publicRafCount=0;const nativeRaf=window.requestAnimationFrame;window.requestAnimationFrame=callback=>{window.__publicRafCount++;return nativeRaf(callback)}' })
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
  const evidence = JSON.parse(await readFile(join(root, 'public/research/evidence.json'), 'utf8'))
  for (const figure of evidence.figures) {
    assert.equal(createHash('sha256').update(await readFile(join(root, 'public/research', figure.file))).digest('hex'), figure.sha256)
  }
  const ledger = JSON.parse(await readFile(join(root, 'public/research/dashboard-figures.json'), 'utf8'))
  for (const figure of ledger.figures) assert.equal(createHash('sha256').update(await readFile(join(root, 'public/research', figure.file))).digest('hex'), figure.sha256)
  const benchmarkBefore = JSON.parse(await readFile(join(root, '../docs/feed-refresh-baseline.json'), 'utf8'))
  const benchmarkAfter = JSON.parse(await readFile(join(root, '../docs/feed-refresh-optimized.json'), 'utf8'))
  assert.equal(Object.values(benchmarkBefore.http_requests).reduce((a, b) => a + b, 0), 1794)
  assert.equal(Object.values(benchmarkAfter.http_requests).reduce((a, b) => a + b, 0), 578)
  assert.deepEqual(benchmarkBefore.observation_sha256_by_feed, benchmarkAfter.observation_sha256_by_feed)
  assert.equal(benchmarkBefore.site_score_sha256, benchmarkAfter.site_score_sha256)
  for (const path of ['/landing.html', '/platform.html', '/data.html', '/case-study.html', '/public-site.css', '/platform.css', '/platform.js', '/data.css', '/case-study.css', '/case-study.js', '/case-study/crew-overview.webp', '/case-study/supervisor-notice.webp']) {
    const response = await fetch(new URL(path, base))
    assert.equal(response.status, 200, path)
    if (path === '/data.html') {
      const html = await response.text()
      assert(html.includes('THE SCIENCE BEHIND FORESITE.') && !html.includes('id="root"') && html.includes('/data-research.js') && !html.includes('/src/main'))
    }
  }
  await send('Page.navigate', { url: new URL('/landing.html', base).href }); await loaded('/landing.html')
  await evaluate("localStorage.setItem('@@auth0spajs@@public-page-sentinel','synthetic-session-only');sessionStorage.setItem('public-page-role-sentinel','supervisor')")
  const originalStorage = await evaluate(storage)
  for (const [width, height] of [[1440, 1000], [768, 1024], [390, 844], [320, 740]]) {
    await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: width < 600 })
    const requestStart = requests.length
    await send('Page.navigate', { url: new URL('/landing.html', base).href }); await loaded('/landing.html')
    const home = await evaluate(layout)
    assert(!home.overflow && !home.clipped.length && home.headerFits && !home.headerOverlaps, JSON.stringify({ width, home }))
    assert(await evaluate("document.querySelector('header a[aria-current=page]').getAttribute('href')==='/landing.html'"))
    assert(await evaluate("document.querySelector('.top .brand').getAttribute('href')==='/landing.html'&&Array.from(document.querySelectorAll('.top .public-nav a')).map(a=>a.textContent).join(',')==='Platform,Data,Case Study'&&!Array.from(document.querySelectorAll('.top a')).some(a=>a.textContent.trim()==='Home')"))
    assert(await evaluate("!document.querySelector('.lab')&&!document.querySelector('link[href=\"/data.css\"]')&&!document.querySelector('img[src*=\"/research/\"]')&&document.querySelectorAll('.feature').length===3&&document.querySelector('h1').textContent==='SEE THE RISK.PLAN BEYOND THE ALERT.'"))
    assert.deepEqual(await evaluate("Array.from(document.querySelectorAll('.stats b')).map(e=>e.textContent)"), ['526K+', '6', '5,000', '50+'])
    assert.deepEqual(await evaluate("Array.from(document.querySelectorAll('.signin,.cta-btn')).map(e=>e.getAttribute('href'))"), ['/?signin', '/?demo#/crew/overview'])
    assert(!requests.slice(requestStart).some(p => p.startsWith('/research/') || p.startsWith('/case-study/') || ['/data.css', '/platform.css', '/platform.js', '/case-study.css', '/case-study.js'].includes(p)), 'Homepage loads no research, Platform or Case Study assets')
    await shot(`public-home-${width}`)
    await evaluate("document.querySelector('header a[href=\"/data.html\"]').focus()")
    assert(await evaluate("document.activeElement.matches('a[href=\"/data.html\"]')"))
    await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
    await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
    await loaded('/data.html')
    await send('Page.reload'); await loaded('/data.html')
    await until(() => evaluate("document.querySelector('#research-controls-status').textContent.startsWith('Interactive controls select')"), 'static research controls')
    for (let index = 0; index < 12; index++) {
      await evaluate(`document.querySelectorAll('.lab picture img')[${index}].scrollIntoView({block:'center'})`)
      await until(() => evaluate(`document.querySelectorAll('.lab picture img')[${index}].complete&&document.querySelectorAll('.lab picture img')[${index}].naturalWidth>0`), 'chart')
    }
    await evaluate("document.querySelectorAll('details').forEach(d=>d.open=true)")
    const data = await evaluate(layout)
    assert(!data.overflow && !data.clipped.length && data.headerFits && !data.headerOverlaps, JSON.stringify({ width, data }))
    assert(await evaluate(`document.querySelectorAll('.lab picture').length===12&&document.querySelectorAll('.lab-targets li').length===6&&document.querySelector('header a[aria-current=page]').getAttribute('href')==='/data.html'&&Array.from(document.querySelectorAll('.lab picture img')).every(img=>img.currentSrc.includes('-mobile.svg')===${width <= 600})`))
    assert(await evaluate("!document.querySelector('.research-disabled')&&!document.body.textContent.includes('Evaluation includes saying no.')&&!document.body.textContent.includes('Read the separate experiment')&&!Array.from(document.querySelectorAll('.top a')).some(a=>a.textContent.trim()==='Home')"))
    assert(await evaluate("document.body.innerText.includes('Discrete-time logistic')&&document.body.innerText.includes('Kaplan–Meier')&&document.body.innerText.includes('previously inspected')&&document.body.innerText.includes('0.619922')&&document.body.innerText.includes('0.211733')&&document.body.innerText.includes('Prediction is not permission.')"))
    assert.equal(await evaluate(storage), originalStorage, 'Public navigation preserves storage/session sentinels')
    await evaluate("document.querySelectorAll('details').forEach(d=>d.open=false)")
    await shot(`public-data-${width}`); await shot(`public-data-top-${width}`, false)
    // Controls select genuine static variants, including target-specific horizons.
    await evaluate("document.querySelector('#calibration-model').value='logistic';document.querySelector('#calibration-horizon').value='6';document.querySelector('#calibration-model').dispatchEvent(new Event('change'))")
    assert(await evaluate("document.querySelector('#figure-calibration img').src.includes('calibration-logistic-6.svg')&&document.querySelector('#calibration-context').textContent.includes('6h')&&document.querySelector('#figure-calibration tbody').textContent.includes('2025 inspected test')"))
    await evaluate("document.querySelector('#duration-model').value='logistic';document.querySelector('#duration-scale').value='linear';document.querySelector('#duration-scale').dispatchEvent(new Event('change'))")
    assert(await evaluate("document.querySelector('#figure-duration-errors img').src.includes('duration-errors-logistic-linear.svg')&&document.querySelector('#duration-context').textContent.includes('40.712h')"))
    await evaluate("document.querySelector('#research-event').value='Heat Index Exceedance';document.querySelector('#research-event').dispatchEvent(new Event('change'))")
    assert.deepEqual(await evaluate("Array.from(document.querySelector('#research-horizon').options).map(o=>o.value)"), ['1', '3', '6'])
    assert(await evaluate("document.querySelector('#research-readout').textContent.includes('Heat Index Exceedance')&&document.querySelector('#research-target-limits').textContent.includes('Three airport stations')"))
    await evaluate("document.querySelector('#research-period').value='validation';document.querySelector('#research-period').dispatchEvent(new Event('change'))")
    assert(await evaluate("document.querySelector('#research-readout').textContent.includes('2024 validation')"))
    await evaluate("document.querySelector('#research-event').value='Flood';document.querySelector('#research-event').dispatchEvent(new Event('change'))")
    assert.deepEqual(await evaluate("Array.from(document.querySelector('#research-horizon').options).map(o=>o.value)"), ['6', '12', '24'])
    await evaluate('history.back()'); await loaded('/landing.html')
    await evaluate('history.forward()'); await loaded('/data.html')
    await evaluate("document.querySelector('.top .brand').focus()")
    await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
    await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
    await loaded('/landing.html')
    await evaluate("document.querySelector('header a[href=\"/data.html\"]').click()"); await loaded('/data.html')
    await evaluate("document.querySelector('.brand').click()"); await loaded('/landing.html')
    await evaluate("document.querySelector('.top a[href=\"/platform.html\"]').focus()")
    await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
    await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
    await loaded('/platform.html')
    await send('Page.reload'); await loaded('/platform.html')
    await until(() => evaluate("document.querySelector('.architecture-section').dataset.enhanced==='true'"), 'architecture enhancement')
    assert(await evaluate("document.querySelectorAll('.system-node').length===27&&document.querySelectorAll('.component-reference article').length===27&&document.querySelectorAll('.architecture-lane').length===5&&document.querySelector('.top a[aria-current=page]').getAttribute('href')==='/platform.html'&&!document.querySelector('#root')&&!document.querySelector('link[href=\"/data.css\"]')&&!document.querySelector('img[src*=\"/research/\"]')"))
    assert.deepEqual(await evaluate("Array.from(document.querySelectorAll('.platform-button[href*=\"demo\"]')).map(a=>a.getAttribute('href'))"), ['/?demo#/crew/overview', '/?demo#/crew/overview'])
    // Exercise every actual component reference through the explorer, then real keyboard/mouse selection.
    assert(await evaluate(`(()=>{
      const links=Array.from(document.querySelectorAll('.system-node'));
      for(const link of links){
        const lane=link.closest('.architecture-lane');
        if(innerWidth<=900)document.querySelector('[data-layer="'+lane.id.slice(5)+'"]').click();
        link.click();
        const reference=document.getElementById(link.getAttribute('href').slice(1));
        if(document.querySelector('#component-detail-title').textContent!==reference.querySelector('h3').textContent)return false;
      }
      return document.querySelectorAll('.system-node[aria-current=true]').length===1&&new Set(Array.from(document.querySelectorAll('[id]')).map(e=>e.id)).size===document.querySelectorAll('[id]').length;
    })()`))
    await evaluate("document.querySelector('[data-layer=analysis]').click();document.querySelector('[data-node=monte-carlo]').focus()")
    await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
    await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
    assert(await evaluate("document.querySelector('#component-detail-title').textContent==='Offline Monte Carlo'&&document.querySelector('#architecture-detail').textContent.includes('does not execute for every live request')&&!location.hash"))
    if (width <= 900) {
      assert.equal(await evaluate("Array.from(document.querySelectorAll('.architecture-lane')).filter(l=>getComputedStyle(l).display!=='none').length"), 1)
      assert(await evaluate("document.querySelector('[data-layer=analysis]').getAttribute('aria-pressed')==='true'"))
    } else assert.equal(await evaluate("Array.from(document.querySelectorAll('.architecture-lane')).filter(l=>getComputedStyle(l).display!=='none').length"), 5)
    await evaluate("document.querySelector('[data-node=score]').scrollIntoView({block:'center'})")
    const scoreTarget = await evaluate("(()=>{const r=document.querySelector('[data-node=score]').getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()")
    await send('Input.dispatchMouseEvent', { type: 'mousePressed', button: 'left', clickCount: 1, ...scoreTarget })
    await send('Input.dispatchMouseEvent', { type: 'mouseReleased', button: 'left', clickCount: 1, ...scoreTarget })
    assert(await evaluate("document.querySelector('#component-detail-title').textContent==='Deterministic hazard index'&&document.querySelector('#architecture-detail').textContent.includes('Gemini output never contribute')"))
    const platform = await evaluate(layout)
    assert(!platform.overflow && !platform.clipped.length && platform.headerFits && !platform.headerOverlaps, JSON.stringify({ width, platform }))
    assert(await evaluate("getComputedStyle(document.querySelector('.rail-pulse')).animationName==='none'&&getComputedStyle(document.querySelector('.grain')).animationName==='none'"))
    const rafCount = await evaluate('window.__publicRafCount')
    await delay(150)
    assert.equal(await evaluate('window.__publicRafCount'), rafCount, 'Reduced motion stops the decorative frame loop')
    await evaluate("document.querySelector('.component-reference').open=true")
    const references = await evaluate(layout)
    assert(!references.overflow && !references.clipped.length, JSON.stringify({ width, references }))
    await evaluate("document.querySelector('.component-reference').open=false;document.querySelector('[data-node=monte-carlo]').click()")
    await shot(`public-platform-${width}`); await shot(`public-platform-top-${width}`, false)
    await evaluate("document.querySelector('#architecture').scrollIntoView({block:'start'})")
    const architectureShot = await send('Page.captureScreenshot', { format: 'png' })
    await writeFile(join(output, `public-platform-architecture-${width}.png`), Buffer.from(architectureShot.data, 'base64'))
    assert.equal(await evaluate(storage), originalStorage, 'Platform preserves sessions')
    await evaluate("document.querySelector('.top a[href=\"/data.html\"]').click()"); await loaded('/data.html')
    await evaluate("document.querySelector('.top a[href=\"/platform.html\"]').click()"); await loaded('/platform.html')
    await evaluate("document.querySelector('.top .brand').click()"); await loaded('/landing.html')
    assert.equal(await evaluate(storage), originalStorage)
    await evaluate("document.querySelector('.top a[href=\"/case-study.html\"]').focus()")
    await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
    await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
    await loaded('/case-study.html')
    await send('Page.reload'); await loaded('/case-study.html')
    await until(() => evaluate("document.body.classList.contains('case-interactive')"), 'scenario controls')
    assert(await evaluate("document.body.innerText.includes('Simulated scenario — not live worksite conditions.')&&document.querySelectorAll('.stage-panel').length===7&&document.querySelector('.top a[aria-current=page]').getAttribute('href')==='/case-study.html'&&!document.querySelector('#root')"))
    const caseStudy = await evaluate(layout)
    assert(!caseStudy.overflow && !caseStudy.clipped.length && caseStudy.headerFits && !caseStudy.headerOverlaps, JSON.stringify({ width, caseStudy }))
    await shot(`public-case-study-${width}`); await shot(`public-case-study-top-${width}`, false)
    for (let stage = 1; stage <= 7; stage++) {
      await evaluate(`document.querySelector('[data-stage="${stage}"]').click()`)
      for (const persona of ['crew', 'supervisor']) {
        await evaluate(`document.querySelector('[data-perspective="${persona}"]').click()`)
        assert(await evaluate(`(()=>{const panel=document.querySelector('#stage-${stage}');return !panel.hidden&&document.querySelectorAll('.stage-panel:not([hidden])').length===1&&panel.querySelector('[data-view=${persona}]').hidden===false&&document.querySelector('[data-perspective=${persona}]').getAttribute('aria-pressed')==='true'})()`), `Scenario ${width}px / stage ${stage} / ${persona}`)
        const stageLayout = await evaluate(layout)
        assert(!stageLayout.overflow && !stageLayout.clipped.length, JSON.stringify({ width, stage, persona, stageLayout }))
        for (const path of await evaluate(`Array.from(document.querySelectorAll('#stage-${stage} img')).map(e=>e.getAttribute('src'))`)) {
          await evaluate(`document.querySelector('img[src="${path}"]').scrollIntoView({block:'center'})`)
          assert(await until(() => evaluate(`document.querySelector('img[src="${path}"]').complete&&document.querySelector('img[src="${path}"]').naturalWidth>0`), 'authentic screenshot'))
        }
      }
      if ([2, 3, 5].includes(stage)) {
        await evaluate("document.querySelector('#scenario').scrollIntoView({block:'start'})")
        const picture = await send('Page.captureScreenshot', { format: 'png' })
        await writeFile(join(output, `public-case-study-stage-${stage}-${width}.png`), Buffer.from(picture.data, 'base64'))
      }
    }
    assert(await evaluate("document.querySelector('#stage-next').disabled&&document.querySelector('[data-demo-link]').getAttribute('href')==='/?demo#/supervisor/overview'"))
    await evaluate("document.querySelector('#stage-prev').focus()")
    await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, text: '\r' })
    await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
    const previousStage = await evaluate("({shown:!document.querySelector('#stage-6').hidden,focus:document.activeElement.id,text:document.querySelector('#stage-6').innerText})")
    assert(previousStage.shown && previousStage.focus === 'stage-title-6' && previousStage.text.includes('does not reuse them as site predictions'), JSON.stringify(previousStage))
    await evaluate("document.querySelector('[data-stage=\"2\"]').click()")
    assert(await evaluate("document.querySelector('#stage-2').innerText.includes('7.9')&&document.querySelector('#stage-2').innerText.includes('7.91')&&document.querySelector('#stage-2').innerText.includes('rules-0.2')&&document.querySelector('#stage-2').innerText.includes('Zero verified live coverage.')"))
    await send('Page.reload'); await loaded('/case-study.html')
    await until(() => evaluate("!document.querySelector('#stage-2').hidden"), 'deep-linked stage after reload')
    await evaluate("document.querySelector('.case-source details').open=true")
    const sourceLayout = await evaluate(layout)
    assert(!sourceLayout.overflow && !sourceLayout.clipped.length)
    assert.equal(await evaluate(storage), originalStorage, 'Case Study preserves Auth0 and app storage')
    assert(await evaluate("getComputedStyle(document.querySelector('.site-pulse')).animationName==='none'"))
    assert(await evaluate("Array.from(document.querySelectorAll('.stage-nav a,.perspective-picker button,.stage-controls button')).filter(e=>e.getClientRects().length).every(e=>{const r=e.getBoundingClientRect();return r.width>=44&&r.height>=44})"), 'Scenario controls retain 44px targets')
    await evaluate("document.querySelector('.top a[href=\"/platform.html\"]').click()"); await loaded('/platform.html')
    await evaluate("document.querySelector('.top a[href=\"/case-study.html\"]').click()"); await loaded('/case-study.html')
    await evaluate("document.querySelector('.top .brand').click()"); await loaded('/landing.html')
    results.push({ width, home, data, platform, caseStudy, scenarioStages: 7, scenarioPerspectives: 2, componentReferences: 27, separateDocuments: true, reload: true, history: true, sessionStoragePreserved: true })
  }
  // Direct access has no preceding homepage or app initialization requirement.
  await send('Page.navigate', { url: new URL('/data.html', base).href }); await loaded('/data.html')
  assert(await evaluate("Array.from(document.scripts).every(s=>['/@vite/client','/public-atmosphere.js','/data-research.js'].some(path=>s.src.endsWith(path)))&&!document.querySelector('#root')&&!location.hash&&!location.search&&document.querySelector('#sky')&&document.querySelector('#bolt')"))
  // A missing static research JSON disables controls while preserving figures and tables.
  await send('Network.setBlockedURLs', { urls: ['*/research/dashboard.json'] })
  await send('Page.reload'); await loaded('/data.html')
  await until(() => evaluate("document.querySelector('#research-controls-status').textContent.startsWith('Interactive research data is unavailable')"), 'missing static export fallback')
  assert(await evaluate("document.querySelectorAll('.lab picture').length===12&&Array.from(document.querySelectorAll('.research-controls select')).every(s=>s.disabled)"))
  await send('Network.setBlockedURLs', { urls: [] })
  // JS-disabled visitors retain all explanatory content, figures and numerical tables.
  await send('Emulation.setScriptExecutionDisabled', { value: true })
  await send('Page.reload'); await loaded('/data.html')
  assert(await evaluate("document.querySelectorAll('.lab picture').length===12&&document.querySelectorAll('.lab-values table').length===12"))
  await send('Page.navigate', { url: new URL('/platform.html', base).href }); await loaded('/platform.html')
  assert.equal(await evaluate("Array.from(document.querySelectorAll('.architecture-lane')).filter(l=>getComputedStyle(l).display!=='none').length"), 5)
  assert(await evaluate("document.querySelectorAll('.component-reference article').length===27&&document.querySelector('.layer-picker').hidden"))
  await evaluate("document.querySelector('.component-reference').open=true")
  assert(await evaluate("document.querySelector('#component-monte-carlo').textContent.includes('does not execute for every live request')"))
  await send('Page.navigate', { url: new URL('/case-study.html', base).href }); await loaded('/case-study.html')
  assert(await evaluate("document.querySelectorAll('.stage-panel:not([hidden])').length===7&&document.querySelector('.scenario-toolbar').hidden&&document.querySelector('#stage-5').innerText.includes('west gate')&&document.querySelector('#stage-6').innerText.includes('explicitly synthetic')"), 'All seven static stages remain readable without JS')
  await send('Page.navigate', { url: new URL('/platform.html', base).href }); await loaded('/platform.html')
  await send('Emulation.setScriptExecutionDisabled', { value: false })
  // Normal motion retains the shared storm atmosphere and diagram flow.
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] })
  await send('Page.reload'); await loaded('/platform.html')
  const animatedRaf = await evaluate('window.__publicRafCount')
  await delay(200)
  assert(await evaluate(`window.__publicRafCount>${animatedRaf}&&getComputedStyle(document.querySelector('.rail-pulse')).animationName==='signal-flow'`))
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
  await delay(150)
  const changedRaf = await evaluate('window.__publicRafCount')
  await delay(150)
  assert.equal(await evaluate('window.__publicRafCount'), changedRaf, 'Changing the motion preference pauses the storm without a reload')
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false })
  await evaluate("document.querySelector('[data-node=monte-carlo]').click()")
  const beforeResizeRaf = await evaluate('window.__publicRafCount')
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true })
  await delay(150)
  assert(await evaluate(`window.__publicRafCount>${beforeResizeRaf}`), 'Reduced-motion sky redraws after resizing')
  assert(await evaluate("getComputedStyle(document.querySelector('#lane-analysis')).display!=='none'&&document.querySelector('[data-layer=analysis]').getAttribute('aria-pressed')==='true'&&document.querySelector('#component-detail-title').textContent==='Offline Monte Carlo'"), 'Selected component survives desktop-to-phone resize')
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] })
  await send('Page.navigate', { url: new URL('/case-study.html#stage-5', base).href }); await loaded('/case-study.html')
  await until(() => evaluate("!document.querySelector('#stage-5').hidden"), 'direct stage access')
  assert(await evaluate("getComputedStyle(document.querySelector('.site-pulse')).animationName==='site-pulse'"))
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
  assert(await evaluate("getComputedStyle(document.querySelector('.site-pulse')).animationName==='none'&&getComputedStyle(document.querySelector('#stage-5')).animationName==='none'"))
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false })
  assert(await evaluate("!document.querySelector('#stage-5').hidden"), 'Scenario selection survives resize')
  if (fixtures) {
    await send('Page.navigate', { url: new URL('/platform.html', base).href }); await loaded('/platform.html')
    await evaluate("document.querySelector('.platform-button[href*=\"demo\"]').click()")
    await until(() => evaluate("location.search==='?demo'&&location.hash==='#/crew/overview'&&document.body.innerText.includes('Simulated demo')"), 'Platform uses existing demo entry')
    if (captureFixtures) {
      // Use a new browser profile, the real React fixture view and no mutation API.
      await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 2, mobile: false })
      await evaluate('document.fonts.ready')
      await until(() => evaluate("!!document.querySelector('[data-crew-alerts]')&&document.body.innerText.includes('4.2 mi')"), 'actual crew screenshot')
      await evaluate('scrollTo(0,0)')
      const crew = await send('Page.captureScreenshot', { format: 'webp', quality: 88 })
      await writeFile(join(root, 'public/case-study/crew-overview.webp'), Buffer.from(crew.data, 'base64'))
      await evaluate("location.hash='/supervisor/sites/site-demo-everglades'")
      await until(() => evaluate("!!document.querySelector('[data-notice-id=notice-wildlife-1]')&&document.body.innerText.includes('7.9')"), 'actual supervisor screenshot')
      const instruction = await evaluate("(()=>{const e=document.querySelector('[data-notice-id=notice-wildlife-1]');e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+scrollX,y:r.y+scrollY,width:r.width,height:r.height,scale:1}})()")
      assert(await evaluate("document.querySelector('[data-notice-id=notice-wildlife-1]').innerText.includes('Avoid the east access road. Use the west gate until wildlife control clears it.')"))
      const supervisor = await send('Page.captureScreenshot', { format: 'webp', quality: 88, captureBeyondViewport: true, clip: instruction })
      await writeFile(join(root, 'public/case-study/supervisor-notice.webp'), Buffer.from(supervisor.data, 'base64'))
      const fixtureHashes = {}, imageHashes = {}
      for (const path of ['src/fixtures/site-detail.json', 'src/fixtures/reports.json', 'src/fixtures/hazard-notices.json']) fixtureHashes[path] = createHash('sha256').update((await readFile(join(root, path), 'utf8')).replaceAll('\r\n', '\n')).digest('hex')
      for (const path of ['crew-overview.webp', 'supervisor-notice.webp']) imageHashes[path] = createHash('sha256').update(await readFile(join(root, 'public/case-study', path))).digest('hex')
      await writeFile(join(root, 'public/case-study/capture-provenance.json'), JSON.stringify({
        capture: 'Installed Edge CDP: actual React app, fixture build, new isolated browser profile',
        fixture_as_of_utc: '2026-10-17T18:00:00Z',
        viewport_css_pixels: { width: 1440, height: 1000, device_scale_factor: 2 },
        crew_route: '/?demo#/crew/overview', supervisor_route: '/?demo#/supervisor/sites/site-demo-everglades',
        supervisor_crop: '[data-notice-id=notice-wildlife-1]',
        backend_requests: 0, mutations: 0, fixture_hash_encoding: 'UTF-8, CRLF normalized to LF', fixture_sha256: fixtureHashes, image_sha256: imageHashes,
      }, null, 2) + '\n')
    }
    await send('Page.navigate', { url: base.href }); await loaded('/landing.html')
    await send('Page.navigate', { url: new URL('/landing.html', base).href }); await loaded('/landing.html')
    await evaluate("document.querySelector('.cta-btn').click()")
    await until(() => evaluate("location.search==='?demo'&&location.hash==='#/crew/overview'&&document.body.innerText.includes('Simulated demo')"), 'existing demo CTA')
  }
  const unexpected = errors.filter(e => !JSON.stringify(e).includes('ERR_BLOCKED_BY_CLIENT'))
  assert.deepEqual(unexpected, [])
  assert(!requests.some(p => p.startsWith('/api/')), 'No actual backend calls')
  await writeFile(join(output, 'public-pages-acceptance.json'), JSON.stringify({ results, errors, apiRequests: 0, fixtures }, null, 2))
  console.log(JSON.stringify({ passed: true, widths: results.map(r => r.width), publicPages: 4, scenarioStages: 7, scenarioPerspectives: 2, architectureComponents: 27, keyboardAndMouse: true, reducedAndNormalMotion: true, figures: 12, originalChartAssetsPreserved: 6, savedSelectors: true, missingJsonFallback: true, scriptDisabledFallback: true, separateDocuments: true, noHomeResearchLoads: true, reloadAndHistory: true, sessionSentinelsPreserved: true, demoClick: fixtures, exceptions: 0, apiRequests: 0 }))
} finally {
  if (ws?.readyState === WebSocket.OPEN) { await send('Browser.close').catch(() => {}); ws.close() }
  browser.kill()
}
