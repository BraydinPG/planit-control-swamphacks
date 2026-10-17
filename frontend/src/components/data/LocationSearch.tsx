import { useId, useMemo, useState, type KeyboardEvent } from 'react'
import type { SiteSummary } from '../../types/api'
import { field, labelText } from './Interaction'
import { RiskBadge } from './Risk'
import { evidenceOf } from './evidence'
import { Icon } from '../shell/Icon'

const LIMIT = 6

/** Lower is better; -1 means no match. Name matches outrank team/ID matches. */
function rank(site: SiteSummary, query: string) {
  const name = site.name.toLowerCase()
  if (name.startsWith(query)) return 0
  if (name.split(/[\s(/,-]+/).some((word) => word.startsWith(query))) return 1
  if (name.includes(query)) return 2
  const team = site.assigned_team?.name.toLowerCase() ?? ''
  if (team.includes(query)) return 3
  return site.id.toLowerCase().includes(query) ? 4 : -1
}

function Highlight({ text, query }: { text: string; query: string }) {
  const at = query ? text.toLowerCase().indexOf(query) : -1
  if (at < 0) return <>{text}</>
  return (
    <>
      {text.slice(0, at)}
      <mark className="rounded-sm bg-transparent text-ink underline decoration-2 underline-offset-2">
        {text.slice(at, at + query.length)}
      </mark>
      {text.slice(at + query.length)}
    </>
  )
}

/**
 * Search box with suggested locations (ARIA combobox). Typing still filters
 * the map and ranked list through `onChange`; picking a suggestion opens
 * that location. With an empty box it suggests the first locations in
 * ranked order: assigned teams, then highest eligible supplied score.
 */
export function LocationSearch({
  sites,
  value,
  onChange,
  onPick,
  withheld,
}: {
  /** Already in ranked order. */
  sites: SiteSummary[]
  value: string
  onChange: (value: string) => void
  onPick: (id: string) => void
  withheld: (site: SiteSummary) => boolean
}) {
  const id = useId()
  const listId = `${id}-list`
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const query = value.trim().toLowerCase()
  const suggestions = useMemo(() => {
    if (!query) return sites.slice(0, LIMIT)
    return sites
      .map((site, order) => ({ site, order, score: rank(site, query) }))
      .filter((row) => row.score >= 0)
      .sort((a, b) => a.score - b.score || a.order - b.order)
      .slice(0, LIMIT)
      .map((row) => row.site)
  }, [sites, query])
  const expanded = open && (suggestions.length > 0 || query.length > 0)

  function pick(site: SiteSummary) {
    setOpen(false)
    setActive(-1)
    onPick(site.id)
  }
  function keyDown(event: KeyboardEvent<HTMLInputElement>) {
    const count = suggestions.length
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      setOpen(true)
      if (!count) return
      const step = event.key === 'ArrowDown' ? 1 : -1
      setActive((current) =>
        current < 0 && step < 0 ? count - 1 : (current + step + count) % count,
      )
    } else if (event.key === 'Enter' && open && active >= 0) {
      event.preventDefault()
      pick(suggestions[active])
    } else if (event.key === 'Escape' && open) {
      event.preventDefault()
      setOpen(false)
      setActive(-1)
    }
  }

  return (
    <div className="relative">
      <label className={labelText} htmlFor={`${id}-input`}>
        Search locations
      </label>
      <div className="relative">
        <Icon
          name="sites"
          className="pointer-events-none absolute top-1/2 left-3 mt-0.75 size-4 -translate-y-1/2 text-faint"
        />
        <input
          id={`${id}-input`}
          className={`${field} pl-9`}
          type="search"
          role="combobox"
          autoComplete="off"
          aria-autocomplete="list"
          aria-expanded={expanded}
          aria-controls={listId}
          aria-activedescendant={
            expanded && active >= 0 ? `${listId}-${active}` : undefined
          }
          aria-describedby={`${id}-hint`}
          placeholder="Name, team or site ID"
          value={value}
          onChange={(e) => {
            onChange(e.target.value)
            setOpen(true)
            setActive(-1)
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => {
            setOpen(false)
            setActive(-1)
          }}
          onKeyDown={keyDown}
        />
      </div>
      <p id={`${id}-hint`} className="sr-only">
        Typing filters the map and list. Use the arrow keys to choose a
        suggested location and Enter to open it.
      </p>
      <div
        className={`absolute top-full left-0 z-[1100] mt-1.5 w-[max(100%,min(30rem,calc(100vw-2rem)))] overflow-hidden rounded-xl border border-line-strong bg-surface shadow-2xl shadow-black/40 ${expanded ? '' : 'hidden'}`}
      >
        <p className="kicker border-b border-line px-3 py-2" aria-hidden="true">
          {query ? 'Matching locations' : 'Suggested locations'}
        </p>
        <ul
          id={listId}
          role="listbox"
          aria-label={query ? 'Matching locations' : 'Suggested locations'}
          className="max-h-80 overflow-y-auto py-1"
        >
          {suggestions.map((site, index) => (
            <li
              key={site.id}
              id={`${listId}-${index}`}
              role="option"
              aria-selected={index === active}
              onMouseDown={(e) => e.preventDefault()}
              onMouseEnter={() => setActive(index)}
              onClick={() => pick(site)}
              className={`flex min-h-12 cursor-pointer items-center gap-3 px-3 py-2 ${index === active ? 'bg-surface-2 shadow-[inset_3px_0_0_var(--pc-focus)]' : ''}`}
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate font-semibold text-ink">
                  <Highlight text={site.name} query={query} />
                </span>
                <span className="block truncate text-xs text-muted">
                  {site.assigned_team?.name ?? 'No team assigned'} · {site.id}
                  {site.active_alerts > 0 &&
                    ` · ${site.active_alerts} active alert${site.active_alerts === 1 ? '' : 's'}`}
                </span>
              </span>
              <RiskBadge
                level={site.risk_score === null ? null : site.risk_level}
                withheld={withheld(site)}
                evidence={evidenceOf(site)}
              />
            </li>
          ))}
        </ul>
        {!suggestions.length && (
          <p className="px-3 py-3 text-sm text-ink-2">
            No locations match “{value.trim()}”.
          </p>
        )}
      </div>
      <p className="sr-only" aria-live="polite">
        {expanded
          ? suggestions.length
            ? `${suggestions.length} ${query ? 'matching' : 'suggested'} locations available.`
            : 'No matching locations.'
          : ''}
      </p>
    </div>
  )
}
