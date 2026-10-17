import { useEffect, useRef, useState, type ReactNode } from 'react'
import { shellContext, shellMode } from '../../api/shell-fixtures'
import { Icon, type IconName } from './Icon'
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
      'A shared place for locations, assigned teams and the evidence behind site conditions.',
    pending: 'The site list, map and site detail are not connected yet.',
  },
  alerts: {
    title: 'Crew alerts',
    description:
      'Official controls and deterministic alerts will stay visible alongside their triggering evidence.',
    pending:
      'Alert details, acknowledgements and timers are not connected yet.',
  },
  reports: {
    title: 'Hazard reports',
    description:
      'Crew observations and supervisor review will bring field knowledge into the shared picture.',
    pending: 'Report submission and review are not connected yet.',
  },
  briefings: {
    title: 'Shift briefings',
    description:
      'A place for evidence-based summaries, source references and the conditions that remain unknown.',
    pending: 'Briefings and explanations are not connected yet.',
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

  function navigation(mobile = false) {
    return (
      <nav
        aria-label={mobile ? 'Mobile workspace' : 'Workspace'}
        className={mobile ? 'grid grid-cols-5' : 'space-y-1.5'}
      >
        {destinations.map((item) => (
          <a
            key={item.id}
            href={`#/${route.workspace}/${item.id}`}
            aria-current={route.page === item.id ? 'page' : undefined}
            className={
              mobile
                ? `flex min-h-16 min-w-0 flex-col items-center justify-center gap-1 text-[11px] font-semibold ${route.page === item.id ? 'text-teal-800' : 'text-slate-600'} focus-visible:outline-2 focus-visible:-outline-offset-4 focus-visible:outline-teal-600`
                : `flex min-h-12 items-center gap-3 rounded-lg px-4 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-300 ${route.page === item.id ? 'bg-teal-400/15 text-teal-200 ring-1 ring-inset ring-teal-300/20' : 'text-slate-300 hover:bg-white/5 hover:text-white'}`
            }
          >
            <Icon name={item.icon} className="size-5 shrink-0" />
            {item.id === 'sites' && route.workspace === 'crew'
              ? 'My worksite'
              : item.title}
            {!mobile && route.page === item.id && (
              <span className="ml-auto size-1.5 rounded-full bg-teal-300" />
            )}
          </a>
        ))}
      </nav>
    )
  }

  return (
    <div className="min-h-svh bg-[#f4f6f7] text-slate-900 lg:pl-60">
      <a
        href="#main-content"
        onClick={(event) => {
          event.preventDefault()
          document.getElementById('main-content')?.focus()
        }}
        className="sr-only fixed left-4 top-4 z-50 rounded-lg bg-white p-4 text-teal-900 shadow-lg focus:not-sr-only"
      >
        Skip to content
      </a>
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col bg-[#142a34] px-5 py-8 lg:flex">
        <a
          href={`#/${route.workspace}/overview`}
          aria-label="PlanIT Control overview"
          className="flex min-h-12 items-center gap-3 rounded-md text-white focus-visible:outline-2 focus-visible:outline-teal-300"
        >
          <span className="flex size-10 items-center justify-center rounded-lg bg-teal-300 text-[#142a34]">
            <Icon name="grid" className="size-7" />
          </span>
          <span>
            <span className="block text-xl font-bold tracking-tight">
              PlanIT<span className="font-normal text-teal-200"> Control</span>
            </span>
            <span className="text-[10px] uppercase tracking-[.2em] text-slate-400">
              Utility field operations
            </span>
          </span>
        </a>
        <p className="mb-4 mt-12 px-4 text-[10px] font-semibold uppercase tracking-[.2em] text-slate-400">
          Workspace
        </p>
        {navigation()}
        <div className="mt-auto border-t border-white/10 px-3 pt-5 text-xs leading-relaxed text-slate-400">
          <p className="font-semibold text-slate-200">
            Built around the field.
          </p>
          <p className="mt-2">
            Evidence informs the picture.
            <br />
            People and official controls govern the work.
          </p>
          <p className="mt-6 text-[10px] uppercase tracking-widest text-teal-200">
            Application preview
          </p>
        </div>
      </aside>
      <header className="border-b border-slate-200 bg-white px-5 sm:px-8 lg:px-10">
        <div className="mx-auto flex min-h-20 max-w-7xl items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-[#142a34] text-teal-200 lg:hidden">
              <Icon name="grid" className="size-6" />
            </span>
            <div>
              <p className="text-sm font-bold lg:hidden">PlanIT Control</p>
              <p className="text-xs text-slate-500 sm:text-sm">
                <span className="hidden sm:inline">
                  Field operations{' '}
                  <span className="px-2 text-slate-300">/</span>
                </span>
                {active.title}
              </p>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-900">
            <span className="size-1.5 rounded-full bg-amber-600" />
            {badge ?? (isFixture ? 'Fixture mode' : 'No live data')}
          </div>
        </div>
      </header>
      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto max-w-7xl min-w-0 [overflow-wrap:anywhere] px-5 pb-28 pt-6 outline-none sm:px-8 sm:pt-8 lg:px-10 lg:pb-10"
      >
        <div className="mb-7 flex flex-col justify-between gap-4 xl:flex-row xl:items-center">
          <p className="max-w-xl text-xs leading-relaxed text-slate-600">
            <strong className="font-semibold text-slate-800">
              {badge ??
                (isFixture ? 'Demonstration workspace.' : 'No connected data.')}
            </strong>{' '}
            {message ??
              (isFixture
                ? 'Bundled sample data, not live conditions. Sign-in is not connected to this shell.'
                : 'Live API and sign-in integration are not connected to this shell.')}
          </p>
          {controls ?? (
            <div className="flex shrink-0 flex-wrap items-center gap-3">
              <span className="text-[11px] font-medium text-slate-500">
                Preview workspace
              </span>
              <div
                role="group"
                aria-label="Preview workspace, not an authorization role"
                className="flex rounded-lg border border-slate-200 bg-white p-1"
              >
                {(['crew', 'supervisor'] as const).map((workspace) => (
                  <button
                    key={workspace}
                    type="button"
                    aria-pressed={route.workspace === workspace}
                    onClick={() => {
                      window.location.hash = `/${workspace}/overview`
                    }}
                    className={`min-h-11 rounded-md px-4 text-xs font-semibold capitalize transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700 ${route.workspace === workspace ? 'bg-[#142a34] text-white shadow-sm' : 'text-slate-600 hover:bg-slate-50'}`}
                  >
                    {workspace}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
        <div className="mb-7">
          <p className="mb-2 text-[10px] font-bold uppercase tracking-[.2em] text-teal-800">
            {route.workspace === 'crew'
              ? 'Crew workspace'
              : 'Supervisor workspace'}
          </p>
          <h1
            ref={heading}
            tabIndex={-1}
            className="text-3xl font-semibold tracking-tight outline-none sm:text-4xl"
          >
            {route.page === 'overview'
              ? 'Field overview'
              : descriptions[route.page].title}
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-600">
            {route.page === 'overview'
              ? 'Site context, field knowledge and the evidence that connects them.'
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
              className="rounded-2xl border border-slate-200 bg-white p-7 sm:p-10"
              aria-labelledby="workspace-status"
            >
              <div className="mb-6 flex size-14 items-center justify-center rounded-xl bg-slate-100 text-slate-500">
                <Icon name={active.icon} className="size-7" />
              </div>
              <p className="text-[10px] font-bold uppercase tracking-[.16em] text-slate-500">
                Workspace foundation
              </p>
              <h2 id="workspace-status" className="mt-3 text-xl font-semibold">
                This workspace is being connected
              </h2>
              <p className="mt-3 max-w-xl text-sm leading-7 text-slate-600">
                {descriptions[route.page].pending} No live{' '}
                {active.title.toLowerCase()} are loaded in this shell.
              </p>
              <a
                href={`#/${route.workspace}/overview`}
                className="mt-7 inline-flex min-h-12 items-center gap-3 rounded-lg bg-teal-800 px-5 text-sm font-semibold text-white hover:bg-teal-900 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal-700"
              >
                Back to overview <Icon name="arrow" className="size-4" />
              </a>
            </section>
          ))}
        <footer className="mt-8 flex flex-col gap-2 border-t border-slate-200 pt-5 text-[11px] leading-relaxed text-slate-500 sm:flex-row sm:justify-between">
          <span>
            PlanIT Control <span className="px-1 text-slate-300">/</span> Shared
            context for utility crews
          </span>
          <span>
            Advisory context does not authorize work or clear an alert.
          </span>
        </footer>
      </main>
      <div className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white pb-[env(safe-area-inset-bottom)] lg:hidden">
        {navigation(true)}
      </div>
    </div>
  )
}
