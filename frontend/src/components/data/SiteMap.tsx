import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import '../../styles/map.css'
import type { SiteSummary } from '../../types/api'
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
        { color: '#cbd5e1', weight: 1, interactive: false },
      ).addTo(map)
    for (let lat = -60; lat <= 60; lat += 30)
      L.polyline(
        [
          [lat, -180],
          [lat, 180],
        ],
        { color: '#cbd5e1', weight: 1, interactive: false },
      ).addTo(map)
    sites.forEach((s) => {
      const button = document.createElement('button')
      button.textContent = s.name
      button.className = 'min-h-11 p-2 font-semibold'
      button.onclick = () => select(s.id)
      L.circleMarker([s.lat, s.lon], {
        radius: s.assigned_team ? 8 : 5,
        color: s.assigned_team ? '#0f766e' : '#475569',
        fillOpacity: 0.8,
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
    <section className="space-y-2" aria-label="Geographic site map">
      <p className="text-sm">
        Interactive geographic reference map · {sites.length} supplied points.
        Use the equivalent location list below for keyboard access. Points do
        not establish worksite conditions.
      </p>
      <label className="flex min-h-11 items-center gap-3 text-sm">
        <input
          type="checkbox"
          checked={basemap}
          onChange={(e) => {
            setFailed(false)
            setBasemap(e.target.checked)
          }}
        />
        Load online OpenStreetMap basemap (network required)
      </label>
      {failed && (
        <p role="status">
          Basemap unavailable. Geographic markers and the list remain available.
        </p>
      )}
      <div
        ref={container}
        role="region"
        aria-label="Interactive geographic reference map; locations also listed below"
        className="map-shell relative z-0 h-80 w-full rounded border border-slate-300"
      />
    </section>
  )
}
