import { useEffect, useRef, useState, type ReactNode } from 'react'
import { shellContext, shellMode } from '../../api/shell-fixtures'
import { Icon, type IconName } from './Icon'
import { Brand } from './Brand'
import { WorkspaceOverview } from '../../pages/WorkspaceOverview'
import { useVividStorm } from './stormLevel'

export type Workspace = 'crew' | 'supervisor'
export type ShellPage =
  'overview' | 'sites' | 'alerts' | 'reports' | 'briefings' | 'team'
const destinations: { id: ShellPage; title: string; icon: IconName }[] = [
  { id: 'overview', title: 'Overview', icon: 'overview' },
  { id: 'sites', title: 'Worksites', icon: 'sites' },
  { id: 'alerts', title: 'Alerts', icon: 'alerts' },
  { id: 'reports', title: 'Reports', icon: 'reports' },
  { id: 'briefings', title: 'Briefings', icon: 'briefings' },
  { id: 'team', title: 'Team', icon: 'team' },
]
/** Team management is supervisor-only. */
const destinationsFor = (workspace: Workspace) =>
  destinations.filter(
    (item) => item.id !== 'team' || workspace === 'supervisor',
  )
function readRoute(): { workspace: Workspace; page: ShellPage } {
  const [, raw, page] = window.location.hash.split('/')
  const workspace: Workspace = raw === 'supervisor' ? 'supervisor' : 'crew'
  return {
    workspace,
    page: destinationsFor(workspace).some((item) => item.id === page)
      ? (page as ShellPage)
      : 'overview',
  }
}
const descriptions: Record<
  Exclude<ShellPage, 'overview'>,
  { title: string; description: string; pending: string }
> = {
  sites: {
    title: 'Worksites',
    description:
      'Locations, assigned teams and the evidence behind site conditions.',
    pending: 'The site list, map and site detail are not available here.',
  },
  alerts: {
    title: 'Alerts',
    description:
      'Current alerts, lightning watch windows and acknowledgements.',
    pending: 'Alert details, acknowledgements and timers are not available.',
  },
  reports: {
    title: 'Hazard reports',
    description:
      'Report what you see in the field. A supervisor reviews every report.',
    pending: 'Report submission and review are not available.',
  },
  briefings: {
    title: 'Shift briefings',
    description:
      'Saved shift summaries, supporting evidence and unknown conditions.',
    pending: 'Briefings are not available.',
  },
  team: {
    title: 'Team',
    description: 'Manage team assignments and invite crew with join codes.',
    pending: 'Team management is not available.',
  },
}

export function AppShell({
  children,
  workspaceOverride,
  controls,
  message,
  badge,
  headerControls,
  hideConnectionInfo = false,
}: {
  children?: ReactNode
  workspaceOverride?: Workspace
  controls?: ReactNode
  message?: string
  badge?: string
  headerControls?: ReactNode
  hideConnectionInfo?: boolean
}) {
  const [locationRoute, setRoute] = useState(readRoute)
  const route = {
    ...locationRoute,
    workspace: workspaceOverride ?? locationRoute.workspace,
  }
  const heading = useRef<HTMLHeadingElement>(null)
  // App pages get the brighter fog and more frequent lightning; sign-in stays calm.
  useVividStorm()
  const context = shellContext(shellMode)
  const isFixture = shellMode === 'fixture'
  const visible = destinationsFor(route.workspace)
  const active = visible.find((item) => item.id === route.page) ?? visible[0]
  useEffect(() => {
    const update = () => setRoute(readRoute())
    window.addEventListener('hashchange', update)
    return () => window.removeEventListener('hashchange', update)
  }, [])
  useEffect(() => {
    document.title = 'FORESITE'
    heading.current?.focus({ preventScroll: true })
    window.scrollTo(0, 0)
  }, [active.title, route.workspace, locationRoute])

  const label = (item: (typeof destinations)[number]) =>
    item.id === 'sites' && route.workspace === 'crew'
      ? 'My worksite'
      : item.title
  const badgeText = badge ?? (isFixture ? 'Fixture mode' : 'No live data')
  const authenticated = badgeText === 'Authenticated API'
  // Keep the field layout on phones/tablets; give desktop crews a full workspace.
  const crew = route.workspace === 'crew'
  const column = crew ? 'max-w-lg lg:max-w-[1440px]' : 'max-w-7xl'

  // Desktop: a row of links in the header. Phones and tablets: the bottom tab bar.
  function navigation(mobile = false) {
    return (
      <nav
        aria-label={mobile ? 'Mobile workspace' : 'Workspace'}
        className={
          mobile
            ? `grid ${visible.length > 5 ? 'grid-cols-6 gap-0.5' : 'grid-cols-5 gap-1.5'}`
            : 'flex min-w-0 items-center gap-1'
        }
      >
        {visible.map((item) => {
          const current = route.page === item.id
          return (
            <a
              key={item.id}
              href={`#/${route.workspace}/${item.id}`}
              aria-current={current ? 'page' : undefined}
              className={
                mobile
                  ? `flex min-h-14 min-w-0 flex-col items-center justify-center gap-1 rounded-xl px-0.5 text-center text-xs leading-tight transition-colors ${current ? 'font-bold text-accent' : 'font-medium text-muted hover:text-ink'}`
                  : `inline-flex min-h-11 shrink-0 items-center gap-2 rounded-lg px-3 text-[15px] whitespace-nowrap transition-colors ${current ? 'bg-accent/15 font-semibold text-ink' : 'font-medium text-ink-2 hover:bg-white/5 hover:text-ink'}`
              }
            >
              <Icon
                name={item.icon}
                className={
                  mobile
                    ? 'size-6 shrink-0'
                    : // icons only on wide screens, so six links still fit at 1024px
                      `hidden size-4 shrink-0 xl:block ${current ? 'text-accent' : 'text-accent/80'}`
                }
              />
              <span className={mobile ? 'max-w-full' : ''}>
                {mobile && item.id === 'overview' ? 'Home' : label(item)}
              </span>
            </a>
          )
        })}
      </nav>
    )
  }

  return (
    <div
      data-theme={route.workspace}
      className="min-h-svh font-sans text-ink"
    >
      <a
        href="#main-content"
        onClick={(event) => {
          event.preventDefault()
          document.getElementById('main-content')?.focus()
        }}
        className="sr-only fixed left-4 top-4 z-50 rounded-lg bg-surface p-4 font-semibold text-ink shadow-lg focus:not-sr-only"
      >
        Skip to content
      </a>
      <header
        className={`sticky top-0 z-20 border-b border-line bg-nav/80 px-4 backdrop-blur-xl backdrop-saturate-150 ${crew ? 'lg:px-10' : 'sm:px-6 lg:px-10'}`}
      >
        <div
          className={`mx-auto flex min-h-14 ${column} items-center justify-between gap-3 lg:grid lg:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]`}
        >
          <div className="flex min-w-0 items-center gap-4 xl:gap-6">
            <a
              href={`#/${route.workspace}/overview`}
              aria-label={`FORESITE ${route.workspace} home`}
              className="inline-flex min-h-11 shrink-0 items-center rounded-lg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent"
            >
              <Brand variant="compact" className="w-28 sm:w-32" decorative />
            </a>
          </div>
          <div className="hidden min-w-0 lg:block lg:justify-self-center">{navigation()}</div>
          <div className="flex shrink-0 items-center justify-self-end">
          {headerControls ?? (<span
            className={`inline-flex shrink-0 items-center gap-1.5 chip border ${authenticated ? 'border-ok text-ok' : 'border-dotted border-sim text-sim'}`}
          >
            <span
              className={`size-1.5 rounded-full ${authenticated ? 'bg-ok' : 'bg-sim'}`}
              aria-hidden="true"
            />
            {badgeText}
          </span>)}
          </div>
        </div>
      </header>
      <main
        id="main-content"
        tabIndex={-1}
        className={`@container mx-auto ${column} min-w-0 [overflow-wrap:anywhere] px-4 pb-32 pt-4 outline-none ${crew ? 'lg:px-10 lg:pt-6 lg:pb-12' : 'sm:px-6 sm:pt-6 lg:px-10 lg:pb-12'}`}
      >
        {!hideConnectionInfo && <div className="mb-5 flex flex-col gap-3 rounded-xl border border-dotted border-line-strong bg-surface/60 px-3 py-2.5 @2xl:flex-row @2xl:items-center @2xl:justify-between @2xl:px-4">
          <p className="max-w-2xl text-sm leading-relaxed text-ink-2">
            <strong className="font-semibold text-ink">
              {badge ??
                (isFixture ? 'Demonstration workspace.' : 'No connected data.')}
            </strong>{' '}
            {message ??
              (isFixture
                ? 'Bundled sample data, not live conditions. Sign-in is not connected to this shell.'
                : 'Live API and sign-in integration are not connected to this shell.')}
          </p>
          <div className="shrink-0 [&_button]:min-h-11">
            {controls ?? (
              <div className="flex flex-wrap items-center gap-3">
                <span className="kicker">Preview workspace</span>
                <div
                  role="group"
                  aria-label="Preview workspace, not an authorization role"
                  className="flex rounded-[10px] bg-surface-2 p-0.5"
                >
                  {(['crew', 'supervisor'] as const).map((workspace) => (
                    <button
                      key={workspace}
                      type="button"
                      aria-pressed={route.workspace === workspace}
                      onClick={() => {
                        window.location.hash = `/${workspace}/overview`
                      }}
                      className={`min-h-11 rounded-lg px-4 text-sm font-semibold capitalize transition-colors ${route.workspace === workspace ? 'bg-control-hover text-ink shadow-[0_1px_2px_rgba(0,0,0,0.4)]' : 'text-ink-2 hover:text-ink'}`}
                    >
                      {workspace}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>}
        <div className="mb-5 @2xl:mb-7">
          <p className="kicker mb-1.5">
            {route.workspace === 'crew'
              ? 'Crew workspace'
              : 'Supervisor workspace'}
          </p>
          <h1
            ref={heading}
            tabIndex={-1}
            className="text-[28px] leading-tight font-bold tracking-tight outline-none @2xl:text-[34px]"
          >
            {route.page === 'overview'
              ? crew
                ? 'Home'
                : 'Supervisor overview'
              : descriptions[route.page].title}
          </h1>
          <p className="mt-2 hidden max-w-2xl text-sm leading-relaxed text-muted @2xl:block">
            {route.page === 'overview'
              ? 'Alerts, reports and worksites needing attention.'
              : descriptions[route.page].description}
          </p>
        </div>
        {children ??
          (route.page === 'overview' ? (
            <WorkspaceOverview
              workspace={route.workspace}
              mode={shellMode}
              context={context}
            />
          ) : (
            <section
              className="rounded-2xl border border-line bg-surface p-7 sm:p-10"
              aria-labelledby="workspace-status"
            >
              <div className="mb-6 flex size-14 items-center justify-center rounded-xl bg-surface-2 text-muted">
                <Icon name={active.icon} className="size-7" />
              </div>
              <h2 id="workspace-status" className="text-xl font-semibold">
                This view is unavailable
              </h2>
              <p className="mt-3 max-w-xl text-sm leading-7 text-muted">
                {descriptions[route.page].pending} No live{' '}
                {active.title.toLowerCase()} are loaded in this shell.
              </p>
              <a
                href={`#/${route.workspace}/overview`}
                className="mt-7 inline-flex min-h-12 items-center gap-3 rounded-xl bg-accent-fill px-5 text-sm font-semibold text-white"
              >
                Back to overview <Icon name="arrow" className="size-4" />
              </a>
            </section>
          ))}
        <footer className="mt-10 flex flex-col gap-2 border-t border-line pt-5 text-xs leading-relaxed text-muted @2xl:flex-row @2xl:justify-between">
          <Brand variant="full" />
          <span>
            Advisory context does not authorize work or clear an alert.
          </span>
        </footer>
      </main>
      <div
        className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-nav/85 px-2 pt-1.5 pb-[max(0.5rem,env(safe-area-inset-bottom))] backdrop-blur-xl backdrop-saturate-150 lg:hidden"
      >
        <div className={`mx-auto ${column}`}>{navigation(true)}</div>
      </div>
    </div>
  )
}
