import { ApiError } from './contracts'
import type {
  Briefing,
  CrewReport,
  HazardNotice,
  HazardConfirmResponse,
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
      ].includes(String(e.kind)) &&
      (e.observed_at === null || date(e.observed_at)),
  )
const risk = (v: unknown) =>
  ['low', 'moderate', 'high', 'critical'].includes(String(v))
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
    !['gemini', 'fallback'].includes(String(v.generated_by)) ||
    !strings(v.unknowns) ||
    !evidence(v.evidence) ||
    !Array.isArray(v.hazards) ||
    !v.hazards.every(
      (h) =>
        record(h) &&
        text(h.hazard) &&
        risk(h.risk_level) &&
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
      v.enrichment === null ||
      (record(v.enrichment) &&
        category(v.enrichment.suggested_category) &&
        text(v.enrichment.description) &&
        strings(v.enrichment.visible_evidence) &&
        v.enrichment.needs_review === true &&
        ['gemini', 'fallback'].includes(String(v.enrichment.generated_by)) &&
        ['low', 'moderate', 'high'].includes(
          String(v.enrichment.severity_suggestion),
        ) &&
        typeof v.enrichment.confidence === 'number' &&
        v.enrichment.confidence >= 0 &&
        v.enrichment.confidence <= 1)
    )
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
