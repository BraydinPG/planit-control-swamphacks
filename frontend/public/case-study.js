// Progressive, read-only document controls. Never fetches APIs or changes app state.
const links = [...document.querySelectorAll('[data-stage]')]
const panels = [...document.querySelectorAll('.stage-panel')]
const perspectives = [...document.querySelectorAll('[data-perspective]')]
const previous = document.querySelector('#stage-prev')
const next = document.querySelector('#stage-next')
const announcement = document.querySelector('#case-announcement')
let stage = 1
let perspective = 'crew'

function render(focus = false) {
  document.querySelector('.scenario-workspace').dataset.activePerspective = perspective
  for (const [index, panel] of panels.entries()) panel.hidden = index + 1 !== stage
  for (const link of links) {
    if (Number(link.dataset.stage) === stage) link.setAttribute('aria-current', 'step')
    else link.removeAttribute('aria-current')
  }
  previous.disabled = stage === 1
  next.disabled = stage === panels.length
  document.querySelector('#stage-position').textContent = `STAGE ${String(stage).padStart(2, '0')} / 07`
  document.querySelector('.scene-index').textContent = `${String(stage).padStart(2, '0')} / 07`
  document.querySelector('.stage-progress i').style.width = `${stage / panels.length * 100}%`
  for (const button of perspectives) button.setAttribute('aria-pressed', String(button.dataset.perspective === perspective))
  for (const note of document.querySelectorAll('[data-view]')) note.hidden = note.dataset.view !== perspective
  for (const link of document.querySelectorAll('[data-demo-link]')) link.href = `/?demo#/${perspective}/overview`
  announcement.textContent = `Stage ${stage} of 7. ${perspective === 'crew' ? 'Crew' : 'Supervisor'} perspective. ${panels[stage - 1].querySelector('h3').textContent}`
  if (focus) {
    const heading = panels[stage - 1].querySelector('h3')
    heading.focus({ preventScroll: true })
    const rect = heading.getBoundingClientRect()
    const header = document.querySelector('.top').getBoundingClientRect()
    if (rect.top < header.bottom + 16 || rect.bottom > innerHeight - 24) heading.scrollIntoView({ block: 'start', behavior: 'instant' })
  }
}
function select(value, focus = false) {
  stage = Math.max(1, Math.min(panels.length, value))
  render(focus)
}
function fromHash() {
  const match = /^#stage-([1-7])$/.exec(location.hash)
  if (match) select(Number(match[1]))
}
if (links.length === 7 && panels.length === 7 && previous && next) {
  document.body.classList.add('case-interactive')
  document.querySelector('.scenario-toolbar').hidden = false
  document.querySelector('.stage-controls').hidden = false
  for (const link of links) {
    // Number-only mobile steps retain full accessible names.
    link.setAttribute('aria-label', `Stage ${link.dataset.stage}: ${link.children[1].firstChild.textContent}`)
    link.setAttribute('aria-controls', `stage-${link.dataset.stage}`)
    link.addEventListener('click', event => {
      event.preventDefault()
      history.replaceState(null, '', link.hash)
      select(Number(link.dataset.stage), true)
    })
  }
  for (const button of perspectives) button.addEventListener('click', () => {
    perspective = button.dataset.perspective
    render()
  })
  previous.addEventListener('click', () => { select(stage - 1, true); history.replaceState(null, '', `#stage-${stage}`) })
  next.addEventListener('click', () => { select(stage + 1, true); history.replaceState(null, '', `#stage-${stage}`) })
  addEventListener('hashchange', fromHash)
  fromHash()
  render()
}
