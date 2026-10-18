import { useState, type ReactNode } from 'react'

/** Native keyboard-accessible disclosure; safety-critical content stays outside. */
export function Details({
  title = 'More details',
  label,
  inline = false,
  children,
}: {
  title?: string
  label?: string
  inline?: boolean
  children: ReactNode
}) {
  const [expanded, setExpanded] = useState(false)
  if (inline)
    return (
      <div className="space-y-3 text-ink-2 [overflow-wrap:anywhere]">
        {children}
      </div>
    )
  const displayTitle = expanded ? title.replace(/^View more\b/i, 'View less') : title
  const displayLabel = expanded ? label?.replace(/^View more\b/i, 'View less') : label
  return (
    <details
      className="details-panel border-t border-line text-sm"
      onToggle={(event) => {
        if (event.target === event.currentTarget)
          setExpanded(event.currentTarget.open)
      }}
    >
      <summary
        aria-label={displayLabel}
        className="min-h-11 cursor-pointer py-3 font-semibold text-link"
      >
        {displayTitle}
      </summary>
      <div className="space-y-3 pb-3 text-ink-2 [overflow-wrap:anywhere]">
        {children}
      </div>
    </details>
  )
}
