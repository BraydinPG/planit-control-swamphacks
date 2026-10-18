import { createContext, useContext, useEffect, useRef, useState } from 'react'
import type { Client, Persona } from '../api/contracts'
import type { DemoClient } from '../demo/client'

export interface Application {
  client: Client
  persona: Persona
  principalId: string | null
  revision: number
  /** Bumped by background polling; a failed poll keeps the data already shown. */
  poll?: number
  refresh: () => void
}
export const ApplicationContext = createContext<Application | null>(null)
export function useApplication() {
  const context = useContext(ApplicationContext)
  if (!context) throw new Error('ApplicationProvider required')
  return context
}
export function useRoute() {
  const read = () => window.location.hash.split('/').slice(1)
  const [route, setRoute] = useState(read)
  useEffect(() => {
    const update = () => setRoute(read())
    window.addEventListener('hashchange', update)
    return () => window.removeEventListener('hashchange', update)
  }, [])
  return route
}
export function useResource<T>(key: string, load: () => Promise<T>) {
  const { revision, poll = 0 } = useApplication()
  const seenRevision = useRef(revision)
  const [state, setState] = useState<{
    key: string
    data: T | null
    error: string | null
  }>({ key: '', data: null, error: null })
  useEffect(() => {
    let current = true
    // Only a poll changed: a failure leaves the current data on screen.
    const background = seenRevision.current === revision
    seenRevision.current = revision
    Promise.resolve()
      .then(load)
      .then((data) => {
        if (current) setState({ key, data, error: null })
      })
      .catch((error) => {
        if (current)
          setState((previous) =>
            background && previous.key === key && previous.data !== null
              ? previous
              : {
                  key,
                  data: null,
                  error:
                    error instanceof Error
                      ? error.message
                      : 'Service unavailable',
                },
          )
      })
    return () => {
      current = false
    }
  }, [key, revision, poll, load])
  return state.key === key ? state : { key, data: null, error: null }
}
export function demoClient(client: Client) {
  return client.mode === 'demo' ? (client as DemoClient) : null
}
export function useClock() {
  const { client } = useApplication()
  const tick = () => client.now?.() ?? Date.now()
  const [now, setNow] = useState(tick)
  useEffect(() => {
    const timer = setInterval(() => setNow(client.now?.() ?? Date.now()), 1000)
    return () => clearInterval(timer)
  }, [client])
  return now
}
