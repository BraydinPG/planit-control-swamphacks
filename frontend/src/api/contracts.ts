import type {
  Alert,
  Briefing,
  CrewReport,
  Explanation,
  HazardNotice,
  ReportCreate,
  ReportReview,
  SiteDetail,
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
    hazards: boolean
    ai: boolean
  }
  now?(): number
  sites(): Promise<SiteSummary[]>
  site(id: string): Promise<SiteRecord>
  alerts(): Promise<Alert[]>
  reports(): Promise<CrewReport[]>
  acknowledge(id: string): Promise<unknown>
  submit(input: ReportCreate, photo: File | null): Promise<CrewReport>
  review(id: string, input: ReportReview): Promise<CrewReport>
  confirm(id: string): Promise<unknown>
  instruct(id: string, instruction: string): Promise<unknown>
  briefing(id: string, fallback?: boolean): Promise<Briefing>
  explanation(id: string, fallback?: boolean): Promise<Explanation>
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
  constructor(status: number, message: string) {
    super(message)
    this.status = status
    this.name = 'ApiError'
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
