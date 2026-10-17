import type { SiteSummary } from '../../types/api'

/**
 * How much evidence stands behind a server-supplied score. Presentation only:
 * the backend number and band are always shown as supplied and never
 * recalculated here. A numeric score with missing inputs is not a low reading.
 */
export type Evidence = 'none' | 'partial' | 'full'

export function evidenceOf(
  site: Pick<SiteSummary, 'risk_score' | 'data_completeness'>,
): Evidence | null {
  if (site.risk_score === null) return null
  if (!(site.data_completeness > 0)) return 'none'
  return site.data_completeness < 1 ? 'partial' : 'full'
}

export const evidenceLabel: Record<Exclude<Evidence, 'full'>, string> = {
  none: 'Unknown: no current evidence',
  partial: 'Evidence incomplete',
}

/** True when any supplied factor is stale or simulated/replayed. */
export function hasStaleOrReplay(site: Pick<SiteSummary, 'top_factors'>) {
  return site.top_factors.some(
    (f) => f.data_state === 'stale' || f.data_state === 'simulated',
  )
}
