/** Development test entry only. Synthetic positions; no Auth0, reports, storage or API. */
import { StrictMode, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import { useReportLocation } from '../src/application/useReportLocation'
import type { ReportLocationSite, ReportLocationMode } from '../src/application/report-location'

const root = createRoot(document.getElementById('location-test')!)
const requests: { success: PositionCallback; error?: PositionErrorCallback | null; options?: PositionOptions }[] = []
const provider = { getCurrentPosition(success: PositionCallback, error?: PositionErrorCallback | null, options?: PositionOptions) {
  requests.push({ success, error, options })
} }
let supported = true
Object.defineProperty(navigator, 'geolocation', { configurable: true, get: () => supported ? provider : undefined })
let site: ReportLocationSite = { id: 'synthetic-site-a', lat: 25, lon: -80 }
let mode: ReportLocationMode = 'live', open = false
let latest: ReturnType<typeof useReportLocation>
let retainedPin: ReturnType<typeof useReportLocation>['setPin']
export function Harness() {
  const state = useReportLocation(open ? site : null, mode)
  useEffect(() => { latest = state }, [state])
  return <><p>MOCKED LOCATION HOOK ONLY — no real permission or report submission</p>
    <output>{JSON.stringify(state)}</output></>
}
function render() { root.render(<StrictMode><Harness /></StrictMode>) }
const controls = {
  configure(settings: { open?: boolean; mode?: ReportLocationMode; site?: ReportLocationSite; supported?: boolean }) {
    open = settings.open ?? open
    mode = settings.mode ?? mode
    site = settings.site ?? site
    supported = settings.supported ?? supported
    render()
  },
  snapshot: () => latest,
  requests: () => requests.map((request) => request.options),
  grant(index: number, lat = 26, lon = -81, accuracy = 9) {
    requests[index].success({ coords: { latitude: lat, longitude: lon, accuracy } } as GeolocationPosition)
  },
  fail(index: number, code: number) {
    requests[index].error?.({ code } as GeolocationPositionError)
  },
  pin: (lat: number, lon: number) => latest.setPin(lat, lon),
  retainPin: () => { retainedPin = latest.setPin },
  oldPin: () => retainedPin(31, -86),
  unmount: () => root.unmount(),
}
Object.assign(window, { locationHarness: controls })
render()
