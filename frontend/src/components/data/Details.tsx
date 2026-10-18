import type { ReactNode } from 'react'

/** Native keyboard-accessible disclosure; safety-critical content stays outside. */
export function Details({
  title = 'More details',
  label,
  children,
}: {
  title?: string
  label?: string
  children: ReactNode
}) {
  return (
    <details className="details-panel border-t border-line text-sm">
      <summary
        aria-label={label}
        className="min-h-11 cursor-pointer py-3 font-semibold text-link"
      >
        {title}
      </summary>
      <div className="space-y-3 pb-3 text-ink-2 [overflow-wrap:anywhere]">
        {children}
      </div>
    </details>
  )
}
