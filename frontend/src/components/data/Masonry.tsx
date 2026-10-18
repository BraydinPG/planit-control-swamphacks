import { useLayoutEffect, useRef, useState, type ReactNode } from 'react'

/**
 * Cards in connected columns: each card sits directly under the one above it,
 * instead of every row waiting for its tallest card. Items are dealt left to
 * right (item i goes to column i mod n), so reading order stays across.
 * The column count comes from the list's own width, not the window.
 */
export function Masonry({
  items,
  label,
  minColumnWidth = 340,
  maxColumns = 3,
}: {
  items: { key: string; node: ReactNode }[]
  label?: string
  minColumnWidth?: number
  maxColumns?: number
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [columns, setColumns] = useState(1)
  useLayoutEffect(() => {
    const element = ref.current
    if (!element) return
    const measure = () =>
      setColumns(
        Math.max(
          1,
          Math.min(
            maxColumns,
            Math.floor(element.clientWidth / minColumnWidth),
          ),
        ),
      )
    measure()
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  }, [minColumnWidth, maxColumns])
  const lanes = Array.from({ length: columns }, (_, lane) =>
    items.filter((_, i) => i % columns === lane),
  )
  return (
    <div ref={ref} role="list" aria-label={label} className="flex gap-4">
      {lanes.map((lane, i) => (
        <div key={i} className="flex min-w-0 flex-1 flex-col gap-4">
          {lane.map((item) => (
            <div key={item.key} role="listitem" className="min-w-0">
              {item.node}
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}
