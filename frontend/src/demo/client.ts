import sitesJSON from '../fixtures/sites.json'
import detailJSON from '../fixtures/site-detail.json'
import reportsJSON from '../fixtures/reports.json'
import alertsJSON from '../fixtures/alerts.json'
import noticesJSON from '../fixtures/hazard-notices.json'
import briefingsJSON from '../fixtures/briefings.json'
import speciesJSON from '../fixtures/species-context.json'
import references from './generated/references.json'
import type {
  Account,
  Alert,
  Briefing,
  CrewReport,
  HazardNotice,
  JoinCode,
  SupervisorInvite,
  OrganizationTeams,
  ReportCreate,
  ReportReview,
  SiteSpeciesContext,
  SiteSummary,
  TeamCreate,
  TeamMember,
  TeamRoster,
  TeamUpdate,
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
      event_outlook: null,
      event_outlooks: [],
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
// Same alphabet as the backend: no 0/O or 1/I/L.
const CODE_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
function joinCode() {
  const pick = () =>
    CODE_ALPHABET[
      crypto.getRandomValues(new Uint32Array(1))[0] % CODE_ALPHABET.length
    ]
  const half = () => Array.from({ length: 4 }, pick).join('')
  return `${half()}-${half()}`
}
function demoRoster(): OrganizationTeams {
  const person = (
    id: string,
    name: string,
    role: 'crew' | 'supervisor' = 'crew',
  ): TeamMember => ({
    user_id: `demo|${id}`,
    name: `${name} (simulated)`,
    email: null,
    role,
    joined_at: '2026-10-10T14:00:00Z',
  })
  const teams = new Map<string, TeamRoster>()
  for (const site of sitesJSON as SiteSummary[])
    if (site.assigned_team && !teams.has(site.assigned_team.id))
      teams.set(site.assigned_team.id, {
        id: site.assigned_team.id,
        name: site.assigned_team.name,
        site_id: site.id,
        site_name: site.name,
        members: [],
        join_codes: [],
      })
  const [a, b, c] = [...teams.values()]
  a.members = [
    person('crew', 'Demo crew'),
    person('ana', 'Ana Ruiz'),
    person('dev', 'Dev Patel'),
  ]
  if (b) b.members = [person('kim', 'Kim Lee')]
  if (c) c.members = []
  return {
    organization_id: org,
    organization_name: 'Sunbelt Utility (simulated)',
    supervisors: [person('supervisor', 'Demo supervisor', 'supervisor')],
    teams: [...teams.values()],
  }
}

export class DemoClient implements Client {
  mode = 'demo' as const
  capabilities = {
    acknowledge: true,
    reports: true,
    reviewReports: true,
    hazards: true,
    briefings: true,
    team: true,
  }
  private state: DemoSnapshot
  // Simulated roster and join codes; kept in memory only, so a reload resets them.
  private roster = demoRoster()
  // Sites the simulated organization claimed (besides those its teams already hold).
  private claims = new Set<string>()
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
          // Saved before danger tiers existed: start over rather than hide alerts.
          value.alerts.every(
            (a: { danger_tier?: unknown }) => typeof a.danger_tier === 'number',
          ) &&
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
        'access_mat_deterioration',
        'wildlife',
        'flooding',
        'other',
      ].includes(input.category) ||
      (input.note?.length ?? 0) > 1000
    )
      throw new ApiError(422, 'Check report fields')
    // Same rule as the backend (T034B): a grade only for access mats, and
    // A means absent while B, C and D mean present.
    const mat = input.category === 'access_mat_deterioration'
    const grade = input.mat_condition ?? null
    if (
      mat !== (grade !== null) ||
      (grade !== null &&
        (!['A', 'B', 'C', 'D'].includes(grade) ||
          input.hazard_present !== (grade !== 'A')))
    )
      throw new ApiError(422, 'Access mat reports need a matching A-D grade')
    if (
      photo &&
      (!['image/jpeg', 'image/png', 'image/webp'].includes(photo.type) ||
        photo.size > 5 * 1024 * 1024)
    )
      throw new ApiError(422, 'Photo must be JPEG/PNG/WebP, at most 5 MB')
    // Nothing is sent until the supervisor accepts the report (see `review`).
    const site = this.state.details[input.site_id],
      id = 'demo-report-' + crypto.randomUUID()
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
      location_source: input.location_source ?? 'site',
      location_accuracy_m: input.location_accuracy_m ?? null,
      mat_condition: grade,
      site_distance_miles: null,
      enrichment: null,
      notice_id: null,
      created_at: this.time(),
    }
    if (photo) this.photoURLs.set(id, URL.createObjectURL(photo))
    this.state.reports.unshift(report)
    this.save()
    return clone(report)
  }
  async review(id: string, input: ReportReview) {
    this.supervisor()
    const r = this.state.reports.find((r) => r.id === id)
    if (!r || r.organization_id !== org)
      throw new ApiError(403, 'Report is outside the simulated organization')
    if (r.review_status !== 'pending')
      throw new ApiError(409, 'This report has already been reviewed')
    const accepted = input.decision === 'confirmed'
    r.review_status = input.decision
    r.reviewed_by = 'demo-supervisor'
    r.reviewed_at = this.time()
    r.confirmed_category = accepted ? (input.category ?? r.category) : null
    r.confirmed_severity = accepted ? (input.severity ?? null) : null
    const legacy = r.notice_id
      ? this.state.notices.find((n) => n.id === r.notice_id)
      : undefined
    if (accepted && r.hazard_present && legacy) {
      // Filed before reports were reviewed first: accepting confirms its notice.
      legacy.status = 'confirmed'
      legacy.confirmed_by = 'demo-supervisor'
      legacy.confirmed_at = this.time()
    } else if (accepted && r.hazard_present) {
      // Accepting sends the notice to every organization inside the radius. The
      // simulated demo has no Gemini, so it uses the category default.
      const category = r.confirmed_category ?? r.category
      const noticeId = 'demo-notice-' + crypto.randomUUID()
      r.notice_id = noticeId
      this.state.notices.unshift({
        id: noticeId,
        hazard_label: category.replaceAll('_', ' '),
        source: 'crew_report',
        source_ref: r.id,
        lat: r.lat,
        lon: r.lon,
        radius_miles: category === 'flooding' ? 5 : 1,
        radius_source: 'default',
        status: 'confirmed',
        created_at: this.time(),
        confirmed_by: 'demo-supervisor',
        confirmed_at: this.time(),
        suggested_instruction: null,
        instruction: null,
        instruction_sent_at: null,
        evidence: [
          {
            id: r.id,
            kind: 'report',
            label: 'Simulated crew report',
            observed_at: r.created_at,
          },
        ],
      })
    }
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
    if (n.status !== 'potential')
      throw new ApiError(409, 'This hazard has already been confirmed')
    if (n.source === 'crew_report') {
      const report = this.state.reports.find((r) => r.id === n.source_ref)
      if (
        !report ||
        !report.hazard_present ||
        report.notice_id !== n.id ||
        report.review_status !== 'pending'
      )
        throw new ApiError(409, 'The notice has no pending present report')
      report.review_status = 'confirmed'
      report.reviewed_by = 'demo-supervisor'
      report.reviewed_at = this.time()
      report.confirmed_category = report.category
    }
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
    if (n.instruction_sent_at)
      throw new ApiError(409, 'An instruction has already been sent')
    if (!instruction.trim() || instruction.trim().length > 500)
      throw new ApiError(422, 'Enter an instruction of 1–1000 characters')
    n.instruction = instruction.trim()
    n.instruction_sent_at = this.time()
    this.save()
    return clone(n)
  }
  async briefing(id: string) {
    this.allowed(id)
    const rows = (briefingsJSON as Briefing[])
      .filter((b) => b.site_id === id)
      .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
    return rows.length ? clone(rows[0]) : null
  }
  async briefings() {
    // Public archived fixture examples, including a template; never generated here.
    return clone(briefingsJSON as Briefing[])
  }
  async species(id: string) {
    this.allowed(id)
    // Recorded IPaC snapshot for the demo team site only; labeled simulated.
    if (!this.state.sites.find((s) => s.id === id)?.assigned_team) return null
    const fixture = speciesJSON as SiteSpeciesContext
    return fixture.site_id === id ? clone(fixture) : null
  }
  async me(): Promise<Account> {
    const team = this.roster.teams[0]
    return this.persona() === 'supervisor'
      ? {
          role: 'supervisor',
          // The preview supervisor also owns the simulated organization.
          is_owner: true,
          organization_id: org,
          organization_name: this.roster.organization_name,
          team_id: null,
          team_name: null,
          site_id: null,
        }
      : {
          role: 'crew',
          organization_id: org,
          organization_name: this.roster.organization_name,
          team_id: team.id,
          team_name: team.name,
          site_id: team.site_id,
        }
  }
  async team() {
    this.supervisor()
    const now = this.now()
    const held = new Map(
      this.roster.teams.filter((t) => t.site_id).map((t) => [t.site_id!, t.id]),
    )
    const claimed = new Set([...this.claims, ...held.keys()])
    return clone({
      ...this.roster,
      teams: this.roster.teams.map((t) => ({
        ...t,
        join_codes: t.join_codes.filter((c) => Date.parse(c.expires_at) > now),
      })),
      claimed_sites: this.state.sites
        .filter((s) => claimed.has(s.id))
        .map((s) => ({
          site_id: s.id,
          site_name: s.name,
          team_id: held.get(s.id) ?? null,
        })),
      unavailable_site_ids: this.state.sites
        .filter((s) => s.assigned_team && !held.has(s.id))
        .map((s) => s.id),
      is_owner: true,
      is_supervisor: true,
    })
  }
  async claimSite(siteId: string) {
    this.supervisor()
    const site = this.state.sites.find((s) => s.id === siteId)
    if (!site) throw new ApiError(404, "That site doesn't exist.")
    const ours = this.roster.teams.some((t) => t.site_id === siteId)
    if (site.assigned_team && !ours)
      throw new ApiError(409, 'Site claimed', {
        reason: 'claimed',
        detail: 'Another organization already claimed that site.',
      })
    this.claims.add(siteId)
  }
  async releaseSite(siteId: string) {
    this.supervisor()
    if (this.roster.teams.some((t) => t.site_id === siteId))
      throw new ApiError(409, 'Site has a team', {
        reason: 'has_team',
        detail: 'Move the team on this site to another site first.',
      })
    if (!this.claims.delete(siteId))
      throw new ApiError(404, "Your organization hasn't claimed that site")
  }
  async createOrganization(): Promise<Account> {
    throw new ApiError(
      409,
      'Simulated demo: preview accounts already have an organization. Creating one works with a live sign-in.',
    )
  }
  async removeSupervisor() {
    throw new ApiError(
      409,
      'Simulated demo: the preview supervisor stays. Removing a supervisor works with a live sign-in.',
    )
  }
  async createJoinCode(teamId: string) {
    this.supervisor()
    const team = this.roster.teams.find((t) => t.id === teamId)
    if (!team) throw new ApiError(404, 'Team not found in your organization')
    const now = this.now()
    const code: JoinCode = {
      code: joinCode(),
      team_id: teamId,
      created_at: new Date(now).toISOString(),
      expires_at: new Date(now + 7 * 24 * 3600 * 1000).toISOString(),
    }
    team.join_codes.unshift(code)
    return clone(code)
  }
  async revokeJoinCode(code: string) {
    this.supervisor()
    for (const t of this.roster.teams)
      t.join_codes = t.join_codes.filter((c) => c.code !== code)
  }
  private invites: SupervisorInvite[] = []
  async supervisorInvites() {
    this.supervisor()
    const now = this.now()
    return clone(this.invites.filter((i) => Date.parse(i.expires_at) > now))
  }
  async createSupervisorInvite() {
    this.supervisor()
    const now = this.now()
    const invite: SupervisorInvite = {
      code: joinCode(),
      created_at: new Date(now).toISOString(),
      expires_at: new Date(now + 7 * 24 * 3600 * 1000).toISOString(),
    }
    this.invites.unshift(invite)
    return clone(invite)
  }
  async revokeSupervisorInvite(code: string) {
    this.supervisor()
    this.invites = this.invites.filter((i) => i.code !== code)
  }
  async becomeSupervisor(): Promise<Account> {
    throw new ApiError(
      409,
      'Simulated demo: preview accounts already have an organization. Supervisor keys work with a live sign-in.',
    )
  }
  private freeSite(siteId: string | null | undefined, teamId: string | null) {
    if (!siteId) return null
    const site = this.state.sites.find((s) => s.id === siteId)
    if (!site)
      throw new ApiError(404, 'Site not found', {
        reason: 'site_not_found',
        detail: "That site doesn't exist.",
      })
    const holder = this.roster.teams.find((t) => t.site_id === siteId)
    if ((holder && holder.id !== teamId) || (!holder && site.assigned_team))
      throw new ApiError(409, 'Site taken', {
        reason: 'site_taken',
        detail: 'That site already has a team.',
      })
    if (!holder && !this.claims.has(siteId))
      throw new ApiError(409, 'Site not claimed', {
        reason: 'not_claimed',
        detail: 'Claim that site for your organization first.',
      })
    return site
  }
  async renameOrganization(name: string) {
    this.supervisor()
    this.roster.organization_name = name.trim()
    return this.team()
  }
  async createTeam(input: TeamCreate) {
    this.supervisor()
    const site = this.freeSite(input.site_id, null)
    const team: TeamRoster = {
      id: `demo-team-${crypto.randomUUID().slice(0, 8)}`,
      name: input.name.trim(),
      site_id: site?.id ?? null,
      site_name: site?.name ?? null,
      members: [],
      join_codes: [],
    }
    this.roster.teams.push(team)
    return clone(team)
  }
  async updateTeam(id: string, input: TeamUpdate) {
    this.supervisor()
    const team = this.roster.teams.find((t) => t.id === id)
    if (!team) throw new ApiError(404, 'Team not found in your organization')
    if (input.name) team.name = input.name.trim()
    if ('site_id' in input) {
      const site = this.freeSite(input.site_id, id)
      // A site the team leaves stays claimed.
      if (team.site_id && team.site_id !== site?.id) this.claims.add(team.site_id)
      team.site_id = site?.id ?? null
      team.site_name = site?.name ?? null
    }
    return clone(team)
  }
  async deleteTeam(id: string) {
    this.supervisor()
    const team = this.roster.teams.find((t) => t.id === id)
    if (!team) throw new ApiError(404, 'Team not found in your organization')
    if (team.members.length)
      throw new ApiError(409, 'Team has members', {
        reason: 'has_members',
        detail: "Move or remove this team's members first.",
      })
    this.roster.teams = this.roster.teams.filter((t) => t.id !== id)
  }
  async removeMember(teamId: string, userId: string) {
    this.supervisor()
    const team = this.roster.teams.find((t) => t.id === teamId)
    if (!team || !team.members.some((m) => m.user_id === userId))
      throw new ApiError(404, "That person isn't on this team")
    team.members = team.members.filter((m) => m.user_id !== userId)
  }
  async join(): Promise<Account> {
    throw new ApiError(
      409,
      'Simulated demo: preview accounts already belong to a team. Join codes work with a live sign-in.',
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
