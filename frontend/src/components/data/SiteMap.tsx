import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import '../../styles/map.css'
import type { SiteSummary } from '../../types/api'
import { levelHex, RiskShape } from './Risk'
import { evidenceOf } from './evidence'
export function SiteMap({
  sites,
  select,
}: {
  sites: SiteSummary[]
  select: (id: string) => void
}) {
  const container = useRef<HTMLDivElement>(null)
  const [basemap, setBasemap] = useState(false)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    if (!container.current || !sites.length) return
    const map = L.map(container.current, { scrollWheelZoom: false }).fitBounds(
      L.latLngBounds(sites.map((s) => [s.lat, s.lon] as [number, number])).pad(
        0.15,
      ),
    )
    for (let lon = -180; lon <= 180; lon += 30)
      L.polyline(
        [
          [-80, lon],
          [80, lon],
        ],
        { color: '#9aa3ad', weight: 1, opacity: 0.35, interactive: false },
      ).addTo(map)
    for (let lat = -60; lat <= 60; lat += 30)
      L.polyline(
        [
          [lat, -180],
          [lat, 180],
        ],
        { color: '#9aa3ad', weight: 1, opacity: 0.35, interactive: false },
      ).addTo(map)
    sites.forEach((s) => {
      const button = document.createElement('button')
      button.textContent = s.name
      button.className = 'min-h-11 px-2 py-2 font-semibold text-ink underline'
      button.onclick = () => select(s.id)
      L.circleMarker([s.lat, s.lon], {
        radius: s.assigned_team ? 9 : 5,
        color: s.assigned_team ? '#f2f4f6' : '#1a1e24',
        weight: s.assigned_team ? 2.5 : 1,
        // No evidence reads as unknown; partial evidence gets a dashed outline.
        fillColor:
          levelHex[
            evidenceOf(s) === 'none' ? 'none' : (s.risk_level ?? 'none')
          ],
        dashArray: evidenceOf(s) === 'partial' ? '2 3' : undefined,
        fillOpacity: 0.9,
      })
        .bindPopup(button)
        .addTo(map)
    })
    if (basemap)
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 18,
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      })
        .on('tileerror', () => setFailed(true))
        .addTo(map)
    return () => {
      map.remove()
    }
  }, [sites, select, basemap])
  return (
    <section
      className="space-y-3 rounded-2xl border border-line bg-surface p-4"
      aria-label="Geographic site map"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="text-lg font-bold">Map</h2>
        <ul
          className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-2"
          aria-label="Map legend"
        >
          <li className="inline-flex items-center gap-1.5">
            <RiskShape kind="stop" className="size-3.5" />
            Critical
          </li>
          <li className="inline-flex items-center gap-1.5">
            <RiskShape kind="warn" className="size-3.5" />
            High
          </li>
          <li className="inline-flex items-center gap-1.5">
            <RiskShape kind="caution" className="size-3.5" />
            Moderate
          </li>
          <li className="inline-flex items-center gap-1.5">
            <RiskShape kind="low" className="size-3.5" />
            Low
          </li>
          <li className="inline-flex items-center gap-1.5">
            <RiskShape kind="nodata" className="size-3.5" />
            Not scored or no evidence
          </li>
          <li className="inline-flex items-center gap-1.5">
            <span
              className="size-3.5 rounded-full border-2 border-dashed border-ink-2"
              aria-hidden="true"
            />
            Dashed outline: evidence incomplete
          </li>
          <li className="inline-flex items-center gap-1.5">
            <span
              className="size-3.5 rounded-full border-2 border-ink"
              aria-hidden="true"
            />
            Team assigned (large, outlined)
          </li>
        </ul>
      </div>
      <p className="text-sm text-muted">
        Interactive geographic reference map · {sites.length} supplied points.
        Use the equivalent location list below for keyboard access. Points do
        not establish worksite conditions.
      </p>
      <label className="flex min-h-11 items-center gap-3 text-sm text-ink-2">
        <input
          type="checkbox"
          className="size-5"
          checked={basemap}
          onChange={(e) => {
            setFailed(false)
            setBasemap(e.target.checked)
          }}
        />
        Load online OpenStreetMap basemap (network required)
      </label>
      {failed && (
        <p role="status" className="text-sm font-semibold text-warn-text">
          Basemap unavailable. Geographic markers and the list remain available.
        </p>
      )}
      <div
        ref={container}
        role="region"
        aria-label="Interactive geographic reference map; locations also listed below"
        className="map-shell relative z-0 h-80 w-full overflow-hidden rounded-xl border border-line @3xl:h-[26rem]"
      />
    </section>
  )
}
