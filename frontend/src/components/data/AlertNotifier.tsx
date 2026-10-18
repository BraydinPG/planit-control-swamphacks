import { useCallback, useEffect, useRef, useState } from 'react'
import type { Alert } from '../../types/api'
import { useApplication } from '../../application/context'
import { alertTitle, alertTone } from '../../presentation/alerts'
import { RiskShape } from './Risk'
import { Icon } from '../shell/Icon'

type Tone = 'heat' | 'stop'
type Seen = Record<
  string,
  { active: boolean; title: string; tone: Tone; stop: boolean }
>
interface Note {
  key: string
  alertId: string
  kind: 'start' | 'end'
  title: string
  tone: Tone
  /** Lightning stop-work: octagon icon; advisories use the triangle. */
  stop: boolean
}

const storageKey = 'foresite:alert-watch'
const pollMs = 30_000
const endNoteMs = 10_000

function readSeen(): Seen {
  try {
    return JSON.parse(sessionStorage.getItem(storageKey) ?? '{}') as Seen
  } catch {
    return {}
  }
}
function writeSeen(seen: Seen) {
  try {
    sessionStorage.setItem(storageKey, JSON.stringify(seen))
  } catch {
    // Storage can be blocked; notifications then only dedupe within this page.
  }
}

/**
 * Top-right notices when an alert starts and when the server ends it. Only the
 * server's alert state drives these; nothing here clears or creates an alert.
 */
export function AlertNotifier() {
  const { client, persona, revision } = useApplication()
  const seen = useRef<Seen | null>(null)
  const [notes, setNotes] = useState<Note[]>([])
  const dismiss = useCallback(
    (key: string) => setNotes((all) => all.filter((n) => n.key !== key)),
    [],
  )

  const update = useCallback((alerts: Alert[]) => {
    const known = (seen.current ??= readSeen())
    const started: Note[] = []
    const ended: Note[] = []
    const active = new Set<string>()
    for (const alert of alerts) {
      const title = alertTitle(alert),
        tone = alertTone(alert),
        stop = alert.rule === 'lightning_stop_work'
      if (alert.state !== 'active') {
        if (!known[alert.id])
          known[alert.id] = { active: false, title, tone, stop }
        continue
      }
      active.add(alert.id)
      if (!known[alert.id]?.active)
        started.push({
          key: `start:${alert.id}:${Date.now()}`,
          alertId: alert.id,
          kind: 'start',
          title,
          tone,
          stop,
        })
      known[alert.id] = { active: true, title, tone, stop }
    }
    for (const [id, entry] of Object.entries(known)) {
      if (!entry.active || active.has(id)) continue
      ended.push({
        key: `end:${id}:${Date.now()}`,
        alertId: id,
        kind: 'end',
        title: entry.title,
        tone: entry.tone,
        stop: entry.stop,
      })
      known[id] = { ...entry, active: false }
    }
    writeSeen(known)
    if (!started.length && !ended.length) return
    const over = new Set(ended.map((n) => n.alertId))
    setNotes((all) => [
      ...all.filter((n) => !(n.kind === 'start' && over.has(n.alertId))),
      ...ended,
      ...started.filter(
        (s) => !all.some((n) => n.kind === 'start' && n.alertId === s.alertId),
      ),
    ])
    for (const note of ended) setTimeout(() => dismiss(note.key), endNoteMs)
  }, [dismiss])

  useEffect(() => {
    let current = true
    const load = () =>
      client
        .alerts()
        .then((alerts) => {
          if (current) update(alerts)
        })
        // Pages show their own load errors; a failed check simply waits for the next one.
        .catch(() => {})
    load()
    const timer = setInterval(load, pollMs)
    return () => {
      current = false
      clearInterval(timer)
    }
  }, [client, revision, update])

  if (!notes.length) return null
  return (
    <div className="fixed left-4 right-4 top-16 z-50 space-y-2 sm:left-auto sm:w-80">
      {notes.map((note) => {
        const border =
          note.kind === 'end'
            ? 'border-ok'
            : note.tone === 'heat'
              ? 'border-warn'
              : 'border-stop'
        return (
          <div
            key={note.key}
            role={note.kind === 'start' ? 'alert' : 'status'}
            data-alert-notice={note.kind}
            className={`flex items-start gap-3 rounded-xl border-2 bg-surface p-3 shadow-lg ${border}`}
          >
            {note.kind === 'end' ? (
              <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full bg-ok text-white">
                <Icon name="check" className="size-4" />
              </span>
            ) : (
              <RiskShape
                kind={note.stop ? 'stop' : 'warn'}
                fill={note.tone === 'heat' ? undefined : 'var(--pc-stop)'}
                className="mt-0.5 size-6"
              />
            )}
            <div className="min-w-0 flex-1">
              <p
                className={`font-bold leading-snug ${note.kind === 'end' ? 'text-ok' : note.tone === 'heat' ? 'text-warn-text' : 'text-stop-text'}`}
              >
                {note.kind === 'end' ? `${note.title} is over` : note.title}
              </p>
              <a
                href={`#/${persona}/alerts`}
                className="inline-flex min-h-11 items-center text-sm font-semibold text-link underline"
              >
                View alerts
              </a>
            </div>
            <button
              type="button"
              aria-label="Dismiss"
              onClick={() => dismiss(note.key)}
              className="grid size-11 shrink-0 place-items-center rounded-lg text-xl text-muted hover:bg-surface-2 hover:text-ink"
            >
              <span aria-hidden="true">×</span>
            </button>
          </div>
        )
      })}
    </div>
  )
}
