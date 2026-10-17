import { ApiError } from './contracts'
import type { Briefing } from '../types/api'

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
