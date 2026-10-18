import type { Alert } from '../types/api'
import { displayLabel } from './display'

/**
 * Lightning is the only backend stop-work rule, so only it says "Stop work".
 * Flood, heat, hurricane and earthquake are prototype rules: advisories.
 */
export function alertTitle(alert: Pick<Alert, 'rule'>) {
  return alert.rule === 'lightning_stop_work'
    ? 'Stop work alert - Lightning'
    : `${displayLabel(alert.rule)} advisory`
}

/** Heat uses orange; every other alert uses the shared stop red. */
export function alertTone(alert: Pick<Alert, 'rule'>): 'heat' | 'stop' {
  return alert.rule === 'heat' ? 'heat' : 'stop'
}
