/** Presentation only. Never use these labels as API values or rewrite authored prose. */
export const reportCategories = {
  broken_pole_downed_line: 'Broken pole or downed line',
  on_site_fire: 'On-site fire',
  access_mat_deterioration: 'Access mat deterioration',
  wildlife: 'Wildlife',
  flooding: 'Flooding',
  other: 'Other hazard',
} as const

const labels: Record<string, string> = {
  ...reportCategories,
  lightning: 'Lightning',
  lightning_stop_work: 'Lightning stop-work',
  heat: 'Heat',
  flood: 'Flood',
  flash_flood: 'Flash flood',
  tornado: 'Tornado',
  severe_thunderstorm: 'Severe thunderstorm',
  tropical_storm: 'Tropical storm',
  severe_storm: 'Severe storm',
  flash_flood_warning: 'Flash Flood Warning',
  flood_watch: 'Flood Watch',
  flood_warning: 'Flood Warning',
  high_wind: 'High wind',
  crew_report: 'Crew report',
  crew_reported: 'Crew report',
  model: 'Legacy model contribution',
  simulated_worksite: 'Simulated worksite',
  reference_power_plant: 'Reference power plant',
  power_plant: 'Power plant',
  observed: 'Observed',
  forecast: 'Forecast',
  simulated: 'Simulated',
  stale: 'Stale',
  unavailable: 'Unavailable',
  unknown: 'Unknown',
  pending: 'Awaiting review',
  confirmed: 'Confirmed',
  rejected: 'Rejected',
  pending_review: 'Awaiting review',
  active: 'Active',
  cleared: 'Cleared',
  potential: 'Potential hazard',
  low: 'Low',
  medium: 'Medium',
  high: 'High',
  critical: 'Critical',
  severe: 'Severe',
  moderate: 'Moderate',
  minor: 'Minor',
  site_verified: 'Verified for this site',
  regional_context: 'Regional context only',
  reference_replay: 'Replay at a reference location',
  historical_duration_research: 'Research duration estimate',
  independent_observation: 'Independent observation',
  confirmed_worksite_report: 'Supervisor-confirmed report',
  historical_record: 'Historical record',
  hypothetical_activation: 'Simulated activation',
  official_event_record: 'Official event record',
  warning_only: 'Warning only',
  none: 'None',
  downed_lines: 'Downed power lines',
  energized_floodwater: 'Energized floodwater',
  structural_collapse: 'Structural instability',
  blocked_egress: 'Blocked access or exit',
  chemical_release: 'Chemical release',
  fallback: 'Template',
  gemini: 'Gemini',
  wind_gust: 'Wind gust',
  heat_index: 'Heat index',
  precipitation: 'Rainfall',
  temperature: 'Temperature',
  relative_humidity: 'Relative humidity',
  HURRICANE: 'Hurricane',
  TROPICAL_STORM: 'Tropical storm',
  TROPICAL_DEPRESSION: 'Tropical depression',
  EXTRATROPICAL: 'Extratropical cyclone',
  'broken pole downed line': 'Broken pole or downed line',
  not_applicable: 'Not applicable',
  insufficient_evidence: 'Insufficient evidence',
}

/** For controlled enums only; free text, source names and IDs stay verbatim. */
export function displayLabel(
  value: string | null | undefined,
  missing = 'Unknown',
) {
  if (!value?.trim()) return missing
  return (
    labels[value] ??
    value.replaceAll('_', ' ').replace(/^\w/, (c) => c.toUpperCase())
  )
}

export function factorLabel(value: string) {
  return labels[value] ?? displayLabel(value)
}

/** Translate only known transport diagnostics; preserve all other error meaning. */
export function errorSummary(message: string) {
  if (/^Invalid .+ response/i.test(message))
    return 'This information could not be verified. Try again.'
  return message
}

export function outlookUnavailableLabel(code: string) {
  const reasons: Record<string, string> = {
    event_start_missing: 'The event start time is unknown.',
    invalid_event_start: 'A valid event start time is needed.',
    no_confirmed_active_event: 'No confirmed active event is available.',
    model_unavailable: 'The duration model is unavailable.',
    unsupported_target: 'No supported prediction exists for this hazard.',
    site_association_unverified:
      'The event could not be linked to this worksite.',
    local_confirmation_missing: 'Local confirmation is missing.',
    stale_local_confirmation: 'Local confirmation is out of date.',
    official_forecast_missing: 'No qualifying agency forecast is available.',
    official_forecast_stale: 'The agency forecast is out of date.',
  }
  return (
    reasons[code] ?? 'A supported estimate is not available for this event.'
  )
}

/** Browser-local time, with timezone; the original ISO value stays on <time>. */
export function formatTimestamp(value: string | null, timeZone?: string) {
  if (!value || !Number.isFinite(Date.parse(value))) return 'Time unavailable'
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short',
    ...(timeZone ? { timeZone } : {}),
  }).format(new Date(value))
}

export function unitLabel(value: string | null | undefined) {
  const units: Record<string, string> = {
    degF: '°F',
    fahrenheit: '°F',
    degC: '°C',
    celsius: '°C',
    percent: '%',
    miles: 'mi',
    knots: 'kn',
    kt: 'kn',
  }
  return value ? (units[value] ?? value) : ''
}
