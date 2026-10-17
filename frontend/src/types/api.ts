// PlanIT Control API types. Mirror of the canonical Pydantic schemas in backend/app/schemas/.
// Owned by Rudra. Do not edit field names here without a versioned contract change in AGENTS.md.
// Timestamps are ISO-8601 strings. Fields marked `| null` are always present in responses.

// ---- common ----

export type DataState =
  | 'observed'
  | 'forecast'
  | 'crew_reported'
  | 'simulated'
  | 'stale'
  | 'unavailable'

export type RiskLevel = 'low' | 'moderate' | 'high' | 'critical'

export type EvidenceKind =
  | 'observation'
  | 'alert'
  | 'report'
  | 'score_factor'
  | 'model_output'
  | 'notice'

/** `fallback` is the deterministic template used when Gemini fails. */
export type GeneratedBy = 'gemini' | 'fallback'

export interface Evidence {
  id: string
  kind: EvidenceKind
  label: string
  observed_at: string | null
}

export interface FactorContribution {
  factor: string
  label: string
  /** Points added to the 0–10 score. */
  contribution: number
  value: number | string | null
  unit: string | null
  source: string
  observed_at: string | null
  data_state: DataState
  /** True when the threshold is a configurable prototype, not policy. */
  is_prototype: boolean
  evidence_id: string | null
}

// ---- organizations ----

export interface Organization {
  id: string
  name: string
}

export interface TeamRef {
  id: string
  name: string
  organization_id: string
}

export interface Team {
  id: string
  organization_id: string
  name: string
  site_id: string | null
}

// ---- observations ----

export type HazardType =
  | 'weather'
  | 'forecast'
  | 'flood_alert'
  | 'flood_gauge'
  | 'lightning_strike'
  | 'hurricane'
  | 'earthquake'

export interface Observation {
  source: string
  hazard_type: HazardType
  value: number | string | null
  unit: string | null
  lat: number
  lon: number
  observed_at: string
  valid_at: string | null
  data_state: DataState
  id: string | null
  site_id: string | null
  simulated: boolean
  label: string | null
  source_ref: string | null
  fetched_at: string | null
}

// ---- scores ----

export interface ModelDataQuality {
  completeness: number | null
  missing_features: string[]
  is_fallback: boolean
  notes: string[]
  status: 'not_approved_for_score'
  prediction_scope: 'conditional_on_confirmed_active_event'
  event_type: string | null
  event_status: string | null
  as_of_utc: string | null
  include_model_component_in_site_score: false
  confidence_status: 'not_calibrated'
  outlook_status: 'ok' | 'unavailable' | 'not_applicable_no_confirmed_event'
  evidence_quality: string | null
}

export interface HazardScore {
  site_id: string
  risk_score: number
  risk_level: RiskLevel
  factor_contributions: FactorContribution[]
  model_version: string
  model_is_fallback: boolean
  confidence: number
  data_completeness: number
  previous_score: number | null
  created_at: string
}

// ---- alerts ----

export type AlertRule = 'lightning_stop_work' | 'flood' | 'heat' | 'hurricane' | 'earthquake'

export type AlertState = 'active' | 'cleared'

export interface Acknowledgement {
  id: string
  alert_id: string
  user_id: string
  acknowledged_at: string
}

/** POST /api/alerts/{id}/acknowledge takes no body. */
export interface Alert {
  id: string
  site_id: string
  rule: AlertRule
  state: AlertState
  triggered_at: string
  /** Latest qualifying event, e.g. the newest strike. */
  latest_event_at: string
  /** Lightning: latest_event_at + 30 minutes. Resets on each strike. */
  clear_after: string | null
  distance_miles: number | null
  trigger_observation_ids: string[]
  evidence: Evidence[]
  simulated: boolean
  /** False only for the required lightning rule. */
  is_prototype_rule: boolean
  acknowledgements: Acknowledgement[]
}

// ---- reports ----

export type ReportCategory =
  | 'broken_pole_downed_line'
  | 'on_site_fire'
  | 'wildlife'
  | 'flooding'
  | 'other'

export type ReviewStatus = 'pending' | 'confirmed' | 'rejected'

export type Severity = 'low' | 'moderate' | 'high'

/** Gemini suggestion. Always pending human review; never affects the score. */
export interface ReportEnrichment {
  suggested_category: ReportCategory
  description: string
  severity_suggestion: Severity
  confidence: number
  visible_evidence: string[]
  needs_review: true
  generated_by: GeneratedBy
}

export interface CrewReport {
  id: string
  organization_id: string
  team_id: string
  site_id: string
  reporter_id: string
  category: ReportCategory
  hazard_present: boolean
  note: string | null
  photo_url: string | null
  lat: number
  lon: number
  review_status: ReviewStatus
  reviewed_by: string | null
  reviewed_at: string | null
  confirmed_category: ReportCategory | null
  confirmed_severity: Severity | null
  enrichment: ReportEnrichment | null
  notice_id: string | null
  created_at: string
}

/** Multipart form fields for POST /api/reports. Send the photo as the `photo` file part. */
export interface ReportCreate {
  site_id: string
  category: ReportCategory
  hazard_present: boolean
  lat: number
  lon: number
  note?: string | null
}

/** Body for POST /api/reports/{id}/review. */
export interface ReportReview {
  decision: 'confirmed' | 'rejected'
  category?: ReportCategory | null
  severity?: Severity | null
  note?: string | null
}

// ---- hazard notices ----

export type NoticeSource = 'feed' | 'crew_report'

export type RadiusSource = 'gemini' | 'default'

export type NoticeStatus = 'potential' | 'confirmed'

/** Shown as "potential {hazard_label}". A potential notice has no instruction. */
export interface HazardNotice {
  id: string
  hazard_label: string
  source: NoticeSource
  source_ref: string
  lat: number
  lon: number
  radius_miles: number
  radius_source: RadiusSource
  status: NoticeStatus
  created_at: string
  confirmed_by: string | null
  confirmed_at: string | null
  suggested_instruction: string | null
  instruction: string | null
  instruction_sent_at: string | null
  evidence: Evidence[]
}

/** Response of POST /api/hazards/{id}/confirm (no request body). */
export interface HazardConfirmResponse {
  notice: HazardNotice
  /** Null when Gemini fails; the supervisor writes the instruction. */
  suggested_instruction: string | null
  generated_by: GeneratedBy | null
}

/** Body for POST /api/hazards/{id}/instruction. */
export interface InstructionSend {
  instruction: string
}

// ---- briefings and explanations ----

export interface BriefingHazard {
  hazard: string
  risk_level: RiskLevel
  evidence_ids: string[]
}

export interface RecommendedAction {
  action: string
  evidence_ids: string[]
}

/** Body for POST /api/sites/{id}/briefings. `organization` is supervisor-only. */
export interface BriefingRequest {
  scope?: 'site' | 'organization'
}

export interface Briefing {
  id: string
  site_id: string | null
  organization_id: string | null
  forecast_window_start: string
  forecast_window_end: string
  summary: string
  risk_level: RiskLevel
  hazards: BriefingHazard[]
  recommended_actions: RecommendedAction[]
  evidence: Evidence[]
  unknowns: string[]
  generated_by: GeneratedBy
  created_at: string
}

/** On fallback, `explanation` is null and the UI shows `top_factors` without prose. */
export interface Explanation {
  site_id: string
  score_created_at: string
  explanation: string | null
  top_factors: FactorContribution[]
  change_since_previous: string | null
  evidence: Evidence[]
  unknowns: string[]
  generated_by: GeneratedBy
  created_at: string
}

// ---- sites ----

/** Item of GET /api/sites. Assigned sites first, then by risk_score descending. */
export interface SiteSummary {
  id: string
  name: string
  lat: number
  lon: number
  assigned_team: TeamRef | null
  risk_score: number
  risk_level: RiskLevel
  updated_at: string
  active_alerts: number
  top_factors: FactorContribution[]
  data_completeness: number
  model_version: string
}

/** Response of GET /api/sites/{id}. */
export interface SiteDetail extends SiteSummary {
  location_type: string
  source: string
  region: string | null
  observations: Observation[]
  score: HazardScore | null
  alerts: Alert[]
  reports: CrewReport[]
  notices: HazardNotice[]
}
