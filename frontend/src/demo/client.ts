import sitesJSON from '../fixtures/sites.json'
import detailJSON from '../fixtures/site-detail.json'
import reportsJSON from '../fixtures/reports.json'
import alertsJSON from '../fixtures/alerts.json'
import noticesJSON from '../fixtures/hazard-notices.json'
import briefingsJSON from '../fixtures/briefings.json'
import explanationsJSON from '../fixtures/explanations.json'
import references from './generated/references.json'
import type {
  Alert,
  Briefing,
  CrewReport,
  Explanation,
  HazardNotice,
  ReportCreate,
  ReportReview,
  SiteSummary,
} from '../types/api'
import {
  ApiError,
  sortSites,
  validCoordinate,
  type Client,
  type DemoSnapshot,
  type Persona,
  type SiteRecord,
} from '../api/contracts'

export const DEMO_KEY = 'planit:frontend-demo:v1'
export const DEMO_AS_OF = Date.parse('2026-10-17T18:00:00Z')
const clone = <T>(value: T): T => structuredClone(value)
const assigned = 'site-demo-everglades'
const org = 'org-sunbelt'
function browserStorage(): Storage | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage
  } catch {
    return null
  }
}
export function distanceMiles(
  a: { lat: number; lon: number },
  b: { lat: number; lon: number },
) {
  const r = Math.PI / 180,
    dlat = (b.lat - a.lat) * r,
    dlon = (b.lon - a.lon) * r
  return (
    3958.8 *
    2 *
    Math.asin(
      Math.sqrt(
        Math.sin(dlat / 2) ** 2 +
          Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(dlon / 2) ** 2,
      ),
    )
  )
}
export function initialDemo(): DemoSnapshot {
  const referenceSites: SiteSummary[] = references.map((r) => ({
    id: r.id,
    name: r.site.name,
    lat: r.site.lat,
    lon: r.site.lon,
    assigned_team: null,
    risk_score: null,
    risk_level: null,
    updated_at: null,
    active_alerts: 0,
    top_factors: [],
    data_completeness: 0,
    model_version: 'unscored-reference-only',
  }))
  const sites = clone([...(sitesJSON as SiteSummary[]), ...referenceSites])
  const details: Record<string, SiteRecord> = {}
  sites.forEach((s) => {
    details[s.id] = {
      ...s,
      location_type: 'power_plant',
      source: referenceSites.some((r) => r.id === s.id)
        ? 'EIA-860M reference export; no active job or live conditions verified'
        : 'Canonical simulated fixture',
      region: null,
      observations: [],
      score: null,
      alerts: [],
      reports: [],
      notices: [],
    }
  })
  details[assigned] = clone(detailJSON as SiteRecord)
  return {
    version: 1,
    started: Date.now(),
    sites,
    details,
    alerts: clone(alertsJSON as Alert[]),
    reports: clone(reportsJSON as CrewReport[]),
    notices: clone(noticesJSON as HazardNotice[]),
  }
}
export class DemoClient implements Client {
  mode = 'demo' as const
  writesAvailable = true
  private state: DemoSnapshot
  private photoURLs = new Map<string, string>()
  private persona: () => Persona
  private storage: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'> | null
  constructor(
    persona: () => Persona,
    storage: Pick<
      Storage,
      'getItem' | 'setItem' | 'removeItem'
    > | null = browserStorage(),
  ) {
    this.persona = persona
    this.storage = storage
    this.state = initialDemo()
    try {
      const raw = storage?.getItem(DEMO_KEY)
      if (raw && raw.length < 2000000) {
        const value = JSON.parse(raw)
        if (
          value.version === 1 &&
          Array.isArray(value.sites) &&
          value.sites.length === 55 &&
          Array.isArray(value.reports) &&
          Array.isArray(value.notices) &&
          Array.isArray(value.alerts) &&
          typeof value.started === 'number' &&
          value.details
        )
          this.state = value
      }
    } catch {
      /* Corrupt demo storage resets only this namespace. */
    }
  }
  now() {
    return DEMO_AS_OF + Math.max(0, Date.now() - this.state.started)
  }
  private time() {
    return new Date(this.now()).toISOString()
  }
  private save() {
    try {
      if (!this.storage) throw new Error('Storage unavailable')
      this.storage.setItem(DEMO_KEY, JSON.stringify(this.state))
    } catch {
      throw new ApiError(
        0,
        'Demo storage is unavailable; this change exists in memory only and will not survive reload.',
      )
    }
  }
  private allowed(id: string) {
    if (
      !this.state.details[id] ||
      (this.persona() === 'crew' && id !== assigned)
    )
      throw new ApiError(403, 'Demo persona is not assigned to this site')
  }
  private supervisor() {
    if (this.persona() !== 'supervisor')
      throw new ApiError(403, 'Supervisor preview required')
  }
  reset() {
    this.state = initialDemo()
    for (const url of this.photoURLs.values()) URL.revokeObjectURL(url)
    this.photoURLs.clear()
    this.save()
  }
  photo(id: string) {
    return this.photoURLs.get(id) ?? null
  }
  async sites() {
    return sortSites(
      clone(
        this.state.sites.filter(
          (s) => this.persona() === 'supervisor' || s.id === assigned,
        ),
      ),
      true,
    )
  }
  async site(id: string) {
    this.allowed(id)
    const detail = clone(this.state.details[id])
    return {
      ...detail,
      alerts: clone(this.state.alerts.filter((a) => a.site_id === id)),
      reports: clone(this.state.reports.filter((r) => r.site_id === id)),
      notices: clone(
        this.state.notices.filter(
          (n) => distanceMiles(detail, n) <= n.radius_miles,
        ),
      ),
    }
  }
  async alerts() {
    return clone(
      this.state.alerts.filter(
        (a) => this.persona() === 'supervisor' || a.site_id === assigned,
      ),
    )
  }
  async reports() {
    return clone(
      this.state.reports.filter(
        (r) => this.persona() === 'supervisor' || r.site_id === assigned,
      ),
    )
  }
  async acknowledge(id: string) {
    const a = this.state.alerts.find((a) => a.id === id)
    if (!a) throw new ApiError(404, 'Alert not found')
    this.allowed(a.site_id)
    const user = `demo-${this.persona()}`
    if (!a.acknowledgements.some((x) => x.user_id === user))
      a.acknowledgements.push({
        id: crypto.randomUUID(),
        alert_id: id,
        user_id: user,
        acknowledged_at: this.time(),
      })
    this.save()
    return clone(a)
  }
  async submit(input: ReportCreate, photo: File | null) {
    this.allowed(input.site_id)
    if (
      !validCoordinate(input.lat, true) ||
      !validCoordinate(input.lon, false) ||
      typeof input.hazard_present !== 'boolean' ||
      ![
        'broken_pole_downed_line',
        'on_site_fire',
        'wildlife',
        'flooding',
        'other',
      ].includes(input.category) ||
      (input.note?.length ?? 0) > 1000
    )
      throw new ApiError(422, 'Check report fields')
    if (
      photo &&
      (!['image/jpeg', 'image/png', 'image/webp'].includes(photo.type) ||
        photo.size > 5 * 1024 * 1024)
    )
      throw new ApiError(422, 'Photo must be JPEG/PNG/WebP, at most 5 MB')
    const site = this.state.details[input.site_id],
      id = 'demo-report-' + crypto.randomUUID(),
      noticeId = input.hazard_present
        ? 'demo-notice-' + crypto.randomUUID()
        : null
    const report: CrewReport = {
      ...input,
      id,
      organization_id: org,
      team_id: site.assigned_team?.id ?? 'demo-team',
      reporter_id: `demo-${this.persona()}`,
      note: input.note ?? null,
      photo_url: null,
      review_status: 'pending',
      reviewed_by: null,
      reviewed_at: null,
      confirmed_category: null,
      confirmed_severity: null,
      enrichment: null,
      notice_id: noticeId,
      created_at: this.time(),
    }
    if (photo) this.photoURLs.set(id, URL.createObjectURL(photo))
    this.state.reports.unshift(report)
    if (noticeId)
      this.state.notices.unshift({
        id: noticeId,
        hazard_label: input.category.replaceAll('_', ' '),
        source: 'crew_report',
        source_ref: id,
        lat: input.lat,
        lon: input.lon,
        radius_miles: input.category === 'flooding' ? 5 : 1,
        radius_source: 'default',
        status: 'potential',
        created_at: this.time(),
        confirmed_by: null,
        confirmed_at: null,
        suggested_instruction: null,
        instruction: null,
        instruction_sent_at: null,
        evidence: [
          {
            id,
            kind: 'report',
            label: 'Simulated crew report',
            observed_at: this.time(),
          },
        ],
      })
    this.save()
    return clone(report)
  }
  async review(id: string, input: ReportReview) {
    this.supervisor()
    const r = this.state.reports.find((r) => r.id === id)
    if (!r || r.organization_id !== org)
      throw new ApiError(403, 'Report is outside the simulated organization')
    r.review_status = input.decision
    r.reviewed_by = 'demo-supervisor'
    r.reviewed_at = this.time()
    r.confirmed_category =
      input.decision === 'confirmed' ? (input.category ?? r.category) : null
    r.confirmed_severity =
      input.decision === 'confirmed' ? (input.severity ?? null) : null
    this.save()
    return clone(r)
  }
  private relevantNotice(id: string) {
    const notice = this.state.notices.find((n) => n.id === id)
    if (
      !notice ||
      !this.state.sites.some(
        (s) =>
          s.assigned_team?.organization_id === org &&
          distanceMiles(s, notice) <= notice.radius_miles,
      )
    )
      throw new ApiError(403, 'No simulated team received this notice')
    return notice
  }
  async confirm(id: string) {
    this.supervisor()
    const n = this.relevantNotice(id)
    if (n.confirmed_by && n.confirmed_by !== 'demo-supervisor')
      throw new ApiError(403, 'Another supervisor owns this instruction')
    n.status = 'confirmed'
    n.confirmed_by = 'demo-supervisor'
    n.confirmed_at = this.time()
    n.suggested_instruction = null
    this.save()
    return { notice: clone(n), suggested_instruction: null, generated_by: null }
  }
  async instruct(id: string, instruction: string) {
    this.supervisor()
    const n = this.relevantNotice(id)
    if (n.status !== 'confirmed' || n.confirmed_by !== 'demo-supervisor')
      throw new ApiError(
        403,
        'Only the confirming supervisor may send instructions',
      )
    if (!instruction.trim() || instruction.length > 1000)
      throw new ApiError(422, 'Enter an instruction of 1–1000 characters')
    n.instruction = instruction.trim()
    n.instruction_sent_at = this.time()
    this.save()
    return clone(n)
  }
  async briefing(id: string, fallback = false) {
    this.allowed(id)
    const b = clone(
      (briefingsJSON as Briefing[]).find(
        (b) => b.generated_by === (fallback ? 'fallback' : 'gemini'),
      )!,
    )
    if (id !== assigned)
      throw new ApiError(503, 'No briefing fixture for this reference site')
    return b
  }
  async explanation(id: string, fallback = false) {
    this.allowed(id)
    if (id !== assigned)
      throw new ApiError(503, 'No explanation fixture for this reference site')
    return clone(
      (explanationsJSON as Explanation[]).find(
        (e) => e.generated_by === (fallback ? 'fallback' : 'gemini'),
      )!,
    )
  }
  replay(kind: 'strike' | 'cleared') {
    const a = this.state.alerts.find((a) => a.id === 'alert-ltg-demo')!
    if (kind === 'cleared') a.state = 'cleared'
    else {
      a.state = 'active'
      a.latest_event_at = this.time()
      a.clear_after = new Date(this.now() + 30 * 60 * 1000).toISOString()
      a.evidence.push({
        id: 'demo-strike-' + crypto.randomUUID(),
        kind: 'observation',
        label: 'Explicit simulated server strike update',
        observed_at: a.latest_event_at,
      })
    }
    this.save()
  }
}
