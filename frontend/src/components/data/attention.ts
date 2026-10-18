import type {
  Alert,
  CrewReport,
  HazardNotice,
  SiteSummary,
} from '../../types/api'
import type { RiskShape } from './Risk'
import { evidenceOf } from './evidence'
import { displayLabel, reportCategories } from '../../presentation/display'

/** What waits on a supervisor, for the Overview (spec.md sections 3 and 7). */
export type Shape = Parameters<typeof RiskShape>[0]['kind']
export interface AttentionItem {
  key: string
  shape: Shape
  title: string
  detail: string
  href: string
  action: string
}

const categoryNames = reportCategories
const rule = displayLabel

/** Everything waiting on the supervisor, most urgent first. */
export function attentionItems(
  sites: SiteSummary[],
  alerts: Alert[],
  reports: CrewReport[],
  notices: { notice: HazardNotice; site: SiteSummary }[],
): AttentionItem[] {
  const name = (id: string) => sites.find((s) => s.id === id)?.name ?? id
  return [
    ...alerts
      .filter((a) => a.state === 'active')
      .map((a) => ({
        key: `alert:${a.id}`,
        shape: 'stop' as Shape,
        title: `${rule(a.rule)} alert`,
        detail: name(a.site_id),
        href: `#/supervisor/alerts/${encodeURIComponent(a.id)}`,
        action: 'Review alert',
      })),
    ...notices.map(({ notice, site }) => ({
      key: `notice:${notice.id}`,
      shape: 'caution' as Shape,
      title: `Potential hazard: ${displayLabel(notice.hazard_label)}`,
      detail: `${site.name} · within ${notice.radius_miles} mi`,
      href: `#/supervisor/sites/${encodeURIComponent(site.id)}`,
      action: 'Confirm or dismiss',
    })),
    ...reports
      .filter((r) => r.review_status === 'pending' && !r.hazard_present)
      .map((r) => ({
        key: `report:${r.id}`,
        shape: 'nodata' as Shape,
        title: `Reported absent: ${categoryNames[r.category]}`,
        detail: name(r.site_id),
        href: '#/supervisor/reports',
        action: 'Review report',
      })),
  ]
}

/** The three highest scored sites; unscored or no-evidence sites never rank as risky. */
export function highestRisk(sites: SiteSummary[], count = 3) {
  return sites
    .filter((s) => s.risk_score !== null && evidenceOf(s) !== 'none')
    .filter((s) => !s.top_factors.some((f) => f.factor === 'model'))
    .sort((a, b) => (b.risk_score ?? 0) - (a.risk_score ?? 0))
    .slice(0, count)
}
