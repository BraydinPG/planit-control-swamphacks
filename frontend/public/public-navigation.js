// A non-modal disclosure: no network, authentication or storage access.
(() => {
  const header = document.querySelector('header.top')
  const toggle = header?.querySelector('.menu-toggle')
  const navigation = header?.querySelector('.public-nav')
  if (!header || !toggle || !navigation) return
  const compact = matchMedia('(max-width:700px)')
  let open = false
  function setOpen(value, restoreFocus = false) {
    open = value && compact.matches
    header.dataset.navOpen = String(open)
    toggle.setAttribute('aria-expanded', String(open))
    toggle.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation')
    if (open) navigation.querySelector('a')?.focus()
    else if (restoreFocus) toggle.focus()
  }
  document.documentElement.classList.add('public-navigation-ready')
  toggle.hidden = false
  toggle.addEventListener('click', () => setOpen(!open))
  header.addEventListener('keydown', event => {
    if (event.key === 'Escape' && open) { event.preventDefault(); setOpen(false, true) }
  })
  navigation.addEventListener('click', event => { if (event.target.closest('a')) setOpen(false) })
  document.addEventListener('pointerdown', event => { if (open && !header.contains(event.target)) setOpen(false) })
  header.addEventListener('focusout', event => { if (open && event.relatedTarget && !header.contains(event.relatedTarget)) setOpen(false) })
  compact.addEventListener('change', () => {
    const focusWasInNavigation = navigation.contains(document.activeElement)
    setOpen(false, compact.matches && focusWasInNavigation)
  })
})()
