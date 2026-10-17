import type { EventOutlook } from '../../types/api'

/** T036B: how long a confirmed hazard is expected to last, in plain words. */
export const NO_ESTIMATE = 'No duration estimate for this hazard.'

const span = (h: number) => {
  if (h < 1) return 'under 1 hour'
  const n = Math.round(h)
  return `${n} hour${n === 1 ? '' : 's'}`
}

/** One plain sentence, or null when there is no usable estimate. Never "0 hours". */
export function durationSentence(outlook: EventOutlook | null | undefined) {
  if (
    !outlook ||
    outlook.status !== 'ok' ||
    outlook.remaining_hours_median === null
  )
    return null
  const median = outlook.remaining_hours_median
  const event = (outlook.event_type ?? 'event').toLowerCase()
  const more =
    median < 1
      ? 'less than an hour more'
      : `about ${Math.round(median)} more hour${Math.round(median) === 1 ? '' : 's'}`
  const { remaining_hours_p10: low, remaining_hours_p90: high } = outlook
  const range =
    low !== null && high !== null && high > low
      ? ` (likely range ${span(low)} to ${span(high)})`
      : ''
  return `This ${event} is likely to continue for ${more}${range}.`
}
