import type { HazardScore, SiteSummary } from '../../types/api'

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
  // Completeness counts current monitored inputs only (heat, flood, live lightning).
  // A positive index at 0% still rests on real evidence (an alert, a confirmed report,
  // replayed or stale readings): show it, qualified as incomplete. Only a zero with no
  // current input is unknown rather than a measured low.
  if (!(site.data_completeness > 0))
    return site.risk_score > 0 ? 'partial' : 'none'
  return site.data_completeness < 1 ? 'partial' : 'full'
}

export const evidenceLabel: Record<Exclude<Evidence, 'full'>, string> = {
  none: 'Unknown: no current evidence',
  partial: 'Evidence incomplete',
}

/** True when any supplied factor is stale or simulated/replayed (full breakdown when given). */
export function hasStaleOrReplay(
  site: Pick<SiteSummary, 'top_factors'> & { score?: HazardScore | null },
) {
  return (site.score?.factor_contributions ?? site.top_factors).some(
    (f) => f.data_state === 'stale' || f.data_state === 'simulated',
  )
}
