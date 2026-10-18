import { createContext, useContext } from 'react'

/**
 * True on a demo site's page. Its name already says "(demo)", which is the only place a
 * demo site says so (user decision, 2026-10-18): its readings look live, and replay
 * labels are hidden. Real sites keep every simulated, stale and replay label.
 */
export const DemoSiteContext = createContext(false)

export function useDemoSite(): boolean {
  return useContext(DemoSiteContext)
}

export function isDemoSite(site: { location_type?: string | null }): boolean {
  return site.location_type === 'demo_site'
}
