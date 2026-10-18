// One build-time source for the static public documents. No application imports.
export const repository = 'https://github.com/BraydinPG/planit-control-swamphacks'
export const pages = [
  { path: '/landing.html', label: 'Home', title: 'FORESITE | Intelligent Worksite Operations', description: 'FORESITE connects environmental evidence, explainable hazard evaluation, historically evaluated duration research and human-led worksite decisions.' },
  { path: '/platform.html', label: 'Platform', title: 'Platform | FORESITE', description: 'Explore the engineering that connects environmental evidence, deterministic alerts, event-duration research and human-led field operations in FORESITE.' },
  { path: '/data.html', label: 'Data', title: 'Data & Research | FORESITE', description: 'Inspect FORESITE historical datasets, duration models, Monte Carlo consistency checks and chronological backtests, with sources and research limitations.' },
  { path: '/about.html', label: 'About', title: 'About & Documentation | FORESITE', description: 'Meet the FORESITE team, explore the SwampHacks 2026 engineering process, and access research documentation, safety context and technical data-handling information.' },
]
const escape = value => value.replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;')
export function header(path) {
  return `<header class="top" data-nav-open="false">
  <a class="brand" href="/landing.html" aria-label="FORESITE home"${path === '/landing.html' ? ' aria-current="page"' : ''}><img src="/foresite-wordmark.png?v=daaf5322" width="768" height="166" alt="" decoding="async" draggable="false"></a>
  <button class="menu-toggle" type="button" aria-expanded="false" aria-controls="public-menu" aria-label="Open navigation" hidden><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg></button>
  <nav class="public-nav" id="public-menu" aria-label="Public website">${pages.filter(p => p.label !== 'Home').map(p => `<a class="public-link" href="${p.path}"${path === p.path ? ' aria-current="page"' : ''}>${p.label}</a>`).join('')}</nav>
  <a class="signin" href="/?signin">Sign In<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8h9M8.5 4.5 12 8l-3.5 3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></a>
</header>`
}
export function footer() {
  return `<footer class="public-footer">
  <div class="footer-identity"><a class="footer-brand" href="/landing.html" aria-label="FORESITE home"><img src="/foresite-wordmark.png?v=daaf5322" width="768" height="166" alt="" loading="lazy"></a><p>Intelligent Worksite Operations</p><span>A SwampHacks 2026 project.</span></div>
  <nav class="footer-groups" aria-label="Footer resources"><div><h2>Explore</h2><a href="/landing.html">Home</a><a href="/platform.html">Platform</a><a href="/data.html">Data</a></div><div><h2>Resources</h2><a href="/about.html#resources">Documentation</a><a href="${repository}">GitHub <span aria-hidden="true">↗</span></a></div><div><h2>FORESITE</h2><a href="/about.html">About</a><a href="/about.html#safety">Safety &amp; transparency</a><a href="/about.html#data-handling">Data handling</a></div></nav>
  <div class="footer-note"><span>Evidence informs. People decide.</span><span>Advisory context does not authorize work or clear an alert.</span></div>
</footer>`
}
export function metadata(page) {
  return `<title>${escape(page.title)}</title>
<meta name="description" content="${escape(page.description)}">
<link rel="canonical" href="https://foresiteoperations.org${page.path}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="FORESITE">
<meta property="og:title" content="${escape(page.title)}">
<meta property="og:description" content="${escape(page.description)}">
<meta property="og:url" content="https://foresiteoperations.org${page.path}">
<meta property="og:image" content="https://foresiteoperations.org/foresite-social.png">
<meta property="og:image:alt" content="FORESITE — Intelligent Worksite Operations">
<meta name="twitter:card" content="summary_large_image">`
}
