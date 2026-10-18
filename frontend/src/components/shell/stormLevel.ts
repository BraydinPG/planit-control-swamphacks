import { useEffect } from 'react'

/*
 * The storm backdrop has two levels: calm on the sign-in and loading screens, vivid
 * (brighter fog, more frequent lightning) on app pages. AppShell turns vivid on with
 * useVividStorm(); StormBackdrop reads the level.
 */
let vividCount = 0
const listeners = new Set<() => void>()

export const isVivid = () => vividCount > 0

export function onStormLevel(fn: () => void): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export function useVividStorm() {
  useEffect(() => {
    vividCount += 1
    listeners.forEach((fn) => fn())
    return () => {
      vividCount -= 1
      listeners.forEach((fn) => fn())
    }
  }, [])
}
