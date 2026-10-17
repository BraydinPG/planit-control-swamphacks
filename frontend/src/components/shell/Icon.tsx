import type { SVGProps } from 'react'

export type IconName =
  'overview' | 'sites' | 'alerts' | 'reports' | 'briefings' | 'arrow' | 'grid'
const paths: Record<IconName, string> = {
  overview: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  sites:
    'M20 10c0 6-8 11-8 11S4 16 4 10a8 8 0 1 1 16 0Z M15 10a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
  alerts: 'M12 3 2 21h20L12 3Z M12 9v5 M12 17v1',
  reports: 'M8 3H5v18h14V3h-3 M8 2h8v4H8z M8 11h8 M8 15h5',
  briefings: 'M4 3h16v18H4z M8 8h8 M8 12h8 M8 16h4',
  arrow: 'M4 12h15 M13 6l6 6-6 6',
  grid: 'M10 2 5 22 M14 2l5 20 M9 6h6 M7 12h10 M6 17h12 M3 6h18 M1 12h22',
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
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      <path d={paths[name]} />
    </svg>
  )
}
