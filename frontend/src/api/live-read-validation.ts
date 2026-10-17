/** Runtime checks for canonical T063/T064 reads. Never derives a score or alert state. */
import type {
  Alert,
  EventOutlookCard,
  SiteDetail,
  SiteSummary,
} from '../types/api'
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
const nonnegative = (v: unknown) => finite(v) && v >= 0
const nullableCount = (v: unknown) =>
  v === null || (nonnegative(v) && Number.isInteger(v))
const point = (v: Record<string, unknown>) =>
  range(v.lat, -90, 90) && range(v.lon, -180, 180)
const sourceURL = (v: unknown) => {
  if (!text(v)) return false
  try {
    const url = new URL(v)
    return url.protocol === 'https:' && !url.username && !url.password
  } catch {
    return false
  }
}
const officialSource = (v: unknown, provider: 'NHC' | 'USGS') =>
  record(v) &&
  text(v.id) &&
  v.provider === provider &&
  sourceURL(v.url) &&
  text(v.sha256) &&
  /^[a-f0-9]{64}$/.test(v.sha256) &&
  date(v.issued_at_utc) &&
  date(v.retrieved_at_utc) &&
  nullableDate(v.available_at_utc) &&
  ['archive_capture', 'contemporaneous_capture'].includes(String(v.vintage))
const stormPoint = (v: unknown) =>
  record(v) &&
  point(v) &&
  date(v.valid_at_utc) &&
  nonnegative(v.max_sustained_wind_kt) &&
  nullableDuration(v.gust_kt) &&
  nullableText(v.phase)

/** Check the whole discriminated payload before the renderer reads nested fields. */
function forecast(v: unknown): boolean {
  if (!record(v)) return false
  switch (v.kind) {
    case 'historical_duration_research': {
      const d = v.remaining_duration_hours
      return (
        text(v.target_definition) &&
        text(v.model_version) &&
        text(v.estimator) &&
        text(v.model_card) &&
        v.trend === 'unknown' &&
        nullableCount(v.training_support_at_event_age) &&
        Array.isArray(v.persistence) &&
        v.persistence.every(
          (p) =>
            record(p) &&
            Number.isInteger(p.horizon_hours) &&
            nonnegative(p.horizon_hours) &&
            range(p.recorded_event_ongoing_probability, 0, 1),
        ) &&
        record(d) &&
        nullableDuration(d.p10) &&
        nullableDuration(d.median) &&
        nullableDuration(d.p90)
      )
    }
    case 'official_event_forecast':
      return (
        text(v.cyclone_id) &&
        text(v.storm_name) &&
        text(v.provider_version) &&
        officialSource(v.source, 'NHC') &&
        date(v.next_advisory_at_utc) &&
        stormPoint(v.initial_position) &&
        Array.isArray(v.forecast_points) &&
        v.forecast_points.every(stormPoint) &&
        v.site_wind_forecast === null
      )
    case 'official_aftershock_forecast': {
      const main = v.mainshock,
        region = v.region
      return (
        record(main) &&
        point(main) &&
        text(main.event_id) &&
        date(main.time_utc) &&
        finite(main.magnitude) &&
        text(v.provider_version) &&
        officialSource(v.source, 'USGS') &&
        officialSource(v.mainshock_source, 'USGS') &&
        date(v.expires_at_utc) &&
        record(region) &&
        point(region) &&
        finite(region.radius_km) &&
        region.radius_km > 0 &&
        region.interpretation ===
          'provider_sequence_region_not_site_probability' &&
        Array.isArray(v.windows) &&
        v.windows.every(
          (w) =>
            record(w) &&
            text(w.label) &&
            date(w.start_utc) &&
            date(w.end_utc) &&
            Date.parse(w.end_utc) >= Date.parse(w.start_utc) &&
            Array.isArray(w.bins) &&
            w.bins.every(
              (b) =>
                record(b) &&
                finite(b.magnitude_at_least) &&
                range(b.probability_at_least_one, 0, 1) &&
                nullableCount(b.count_p95_minimum) &&
                nullableCount(b.count_p95_maximum),
            ),
        ) &&
        v.earthquake_remaining_duration === null
      )
    }
    case 'unavailable':
      return text(v.reason_code) && text(v.reason) && strings(v.required_inputs)
    default:
      return false
  }
}
const outlookCard = (v: unknown, id: string): v is EventOutlookCard =>
  record(v) &&
  text(v.event_id) &&
  v.site_id === id &&
  text(v.event_name) &&
  text(v.event_type) &&
  ['current', 'replay', 'historical_example'].includes(
    String(v.presentation),
  ) &&
  ['available', 'unavailable', 'not_applicable'].includes(String(v.status)) &&
  record(v.confirmation) &&
  ['confirmed_active', 'historical_replay', 'unconfirmed', 'resolved'].includes(
    String(v.confirmation.status),
  ) &&
  [
    'independent_observation',
    'confirmed_worksite_report',
    'historical_record',
    'hypothetical_activation',
    'official_event_record',
    'warning_only',
    'none',
  ].includes(String(v.confirmation.basis)) &&
  nullableText(v.confirmation.source_id) &&
  nullableDate(v.confirmation.confirmed_at_utc) &&
  nullableDate(v.confirmation.available_at_utc) &&
  record(v.association) &&
  text(v.association.site_id) &&
  (v.association.site_id === id ||
    // Archived demo cards retain their original EIA reference; never a live site link.
    (v.association.method === 'reference_replay' &&
      v.presentation !== 'current' &&
      v.is_simulated === true)) &&
  ['site_verified', 'regional_context', 'reference_replay', 'unknown'].includes(
    String(v.association.method),
  ) &&
  nullableText(v.association.source_id) &&
  text(v.association.description) &&
  date(v.as_of_utc) &&
  nullableText(v.notice_id) &&
  nullableDate(v.event_start_utc) &&
  nullableDate(v.last_observation_at_utc) &&
  nullableDate(v.last_forecast_issued_at_utc) &&
  [
    'rejected_for_forecast',
    'accepted_for_research',
    'issued_provider_product',
  ].includes(String(v.evidence_status)) &&
  record(v.forecast) &&
  forecast(v.forecast) &&
  (v.status === 'available') === (v.forecast.kind !== 'unavailable') &&
  Array.isArray(v.evidence) &&
  v.evidence.every(
    (e) =>
      record(e) &&
      text(e.id) &&
      text(e.source_id) &&
      date(e.valid_time_utc) &&
      date(e.available_at_utc),
  ) &&
  strings(v.limitations) &&
  typeof v.is_simulated === 'boolean' &&
  (v.presentation === 'current' ? !v.is_simulated : v.is_simulated) &&
  typeof v.research_only === 'boolean' &&
  v.production_eligibility === false &&
  v.site_hazard_probability === null &&
  v.advisory_notice ===
    'Advisory only. Does not change the score, clear alerts, or authorize work.'
/**
 * T050A cards are advisory: a malformed card becomes a visible "Prediction
 * unavailable" card instead of failing the whole site page. A backend without
 * the field (pre-T050A) yields no cards.
 */
function outlookCards(v: unknown, id: string): EventOutlookCard[] {
  if (v === undefined) return []
  if (!Array.isArray(v)) throw new ApiError(502, 'Invalid event outlooks')
  return v.map((card, index) =>
    outlookCard(card, id)
      ? card
      : {
          event_id: `invalid-outlook-${index}`,
          site_id: id,
          notice_id: null,
          event_name: 'Event outlook',
          event_type: 'Unknown',
          presentation: 'current',
          confirmation: {
            status: 'unconfirmed',
            basis: 'none',
            source_id: null,
            confirmed_at_utc: null,
            available_at_utc: null,
          },
          association: {
            site_id: id,
            method: 'unknown',
            source_id: null,
            description: 'Not supplied.',
          },
          as_of_utc: new Date().toISOString(),
          event_start_utc: null,
          last_observation_at_utc: null,
          last_forecast_issued_at_utc: null,
          evidence_status: 'rejected_for_forecast',
          status: 'unavailable',
          forecast: {
            kind: 'unavailable',
            reason_code: 'invalid_response',
            reason:
              'Prediction unavailable: the server sent an outlook this page could not verify.',
            required_inputs: [],
          },
          evidence: [],
          limitations: [],
          is_simulated: false,
          research_only: true,
          production_eligibility: false,
          site_hazard_probability: null,
          advisory_notice:
            'Advisory only. Does not change the score, clear alerts, or authorize work.',
        },
  )
}
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
      Date.parse(String(v.updated_at)) !==
        Date.parse(String(v.score.created_at)))
  )
    throw new ApiError(
      502,
      'Inconsistent stored score response. Refresh before using this site detail.',
    )
  if (v.score === null && (v.risk_score !== null || v.risk_level !== null))
    throw new ApiError(
      502,
      'Site detail is missing its stored score breakdown.',
    )
  v.notices.forEach((notice) => validateNotice(notice)) // Radius/receipt scope is enforced by FastAPI.
  v.event_outlooks = outlookCards(v.event_outlooks, id)
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
