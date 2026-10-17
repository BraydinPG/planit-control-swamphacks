import { ApiError } from './contracts'
import type {
  Account,
  Briefing,
  CrewReport,
  HazardNotice,
  HazardConfirmResponse,
  JoinCode,
  OrganizationTeams,
  TeamRoster,
  SiteSpeciesContext,
} from '../types/api'

export const record = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v)
export const text = (v: unknown): v is string => typeof v === 'string'
export const date = (v: unknown): v is string =>
  text(v) && /T.*(Z|[+-]\d{2}:\d{2})$/.test(v) && Number.isFinite(Date.parse(v))
export const strings = (v: unknown): v is string[] =>
  Array.isArray(v) && v.every(text)
export const evidence = (v: unknown) =>
  Array.isArray(v) &&
  v.every(
    (e) =>
      record(e) &&
      text(e.id) &&
      text(e.label) &&
      [
        'observation',
        'alert',
        'report',
        'score_factor',
        'model_output',
        'notice',
        // Trusted start of a confirmed event, written server-side (T050A).
        'event_start',
      ].includes(String(e.kind)) &&
      (e.observed_at === null || date(e.observed_at)),
  )
const risk = (v: unknown) =>
  ['low', 'moderate', 'high', 'critical'].includes(String(v))
/** Null, or a number from 0 to `max` (T058C index, points, completeness). */
const inRange = (v: unknown, max: number) =>
  v === null ||
  (typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= max)
const role = (v: unknown) => v === 'crew' || v === 'supervisor'
const nullable = (v: unknown) => v === null || text(v)
export function validateAccount(v: unknown): Account {
  if (
    !record(v) ||
    !role(v.role) ||
    ![
      'organization_id',
      'organization_name',
      'team_id',
      'team_name',
      'site_id',
    ].every((k) => nullable(v[k]))
  )
    throw new ApiError(502, 'Invalid account response')
  return v as unknown as Account
}
const codeShape = /^[A-Z2-9]{4}-[A-Z2-9]{4}$/
export function validateJoinCode(v: unknown): JoinCode {
  if (
    !record(v) ||
    !text(v.code) ||
    !codeShape.test(v.code) ||
    !text(v.team_id) ||
    !date(v.created_at) ||
    !date(v.expires_at)
  )
    throw new ApiError(502, 'Invalid join code response')
  return v as unknown as JoinCode
}
export function validateTeamRoster(v: unknown): TeamRoster {
  if (
    !record(v) ||
    !text(v.id) ||
    !text(v.name) ||
    !nullable(v.site_id) ||
    !nullable(v.site_name) ||
    !Array.isArray(v.members) ||
    !v.members.every(member) ||
    !Array.isArray(v.join_codes) ||
    !v.join_codes.every((c) => {
      try {
        return Boolean(validateJoinCode(c))
      } catch {
        return false
      }
    })
  )
    throw new ApiError(502, 'Invalid team response')
  return v as unknown as TeamRoster
}
const member = (v: unknown) =>
  record(v) &&
  text(v.user_id) &&
  nullable(v.name) &&
  nullable(v.email) &&
  role(v.role) &&
  (v.joined_at === null || date(v.joined_at))
export function validateTeams(v: unknown): OrganizationTeams {
  if (
    !record(v) ||
    !text(v.organization_id) ||
    !text(v.organization_name) ||
    !Array.isArray(v.supervisors) ||
    !v.supervisors.every(member) ||
    !Array.isArray(v.teams) ||
    !v.teams.every((t) => {
      try {
        return Boolean(validateTeamRoster(t))
      } catch {
        return false
      }
    })
  )
    throw new ApiError(502, 'Invalid team response')
  return v as unknown as OrganizationTeams
}
export function validateBriefing(v: unknown, site?: string): Briefing {
  if (
    !record(v) ||
    !text(v.id) ||
    !text(v.summary) ||
    !(v.site_id === null || text(v.site_id)) ||
    !(v.organization_id === null || text(v.organization_id)) ||
    (site !== undefined && v.site_id !== site) ||
    !date(v.created_at) ||
    !date(v.forecast_window_start) ||
    !date(v.forecast_window_end) ||
    Date.parse(v.forecast_window_end) <= Date.parse(v.forecast_window_start) ||
    !risk(v.risk_level) ||
    !inRange(v.risk_score, 10) ||
    !inRange(v.data_completeness, 1) ||
    !['gemini', 'fallback'].includes(String(v.generated_by)) ||
    !strings(v.unknowns) ||
    !evidence(v.evidence) ||
    !Array.isArray(v.hazards) ||
    !v.hazards.every(
      (h) =>
        record(h) &&
        text(h.hazard) &&
        inRange(h.points, 10) &&
        strings(h.evidence_ids),
    ) ||
    !Array.isArray(v.recommended_actions) ||
    !v.recommended_actions.every(
      (a) => record(a) && text(a.action) && strings(a.evidence_ids),
    )
  )
    throw new ApiError(
      502,
      'Invalid stored briefing response. No demo data was substituted.',
    )
  return v as unknown as Briefing
}

const nullableText = (v: unknown) => v === null || text(v)
const nullableDistance = (v: unknown) =>
  v === null || (typeof v === 'number' && Number.isFinite(v) && v >= 0)
const points = (v: unknown) =>
  Array.isArray(v) &&
  v.every((p) => record(p) && text(p.statement) && strings(p.evidence_ids))
/** T060 report analysis: complete with a verdict, or unavailable. */
const analysis = (v: unknown) =>
  record(v) &&
  v.needs_review === true &&
  ['gemini', 'fallback'].includes(String(v.generated_by)) &&
  date(v.analyzed_at) &&
  points(v.supporting) &&
  points(v.contradicting) &&
  strings(v.also_visible) &&
  strings(v.unknowns) &&
  evidence(v.evidence) &&
  (v.suggested_category === null || category(v.suggested_category)) &&
  (v.severity_suggestion === null ||
    ['low', 'moderate', 'high'].includes(String(v.severity_suggestion))) &&
  (v.confidence === null ||
    (typeof v.confidence === 'number' &&
      v.confidence >= 0 &&
      v.confidence <= 1)) &&
  (v.status === 'unavailable'
    ? v.verdict === null
    : v.status === 'complete' &&
      ['supports', 'contradicts', 'inconclusive'].includes(String(v.verdict)) &&
      text(v.summary))
const nullableDate = (v: unknown) => v === null || date(v)
const category = (v: unknown) =>
  [
    'broken_pole_downed_line',
    'on_site_fire',
    'wildlife',
    'flooding',
    'other',
  ].includes(String(v))
export function validateReport(v: unknown, id?: string): CrewReport {
  if (
    !record(v) ||
    !['id', 'site_id', 'organization_id', 'team_id', 'reporter_id'].every(
      (k) => text(v[k]) && v[k],
    ) ||
    (id !== undefined && v.id !== id) ||
    !category(v.category) ||
    typeof v.hazard_present !== 'boolean' ||
    !Number.isFinite(v.lat) ||
    Math.abs(v.lat as number) > 90 ||
    !Number.isFinite(v.lon) ||
    Math.abs(v.lon as number) > 180 ||
    !['pending', 'confirmed', 'rejected'].includes(String(v.review_status)) ||
    !['note', 'photo_url', 'notice_id', 'reviewed_by'].every((k) =>
      nullableText(v[k]),
    ) ||
    !nullableDate(v.reviewed_at) ||
    !date(v.created_at) ||
    !(v.confirmed_category === null || category(v.confirmed_category)) ||
    !(
      v.confirmed_severity === null ||
      ['low', 'moderate', 'high'].includes(String(v.confirmed_severity))
    ) ||
    !(
      v.location_source === null ||
      ['device', 'site', 'pin'].includes(String(v.location_source))
    ) ||
    !nullableDistance(v.location_accuracy_m) ||
    !nullableDistance(v.site_distance_miles) ||
    !(v.enrichment === null || analysis(v.enrichment))
  )
    throw new ApiError(
      502,
      'Invalid report response. Refresh before retrying; the server may have saved the operation.',
    )
  return v as unknown as CrewReport
}
export function validateNotice(v: unknown, id?: string): HazardNotice {
  if (
    !record(v) ||
    !text(v.id) ||
    (id !== undefined && v.id !== id) ||
    !text(v.hazard_label) ||
    !text(v.source_ref) ||
    !['feed', 'crew_report'].includes(String(v.source)) ||
    !['gemini', 'default'].includes(String(v.radius_source)) ||
    !Number.isFinite(v.lat) ||
    Math.abs(v.lat as number) > 90 ||
    !Number.isFinite(v.lon) ||
    Math.abs(v.lon as number) > 180 ||
    typeof v.radius_miles !== 'number' ||
    !(v.radius_miles > 0 && v.radius_miles <= 50) ||
    !['potential', 'confirmed'].includes(String(v.status)) ||
    !date(v.created_at) ||
    !nullableDate(v.confirmed_at) ||
    !nullableDate(v.instruction_sent_at) ||
    !['confirmed_by', 'suggested_instruction', 'instruction'].every((k) =>
      nullableText(v[k]),
    ) ||
    !evidence(v.evidence) ||
    (v.status === 'potential' &&
      [
        v.confirmed_by,
        v.confirmed_at,
        v.suggested_instruction,
        v.instruction,
        v.instruction_sent_at,
      ].some((x) => x !== null)) ||
    (v.status === 'confirmed' && (!v.confirmed_by || !date(v.confirmed_at))) ||
    (v.instruction === null) !== (v.instruction_sent_at === null)
  )
    throw new ApiError(
      502,
      'Invalid hazard notice response. Refresh before retrying; no local confirmation was applied.',
    )
  return v as unknown as HazardNotice
}
export function validateConfirmation(
  v: unknown,
  id: string,
): HazardConfirmResponse {
  if (!record(v)) throw new ApiError(502, 'Invalid confirmation response')
  const notice = validateNotice(v.notice, id)
  if (
    notice.status !== 'confirmed' ||
    !nullableText(v.suggested_instruction) ||
    v.suggested_instruction !== notice.suggested_instruction ||
    !(
      v.generated_by === null ||
      ['gemini', 'fallback'].includes(String(v.generated_by))
    )
  )
    throw new ApiError(
      502,
      'Invalid confirmation response. Refresh before retrying.',
    )
  return v as unknown as HazardConfirmResponse
}

const dataStates = [
  'observed',
  'forecast',
  'crew_reported',
  'simulated',
  'stale',
  'unavailable',
]
const optionalText = (v: unknown) => v === null || text(v)
/**
 * GET /api/sites/{id}/species. Background species context may never claim a crew
 * report: `confirmed_report` is valid only on `wildlife_reports`.
 */
export function validateSpeciesContext(
  v: unknown,
  site: string,
): SiteSpeciesContext {
  const valid =
    record(v) &&
    v.site_id === site &&
    text(v.source) &&
    text(v.caveat) &&
    text(v.footprint_description) &&
    optionalText(v.api_version) &&
    (v.fetched_at === null || date(v.fetched_at)) &&
    dataStates.includes(String(v.data_state)) &&
    dataStates.includes(String(v.critical_habitat_state)) &&
    typeof v.simulated === 'boolean' &&
    ['gemini', 'fallback'].includes(String(v.generated_by)) &&
    strings(v.unknowns) &&
    Array.isArray(v.species) &&
    v.species.every(
      (s) =>
        record(s) &&
        text(s.id) &&
        text(s.summary) &&
        text(s.match_note) &&
        ['regional_range', 'possible_regional_context', 'unknown'].includes(
          String(s.match_basis),
        ) &&
        strings(s.evidence_ids) &&
        (s.protection === null ||
          (record(s.protection) &&
            optionalText(s.protection.status) &&
            text(s.protection.source) &&
            date(s.protection.as_of))) &&
        (s.encounter === null ||
          (record(s.encounter) &&
            strings(s.encounter.actions) &&
            text(s.encounter.source) &&
            text(s.encounter.source_url))),
    ) &&
    Array.isArray(v.critical_habitat) &&
    v.critical_habitat.every(
      (a) =>
        record(a) &&
        text(a.id) &&
        text(a.source) &&
        (a.geometry === null || record(a.geometry)),
    ) &&
    Array.isArray(v.wildlife_reports) &&
    v.wildlife_reports.every(
      (r) =>
        record(r) &&
        text(r.report_id) &&
        date(r.reported_at) &&
        ['confirmed', 'pending', 'rejected'].includes(String(r.confirmation)),
    )
  if (!valid) throw new ApiError(502, 'Invalid species context response')
  return v as unknown as SiteSpeciesContext
}
