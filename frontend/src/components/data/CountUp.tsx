import { useLayoutEffect, useRef } from 'react'

const reducedMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/**
 * A number that counts up to `value` over `duration` ms, easing out, shown with
 * `decimals` places (a score like 6.1 uses 1).
 * Later changes count from the number currently shown. The animation writes the
 * visible text directly on each frame instead of re-rendering React. Screen
 * readers get only the final value; reduced-motion users and server render see
 * the final value immediately.
 */
export function CountUp({
  value,
  duration = 2000,
  decimals = 0,
}: {
  value: number
  duration?: number
  decimals?: number
}) {
  const format = (n: number) => n.toFixed(decimals)
  const visible = useRef<HTMLSpanElement>(null)
  const current = useRef(0)
  // Layout effect: set the starting number before the first paint.
  useLayoutEffect(() => {
    const element = visible.current
    if (!element) return
    if (reducedMotion() || typeof requestAnimationFrame === 'undefined') {
      current.current = value
      element.textContent = format(value)
      return
    }
    const from = current.current
    element.textContent = format(from)
    let frame = 0
    let start: number | null = null
    const step = (now: number) => {
      start ??= now
      const t = Math.min(1, (now - start) / duration)
      const next = from + (value - from) * (1 - (1 - t) ** 3)
      current.current = t < 1 ? next : value
      element.textContent = format(current.current)
      if (t < 1) frame = requestAnimationFrame(step)
    }
    frame = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame)
    // `format` only depends on `decimals`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, duration, decimals])
  return (
    <>
      <span ref={visible} aria-hidden="true">
        {format(value)}
      </span>
      <span className="sr-only">{format(value)}</span>
    </>
  )
}
