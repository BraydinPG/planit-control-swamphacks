/* Progressive enhancement of static component references. No network, storage or app state. */
const architecture = document.querySelector('.architecture-section')
const inspector = document.querySelector('#architecture-detail')
const announcement = document.querySelector('#component-announcement')
const nodes = [...document.querySelectorAll('.system-node')]
const lanes = [...document.querySelectorAll('.architecture-lane')]
const layerButtons = [...document.querySelectorAll('[data-layer]')]

function selectNode(link) {
  const source = document.getElementById(link.getAttribute('href').slice(1))
  if (!source || !source.matches('.component-reference article')) return false
  const content = source.cloneNode(true)
  content.removeAttribute('id')
  content.querySelector('h3').id = 'component-detail-title'
  inspector.replaceChildren(content)
  const lane = link.closest('.architecture-lane')
  lanes.forEach(item => { item.dataset.active = String(item === lane) })
  layerButtons.forEach(button => button.setAttribute('aria-pressed', String(`lane-${button.dataset.layer}` === lane.id)))
  nodes.forEach(node => {
    if (node === link) node.setAttribute('aria-current', 'true')
    else node.removeAttribute('aria-current')
  })
  announcement.textContent = `${source.querySelector('h3').textContent} selected. Component explanation updated.`
  return true
}

function selectLayer(button) {
  const lane = document.getElementById(`lane-${button.dataset.layer}`)
  if (!lane || !lanes.includes(lane)) return
  selectNode(lane.querySelector('.system-node'))
}

if (architecture && inspector && announcement && nodes.length && lanes.length) {
  nodes.forEach(node => node.addEventListener('click', event => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    if (selectNode(node)) event.preventDefault()
  }))
  layerButtons.forEach(button => button.addEventListener('click', () => selectLayer(button)))
  selectLayer(layerButtons[0])
  architecture.dataset.enhanced = 'true'
  document.querySelector('.layer-picker').hidden = false
}
