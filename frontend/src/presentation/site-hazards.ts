import type { SiteRecord } from '../api/contracts'
import type { Alert, CrewReport, FactorContribution, HazardNotice } from '../types/api'
import { displayLabel, factorLabel } from './display'

export interface SiteHazard {
  id: string
  label: string
  factors: FactorContribution[]
  alerts: Alert[]
  notices: HazardNotice[]
  report?: CrewReport
}

// Only explicit names/categories are combined. Unknown notices keep their own ID;
// Flood and Flash Flood stay distinct, and every instruction/evidence record survives.
const hazardAliases: Record<string, string> = {
  flood: 'flood', flooding: 'flood', flash_flood: 'flash_flood',
  flash_flooding: 'flash_flood', lightning: 'lightning',
  lightning_stop_work: 'lightning', heat: 'heat_index', heat_index: 'heat_index',
  hurricane: 'hurricane', earthquake: 'earthquake', wildlife: 'wildlife',
  broken_electrical_pole: 'broken_pole_downed_line',
  broken_pole_downed_line: 'broken_pole_downed_line',
  on_site_fire: 'on_site_fire', access_mat_deterioration: 'access_mat_deterioration',
  tornado: 'tornado', tropical_storm: 'tropical_storm',
  severe_thunderstorm: 'severe_thunderstorm',
}
const categoryKey = (label: string) =>
  hazardAliases[label.trim().toLowerCase().replace(/[\s-]+/g, '_')]
const hazardLabel = (key: string) => key === 'heat_index' ? 'Heat' :
  key === 'flood' ? 'Flooding' : factorLabel(key)

const alertKey = (alert: Alert) =>
  alert.rule === 'lightning_stop_work' ? 'lightning' :
    alert.rule === 'heat' ? 'heat_index' : alert.rule

/** Read-only projection of backend decisions. No thresholds, totals or alert lifecycle here. */
export function siteHazards(site: SiteRecord): SiteHazard[] {
  const rows = new Map<string, SiteHazard>()
  const row = (id: string, label: string) => {
    if (!rows.has(id)) rows.set(id, { id, label, factors: [], alerts: [], notices: [] })
    return rows.get(id)!
  }
  // Include every active tier, even when a higher tier is the primary alert card.
  // Feed failure or an elapsed timer must never hide an authoritative active alert.
  for (const alert of site.alerts) {
    if (alert.site_id !== site.id || alert.state !== 'active') continue
    const key = alertKey(alert)
    row(key, hazardLabel(key)).alerts.push(alert)
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
      const category = report.confirmed_category ?? report.category
      const key = categoryKey(category) ?? `report:${report.id}`
      const entry = row(key, categoryKey(category) ? hazardLabel(key) : displayLabel(category))
      entry.report = report
      entry.factors.push(factor)
    } else {
      // A positive stored factor is evidence, not supervisor confirmation. Preserve
      // forecast, stale and simulated states instead of promoting them to observed.
      row(factor.factor, hazardLabel(factor.factor))
        .factors.push(factor)
    }
  }
  for (const notice of site.notices) {
    if (notice.status !== 'confirmed') continue
    const report = site.reports.find((r) => r.site_id === site.id &&
      r.hazard_present && r.review_status === 'confirmed' &&
      (r.notice_id === notice.id || r.id === notice.source_ref))
    const key = report
      ? categoryKey(report.confirmed_category ?? report.category) ?? `report:${report.id}`
      : categoryKey(notice.hazard_label) ?? `notice:${notice.id}`
    row(key, key.includes(':') ? displayLabel(notice.hazard_label) : hazardLabel(key))
      .notices.push(notice)
  }
  return [...rows.values()]
}
