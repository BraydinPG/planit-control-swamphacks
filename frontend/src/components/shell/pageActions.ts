import { createContext, useContext } from 'react'

/**
 * A slot on the right of the page title row (AppShell). A page can portal a control into
 * it, such as the briefings worksite picker. Null until the shell mounts.
 */
export const PageActionsContext = createContext<HTMLElement | null>(null)

export const usePageActions = () => useContext(PageActionsContext)
