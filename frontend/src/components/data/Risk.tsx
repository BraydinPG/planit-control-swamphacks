import type { RiskLevel } from '../../types/api'
import type { Evidence } from './evidence'

/**
 * Risk is never shown by colour alone: every level has its own shape and word.
 * Octagon = stop / critical, triangle = warning / high, diamond = caution /
 * moderate, dot = low, dashed ring = no data, check ring = clear.
 */
export type RiskShapeKind =
  'stop' | 'warn' | 'caution' | 'low' | 'nodata' | 'clear'

export function RiskShape({
  kind,
  className = 'size-4',
  fill,
}: {
  kind: RiskShapeKind
  className?: string
  /** Overrides the warning triangle's fill, e.g. white on a red alert band. */
  fill?: string
}) {
  const common = {
    viewBox: '0 0 24 24',
    className: 'shrink-0 ' + className,
    'aria-hidden': true,
  } as const
  switch (kind) {
    case 'stop':
      return (
        <svg {...common}>
          <polygon
            points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86"
            fill="var(--pc-stop)"
            stroke="#fff"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
          <path
            d="M12 7v6 M12 17v.2"
            stroke="#fff"
            strokeWidth="2.6"
            strokeLinecap="round"
          />
        </svg>
      )
    case 'warn':
      return (
        <svg {...common}>
          <path d="M12 2.5 22.5 21h-21z" fill={fill ?? 'var(--pc-warn)'} />
          <path
            d="M12 9.5v5 M12 17.6v.2"
            stroke="#1a1e24"
            strokeWidth="2.2"
            strokeLinecap="round"
          />
        </svg>
      )
    case 'caution':
      return (
        <svg {...common}>
          <path
            d="M12 1.5 22.5 12 12 22.5 1.5 12z"
            fill="var(--pc-caution)"
            stroke="#7a6300"
            strokeWidth="1.2"
          />
        </svg>
      )
    case 'low':
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="7" fill="var(--pc-low)" />
        </svg>
      )
    case 'nodata':
      return (
        <svg {...common}>
          <circle
            cx="12"
            cy="12"
            r="8"
            fill="none"
            stroke="var(--pc-faint)"
            strokeWidth="3"
            strokeDasharray="4 3"
          />
        </svg>
      )
    case 'clear':
      return (
        <svg {...common}>
          <circle
            cx="12"
            cy="12"
            r="9.5"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.4"
          />
          <path
            d="M7.5 12.5 10.5 15.5 16.5 9"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      )
  }
}

const levelShape: Record<RiskLevel, RiskShapeKind> = {
  critical: 'stop',
  high: 'warn',
  moderate: 'caution',
  low: 'low',
}
const levelWord: Record<RiskLevel, string> = {
  critical: 'Critical',
  high: 'High',
  moderate: 'Moderate',
  low: 'Low',
}
/** Hex fill per level, for places that cannot use CSS variables (Leaflet). */
// oxlint-disable-next-line react/only-export-components
export const levelHex: Record<RiskLevel | 'none', string> = {
  critical: '#c0262d',
  high: '#c93400',
  moderate: '#e0b000',
  low: '#8e8e93',
  none: '#636366',
}

/**
 * Shape + word for a server risk level. Null renders "Not scored yet".
 * With no supporting evidence the band is shown as unknown; with partial
 * evidence the supplied band is kept and qualified as incomplete.
 */
export function RiskBadge({
  level,
  withheld = false,
  size = 'sm',
  evidence = null,
}: {
  level: RiskLevel | null
  withheld?: boolean
  size?: 'sm' | 'lg'
  evidence?: Evidence | null
}) {
  const unknown = evidence === 'none'
  const text = withheld
    ? 'Withheld'
    : unknown
      ? 'Unknown: no evidence'
      : level
        ? levelWord[level] + (evidence === 'partial' ? ' · incomplete' : '')
        : 'Not scored yet'
  const kind: RiskShapeKind =
    withheld || unknown || !level ? 'nodata' : levelShape[level]
  return (
    <span
      className={`inline-flex items-center gap-1.5 font-semibold text-ink-2 ${size === 'lg' ? 'text-base' : 'text-sm'}`}
    >
      <RiskShape
        kind={kind}
        className={size === 'lg' ? 'size-5' : 'size-3.5'}
      />
      {text}
    </span>
  )
}

/** Segmented 0–10 bar. Empty (dashed) when unscored; never drawn as zero. */
export function ScoreBar({
  score,
  level,
  evidence = null,
}: {
  score: number | null
  level: RiskLevel | null
  evidence?: Evidence | null
}) {
  const color = level ? `var(--pc-${levelVar[level]})` : 'var(--pc-low)'
  // Incomplete evidence remains labeled in the badge and adjacent warning.
  const fill = evidence === 'partial' ? 'var(--pc-stop)' : color
  if (evidence === 'none') score = null
  return (
    <div className="flex h-2.5 w-full gap-0.5" aria-hidden="true">
      {Array.from({ length: 10 }, (_, i) => {
        const part = score === null ? 0 : Math.max(0, Math.min(1, score - i))
        return (
          <span
            key={i}
            className={`relative flex-1 overflow-hidden rounded-[2px] ${score === null ? 'border border-dashed border-line-strong' : 'bg-surface-2'}`}
          >
            {part > 0 && (
              <span
                className="absolute inset-y-0 left-0"
                style={{ width: `${part * 100}%`, background: fill }}
              />
            )}
          </span>
        )
      })}
    </div>
  )
}
const levelVar: Record<RiskLevel, string> = {
  critical: 'stop',
  high: 'warn',
  moderate: 'caution',
  low: 'low',
}
