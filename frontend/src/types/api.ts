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

// ---- team onboarding and roster ----

/** One person on a roster. Name and email come from their Auth0 sign-in. */
export interface TeamMember {
  user_id: string
  name: string | null
  email: string | null
  role: 'crew' | 'supervisor'
  joined_at: string | null
}

/** `XXXX-XXXX`: lets a crew account join one team until it expires (7 days) or is revoked. */
export interface JoinCode {
  code: string
  team_id: string
  created_at: string
  expires_at: string
}

export interface TeamRoster {
  id: string
  name: string
  site_id: string | null
  site_name: string | null
  members: TeamMember[]
  /** Active codes only. */
  join_codes: JoinCode[]
}

/** GET /api/team: the supervisor's organization, its supervisors, and every team. */
export interface OrganizationTeams {
  organization_id: string
  organization_name: string
  supervisors: TeamMember[]
  teams: TeamRoster[]
}

/** GET /api/me and POST /api/join. Organization fields are null until the account joins. */
export interface Account {
  role: 'crew' | 'supervisor'
  organization_id: string | null
  organization_name: string | null
  team_id: string | null
  team_name: string | null
  site_id: string | null
}

/** Body for POST /api/join. Case, spaces and a missing dash are forgiven. */
export interface JoinRequest {
  code: string
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

export type AlertRule =
  'lightning_stop_work' | 'flood' | 'heat' | 'hurricane' | 'earthquake'

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
  'broken_pole_downed_line' | 'on_site_fire' | 'wildlife' | 'flooding' | 'other'

export type ReviewStatus = 'pending' | 'confirmed' | 'rejected'

export type Severity = 'low' | 'moderate' | 'high'

/** Where a report's coordinates came from (T053A). `site` is approximate. */
export type LocationSource = 'device' | 'site' | 'pin'

export type AnalysisVerdict = 'supports' | 'contradicts' | 'inconclusive'

/** One reason for the verdict, citing ids from `ReportEnrichment.evidence`. */
export interface AnalysisPoint {
  statement: string
  evidence_ids: string[]
}

/**
 * Gemini's side-panel analysis of a crew report (T060): does the photo and site data
 * support or contradict the report, and why. A suggestion for the supervisor only; it
 * never changes the report, its review state, or the score. `status: 'unavailable'`
 * means the analysis failed ("Photo analysis unavailable").
 */
export interface ReportEnrichment {
  status: 'complete' | 'unavailable'
  verdict: AnalysisVerdict | null
  summary: string | null
  supporting: AnalysisPoint[]
  contradicting: AnalysisPoint[]
  also_visible: string[]
  suggested_category: ReportCategory | null
  severity_suggestion: Severity | null
  confidence: number | null
  unknowns: string[]
  evidence: Evidence[]
  unavailable_reason: string | null
  needs_review: true
  generated_by: GeneratedBy
  analyzed_at: string
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
  /** Null for reports filed before T053A. */
  location_source: LocationSource | null
  location_accuracy_m: number | null
  /** Backend-computed distance from the report to its site, in miles. */
  site_distance_miles: number | null
  /** Null while the analysis runs (it starts after the report is saved). */
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
  /** Defaults to `site` on the backend. */
  location_source?: LocationSource
  /** Only with `location_source: 'device'`. */
  location_accuracy_m?: number | null
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

// ---- stored briefings ----

export interface BriefingHazard {
  hazard: string
  /**
   * Points this hazard adds to the site's 0–10 index, from the deterministic score (T058C).
   * Null when none of its evidence is a score factor, e.g. a forecast. Never Gemini's.
   */
  points: number | null
  evidence_ids: string[]
}

export interface RecommendedAction {
  action: string
  evidence_ids: string[]
}

export interface Briefing {
  id: string
  site_id: string | null
  organization_id: string | null
  forecast_window_start: string
  forecast_window_end: string
  summary: string
  risk_level: RiskLevel
  /** The site's 0–10 hazard index at generation; null for briefings stored before T058C. */
  risk_score: number | null
  data_completeness: number | null
  hazards: BriefingHazard[]
  recommended_actions: RecommendedAction[]
  evidence: Evidence[]
  unknowns: string[]
  generated_by: GeneratedBy
  created_at: string
}

// ---- active-event outlook (T050) ----

/**
 * Compact view of Cache's predict_active_event() for a supervisor-confirmed active event.
 * Advisory only: never a score factor, never clears alerts, not a return-to-work countdown.
 * ongoing_probability is the chance the recorded event is still ongoing at each horizon.
 */
export interface EventOutlook {
  status: 'ok' | 'unavailable' | 'not_applicable_no_confirmed_event'
  event_id: string | null
  event_type: string | null
  as_of_utc: string | null
  generated_at_utc: string
  /** Horizon ("6h", "12h", "24h") -> probability (0–1). */
  ongoing_probability: Record<string, number>
  remaining_hours_p10: number | null
  remaining_hours_median: number | null
  remaining_hours_p90: number | null
  trend: string
  model_version: string
  is_simulated: boolean
  production_eligible: false
  limitations: string[]
  advisory_notice: 'Advisory only. Does not change the score, clear alerts, or authorize work.'
}

// ---- sites ----

/**
 * Item of GET /api/sites. Assigned sites first, then by risk_score descending.
 * risk_score, risk_level, and updated_at are null until the site is scored.
 * Show null as "Not scored yet", never as low risk.
 */
export interface SiteSummary {
  id: string
  name: string
  lat: number
  lon: number
  assigned_team: TeamRef | null
  risk_score: number | null
  risk_level: RiskLevel | null
  updated_at: string | null
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
  /** Advisory outlook for a supervisor-confirmed active event. Null when none. */
  event_outlook: EventOutlook | null
}
