import { useLayoutEffect, useRef } from 'react'

const reducedMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/**
 * A whole number that counts up to `value` over `duration` ms, easing out.
 * Later changes count from the number currently shown. The animation writes the
 * visible text directly on each frame instead of re-rendering React. Screen
 * readers get only the final value; reduced-motion users and server render see
 * the final value immediately.
 */
export function CountUp({
  value,
  duration = 2000,
}: {
  value: number
  duration?: number
}) {
  const visible = useRef<HTMLSpanElement>(null)
  const current = useRef(0)
  // Layout effect: set the starting number before the first paint.
  useLayoutEffect(() => {
    const element = visible.current
    if (!element) return
    if (reducedMotion() || typeof requestAnimationFrame === 'undefined') {
      current.current = value
      element.textContent = String(value)
      return
    }
    const from = current.current
    element.textContent = String(from)
    let frame = 0
    let start: number | null = null
    const step = (now: number) => {
      start ??= now
      const t = Math.min(1, (now - start) / duration)
      const next = Math.round(from + (value - from) * (1 - (1 - t) ** 3))
      current.current = next
      element.textContent = String(next)
      if (t < 1) frame = requestAnimationFrame(step)
    }
    frame = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame)
  }, [value, duration])
  return (
    <>
      <span ref={visible} aria-hidden="true">
        {value}
      </span>
      <span className="sr-only">{value}</span>
    </>
  )
}
