import type { SiteRecord } from '../api/contracts'
import type { Alert, CrewReport, FactorContribution } from '../types/api'
import { displayLabel, factorLabel } from './display'

export interface SiteHazard {
  id: string
  label: string
  factors: FactorContribution[]
  alerts: Alert[]
  report?: CrewReport
}

const alertKey = (alert: Alert) =>
  alert.rule === 'lightning_stop_work' ? 'lightning' :
    alert.rule === 'heat' ? 'heat_index' : alert.rule

/** Read-only projection of backend decisions. No thresholds, totals or alert lifecycle here. */
export function siteHazards(site: SiteRecord): SiteHazard[] {
  const rows = new Map<string, SiteHazard>()
  const row = (id: string, label: string) => {
    if (!rows.has(id)) rows.set(id, { id, label, factors: [], alerts: [] })
    return rows.get(id)!
  }
  // Include every active tier, even when a higher tier is the primary alert card.
  // Feed failure or an elapsed timer must never hide an authoritative active alert.
  for (const alert of site.alerts) {
    if (alert.site_id !== site.id || alert.state !== 'active') continue
    const key = alertKey(alert)
    row(key, key === 'heat_index' ? 'Heat' : factorLabel(key)).alerts.push(alert)
  }
  const factors = site.score?.site_id === site.id
    ? site.score.factor_contributions : site.score ? [] : site.top_factors
  for (const factor of factors) {
    if (factor.factor === 'model' || !Number.isFinite(factor.contribution) ||
      factor.contribution <= 0 || factor.data_state === 'unavailable') continue
    if (factor.factor === 'crew_report') {
      const report = site.reports.find((r) => r.id === factor.evidence_id &&
        r.site_id === site.id && r.hazard_present && r.review_status === 'confirmed')
      if (!report) continue
      // The existing confirmed-notice row already supplies this hazard and its instruction.
      if (site.notices.some((n) => n.status === 'confirmed' &&
        (n.id === report.notice_id || n.source_ref === report.id))) continue
      const entry = row(`report:${report.id}`,
        displayLabel(report.confirmed_category ?? report.category))
      entry.report = report
      entry.factors.push(factor)
    } else {
      // A positive stored factor is evidence, not supervisor confirmation. Preserve
      // forecast, stale and simulated states instead of promoting them to observed.
      row(factor.factor, factor.factor === 'heat_index' ? 'Heat' : factorLabel(factor.factor))
        .factors.push(factor)
    }
  }
  return [...rows.values()]
}
