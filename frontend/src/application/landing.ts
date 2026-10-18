/**
 * The landing page (public/landing.html) is the front door. A signed-out visit to the
 * bare app address is sent there; its Sign in buttons come back with `?signin`, which
 * skips the landing page and starts sign-in (or opens the demo).
 * Deep links (#/...), Auth0 callbacks (?code=...) and signed-in users are never redirected.
 */
export const LANDING_PATH = '/landing.html'
const SIGN_IN_PARAM = 'signin'

/** The visitor clicked Sign in on the landing page. */
export function cameFromLanding(): boolean {
  return new URLSearchParams(window.location.search).has(SIGN_IN_PARAM)
}

/** The plain app address with no route, query or callback parameters. */
export function isBareEntry(): boolean {
  const { pathname, search, hash } = window.location
  return pathname === '/' && search === '' && hash.replace(/^#\/?/, '') === ''
}

export function showLanding() {
  window.location.replace(LANDING_PATH)
}

const BACK_KEY = 'foresite.backToLanding'

/**
 * Makes the browser Back button return a signed-in user to the landing page instead of
 * the Auth0 login page or `?signin` (which would start sign-in again). It turns the
 * current history entry into a landing-page entry and pushes the app back on top, so
 * Back walks through app pages first and then reaches the landing page. Installed once
 * per tab, so reloads do not stack extra entries. Returns a cleanup for the listener.
 */
export function installBackToLanding(): () => void {
  const onPop = () => {
    if (window.location.pathname === LANDING_PATH) window.location.reload()
  }
  window.addEventListener('popstate', onPop)
  let installed = false
  try {
    installed = window.sessionStorage.getItem(BACK_KEY) === '1'
  } catch {
    // storage blocked: install anyway; at worst Back meets one extra landing entry
  }
  if (!installed) {
    const here = `${window.location.pathname}${window.location.search}${window.location.hash}`
    window.history.replaceState({ foresite: 'landing' }, '', LANDING_PATH)
    window.history.pushState({ foresite: 'app' }, '', here)
    try {
      window.sessionStorage.setItem(BACK_KEY, '1')
    } catch {
      // ignore
    }
  }
  return () => window.removeEventListener('popstate', onPop)
}

/** Signed out: the next sign-in in this tab installs the Back entry again. */
export function resetBackToLanding() {
  try {
    window.sessionStorage.removeItem(BACK_KEY)
  } catch {
    // ignore
  }
}

/** Drops `?signin` from the address bar, keeping any route. */
export function clearSignInParam(hash = window.location.hash) {
  window.history.replaceState(null, document.title, `${window.location.pathname}${hash}`)
}
