import { createContext, useContext, useEffect, useState } from 'react'
import type { Client, Persona } from '../api/contracts'
import type { DemoClient } from '../demo/client'

export interface Application {
  client: Client
  persona: Persona
  principalId: string | null
  revision: number
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
  const { revision } = useApplication()
  const [state, setState] = useState<{
    key: string
    data: T | null
    error: string | null
  }>({ key: '', data: null, error: null })
  useEffect(() => {
    let current = true
    Promise.resolve()
      .then(load)
      .then((data) => {
        if (current) setState({ key, data, error: null })
      })
      .catch((error) => {
        if (current)
          setState({
            key,
            data: null,
            error:
              error instanceof Error ? error.message : 'Service unavailable',
          })
      })
    return () => {
      current = false
    }
  }, [key, revision, load])
  return state.key === key ? state : { key, data: null, error: null }
}
export function demoClient(client: Client) {
  return client.mode === 'demo' ? (client as DemoClient) : null
}
export function useClock() {
  const { client } = useApplication()
  const tick = () => demoClient(client)?.now() ?? Date.now()
  const [now, setNow] = useState(tick)
  useEffect(() => {
    const timer = setInterval(
      () => setNow(demoClient(client)?.now() ?? Date.now()),
      1000,
    )
    return () => clearInterval(timer)
  }, [client])
  return now
}
