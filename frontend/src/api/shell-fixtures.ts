/** T030's bundled context only. No fetches, tokens, writes or live fallback. */
import sitesFixture from '../fixtures/sites.json'
import detailFixture from '../fixtures/site-detail.json'
import type { SiteDetail, SiteSummary } from '../types/api'

export type ShellMode = 'fixture' | 'unavailable' | 'invalid'
const configuredMode: unknown = import.meta.env.VITE_USE_FIXTURES
// Unset explicitly defaults to demo mode, including production previews.
// False or invalid settings must never silently substitute sample data.
export const shellMode: ShellMode =
  configuredMode === undefined || configuredMode === 'true'
    ? 'fixture'
    : configuredMode === 'false'
      ? 'unavailable'
      : 'invalid'

export function shellContext(mode: ShellMode) {
  if (mode !== 'fixture') return null
  // Existing generated JSON validated by backend contract tests.
  const detail = detailFixture as SiteDetail
  const site = (sitesFixture as SiteSummary[]).find(
    (item) => item.id === detail.id,
  )
  return site ? { site, region: detail.region, source: detail.source } : null
}
