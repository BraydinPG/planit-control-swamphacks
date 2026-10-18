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

/** Drops `?signin` from the address bar, keeping any route. */
export function clearSignInParam(hash = window.location.hash) {
  window.history.replaceState(null, document.title, `${window.location.pathname}${hash}`)
}
