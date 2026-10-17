import { useEffect, useRef, useState, type ReactNode } from 'react'
import { shellContext, shellMode } from '../../api/shell-fixtures'
import { Icon, Logo, type IconName } from './Icon'
import { WorkspaceOverview } from '../../pages/WorkspaceOverview'

export type Workspace = 'crew' | 'supervisor'
export type ShellPage =
  'overview' | 'sites' | 'alerts' | 'reports' | 'briefings'
const destinations: { id: ShellPage; title: string; icon: IconName }[] = [
  { id: 'overview', title: 'Overview', icon: 'overview' },
  { id: 'sites', title: 'Worksites', icon: 'sites' },
  { id: 'alerts', title: 'Alerts', icon: 'alerts' },
  { id: 'reports', title: 'Reports', icon: 'reports' },
  { id: 'briefings', title: 'Briefings', icon: 'briefings' },
]
function readRoute(): { workspace: Workspace; page: ShellPage } {
  const [, workspace, page] = window.location.hash.split('/')
  return {
    workspace: workspace === 'supervisor' ? 'supervisor' : 'crew',
    page: destinations.some((item) => item.id === page)
      ? (page as ShellPage)
      : 'overview',
  }
}
const descriptions: Record<
  Exclude<ShellPage, 'overview'>,
  { title: string; description: string; pending: string }
> = {
  sites: {
    title: 'Worksite context',
    description:
      'Locations, assigned teams and the evidence behind site conditions.',
    pending: 'The site list, map and site detail are not available here.',
  },
  alerts: {
    title: 'Crew alerts',
    description:
      'Deterministic alerts with their triggering evidence, countdown and acknowledgements.',
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
      'Stored next-day briefings with evidence references and stated unknowns.',
    pending: 'Briefings are not available.',
  },
}

export function AppShell({
  children,
  workspaceOverride,
  controls,
  message,
  badge,
}: {
  children?: ReactNode
  workspaceOverride?: Workspace
  controls?: ReactNode
  message?: string
  badge?: string
}) {
  const [locationRoute, setRoute] = useState(readRoute)
  const route = {
    ...locationRoute,
    workspace: workspaceOverride ?? locationRoute.workspace,
  }
  const heading = useRef<HTMLHeadingElement>(null)
  const context = shellContext(shellMode)
  const isFixture = shellMode === 'fixture'
  const active = destinations.find((item) => item.id === route.page)!
  useEffect(() => {
    const update = () => setRoute(readRoute())
    window.addEventListener('hashchange', update)
    return () => window.removeEventListener('hashchange', update)
  }, [])
  useEffect(() => {
    document.title = `${active.title} · PlanIT Control`
    heading.current?.focus({ preventScroll: true })
    window.scrollTo(0, 0)
  }, [active.title, route.workspace, locationRoute])

  const label = (item: (typeof destinations)[number]) =>
    item.id === 'sites' && route.workspace === 'crew'
      ? 'My worksite'
      : item.title
  const badgeText = badge ?? (isFixture ? 'Fixture mode' : 'No live data')
  const authenticated = badgeText === 'Authenticated API'

  function navigation(mobile = false) {
    return (
      <nav
        aria-label={mobile ? 'Mobile workspace' : 'Workspace'}
        className={mobile ? 'grid grid-cols-5 gap-1.5' : 'space-y-1'}
      >
        {destinations.map((item) => {
          const current = route.page === item.id
          return (
            <a
              key={item.id}
              href={`#/${route.workspace}/${item.id}`}
              aria-current={current ? 'page' : undefined}
              className={
                mobile
                  ? `flex min-h-14 min-w-0 flex-col items-center justify-center gap-1 rounded-xl px-0.5 text-center text-[11px] font-bold leading-tight ${current ? 'bg-ink text-bg' : 'text-ink-2 hover:bg-surface-2'}`
                  : `flex min-h-11 items-center gap-3 rounded-lg px-3 text-[15px] transition-colors ${current ? 'bg-surface-2 font-bold text-ink shadow-[inset_3px_0_0_var(--pc-ink)]' : 'font-medium text-ink-2 hover:bg-surface-2 hover:text-ink'}`
              }
            >
              <Icon
                name={item.icon}
                className={mobile ? 'size-6 shrink-0' : 'size-5 shrink-0'}
              />
              <span className={mobile ? 'max-w-full' : 'min-w-0 truncate'}>
                {label(item)}
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
      className="min-h-svh bg-bg font-sans text-ink lg:pl-64"
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
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col gap-8 border-r border-line bg-nav px-4 py-6 lg:flex">
        <a
          href={`#/${route.workspace}/overview`}
          aria-label="PlanIT Control overview"
          className="flex min-h-11 items-center gap-2.5 rounded-lg px-2 text-ink"
        >
          <Logo className="size-7 text-ink" />
          <span className="text-lg font-bold tracking-tight">
            PlanIT Control
          </span>
        </a>
        <div className="space-y-2">
          <p className="kicker px-3">
            {route.workspace === 'crew'
              ? 'Crew workspace'
              : 'Supervisor workspace'}
          </p>
          {navigation()}
        </div>
        <div className="mt-auto space-y-3 border-t border-line px-3 pt-5 text-xs leading-relaxed text-muted">
          <p className="font-semibold text-ink-2">
            Rules raise alerts. People make the call.
          </p>
          <p>
            Evidence informs the picture; people and official controls govern
            the work.
          </p>
        </div>
      </aside>
      <header className="sticky top-0 z-20 border-b border-line bg-nav/95 px-4 backdrop-blur sm:px-6 lg:px-10">
        <div className="mx-auto flex min-h-14 max-w-7xl items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2.5">
            <Logo className="size-7 shrink-0 text-ink lg:hidden" />
            <p className="min-w-0 truncate text-sm">
              <span className="font-bold lg:hidden">PlanIT Control</span>
              <span className="hidden text-muted lg:inline">
                {route.workspace === 'crew' ? 'Crew' : 'Supervisor'}
                <span className="px-2 text-line-strong">/</span>
                <span className="font-semibold text-ink">{active.title}</span>
              </span>
            </p>
          </div>
          <span
            className={`inline-flex shrink-0 items-center gap-1.5 rounded-md border px-2 py-1 font-mono text-[11px] font-semibold uppercase tracking-wider ${authenticated ? 'border-ok text-ok' : 'border-dotted border-sim text-sim'}`}
          >
            <span
              className={`size-1.5 rounded-full ${authenticated ? 'bg-ok' : 'bg-sim'}`}
              aria-hidden="true"
            />
            {badgeText}
          </span>
        </div>
      </header>
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto max-w-7xl min-w-0 [overflow-wrap:anywhere] px-4 pb-32 pt-4 outline-none sm:px-6 sm:pt-6 lg:px-10 lg:pb-12"
      >
        <div className="mb-5 flex flex-col gap-3 rounded-xl border border-dotted border-line-strong bg-surface/60 px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between sm:px-4">
          <p className="max-w-2xl text-xs leading-relaxed text-ink-2">
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
                  className="flex rounded-xl border border-line bg-surface p-1"
                >
                  {(['crew', 'supervisor'] as const).map((workspace) => (
                    <button
                      key={workspace}
                      type="button"
                      aria-pressed={route.workspace === workspace}
                      onClick={() => {
                        window.location.hash = `/${workspace}/overview`
                      }}
                      className={`min-h-11 rounded-lg px-4 text-sm font-semibold capitalize transition-colors ${route.workspace === workspace ? 'bg-ink text-bg' : 'text-ink-2 hover:bg-surface-2'}`}
                    >
                      {workspace}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
        <div className="mb-5 sm:mb-7">
          <p className="kicker mb-1.5">
            {route.workspace === 'crew'
              ? 'Crew workspace'
              : 'Supervisor workspace'}
          </p>
          <h1
            ref={heading}
            tabIndex={-1}
            className="text-2xl font-bold tracking-tight outline-none sm:text-4xl"
          >
            {route.page === 'overview'
              ? 'Field overview'
              : descriptions[route.page].title}
          </h1>
          <p className="mt-2 hidden max-w-2xl text-sm leading-relaxed text-muted sm:block">
            {route.page === 'overview'
              ? 'Site status, field knowledge and the evidence that connects them.'
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
                Not available in this shell
              </h2>
              <p className="mt-3 max-w-xl text-sm leading-7 text-muted">
                {descriptions[route.page].pending} No live{' '}
                {active.title.toLowerCase()} are loaded in this shell.
              </p>
              <a
                href={`#/${route.workspace}/overview`}
                className="mt-7 inline-flex min-h-12 items-center gap-3 rounded-xl bg-ink px-5 text-sm font-semibold text-bg"
              >
                Back to overview <Icon name="arrow" className="size-4" />
              </a>
            </section>
          ))}
        <footer className="mt-10 flex flex-col gap-2 border-t border-line pt-5 text-xs leading-relaxed text-muted sm:flex-row sm:justify-between">
          <span className="font-semibold text-ink-2">PlanIT Control</span>
          <span>
            Advisory context does not authorize work or clear an alert.
          </span>
        </footer>
      </main>
      <div className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-nav px-2 pt-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] lg:hidden">
        {navigation(true)}
      </div>
    </div>
  )
}
