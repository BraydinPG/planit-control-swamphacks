/** Runtime checks for canonical T063/T064 reads. Never derives a score or alert state. */
import type { Alert, SiteDetail, SiteSummary } from '../types/api'
import { ApiError } from './contracts'
import {
  date,
  evidence,
  record,
  strings,
  text,
  validateNotice,
  validateReport,
} from './validate'

const finite = (v: unknown): v is number =>
  typeof v === 'number' && Number.isFinite(v)
const range = (v: unknown, low: number, high: number) =>
  finite(v) && v >= low && v <= high
const nullableText = (v: unknown) => v === null || text(v)
const nullableDate = (v: unknown) => v === null || date(v)
const risk = (v: unknown) =>
  ['low', 'moderate', 'high', 'critical'].includes(String(v))
const nullableScore = (v: unknown) => v === null || range(v, 0, 10)
const scalar = (v: unknown) => v === null || text(v) || finite(v)
const nullableDuration = (v: unknown) => v === null || (finite(v) && v >= 0)
const outlook = (v: unknown) =>
  v === null ||
  (record(v) &&
    ['ok', 'unavailable', 'not_applicable_no_confirmed_event'].includes(
      String(v.status),
    ) &&
    nullableText(v.event_id) &&
    nullableText(v.event_type) &&
    nullableDate(v.as_of_utc) &&
    date(v.generated_at_utc) &&
    record(v.ongoing_probability) &&
    Object.values(v.ongoing_probability).every((p) => range(p, 0, 1)) &&
    nullableDuration(v.remaining_hours_p10) &&
    nullableDuration(v.remaining_hours_median) &&
    nullableDuration(v.remaining_hours_p90) &&
    text(v.trend) &&
    text(v.model_version) &&
    typeof v.is_simulated === 'boolean' &&
    v.production_eligible === false &&
    strings(v.limitations) &&
    v.advisory_notice ===
      'Advisory only. Does not change the score, clear alerts, or authorize work.')
const factors = (v: unknown) =>
  Array.isArray(v) &&
  v.every(
    (f) =>
      record(f) &&
      text(f.factor) &&
      text(f.label) &&
      finite(f.contribution) &&
      scalar(f.value) &&
      nullableText(f.unit) &&
      text(f.source) &&
      nullableDate(f.observed_at) &&
      [
        'observed',
        'forecast',
        'crew_reported',
        'simulated',
        'stale',
        'unavailable',
      ].includes(String(f.data_state)) &&
      typeof f.is_prototype === 'boolean' &&
      nullableText(f.evidence_id),
  )

export function validateAlert(v: unknown, expectedId?: string): Alert {
  if (
    !record(v) ||
    !text(v.id) ||
    !v.id ||
    (expectedId !== undefined && v.id !== expectedId) ||
    !text(v.site_id) ||
    !v.site_id ||
    ![
      'lightning_stop_work',
      'flood',
      'heat',
      'hurricane',
      'earthquake',
    ].includes(String(v.rule)) ||
    !['active', 'cleared'].includes(String(v.state)) ||
    !date(v.triggered_at) ||
    !date(v.latest_event_at) ||
    !nullableDate(v.clear_after) ||
    !(
      v.distance_miles === null ||
      (finite(v.distance_miles) && v.distance_miles >= 0)
    ) ||
    !strings(v.trigger_observation_ids) ||
    !evidence(v.evidence) ||
    typeof v.simulated !== 'boolean' ||
    typeof v.is_prototype_rule !== 'boolean' ||
    !Array.isArray(v.acknowledgements) ||
    !v.acknowledgements.every(
      (a) =>
        record(a) &&
        text(a.id) &&
        a.id &&
        a.alert_id === v.id &&
        text(a.user_id) &&
        a.user_id &&
        date(a.acknowledged_at),
    )
  )
    throw new ApiError(
      502,
      'Invalid alert response. No local alert state was substituted.',
    )
  return v as unknown as Alert
}

export function validateSiteSummary(v: unknown): SiteSummary {
  if (
    !record(v) ||
    !text(v.id) ||
    !v.id ||
    !text(v.name) ||
    !range(v.lat, -90, 90) ||
    !range(v.lon, -180, 180) ||
    !(
      v.assigned_team === null ||
      (record(v.assigned_team) &&
        text(v.assigned_team.id) &&
        text(v.assigned_team.name) &&
        text(v.assigned_team.organization_id))
    ) ||
    !nullableScore(v.risk_score) ||
    !(v.risk_level === null || risk(v.risk_level)) ||
    !nullableDate(v.updated_at) ||
    !Number.isInteger(v.active_alerts) ||
    (v.active_alerts as number) < 0 ||
    !factors(v.top_factors) ||
    !range(v.data_completeness, 0, 1) ||
    !text(v.model_version)
  )
    throw new ApiError(
      502,
      'Invalid site-list response. No demo data was substituted.',
    )
  return v as unknown as SiteSummary
}

export function validateSiteDetail(v: unknown, id: string): SiteDetail {
  validateSiteSummary(v)
  if (
    !record(v) ||
    v.id !== id ||
    !text(v.location_type) ||
    !text(v.source) ||
    !nullableText(v.region) ||
    !Array.isArray(v.observations) ||
    !v.observations.every(
      (o) =>
        record(o) &&
        (o.site_id === null || o.site_id === id) &&
        nullableText(o.id) &&
        text(o.source) &&
        [
          'weather',
          'forecast',
          'flood_alert',
          'flood_gauge',
          'lightning_strike',
          'hurricane',
          'earthquake',
        ].includes(String(o.hazard_type)) &&
        scalar(o.value) &&
        nullableText(o.unit) &&
        range(o.lat, -90, 90) &&
        range(o.lon, -180, 180) &&
        date(o.observed_at) &&
        nullableDate(o.valid_at) &&
        nullableDate(o.fetched_at) &&
        nullableText(o.label) &&
        nullableText(o.source_ref) &&
        typeof o.simulated === 'boolean' &&
        [
          'observed',
          'forecast',
          'crew_reported',
          'simulated',
          'stale',
          'unavailable',
        ].includes(String(o.data_state)),
    ) ||
    !(
      v.score === null ||
      (record(v.score) &&
        v.score.site_id === id &&
        range(v.score.risk_score, 0, 10) &&
        risk(v.score.risk_level) &&
        factors(v.score.factor_contributions) &&
        text(v.score.model_version) &&
        typeof v.score.model_is_fallback === 'boolean' &&
        range(v.score.confidence, 0, 1) &&
        range(v.score.data_completeness, 0, 1) &&
        nullableScore(v.score.previous_score) &&
        date(v.score.created_at))
    ) ||
    !Array.isArray(v.alerts) ||
    !Array.isArray(v.reports) ||
    !Array.isArray(v.notices) ||
    !outlook(v.event_outlook)
  )
    throw new ApiError(
      502,
      'Invalid site-detail response. No demo data was substituted.',
    )
  for (const alert of v.alerts)
    if (validateAlert(alert).site_id !== id)
      throw new ApiError(502, 'Alert belongs to a different site')
  for (const report of v.reports)
    if (validateReport(report).site_id !== id)
      throw new ApiError(502, 'Report belongs to a different site')
  // A detail response contains two views of the same persisted score. Accepting
  // different versions would show one headline and another factor breakdown.
  // Compare the server's values; never recalculate the hazard index here.
  if (
    v.score !== null &&
    (v.risk_score !== v.score.risk_score ||
      v.risk_level !== v.score.risk_level ||
      v.model_version !== v.score.model_version ||
      v.data_completeness !== v.score.data_completeness ||
      Date.parse(String(v.updated_at)) !== Date.parse(String(v.score.created_at)))
  )
    throw new ApiError(
      502,
      'Inconsistent stored score response. Refresh before using this site detail.',
    )
  if (v.score === null && (v.risk_score !== null || v.risk_level !== null))
    throw new ApiError(502, 'Site detail is missing its stored score breakdown.')
  v.notices.forEach((notice) => validateNotice(notice)) // Radius/receipt scope is enforced by FastAPI.
  return v as unknown as SiteDetail
}

export function validateUniqueRows<T extends { id: string }>(
  v: unknown,
  validate: (row: unknown) => T,
  label = 'API-list',
): T[] {
  if (!Array.isArray(v)) throw new ApiError(502, `Invalid ${label} response`)
  const rows = v.map((row) => validate(row))
  if (new Set(rows.map((row) => row.id)).size !== rows.length)
    throw new ApiError(502, 'Duplicate identifiers in API list response')
  return rows
}
