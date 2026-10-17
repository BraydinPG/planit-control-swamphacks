import { formatTimestamp } from '../presentation/display'
import type { ShellMode, shellContext } from '../api/shell-fixtures'
import type { Workspace } from '../components/shell/AppShell'
import { Icon, type IconName } from '../components/shell/Icon'

type Context = ReturnType<typeof shellContext>
const scenarioTime = formatTimestamp
const shortcuts: {
  title: string
  page: string
  icon: IconName
  description: string
}[] = [
  {
    title: 'Worksites',
    page: 'sites',
    icon: 'sites',
    description: 'Locations, teams and site evidence.',
  },
  {
    title: 'Field reports',
    page: 'reports',
    icon: 'reports',
    description: 'Crew observations and human review.',
  },
  {
    title: 'Shift briefings',
    page: 'briefings',
    icon: 'briefings',
    description: 'A shared view for the shift ahead.',
  },
]
export function WorkspaceOverview({
  workspace,
  mode,
  context,
}: {
  workspace: Workspace
  mode: ShellMode
  context: Context
}) {
  return (
    <div className="space-y-7">
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.65fr)_minmax(0,1fr)]">
        <section
          className="overflow-hidden rounded-2xl border border-slate-200 bg-white"
          aria-labelledby="reference-workspace"
        >
          <div className="relative overflow-hidden bg-[#193b40] px-6 py-7 text-white sm:px-8">
            <svg
              viewBox="0 0 320 160"
              aria-hidden="true"
              className="pointer-events-none absolute -right-3 -top-3 h-48 w-80 text-teal-200/10"
            >
              <g fill="none" stroke="currentColor" strokeWidth="1">
                <path d="M180 0 132 160M210 0l48 160M170 40h52M157 80h78M145 120h102M132 160l103-80M258 160 157 80M125 35h135M110 78h165M0 60l320-30M0 110l320-65" />
                <circle cx="55" cy="105" r="42" />
                <circle cx="55" cy="105" r="65" />
              </g>
            </svg>
            <p className="relative flex items-center gap-2 text-xs font-bold uppercase tracking-[.18em] text-teal-100">
              <span className="size-1.5 rounded-full bg-amber-300" />
              {context
                ? 'Simulated reference workspace'
                : 'Workspace connection'}
            </p>
            <h2
              id="reference-workspace"
              className="relative mt-5 max-w-md text-2xl font-semibold leading-snug tracking-tight"
            >
              {context ? context.site.name : 'No worksite connected'}
            </h2>
            <p className="relative mt-4 max-w-sm text-sm leading-relaxed text-teal-100/90">
              {context
                ? 'A bundled scenario for exploring the workspace. This location is not a verified active job or an EIA record.'
                : 'No site data loaded. Connect an authorized data source before using site information.'}
            </p>
          </div>
          {context ? (
            <div className="px-6 py-6 sm:px-8">
              <dl className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                <div>
                  <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Example team
                  </dt>
                  <dd className="mt-1.5 text-sm font-semibold">
                    {context.site.assigned_team?.name ?? 'No team assigned'}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Scenario region
                  </dt>
                  <dd className="mt-1.5 text-sm font-semibold">
                    {context.region ?? 'Region unavailable'}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Example updated
                  </dt>
                  <dd className="mt-1.5 text-xs font-medium">
                    {scenarioTime(context.site.updated_at)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Site score
                  </dt>
                  <dd className="mt-1.5 text-xs font-medium">
                    {context.site.risk_score === null
                      ? 'Not scored yet'
                      : 'Not available in this preview'}
                  </dd>
                </div>
              </dl>
              <div className="mt-6 border-t border-slate-100 pt-4 text-[11px] leading-relaxed text-slate-500">
                <span className="font-semibold text-slate-700">Source: </span>
                {context.source}
              </div>
            </div>
          ) : (
            <div
              role="status"
              className="px-6 py-7 text-sm leading-7 text-slate-600"
            >
              {mode === 'invalid'
                ? 'Fixture configuration is invalid. No sample or live data will be substituted.'
                : 'Live connection unavailable. Fixture mode is off; authenticated API integration is a separate step.'}
            </div>
          )}
        </section>
        <section
          aria-labelledby="connection-heading"
          className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-7"
        >
          <div className="flex items-center justify-between gap-3">
            <h2 id="connection-heading" className="text-base font-semibold">
              Workspace connections
            </h2>
            <Icon name="grid" className="size-5 text-slate-400" />
          </div>
          <p className="mt-2 text-sm leading-relaxed text-slate-500">
            Know where the information comes from.
          </p>
          <dl className="mt-6 divide-y divide-slate-100">
            <div className="py-4 first:pt-0">
              <dt className="text-sm font-medium">Sample data</dt>
              <dd className="mt-1 text-xs text-slate-600">
                {context ? 'Loaded · simulated fixtures' : 'Not loaded'}
              </dd>
            </div>
            <div className="py-4">
              <dt className="text-sm font-medium">Live site conditions</dt>
              <dd className="mt-1 text-xs text-slate-600">
                Unavailable · no live connection
              </dd>
            </div>
            <div className="py-4">
              <dt className="text-sm font-medium">Account session</dt>
              <dd className="mt-1 text-xs text-slate-600">Not connected</dd>
            </div>
          </dl>
          <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-relaxed text-amber-950">
            Switching preview workspaces changes navigation only. It does not
            sign you in or grant permissions.
          </div>
        </section>
      </div>
      <section aria-labelledby="workspace-heading">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h2 id="workspace-heading" className="text-base font-semibold">
            Explore the workspace
          </h2>
          <span className="text-[11px] text-slate-500">
            Navigation preview · features being connected
          </span>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {shortcuts.map((item) => (
            <a
              key={item.page}
              href={`#/${workspace}/${item.page}`}
              className="group flex min-h-36 flex-col rounded-xl border border-slate-200 bg-white p-5 transition-colors hover:border-teal-400 hover:bg-teal-50/30 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700"
            >
              <div className="mb-4 flex items-center justify-between">
                <Icon name={item.icon} className="size-6 text-teal-800" />
                <Icon
                  name="arrow"
                  className="size-4 text-slate-400 transition-transform group-hover:translate-x-1"
                />
              </div>
              <h3 className="text-sm font-semibold">{item.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-500">
                {item.description}
              </p>
            </a>
          ))}
        </div>
      </section>
      <div className="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-100/70 px-5 py-4 text-sm leading-relaxed text-slate-600">
        <Icon name="alerts" className="mt-0.5 size-4 shrink-0 text-slate-500" />
        <p>
          <strong className="font-semibold text-slate-800">
            Field verification remains essential.
          </strong>{' '}
          Electrical condition, structural stability and access remain
          unverified. Missing information is not evidence that a hazard is
          absent.
        </p>
      </div>
    </div>
  )
}
