import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from 'react'
import {
  createReportLocationController,
  initialReportLocation,
  sameLocationContext,
  type ReportLocationMode,
  type ReportLocationSite,
} from './report-location'

/** Pass null outside an open report. Not wired into the form until T053A is published. */
export function useReportLocation(
  site: ReportLocationSite | null,
  mode: ReportLocationMode,
) {
  const [controller] = useState(() => createReportLocationController())
  const id = site?.id,
    lat = site?.lat,
    lon = site?.lon
  const reference = useMemo(
    () => id === undefined ? null : { id, lat: lat!, lon: lon! },
    [id, lat, lon],
  )
  const session = useMemo(() => ({ reference, mode }), [reference, mode])
  const activeSession = useRef<typeof session | null>(null)
  const fallback = useMemo(
    () => initialReportLocation(reference, mode),
    [reference, mode],
  )
  const snapshot = useSyncExternalStore(
    controller.subscribe,
    controller.getSnapshot,
    () => fallback,
  )
  useEffect(() => {
    let open = true
    activeSession.current = session
    // StrictMode's discarded effect must not cause a second permission request.
    queueMicrotask(() => {
      if (open && session.reference)
        controller.open(session.reference, session.mode)
    })
    return () => {
      open = false
      activeSession.current = null
      controller.close()
    }
  }, [controller, session])
  const setPin = useCallback(
    (latitude: number, longitude: number) => {
      // Retained handlers cannot change a closed form or a later reporting session.
      if (!session.reference || activeSession.current !== session ||
        !sameLocationContext(controller.getSnapshot(), session.reference, session.mode))
        return false
      return controller.setPin(latitude, longitude)
    },
    [controller, session],
  )
  // Never expose the previous site's fix during the render before effect cleanup.
  const state = sameLocationContext(snapshot, reference, mode) ? snapshot : fallback
  return { ...state, setPin }
}
