import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import '../../styles/map.css'
import type { CriticalHabitatArea, SiteSummary } from '../../types/api'
import { levelHex, RiskShape } from './Risk'
import { evidenceOf } from './evidence'
// The basemap loads by default when online. Offline, or when the tile server can't be
// reached, the map is hidden and the location list below stays the way to browse sites.
// `network` is -1 offline, else a count that rises each time the browser reconnects.
let reconnects = 0
function subscribe(changed: () => void) {
  const online = () => {
    reconnects++
    changed()
  }
  window.addEventListener('online', online)
  window.addEventListener('offline', changed)
  return () => {
    window.removeEventListener('online', online)
    window.removeEventListener('offline', changed)
  }
}
const network = () => (navigator.onLine ? reconnects : -1)

// Critical habitat outlines: dashed for proposed, solid for final, so status never
// depends on colour alone. Each outline also carries its name as a tooltip.
const HABITAT_COLOR = '#9d8ad6'

export function SiteMap({
  sites,
  select,
  habitat,
}: {
  sites: SiteSummary[]
  select: (id: string) => void
  /** Optional critical habitat overlay, already clipped to the map window. */
  habitat?: CriticalHabitatArea[]
}) {
  const container = useRef<HTMLDivElement>(null)
  const connection = useSyncExternalStore(subscribe, network, () => 0)
  // The connection on which the basemap failed; a reconnect tries again.
  const [failedOn, setFailedOn] = useState<number | null>(null)
  const hidden = connection < 0 || failedOn === connection
  useEffect(() => {
    if (hidden || !container.current || !sites.length) return
    const bounds = L.latLngBounds(
      sites.map((s) => [s.lat, s.lon] as [number, number]),
    )
    const outlines = (habitat ?? []).flatMap((area) => {
      if (!area.geometry) return []
      const layer = L.geoJSON(area.geometry as GeoJSON.GeoJsonObject, {
        interactive: true,
        style: {
          color: HABITAT_COLOR,
          weight: 2,
          dashArray: area.status === 'Proposed' ? '6 5' : undefined,
          fillColor: HABITAT_COLOR,
          fillOpacity: 0.12,
        },
      }).bindTooltip(
        `${area.common_name ?? area.scientific_name ?? 'Species'}: ${area.status ?? 'status unknown'} critical habitat`,
      )
      bounds.extend(layer.getBounds())
      return [layer]
    })
    const map = L.map(container.current, { scrollWheelZoom: false }).fitBounds(
      bounds.pad(0.15),
    )
    outlines.forEach((layer) => layer.addTo(map))
    for (let lon = -180; lon <= 180; lon += 30)
      L.polyline(
        [
          [-80, lon],
          [80, lon],
        ],
        { color: '#8e8e93', weight: 1, opacity: 0.3, interactive: false },
      ).addTo(map)
    for (let lat = -60; lat <= 60; lat += 30)
      L.polyline(
        [
          [lat, -180],
          [lat, 180],
        ],
        { color: '#8e8e93', weight: 1, opacity: 0.3, interactive: false },
      ).addTo(map)
    sites.forEach((s) => {
      const button = document.createElement('button')
      button.textContent = s.name
      button.className = 'min-h-11 px-2 py-2 font-semibold text-ink underline'
      button.onclick = () => select(s.id)
      L.circleMarker([s.lat, s.lon], {
        radius: s.assigned_team ? 9 : 5,
        // Light outline on the dark map; assigned sites get the heavier ring.
        color: s.assigned_team ? '#f5f5f7' : '#1d1d1f',
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
    let loaded = false
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    })
      .on('tileload', () => {
        loaded = true
      })
      // One stray tile error is fine; failing before any tile loads means no network.
      .on('tileerror', () => {
        if (!loaded) setFailedOn(connection)
      })
      .addTo(map)
    return () => {
      map.remove()
    }
  }, [sites, select, habitat, hidden, connection])
  if (hidden) return null
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
          {habitat && habitat.length > 0 && (
            <>
              <li className="inline-flex items-center gap-1.5">
                <span
                  className="h-3 w-5 border-2 border-[#9d8ad6] bg-[#9d8ad6]/15"
                  aria-hidden="true"
                />
                Final critical habitat (solid)
              </li>
              <li className="inline-flex items-center gap-1.5">
                <span
                  className="h-3 w-5 border-2 border-dashed border-[#9d8ad6] bg-[#9d8ad6]/15"
                  aria-hidden="true"
                />
                Proposed critical habitat (dashed)
              </li>
            </>
          )}
        </ul>
      </div>
      <p className="text-sm text-muted">
        {habitat?.length
          ? 'Site point and USFWS critical habitat boundaries, clipped to about 3 km. The same areas are listed above for keyboard access. Boundaries are not sightings.'
          : `${sites.length} reference locations. Use the list below to browse by keyboard. Map points do not establish worksite conditions.`}
      </p>
      <div
        ref={container}
        role="region"
        aria-label="Interactive geographic reference map; locations also listed below"
        className="map-shell relative z-0 h-80 w-full overflow-hidden rounded-xl border border-line @3xl:h-[26rem]"
      />
    </section>
  )
}
