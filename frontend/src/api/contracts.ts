import type {
  Account,
  Alert,
  Briefing,
  CrewReport,
  HazardNotice,
  HazardConfirmResponse,
  JoinCode,
  SupervisorInvite,
  OrganizationTeams,
  TeamCreate,
  TeamRoster,
  TeamUpdate,
  ReportCreate,
  ReportReview,
  SiteDetail,
  SiteSpeciesContext,
  SiteSummary,
} from '../types/api'

/** Main now includes Rudra's T050 canonical EventOutlook; no independent mirror. */
export type SiteRecord = SiteDetail
export type Persona = 'crew' | 'supervisor'
export interface Client {
  mode: 'demo' | 'live'
  capabilities: {
    acknowledge: boolean
    reports: boolean
    reviewReports: boolean
    hazards: boolean
    briefings: boolean
    team: boolean
  }
  now?(): number
  sites(): Promise<SiteSummary[]>
  site(id: string): Promise<SiteRecord>
  alerts(): Promise<Alert[]>
  reports(): Promise<CrewReport[]>
  /** A report's private photo, fetched with the session token. Live API only. */
  reportPhoto?(id: string): Promise<Blob>
  acknowledge(id: string): Promise<Alert>
  submit(input: ReportCreate, photo: File | null): Promise<CrewReport>
  review(id: string, input: ReportReview): Promise<CrewReport>
  confirm(id: string): Promise<HazardConfirmResponse>
  instruct(id: string, instruction: string): Promise<HazardNotice>
  briefing(id: string): Promise<Briefing | null>
  briefings(): Promise<Briefing[]>
  /** Regional species context for a team site; null when the site has no team. */
  species(id: string): Promise<SiteSpeciesContext | null>
  /** Where the signed-in account belongs; nulls until it joins a team. */
  me(): Promise<Account>
  /** Supervisor: the organization's supervisors, teams, members and active join codes. */
  team(): Promise<OrganizationTeams>
  createJoinCode(teamId: string): Promise<JoinCode>
  revokeJoinCode(code: string): Promise<void>
  /** Crew account with no team joins the team behind a code. */
  join(code: string): Promise<Account>
  /** New account redeems a supervisor key and starts its own organization. */
  becomeSupervisor(code: string, organizationName: string): Promise<Account>
  /** Supervisor: their one-use supervisor keys that can still be used. */
  supervisorInvites(): Promise<SupervisorInvite[]>
  createSupervisorInvite(): Promise<SupervisorInvite>
  revokeSupervisorInvite(code: string): Promise<void>
  /** Supervisor: rename their organization. */
  renameOrganization(name: string): Promise<OrganizationTeams>
  /** Supervisor: add, rename or move (site), and remove teams in their organization. */
  createTeam(input: TeamCreate): Promise<TeamRoster>
  updateTeam(id: string, input: TeamUpdate): Promise<TeamRoster>
  deleteTeam(id: string): Promise<void>
  removeMember(teamId: string, userId: string): Promise<void>
}
export interface DemoSnapshot {
  version: 1
  started: number
  sites: SiteSummary[]
  details: Record<string, SiteRecord>
  alerts: Alert[]
  reports: CrewReport[]
  notices: HazardNotice[]
}
export class ApiError extends Error {
  status: number
  /** Machine-readable reason the backend gave, e.g. `no_supervisor`. */
  reason?: string
  /** The backend's own explanation, shown instead of the generic status text. */
  detail?: string
  constructor(
    status: number,
    message: string,
    server?: { reason: string; detail: string },
  ) {
    super(message)
    this.status = status
    this.name = 'ApiError'
    this.reason = server?.reason
    this.detail = server?.detail
  }
}
export function validCoordinate(value: number, latitude: boolean) {
  return Number.isFinite(value) && Math.abs(value) <= (latitude ? 90 : 180)
}
export function sortSites(sites: SiteSummary[], excludeLegacy = false) {
  const score = (s: SiteSummary) =>
    excludeLegacy && s.top_factors.some((f) => f.factor === 'model')
      ? null
      : s.risk_score
  return [...sites].sort(
    (a, b) =>
      Number(!a.assigned_team) - Number(!b.assigned_team) ||
      Number(score(a) === null) - Number(score(b) === null) ||
      (score(b) ?? 0) - (score(a) ?? 0) ||
      // Same order as the backend: at equal scores, less evidence ranks first, so an
      // unknown zero never sinks below a fully observed zero.
      (score(a) === null ? 0 : a.data_completeness) -
        (score(b) === null ? 0 : b.data_completeness) ||
      a.name.localeCompare(b.name),
  )
}
export function countdown(alert: Alert, now: number) {
  if (alert.state !== 'active')
    return 'Server reports cleared; this is not work authorization.'
  if (!alert.clear_after || !Number.isFinite(Date.parse(alert.clear_after)))
    return 'No countdown supplied by server.'
  const seconds = Math.ceil((Date.parse(alert.clear_after) - now) / 1000)
  return seconds > 0
    ? `${Math.floor(seconds / 60)}m ${seconds % 60}s remaining in server window`
    : 'Window elapsed; waiting for authoritative server state. Alert remains active.'
}
