import type { SVGProps } from 'react'

export type IconName =
  | 'refresh'
  | 'overview'
  | 'sites'
  | 'alerts'
  | 'reports'
  | 'briefings'
  | 'arrow'
  | 'grid'
  | 'bolt'
  | 'camera'
  | 'back'
  | 'pin'
  | 'clock'
  | 'check'
  | 'spark'
  | 'doc'
  | 'layers'
const paths: Record<IconName, string> = {
  overview: 'M3 10.5 12 3l9 7.5V21H3z',
  sites:
    'M20 10c0 6-8 11-8 11S4 16 4 10a8 8 0 1 1 16 0Z M15 10a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
  alerts: 'M13 2 3 14h9l-1 8 10-12h-9l1-8Z',
  reports:
    'M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z M16 13a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
  briefings: 'M6 2h9l5 5v15H6z M14 2v6h6 M9 13h8 M9 17h6',
  arrow: 'M4 12h15 M13 6l6 6-6 6',
  grid: 'M10 2 5 22 M14 2l5 20 M9 6h6 M7 12h10 M6 17h12 M3 6h18 M1 12h22',
  bolt: 'M13 2 3 14h9l-1 8 10-12h-9l1-8Z',
  camera:
    'M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z M16 13a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
  back: 'M15 18 9 12l6-6',
  pin: 'M20 10c0 6-8 11-8 11S4 16 4 10a8 8 0 1 1 16 0Z M15 10a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
  clock: 'M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18Z M12 7v5l3 2',
  refresh:
    'M20 11a8 8 0 0 0-14.6-4.5 M4 4v3h3 M4 13a8 8 0 0 0 14.6 4.5 M20 20v-3h-3',
  check: 'M5 12.5 10 17.5 19 7',
  spark:
    'M12 3v4 M12 17v4 M3 12h4 M17 12h4 M6 6l2.5 2.5 M15.5 15.5 18 18 M18 6l-2.5 2.5 M8.5 15.5 6 18',
  doc: 'M6 2h9l5 5v15H6z M14 2v6h6 M9 13h8 M9 17h6',
  layers: 'M12 2 2 7l10 5 10-5-10-5Z M2 17l10 5 10-5 M2 12l10 5 10-5',
}

export function Icon({
  name,
  ...props
}: SVGProps<SVGSVGElement> & { name: IconName }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      <path d={paths[name]} />
    </svg>
  )
}

/** Logo mark: stop octagon with a bolt, from the design mockups. */
export function Logo({ className = 'size-8' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={className}>
      <polygon
        points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86"
        fill="currentColor"
      />
      <polygon
        points="13 5.5 8 13 11.5 13 10.5 18.5 16 11 12.5 11 13 5.5"
        fill="var(--pc-bg)"
      />
    </svg>
  )
}
