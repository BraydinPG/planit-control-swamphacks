import { useCallback, useEffect, useRef, useState, type FocusEvent } from 'react'

/**
 * Supervisor sidebar that tucks away on desktop. It starts open, slides out of view
 * once the pointer moves away from it, and slides back when the pointer reaches the
 * left edge of the screen. Keyboard focus inside it also opens it.
 *
 * Only for a wide screen with a mouse or trackpad: touch screens cannot hover, so
 * there the sidebar stays pinned as before.
 */
const QUERY = '(min-width: 1024px) and (hover: hover) and (pointer: fine)'
const SIDEBAR_PX = 256 // w-64
const EDGE_PX = 8 // how close to the left edge reopens it
const CLOSE_DELAY_MS = 300

export function useAutoHideSidebar(enabled: boolean) {
  const [matches, setMatches] = useState(() => window.matchMedia(QUERY).matches)
  const [open, setOpen] = useState(true)
  const focused = useRef(false)
  const timer = useRef(0)
  const autoHide = enabled && matches

  useEffect(() => {
    const query = window.matchMedia(QUERY)
    const update = () => setMatches(query.matches)
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])

  const show = useCallback(() => {
    window.clearTimeout(timer.current)
    setOpen(true)
  }, [])

  useEffect(() => {
    if (!autoHide) return
    const onMove = (event: PointerEvent) => {
      if (event.pointerType && event.pointerType !== 'mouse') return
      if (event.clientX <= EDGE_PX) return show()
      // well clear of the sidebar: tuck it away after a short pause
      if (event.clientX > SIDEBAR_PX + 24 && !focused.current) {
        window.clearTimeout(timer.current)
        timer.current = window.setTimeout(() => setOpen(false), CLOSE_DELAY_MS)
      } else if (event.clientX <= SIDEBAR_PX) {
        window.clearTimeout(timer.current)
      }
    }
    // leaving the window across the left edge also opens it
    const onLeave = (event: MouseEvent) => {
      if (!event.relatedTarget && event.clientX <= EDGE_PX) show()
    }
    window.addEventListener('pointermove', onMove, { passive: true })
    document.addEventListener('mouseout', onLeave)
    return () => {
      window.removeEventListener('pointermove', onMove)
      document.removeEventListener('mouseout', onLeave)
      window.clearTimeout(timer.current)
    }
  }, [autoHide, show])

  const onFocus = useCallback(() => {
    focused.current = true
    show()
  }, [show])
  const onBlur = useCallback((event: FocusEvent<HTMLElement>) => {
    if (event.currentTarget.contains(event.relatedTarget as Node | null)) return
    focused.current = false
  }, [])

  return { autoHide, open: !autoHide || open, show, onFocus, onBlur }
}
