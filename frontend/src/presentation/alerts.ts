import type { Alert, AlertRule } from '../types/api'

/**
 * Danger tiers come from the server (`danger_tier`, a prototype ranking). Tiers 1–3 are
 * stop-work alerts; tier 4 (heat) is an advisory. The interface shows only the most
 * dangerous active tier per site and merges the alerts in it. Hidden alerts stay active
 * on the server and reappear on their own when the higher tier clears.
 */
export const ADVISORY_TIER = 4

const names: Record<AlertRule, string> = {
  tornado: 'Tornado',
  hurricane: 'Hurricane',
  flash_flood: 'Flash Flood',
  earthquake: 'Earthquake',
  lightning_stop_work: 'Lightning',
  severe_thunderstorm: 'Severe Thunderstorm',
  tropical_storm: 'Tropical Storm',
  flood: 'Flood',
  heat: 'Heat',
}

const tierNames: Record<number, string> = {
  1: 'Extreme danger',
  2: 'Severe danger',
  3: 'Elevated danger',
  4: 'Advisory',
}

type Ruled = Pick<Alert, 'rule' | 'danger_tier'>

export const isStopWork = (alert: Pick<Alert, 'danger_tier'>) =>
  alert.danger_tier < ADVISORY_TIER

/** "Tier 1 · Extreme danger"; words, so tier never relies on color alone. */
export function tierLabel(alert: Pick<Alert, 'danger_tier'>) {
  const name = tierNames[alert.danger_tier] ?? 'Unranked'
  return isStopWork(alert) ? `Tier ${alert.danger_tier} · ${name}` : name
}

export function alertTitle(alert: Ruled) {
  return isStopWork(alert)
    ? `Stop work alert - ${names[alert.rule]}`
    : `${names[alert.rule]} advisory`
}

const order = Object.keys(names)

/** One title naming every event in a same-tier group, in a fixed event order. */
export function stopWorkTitle(group: Ruled[]) {
  if (group.length === 1) return alertTitle(group[0])
  const rules = [...new Set(group.map((a) => a.rule))].sort(
    (a, b) => order.indexOf(a) - order.indexOf(b),
  )
  const events = rules.map((r) => names[r])
  return `${isStopWork(group[0]) ? 'Stop work alert' : 'Advisory'} - ${events.join(' + ')}`
}

/** The active alerts in the most dangerous tier present; empty when none is active. */
export function topTier<T extends Pick<Alert, 'state' | 'danger_tier'>>(
  alerts: T[],
): T[] {
  const active = alerts.filter((a) => a.state === 'active')
  if (!active.length) return []
  const tier = Math.min(...active.map((a) => a.danger_tier))
  return active.filter((a) => a.danger_tier === tier)
}

/**
 * What the interface shows, per site in first-seen order: one merged group for the
 * top active tier, then each cleared alert on its own as history. Lower active tiers
 * are left out entirely.
 */
export function visibleAlertGroups<
  T extends Pick<Alert, 'site_id' | 'state' | 'danger_tier'>,
>(alerts: T[]): T[][] {
  const sites = [...new Set(alerts.map((a) => a.site_id))]
  return sites.flatMap((site) => {
    const own = alerts.filter((a) => a.site_id === site)
    const top = topTier(own)
    return [
      ...(top.length ? [top] : []),
      ...own.filter((a) => a.state !== 'active').map((a) => [a]),
    ]
  })
}

/** Heat uses orange; every other alert uses the shared stop red. */
export function alertTone(alert: Pick<Alert, 'rule'>): 'heat' | 'stop' {
  return alert.rule === 'heat' ? 'heat' : 'stop'
}
