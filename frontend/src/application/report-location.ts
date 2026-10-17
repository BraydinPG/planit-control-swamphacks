import { validCoordinate, type Client } from '../api/contracts'
import type { SiteSummary } from '../types/api'

export const REPORT_LOCATION_TIMEOUT_MS = 8000
export type ReportLocationSite = Readonly<Pick<SiteSummary, 'id' | 'lat' | 'lon'>>
export type ReportLocationMode = Client['mode']

/** In-memory form state, NOT a replacement for Rudra's ReportCreate contract. */
export interface ReportLocation {
  readonly lat: number
  readonly lon: number
  readonly source: 'device' | 'site' | 'pin'
  readonly accuracyM: number | null
}
export type LocationReason =
  | 'demo'
  | 'denied'
  | 'unsupported'
  | 'unavailable'
  | 'timeout'
  | 'invalid_device'
  | 'invalid_site'
  | 'invalid_pin'
export interface ReportLocationState {
  readonly site: ReportLocationSite | null
  readonly mode: ReportLocationMode | null
  readonly status: 'closed' | 'locating' | 'device' | 'site' | 'pin' | 'unavailable'
  readonly location: ReportLocation | null
  readonly reason: LocationReason | null
  readonly message: string
}

const closed: ReportLocationState = Object.freeze({
  site: null,
  mode: null,
  status: 'closed',
  location: null,
  reason: null,
  message: 'Report closed. No location requested or retained.',
})
const fallbackMessages = {
  denied: 'Location permission declined.',
  unsupported: 'Browser location is not supported.',
  unavailable: 'Device location is unavailable.',
  timeout: 'Device location request timed out.',
  invalid_device: 'Device location or accuracy was invalid.',
} as const

export function initialReportLocation(
  site: ReportLocationSite | null,
  mode: ReportLocationMode,
): ReportLocationState {
  if (!site) return closed
  const reference = Object.freeze({ id: site.id, lat: site.lat, lon: site.lon })
  if (
    typeof site.id !== 'string' ||
    !site.id.trim() ||
    !validCoordinate(site.lat, true) ||
    !validCoordinate(site.lon, false)
  )
    return Object.freeze({
      site: reference,
      mode,
      status: 'unavailable',
      location: null,
      reason: 'invalid_site',
      message: 'Selected site has no valid reference location.',
    })
  return Object.freeze({
    site: reference,
    mode,
    status: mode === 'demo' ? 'site' : 'locating',
    location: Object.freeze({
      lat: site.lat, lon: site.lon, source: 'site', accuracyM: null,
    }),
    reason: mode === 'demo' ? 'demo' : null,
    message:
      mode === 'demo'
        ? 'Simulated report: approximate fixture site coordinates. Device location was not requested.'
        : 'Requesting device location. Approximate site coordinates are available now; no need to wait.',
  })
}

export function sameLocationContext(
  state: ReportLocationState,
  site: ReportLocationSite | null,
  mode: ReportLocationMode,
) {
  return site === null
    ? state.status === 'closed'
    : state.mode === mode &&
        state.site?.id === site.id &&
        Object.is(state.site.lat, site.lat) &&
        Object.is(state.site.lon, site.lon)
}

/** Injectable one-shot provider/clock for deterministic offline tests. No storage/network. */
interface Dependencies {
  geolocation?: () => Pick<Geolocation, 'getCurrentPosition'> | null
  schedule?: (callback: () => void, milliseconds: number) => () => void
}
export function createReportLocationController(dependencies: Dependencies = {}) {
  let state = closed
  let generation = 0
  let cancelTimeout: (() => void) | null = null
  const listeners = new Set<() => void>()
  const publish = (next: ReportLocationState) => {
    state = Object.freeze(next)
    listeners.forEach((listener) => listener())
  }
  const stop = () => {
    generation++
    cancelTimeout?.()
    cancelTimeout = null
  }
  const schedule =
    dependencies.schedule ??
    ((callback, milliseconds) => {
      const timer = setTimeout(callback, milliseconds)
      return () => clearTimeout(timer)
    })
  return {
    getSnapshot: () => state,
    subscribe(listener: () => void) {
      listeners.add(listener)
      return () => { listeners.delete(listener) }
    },
    open(site: ReportLocationSite, mode: ReportLocationMode) {
      if (sameLocationContext(state, site, mode)) return
      stop()
      publish(initialReportLocation(site, mode))
      if (state.status !== 'locating') return
      const request = generation
      const current = () => request === generation && state.status === 'locating'
      const fallback = (reason: keyof typeof fallbackMessages) => {
        if (!current()) return
        stop()
        publish({
          ...state,
          status: 'site',
          reason,
          message: `${fallbackMessages[reason]} Using approximate site coordinates; accuracy is unknown.`,
        })
      }
      try {
        const provider = dependencies.geolocation
          ? dependencies.geolocation()
          : typeof navigator === 'undefined'
            ? null
            : navigator.geolocation
        if (!provider) {
          fallback('unsupported')
          return
        }
        // Our deadline also covers browsers that wait indefinitely at the permission prompt.
        cancelTimeout = schedule(() => fallback('timeout'), REPORT_LOCATION_TIMEOUT_MS)
        provider.getCurrentPosition(
          (position) => {
            if (!current()) return
            const coords = position?.coords
            if (
              !coords ||
              !validCoordinate(coords.latitude, true) ||
              !validCoordinate(coords.longitude, false) ||
              !Number.isFinite(coords.accuracy) ||
              coords.accuracy < 0
            ) {
              fallback('invalid_device')
              return
            }
            stop()
            publish({
              ...state,
              status: 'device',
              reason: null,
              location: Object.freeze({
                lat: coords.latitude,
                lon: coords.longitude,
                source: 'device',
                accuracyM: coords.accuracy,
              }),
              message: 'Device location supplied with browser permission; accuracy is a reported estimate, not verification of the hazard.',
            })
          },
          (error) => fallback(
            error?.code === 1 ? 'denied' : error?.code === 3 ? 'timeout' : 'unavailable',
          ),
          { enableHighAccuracy: true, maximumAge: 0, timeout: REPORT_LOCATION_TIMEOUT_MS },
        )
      } catch {
        fallback('unavailable')
      }
    },
    /** Invalid/unfinished manual edits also invalidate pending GPS; never submit stale coordinates. */
    setPin(lat: number, lon: number) {
      if (state.status === 'closed' || state.reason === 'invalid_site') return false
      stop()
      if (!validCoordinate(lat, true) || !validCoordinate(lon, false)) {
        publish({
          ...state,
          status: 'unavailable',
          location: null,
          reason: 'invalid_pin',
          message: 'Enter valid latitude and longitude before submitting this location.',
        })
        return false
      }
      publish({
        ...state,
        status: 'pin',
        reason: null,
        location: Object.freeze({ lat, lon, source: 'pin', accuracyM: null }),
        message: 'Manually adjusted report location. Device accuracy does not apply.',
      })
      return true
    },
    close() {
      stop()
      if (state !== closed) publish(closed)
    },
  }
}
