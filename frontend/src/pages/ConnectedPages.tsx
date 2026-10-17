import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from 'react'
import type {
  AnalysisVerdict,
  CrewReport,
  ReportCategory,
  SiteSummary,
} from '../types/api'
import {
  useApplication,
  useResource,
  useRoute,
  demoClient,
  useClock,
} from '../application/context'
import { StoredBriefings } from '../components/data/StoredBriefings'
import { sortSites } from '../api/contracts'
import {
  Action,
  big,
  card,
  control,
  field,
  labelText,
  primary,
  LoadState,
} from '../components/data/Interaction'
import { AlertCard } from '../components/data/AlertCard'
import { NoticeCard } from '../components/data/NoticeCard'
import {
  ScorePanel,
  Factors,
  Observations,
  Timestamp,
} from '../components/data/Status'
import { RiskBadge, RiskShape } from '../components/data/Risk'
import { LocationSearch } from '../components/data/LocationSearch'
import { evidenceOf } from '../components/data/evidence'
import { Icon, type IconName } from '../components/shell/Icon'
const Advisory = lazy(() =>
  import('../components/data/Advisory').then((m) => ({ default: m.Advisory })),
)
const SiteMap = lazy(() =>
  import('../components/data/SiteMap').then((m) => ({ default: m.SiteMap })),
)

function SectionHead({
  title,
  kicker,
  children,
}: {
  title: string
  kicker?: string
  children?: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-2">
      <div>
        {kicker && <p className="kicker mb-1">{kicker}</p>}
        <h2 className="text-lg font-bold tracking-tight @lg:text-xl">
          {title}
        </h2>
      </div>
      {children}
    </div>
  )
}
function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="flex items-start gap-2.5 rounded-2xl border border-dashed border-line-strong p-4 text-sm text-ink-2">
      <RiskShape kind="nodata" className="mt-0.5 size-4" />
      <span>{children}</span>
    </p>
  )
}

export function ConnectedPages() {
  const { client, persona } = useApplication(),
    [, page = 'overview', encodedId] = useRoute()
  const sites = useResource(
    'sites',
    useCallback(() => client.sites(), [client]),
  )
  if (!sites.data) return <LoadState error={sites.error} />
  if (!sites.data.length)
    return (
      <p role="status" className={`${card} p-5 text-ink-2`}>
        No authorized sites returned. Ask your administrator to verify your team
        assignment.
      </p>
    )
  const selected = encodedId ? decodeId(encodedId) : sites.data[0].id
  if (page === 'reports') return <ReportsPage sites={sites.data} />
  if (page === 'alerts') return <AlertsPage id={encodedId ? selected : null} />
  if (page === 'briefings') return <BriefingsPage sites={sites.data} />
  if (page === 'sites' && persona === 'supervisor' && !encodedId)
    return <SitesPage sites={sites.data} />
  if (!sites.data.some((s) => s.id === selected))
    return (
      <p
        role="alert"
        className="rounded-2xl border-2 border-stop bg-surface p-5 font-semibold"
      >
        This site is outside the sites returned for your session.
      </p>
    )
  return (
    <SitePage
      id={selected}
      compact={page === 'overview' && persona === 'crew'}
      dashboard={page === 'overview' && persona === 'supervisor'}
      sites={sites.data}
    />
  )
}
function decodeId(value: string) {
  try {
    return decodeURIComponent(value)
  } catch {
    return 'invalid-id'
  }
}
function SitePage({
  id,
  compact,
  dashboard,
  sites,
}: {
  id: string
  compact: boolean
  dashboard: boolean
  sites: SiteSummary[]
}) {
  const { client, persona, refresh } = useApplication()
  const result = useResource(
    `site:${id}`,
    useCallback(() => client.site(id), [client, id]),
  )
  if (dashboard) return <SitesPage sites={sites} />
  if (!result.data) return <LoadState error={result.error} />
  const site = result.data,
    active = site.alerts.filter((a) => a.state === 'active')
  const actions = (
    <div className="space-y-3">
      <div className="grid gap-3 @lg:grid-cols-2">
        <a className={primary + big} href={`#/${persona}/reports`}>
          <Icon name="camera" className="size-6" />
          Report a hazard
        </a>
        <a className={control + big} href={`#/${persona}/briefings`}>
          <Icon name="briefings" className="size-6" />
          View briefing
        </a>
      </div>
      <button
        type="button"
        className={control + ' w-full border-dashed @lg:w-auto'}
        onClick={refresh}
      >
        <Icon name="refresh" className="size-4" />
        Refresh server state
      </button>
    </div>
  )
  return (
    <div className="pc-enter space-y-5">
      {compact && (
        <div>
          <h2 className="text-xl font-bold leading-tight tracking-tight">
            {site.name}
          </h2>
          <p className="text-sm text-muted">
            {site.assigned_team?.name ?? 'No team assigned'}
          </p>
        </div>
      )}
      {compact && active[0] && <AlertCard alert={active[0]} />}
      {compact && !active.length && (
        <Empty>
          No active alerts supplied for this view. This does not establish safe
          conditions.
        </Empty>
      )}
      <div className="grid gap-5 @3xl:grid-cols-12 @3xl:items-start">
        <div className="space-y-5 @3xl:col-span-7">
          {compact && actions}
          <section className={`${card} p-5`}>
            <p className="kicker mb-1.5">
              {site.location_type?.replaceAll('_', ' ') || 'Location'}
            </p>
            {!compact && (
              <h2 className="text-2xl font-bold tracking-tight">{site.name}</h2>
            )}
            <p className={compact ? 'text-ink-2' : 'mt-1 text-ink-2'}>
              {compact
                ? (site.region ?? 'Region not supplied')
                : `${site.assigned_team?.name ?? 'No team assigned'} · ${site.region ?? 'Region not supplied'}`}
            </p>
            <p className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 break-words font-mono text-xs text-muted">
              <span className="inline-flex items-center gap-1">
                <Icon name="pin" className="size-3.5" />
                {site.id} · {site.lat}, {site.lon}
              </span>
              <span>{site.source}</span>
            </p>
          </section>
          {!compact && actions}
          <ScorePanel site={site} demo={client.mode === 'demo'} />
          <section className="space-y-3">
            <SectionHead
              kicker="Conditions"
              title="Observations and issued forecasts"
            />
            <Observations rows={site.observations} />
          </section>
          <details className={`${card} group`}>
            <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-3 px-5 text-base font-bold">
              Score factors and source evidence
              <Icon
                name="back"
                className="size-5 -rotate-90 transition-transform group-open:rotate-90"
              />
            </summary>
            <div className="border-t border-line px-5 pb-2">
              <Factors factors={site.top_factors} />
            </div>
          </details>
        </div>
        <div className="space-y-5 @3xl:col-span-5">
          {!compact && (
            <section className="space-y-3">
              <SectionHead kicker="Deterministic rules" title="Alert details" />
              {site.alerts.length ? (
                site.alerts.map((a) => (
                  <AlertCard key={a.id} alert={a} detail />
                ))
              ) : (
                <Empty>No alert record supplied for this site.</Empty>
              )}
            </section>
          )}
          <section className="space-y-3">
            <SectionHead
              kicker="Field notices"
              title="Potential notices and approved instructions"
            />
            {site.notices.length ? (
              site.notices.map((n) => <NoticeCard key={n.id} notice={n} />)
            ) : (
              <Empty>
                No notices supplied. Local electrical, structural and access
                conditions remain unverified.
              </Empty>
            )}
          </section>
          <section className="space-y-3">
            <SectionHead kicker="Crew reports" title="Reports at this site" />
            {site.reports.length ? (
              site.reports.map((r) => <ReportCard key={r.id} report={r} />)
            ) : (
              <Empty>No reports supplied.</Empty>
            )}
          </section>
        </div>
      </div>
      <Suspense
        fallback={
          <p role="status" className="kicker">
            Loading advisory…
          </p>
        }
      >
        <Advisory site={site} demo={client.mode === 'demo'} />
      </Suspense>
    </div>
  )
}

function Stat({
  value,
  label,
  shape,
  pressed,
  onToggle,
}: {
  value: number
  label: string
  shape: Parameters<typeof RiskShape>[0]['kind']
  /** When set, the stat doubles as a filter toggle. */
  pressed?: boolean
  onToggle?: () => void
}) {
  const body = (
    <>
      <RiskShape kind={shape} className="mt-1.5 size-4" />
      <span className="leading-tight">
        <span className="block text-3xl font-bold tabular-nums tracking-tight">
          {value}
        </span>
        <span className="text-sm text-ink-2">{label}</span>
        {onToggle && (
          <span className="mt-1.5 block font-mono text-[11px] font-semibold tracking-wider text-muted uppercase">
            {pressed ? 'Filter on · show all' : 'Filter list'}
          </span>
        )}
      </span>
    </>
  )
  return onToggle ? (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onToggle}
      className={`pc-press flex items-start gap-3 rounded-2xl border p-4 text-left hover:border-line-strong ${pressed ? 'border-ink bg-surface-2' : 'border-line bg-surface'}`}
    >
      {body}
    </button>
  ) : (
    <div className={`${card} flex items-start gap-3 p-4`}>{body}</div>
  )
}

function SitesPage({ sites }: { sites: SiteSummary[] }) {
  const { persona, client } = useApplication()
  const [search, setSearch] = useState(''),
    [assignment, setAssignment] = useState('all'),
    [hazard, setHazard] = useState('all'),
    [region, setRegion] = useState('all'),
    [alerts, setAlerts] = useState(false)
  const state = (s: SiteSummary) =>
    s.id.match(/^eia860m-([A-Z]{2})-/)?.[1] ?? 'Not supplied'
  const shown = useMemo(
    () =>
      sortSites(
        sites.filter(
          (s) =>
            (s.name + ' ' + s.id + ' ' + (s.assigned_team?.name ?? ''))
              .toLowerCase()
              .includes(search.toLowerCase()) &&
            (assignment === 'all' ||
              Boolean(s.assigned_team) === (assignment === 'assigned')) &&
            (hazard === 'all' ||
              s.top_factors.some((f) => f.factor === hazard)) &&
            (region === 'all' || state(s) === region) &&
            (!alerts || s.active_alerts > 0),
        ),
        client.mode === 'demo',
      ),
    [sites, search, assignment, hazard, region, alerts, client.mode],
  )
  const select = useCallback(
    (id: string) => {
      location.hash = `/${persona}/sites/${encodeURIComponent(id)}`
    },
    [persona],
  )
  const legacy = (s: SiteSummary) =>
    client.mode === 'demo' && s.top_factors.some((f) => f.factor === 'model')
  const ranked = useMemo(
    () => sortSites(sites, client.mode === 'demo'),
    [sites, client.mode],
  )
  const counts = {
    high: sites.filter(
      (s) => !legacy(s) && s.risk_score !== null && s.risk_score >= 7,
    ).length,
    alerting: sites.filter((s) => s.active_alerts > 0).length,
    unscored: sites.filter(
      (s) => s.risk_score === null || legacy(s) || evidenceOf(s) === 'none',
    ).length,
    teams: sites.filter((s) => s.assigned_team).length,
  }
  const columns =
    '@2xl:grid @2xl:grid-cols-[2.5rem_minmax(0,1.5fr)_10rem_minmax(0,1.6fr)_minmax(0,1fr)] @2xl:items-start @2xl:gap-4'
  return (
    <div className="pc-enter space-y-6">
      <div className="space-y-2">
        <p className="text-base font-semibold">
          {sites.length}{' '}
          {client.mode === 'demo' ? 'sample/reference' : 'backend-authorized'}{' '}
          locations. Assigned teams first, then eligible supplied score. Unknown
          is never low risk.
        </p>
        {client.mode === 'demo' && (
          <p className="max-w-3xl text-sm text-muted">
            Includes 50 reconciled EIA reference plants, not verified active
            jobs, plus five canonical simulated sites. Reference plants have no
            live readings or score. Legacy ML fixture scores are excluded from
            ranking.
          </p>
        )}
      </div>
      <div className="grid grid-cols-2 gap-3 @3xl:grid-cols-4">
        <Stat
          value={counts.alerting}
          label="sites with active alerts"
          shape="stop"
          pressed={alerts}
          onToggle={() => setAlerts(!alerts)}
        />
        <Stat
          value={counts.high}
          label="high-risk sites, score 7.0 or higher"
          shape="warn"
        />
        <Stat
          value={counts.teams}
          label="locations with an assigned team"
          shape="low"
          pressed={assignment === 'assigned'}
          onToggle={() =>
            setAssignment(assignment === 'assigned' ? 'all' : 'assigned')
          }
        />
        <Stat
          value={counts.unscored}
          label="not scored, withheld or without evidence"
          shape="nodata"
        />
      </div>
      <section
        aria-label="Location filters"
        className={`${card} grid gap-3 p-4 @lg:grid-cols-2 @3xl:sticky @3xl:top-[3.75rem] @3xl:z-10 @3xl:grid-cols-[minmax(0,1.4fr)_repeat(3,minmax(0,1fr))_auto] @3xl:items-end @3xl:shadow-xl @3xl:shadow-black/30`}
      >
        <LocationSearch
          sites={ranked}
          value={search}
          onChange={setSearch}
          onPick={select}
          withheld={legacy}
        />
        <label className={labelText}>
          Team assignment
          <select
            className={field}
            value={assignment}
            onChange={(e) => setAssignment(e.target.value)}
          >
            <option value="all">All</option>
            <option value="assigned">Assigned</option>
            <option value="unassigned">Unassigned</option>
          </select>
        </label>
        <label className={labelText}>
          State / reference region
          <select
            className={field}
            value={region}
            onChange={(e) => setRegion(e.target.value)}
          >
            <option value="all">All regions</option>
            {[...new Set(sites.map(state))].sort().map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <label className={labelText}>
          Supplied factor
          <select
            className={field}
            value={hazard}
            onChange={(e) => setHazard(e.target.value)}
          >
            <option value="all">All factors</option>
            {[
              ...new Set(
                sites.flatMap((s) => s.top_factors.map((f) => f.factor)),
              ),
            ].map((f) => (
              <option key={f}>{f}</option>
            ))}
          </select>
        </label>
        <label className="flex min-h-11 items-center gap-3 rounded-xl border border-line-strong px-3 text-sm font-semibold text-ink-2">
          <input
            type="checkbox"
            className="size-5"
            checked={alerts}
            onChange={(e) => setAlerts(e.target.checked)}
          />
          Active alerts supplied
        </label>
      </section>
      {shown.length ? (
        <Suspense
          fallback={
            <p role="status" className="kicker">
              Loading map…
            </p>
          }
        >
          <SiteMap sites={shown} select={select} />
        </Suspense>
      ) : (
        <p role="status" className={`${card} p-5`}>
          No locations match these filters.
        </p>
      )}
      {client.mode === 'demo' && (
        <div
          className="flex flex-wrap items-center gap-2"
          aria-label="Demo replays"
          role="group"
        >
          <span className="kicker mr-1">Replays</span>
          <a className={control} href="#/supervisor/sites/eia860m-FL-59611">
            Flood advisory replay
          </a>
          <a className={control} href="#/supervisor/sites/eia860m-AZ-68414">
            Wind advisory replay
          </a>
        </div>
      )}
      <section className="space-y-3">
        <SectionHead kicker="Ranking" title="All sites by risk" />
        <div className={`${card} overflow-hidden`}>
          <div
            aria-hidden="true"
            className={`hidden border-b border-line bg-surface-2 px-4 py-2.5 text-xs font-semibold text-muted ${columns}`}
          >
            <span>Rank</span>
            <span>Site</span>
            <span>Risk score</span>
            <span>What drives the score</span>
            <span>Alerts · data · updated</span>
          </div>
          <ol aria-label="Ranked locations" className="divide-y divide-line">
            {shown.map((s, i) => (
              <li
                key={s.id}
                className={`grid gap-2 px-4 py-3 ${columns} transition-colors hover:bg-surface-2/60 ${s.active_alerts > 0 ? 'bg-stop/10' : ''}`}
              >
                <span className="hidden pt-2.5 text-sm tabular-nums text-muted @2xl:block">
                  {i + 1}
                </span>
                <div className="min-w-0">
                  <a
                    className="inline-flex min-h-11 items-center text-lg font-bold text-ink underline decoration-line-strong underline-offset-4 hover:decoration-ink"
                    href={`#/${persona}/sites/${encodeURIComponent(s.id)}`}
                  >
                    {s.name}
                  </a>
                  <p className="text-sm text-muted">
                    {s.assigned_team?.name ?? 'No team assigned'} · {s.id}
                  </p>
                </div>
                <div className="space-y-1 @2xl:pt-2">
                  {s.risk_score === null ? (
                    <RiskBadge level={null} size="lg" />
                  ) : legacy(s) ? (
                    <p className="flex items-center gap-1.5 text-sm font-semibold text-ink-2">
                      <RiskShape kind="nodata" className="size-3.5" />
                      Legacy fixture score withheld
                    </p>
                  ) : evidenceOf(s) === 'none' ? (
                    <>
                      <RiskBadge level={s.risk_level} evidence="none" />
                      <p className="text-xs text-muted tabular-nums">
                        Server value {s.risk_score} / 10 ·{' '}
                        {s.risk_level ?? 'level unavailable'}
                      </p>
                    </>
                  ) : (
                    <>
                      <p className="text-lg leading-none font-bold tabular-nums">
                        {s.risk_score}{' '}
                        <span className="text-sm font-semibold text-muted">
                          / 10
                        </span>
                      </p>
                      <RiskBadge
                        level={s.risk_level}
                        evidence={evidenceOf(s)}
                      />
                    </>
                  )}
                </div>
                <p className="text-sm leading-snug text-ink-2 @2xl:pt-2">
                  <span className="@2xl:sr-only">Top supplied factors: </span>
                  {s.top_factors.length
                    ? s.top_factors
                        .map((factor) =>
                          factor.factor === 'model'
                            ? 'unapproved legacy ML factor withheld'
                            : `${factor.label} (${factor.data_state})`,
                        )
                        .join('; ')
                    : 'not supplied'}
                </p>
                <p className="text-sm text-ink-2 @2xl:pt-2">
                  <span
                    className={
                      s.active_alerts > 0 ? 'font-bold text-stop-text' : ''
                    }
                  >
                    {s.active_alerts > 0 && (
                      <RiskShape
                        kind="stop"
                        className="mr-1 inline size-3.5 align-[-2px]"
                      />
                    )}
                    {s.active_alerts}{' '}
                    {client.mode === 'demo' ? 'demo' : 'supplied'} active alerts
                  </span>{' '}
                  · Completeness {Math.round(s.data_completeness * 100)}% ·
                  Updated <Timestamp value={s.updated_at} />
                </p>
              </li>
            ))}
          </ol>
        </div>
        <p className="text-sm text-muted">
          Completeness is the share of inputs that reported. Missing inputs
          lower confidence; they never count as zero risk.
        </p>
      </section>
    </div>
  )
}
function AlertsPage({ id }: { id: string | null }) {
  const { client, refresh } = useApplication()
  const alerts = useResource(
    'alerts',
    useCallback(() => client.alerts(), [client]),
  )
  const demo = demoClient(client)
  if (!alerts.data) return <LoadState error={alerts.error} />
  const rows = id ? alerts.data.filter((a) => a.id === id) : alerts.data
  return (
    <div className="pc-enter space-y-5">
      {id && (
        <a
          href={`#${location.hash.split('/').slice(0, 3).join('/').slice(1)}`}
          className={control}
        >
          <Icon name="back" className="size-4" />
          All alerts
        </a>
      )}
      <div className="grid gap-5 @3xl:grid-cols-2 @3xl:items-start">
        {rows.length ? (
          rows.map((a) => <AlertCard key={a.id} alert={a} detail />)
        ) : (
          <Empty>No alert record supplied for this selection.</Empty>
        )}
      </div>
      {demo && (
        <section
          className="space-y-3 rounded-2xl border border-dotted border-sim p-4"
          aria-label="Simulated server updates"
        >
          <p className="kicker text-sim!">Simulation controls</p>
          <p className="text-sm text-ink-2">
            Demo-only server-payload replay. No production rule is run or
            changed.
          </p>
          <div className="flex flex-wrap gap-3">
            <button
              className={control}
              onClick={() => {
                demo.replay('strike')
                refresh()
              }}
            >
              Replay additional qualifying strike
            </button>
            <button
              className={control}
              onClick={() => {
                demo.replay('cleared')
                refresh()
              }}
            >
              Replay server-cleared payload
            </button>
          </div>
        </section>
      )}
    </div>
  )
}
// T060 verdict in words, never color alone. Cache's T036A builds the full side panel.
const verdictText: Record<AnalysisVerdict, string> = {
  supports: 'Supports the report',
  contradicts: 'Contradicts the report',
  inconclusive: "Inconclusive: the data can't confirm or rule it out",
}
const categories: Record<ReportCategory, string> = {
  broken_pole_downed_line: 'Broken pole / downed line',
  on_site_fire: 'On-site fire',
  wildlife: 'Wildlife',
  flooding: 'Flooding',
  other: 'Other',
}
const categoryIcon: Record<ReportCategory, IconName> = {
  broken_pole_downed_line: 'bolt',
  on_site_fire: 'spark',
  wildlife: 'pin',
  flooding: 'layers',
  other: 'doc',
}
function ReportForm({ site }: { site: SiteSummary }) {
  const { client, refresh } = useApplication()
  const [category, setCategory] = useState<ReportCategory>(
      'broken_pole_downed_line',
    ),
    [presence, setPresence] = useState(''),
    [lat, setLat] = useState(String(site.lat)),
    [lon, setLon] = useState(String(site.lon)),
    [note, setNote] = useState(''),
    [photo, setPhoto] = useState<File | null>(null),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState('')
  const inFlight = useRef(false)
  // Local preview of the selected photo; the object URL never leaves the page.
  const [preview, setPreview] = useState<string | null>(null)
  const previewUrl = useRef<string | null>(null)
  useEffect(
    () => () => {
      if (previewUrl.current) URL.revokeObjectURL(previewUrl.current)
    },
    [],
  )
  function choosePhoto(file: File | null) {
    if (previewUrl.current) URL.revokeObjectURL(previewUrl.current)
    previewUrl.current = file ? URL.createObjectURL(file) : null
    setPreview(previewUrl.current)
    setPhoto(file)
  }
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!presence || inFlight.current) return
    inFlight.current = true
    setBusy(true)
    setMessage('')
    try {
      await client.submit(
        {
          site_id: site.id,
          category,
          hazard_present: presence === 'present',
          lat: Number(lat),
          lon: Number(lon),
          note: note || null,
        },
        photo,
      )
      setMessage(
        client.mode === 'demo'
          ? 'Simulated report stored in this browser only. Review is pending; no score changed.'
          : 'Report accepted by backend; await human review.',
      )
      refresh()
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'Submission unavailable')
    } finally {
      inFlight.current = false
      setBusy(false)
    }
  }
  const step = 'kicker mb-2 flex items-center gap-2 text-ink!'
  return (
    <form
      aria-label="Hazard report"
      onSubmit={submit}
      className={`${card} space-y-6 p-4 @lg:p-6`}
    >
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Report a hazard</h2>
        <p className="mt-1 text-sm text-ink-2">
          {client.mode === 'demo'
            ? 'Demo only. Avoid private photos; selected photos stay in memory and are not persisted across reload.'
            : 'Submitted to the configured backend only; server validates permissions and storage.'}{' '}
          Note is optional.
        </p>
      </div>
      <fieldset>
        <legend className={step}>1 · Hazard category</legend>
        <div className="grid grid-cols-2 gap-2 @lg:grid-cols-3">
          {Object.entries(categories).map(([id, label]) => (
            <label
              key={id}
              className="relative flex min-h-16 cursor-pointer flex-col justify-center gap-1 rounded-xl border-2 border-line px-3 py-2 text-sm font-semibold text-ink-2 transition-colors hover:border-line-strong has-checked:border-ink has-checked:bg-ink has-checked:text-bg has-[input:focus-visible]:outline-3 has-[input:focus-visible]:outline-offset-2 has-[input:focus-visible]:outline-focus"
            >
              <input
                type="radio"
                name="category"
                value={id}
                checked={category === id}
                onChange={() => setCategory(id as ReportCategory)}
                className="absolute inset-0 m-0 size-full cursor-pointer opacity-0"
              />
              <Icon
                name={categoryIcon[id as ReportCategory]}
                className="size-5"
              />
              {label}
            </label>
          ))}
        </div>
      </fieldset>
      <div>
        <p className={step} aria-hidden="true">
          2 · Is it there?
        </p>
        <label className={labelText}>
          Hazard present or absent (required)
          <select
            required
            className={`${field} min-h-14 border-2 text-lg font-bold ${presence === 'present' ? 'border-stop bg-stop text-white' : presence === 'absent' ? 'border-ink' : ''}`}
            value={presence}
            onChange={(e) => setPresence(e.target.value)}
          >
            <option value="">Choose present or absent</option>
            <option value="present">Hazard present</option>
            <option value="absent">Hazard absent</option>
          </select>
        </label>
        <p className="mt-2 text-sm text-muted">
          {presence === 'present'
            ? 'Present: a potential-hazard notice with no instructions goes to teams in the radius after submission.'
            : presence === 'absent'
              ? 'Absent: no notice is sent. Your organization’s supervisor reviews the report.'
              : 'Choose one to continue.'}
        </p>
      </div>
      <div>
        <p className={step} aria-hidden="true">
          3 · Photo
        </p>
        <label className={labelText}>
          <span className="inline-flex items-center gap-2">
            <Icon name="camera" className="size-4" />
            {client.mode === 'demo'
              ? 'Photo (optional in demo)'
              : 'Photo (required when hazard present)'}
          </span>
          <input
            type="file"
            required={client.mode === 'live' && presence === 'present'}
            accept="image/jpeg,image/png,image/webp"
            className={`${field} py-2.5`}
            onChange={(e) => choosePhoto(e.target.files?.[0] ?? null)}
          />
        </label>
        {photo && (
          <div className="mt-3 flex items-center gap-3 rounded-xl bg-surface-2 p-2.5">
            {preview && (
              <img
                src={preview}
                alt="Preview of the selected photo"
                className="size-16 shrink-0 rounded-lg object-cover ring-1 ring-line-strong"
              />
            )}
            <p className="min-w-0 text-sm text-ink-2">
              {photo.name} selected · {Math.ceil(photo.size / 1024)} KB. Allowed
              JPEG/PNG/WebP, maximum 5 MB.
            </p>
          </div>
        )}
      </div>
      <fieldset>
        <legend className={step}>
          <Icon name="pin" className="size-4" />4 · Location
        </legend>
        <div className="grid gap-3 @lg:grid-cols-2">
          <label className={labelText}>
            Latitude
            <input
              required
              type="number"
              min="-90"
              max="90"
              step="any"
              className={field}
              value={lat}
              onChange={(e) => setLat(e.target.value)}
            />
          </label>
          <label className={labelText}>
            Longitude
            <input
              required
              type="number"
              min="-180"
              max="180"
              step="any"
              className={field}
              value={lon}
              onChange={(e) => setLon(e.target.value)}
            />
          </label>
        </div>
        <p className="mt-2 text-xs text-muted">
          Coordinates start at the selected reference location. Confirm the
          actual report location before submission.
        </p>
      </fieldset>
      <label className={labelText}>
        Optional note
        <textarea
          className={field}
          rows={3}
          maxLength={1000}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </label>
      <button
        className={primary + big}
        disabled={
          busy ||
          !presence ||
          !client.capabilities.reports ||
          (client.mode === 'live' && presence === 'present' && !photo)
        }
        type="submit"
      >
        {busy
          ? 'Uploading…'
          : client.mode === 'demo'
            ? 'Submit simulated report'
            : 'Submit report'}
      </button>
      {!client.capabilities.reports && (
        <p className="text-sm text-muted">
          Live report submission and photo storage are unavailable on this
          backend.
        </p>
      )}
      {message && (
        <p
          role="status"
          aria-live="polite"
          className="rounded-xl bg-surface-2 px-3 py-2.5 font-semibold ring-1 ring-line-strong"
        >
          {message}
        </p>
      )}
    </form>
  )
}
const reviewLook = {
  pending: {
    shape: 'nodata',
    text: 'Pending review',
    cls: 'border-dashed border-line-strong text-ink-2',
  },
  confirmed: {
    shape: 'warn',
    text: 'Confirmed',
    cls: 'border-warn text-warn-text',
  },
  rejected: {
    shape: 'clear',
    text: 'Rejected',
    cls: 'border-line-strong text-muted',
  },
} as const
function ReportCard({ report }: { report: CrewReport }) {
  const { client, persona } = useApplication()
  const photo = demoClient(client)?.photo(report.id)
  const [reviewCategory, setReviewCategory] = useState<ReportCategory>(
    report.category,
  )
  const [severity, setSeverity] = useState<'' | 'low' | 'moderate' | 'high'>('')
  const look = reviewLook[report.review_status]
  return (
    <article data-report-id={report.id} className={`${card} space-y-3 p-4`}>
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 font-mono text-[11px] font-semibold uppercase tracking-wider ${look.cls}`}
        >
          <RiskShape kind={look.shape} className="size-3.5" />
          {look.text}
        </span>
        <span
          className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 font-mono text-[11px] font-semibold uppercase tracking-wider ${report.hazard_present ? 'border-stop text-stop-text' : 'border-line-strong text-ink-2'}`}
        >
          {report.hazard_present ? 'Hazard present' : 'Hazard absent'}
        </span>
      </div>
      <h3 className="text-lg font-bold">
        {categories[report.category]} ·{' '}
        {report.hazard_present ? 'present' : 'absent'} · {report.review_status}
      </h3>
      <p className="break-words font-mono text-xs text-muted">
        {report.site_id} · {report.lat}, {report.lon}
      </p>
      <p className="text-xs text-muted">
        Report {report.id} · <Timestamp value={report.created_at} />
      </p>
      {report.note && (
        <p className="rounded-xl bg-surface-2 px-3 py-2 text-ink">
          {report.note}
        </p>
      )}
      {photo ? (
        <img
          className="max-h-48 max-w-full rounded-xl border border-line object-cover"
          src={photo}
          alt={`Selected demo evidence for ${categories[report.category]}`}
        />
      ) : report.photo_url ? (
        <p className="text-xs text-muted">
          Photo reference supplied; private photo retrieval is not connected.
        </p>
      ) : (
        <p className="text-xs text-muted">
          {client.mode === 'demo'
            ? 'No persisted photo. Demo photos are session-only.'
            : 'No photo reference supplied.'}
        </p>
      )}
      {report.enrichment && (
        <div className="rounded-xl border border-dotted border-sim p-3 text-sm">
          <strong className="inline-flex items-center gap-1.5 text-sim">
            <Icon name="spark" className="size-4" />
            AI analysis, needs human review
          </strong>
          {report.enrichment.status === 'complete' ? (
            <>
              <p className="mt-1 font-semibold text-ink">
                {verdictText[report.enrichment.verdict ?? 'inconclusive']}
              </p>
              <p className="mt-1 text-ink">{report.enrichment.summary}</p>
              <p className="mt-1 text-ink-2">
                Suggested: {report.enrichment.suggested_category ?? 'none'};{' '}
                {report.enrichment.severity_suggestion ?? 'no severity'}. Not
                confirmed by this analysis.
              </p>
            </>
          ) : (
            <p className="mt-1 text-ink-2">
              Photo analysis unavailable. The report stands on its own.
            </p>
          )}
        </div>
      )}
      {persona === 'supervisor' &&
        report.review_status === 'pending' &&
        !report.hazard_present && (
          <div className="space-y-3 rounded-xl border border-line bg-surface-2 p-3">
            <p className="kicker">Supervisor review</p>
            <div className="grid gap-3 @lg:grid-cols-2">
              <label className={labelText}>
                Reviewed category
                <select
                  className={field}
                  value={reviewCategory}
                  onChange={(e) =>
                    setReviewCategory(e.target.value as ReportCategory)
                  }
                >
                  {Object.entries(categories).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label className={labelText}>
                Reviewed severity (optional)
                <select
                  className={field}
                  value={severity}
                  onChange={(e) =>
                    setSeverity(e.target.value as typeof severity)
                  }
                >
                  <option value="">Not specified</option>
                  <option value="low">Low</option>
                  <option value="moderate">Moderate</option>
                  <option value="high">High</option>
                </select>
              </label>
            </div>
            <div className="flex flex-wrap gap-3">
              <Action
                tone="primary"
                run={() =>
                  client.review(report.id, {
                    decision: 'confirmed',
                    category: reviewCategory,
                    severity: severity || null,
                  })
                }
              >
                Confirm report classification
              </Action>
              <Action
                run={() => client.review(report.id, { decision: 'rejected' })}
              >
                Reject report
              </Action>
            </div>
          </div>
        )}
      {report.hazard_present && report.review_status === 'pending' && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-dashed border-caution p-3 text-sm text-ink-2">
          <p className="min-w-0 flex-1">
            Present report remains pending until a notified supervisor confirms
            its potential notice.
          </p>
          <a
            className={control}
            href={`#/${persona}/sites/${encodeURIComponent(report.site_id)}`}
          >
            Open site notices
          </a>
        </div>
      )}
      <p className="text-xs text-muted">
        Review does not authorize work. Pending/rejected reports are not
        confirmed hazards.
      </p>
    </article>
  )
}
function ReportsPage({ sites }: { sites: SiteSummary[] }) {
  const { client, refresh } = useApplication()
  const result = useResource(
    'reports',
    useCallback(() => client.reports(), [client]),
  )
  const [siteId, setSiteId] = useState(sites[0].id)
  const site = sites.find((s) => s.id === siteId) ?? sites[0]
  return (
    <div className="pc-enter grid gap-6 @3xl:grid-cols-12 @3xl:items-start">
      <div className="space-y-4 @3xl:col-span-7">
        <label className={labelText}>
          Report location
          <select
            aria-label="Report location"
            className={field}
            value={site.id}
            onChange={(e) => setSiteId(e.target.value)}
          >
            {sites.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className={control} onClick={refresh}>
          <Icon name="refresh" className="size-4" />
          Refresh reports and server state
        </button>
        <ReportForm key={site.id} site={site} />
      </div>
      <div className="@3xl:col-span-5">
        {result.data ? (
          <section className="space-y-3" aria-label="Submitted reports">
            <SectionHead kicker="Review queue" title="Reports and review" />
            {result.data
              .filter((r) => sites.some((s) => s.id === r.site_id))
              .map((r) => (
                <ReportCard key={r.id} report={r} />
              ))}
            {!result.data.length && <Empty>No reports returned.</Empty>}
          </section>
        ) : (
          <LoadState error={result.error} />
        )}
      </div>
    </div>
  )
}
function BriefingsPage({ sites }: { sites: SiteSummary[] }) {
  return <StoredBriefings sites={sites} />
}
export function DemoClock() {
  const now = useClock()
  return (
    <span className="font-mono tracking-wide">
      Replay clock: <Timestamp value={new Date(now).toISOString()} />
    </span>
  )
}
