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
  CrewReport,
  HazardNotice,
  MatCondition,
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
import { useReportLocation } from '../application/useReportLocation'
import type { LocationReason } from '../application/report-location'
import { StoredBriefings } from '../components/data/StoredBriefings'
import { SpeciesSection } from '../components/data/SpeciesPanel'
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
import { topTier, visibleAlertGroups } from '../presentation/alerts'
import { EventOutlooks } from '../components/data/EventOutlooks'
import { ConfirmedHazards, NoticeCard } from '../components/data/NoticeCard'
import { ReportAnalysis } from '../components/data/ReportAnalysis'
import { JoinTeam, TeamPage } from '../components/data/TeamRoster'
import { SupervisorOverview } from '../components/data/SupervisorOverview'
import {
  ScorePanel,
  Factors,
  Observations,
  Timestamp,
} from '../components/data/Status'
import { RiskBadge, RiskShape } from '../components/data/Risk'
import { LocationSearch } from '../components/data/LocationSearch'
import { evidenceOf } from '../components/data/evidence'
import { Masonry } from '../components/data/Masonry'
import { CountUp } from '../components/data/CountUp'
import { Icon, type IconName } from '../components/shell/Icon'
import {
  displayLabel,
  factorLabel,
  reportCategories,
} from '../presentation/display'
import { Details } from '../components/data/Details'
import { DemoSiteContext, isDemoSite } from '../components/data/demo-site'
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
  if (page === 'team' && persona === 'supervisor') return <TeamPage />
  if (!sites.data) return <LoadState error={sites.error} />
  if (!sites.data.length)
    // A live crew account sees no sites until it joins a team with a code.
    return client.mode === 'live' && persona === 'crew' ? (
      <JoinTeam />
    ) : (
      <p role="status" className={`${card} p-5 text-ink-2`}>
        No worksites are available for this account. Ask your administrator to
        check your organization and team assignment.
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
        This worksite is not available to your account. Return to your assigned
        worksites.
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
  const { client, persona, refresh, principalId } = useApplication()
  const result = useResource(
    `site:${id}`,
    useCallback(() => client.site(id), [client, id]),
  )
  if (dashboard) return <SupervisorOverview sites={sites} />
  if (!result.data) return <LoadState error={result.error} />
  const site = result.data,
    active = site.alerts.filter((a) => a.state === 'active'),
    // Only the most dangerous active tier is shown; lower tiers stay hidden until it clears.
    top = topTier(site.alerts)
  // A demo site says so only in its name ("... (demo)"), never in a type label.
  const demoSite = isDemoSite(site)
  const siteKind = demoSite
    ? 'Worksite'
    : displayLabel(site.location_type, 'Worksite')
  // Potential notices need a supervisor to confirm them; a confirmed one still
  // needs its confirming supervisor to send the instruction. Everything else is
  // settled and listed together under Confirmed hazards.
  const needsAction = (n: HazardNotice) =>
    n.status === 'potential' ||
    (persona === 'supervisor' &&
      n.confirmed_by === principalId &&
      !n.instruction_sent_at)
  const refreshButton = (
    <button
      type="button"
      className={control + ' w-full border-dashed @lg:w-auto'}
      onClick={refresh}
    >
      <Icon name="refresh" className="size-4" />
      Refresh worksite
    </button>
  )
  const score = <ScorePanel site={site} demo={client.mode === 'demo'} />
  const header = (
    <div>
      <h2 className="text-xl font-bold leading-tight tracking-tight">
        {site.name}
      </h2>
      <p className="text-sm text-muted">
        {site.assigned_team?.name ?? 'No team assigned'}
      </p>
    </div>
  )
  const locationDetails = (
    <Details title="Location and source">
      <p className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 break-words text-sm text-muted">
        <span className="inline-flex items-center gap-1">
          <Icon name="pin" className="size-3.5" />
          {site.id} · {site.lat}, {site.lon}
        </span>
        <span>{site.source}</span>
      </p>
    </Details>
  )
  const conditions = (
    <section className="space-y-3">
      <SectionHead title="Weather and conditions" />
      <Observations rows={site.observations} />
    </section>
  )
  const factors = (
    <details className={`${card} group`}>
      <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-3 px-5 text-base font-bold">
        Score factors and evidence
        <Icon
          name="back"
          className="size-5 -rotate-90 transition-transform group-open:rotate-90"
        />
      </summary>
      <div className="border-t border-line px-5 pb-2">
        {/* The full stored breakdown; top_factors is the list's top three only. */}
        <Factors
          factors={site.score?.factor_contributions ?? site.top_factors}
        />
      </div>
    </details>
  )
  const hazards = (
    <section className={`${card} space-y-3 border border-line p-3`}>
      <SectionHead title="Hazards and supervisor instructions" />
      {site.notices.length ? (
        <>
          {site.notices.filter(needsAction).map((n) => (
            <NoticeCard key={n.id} notice={n} outlook={site.event_outlook} />
          ))}
          <ConfirmedHazards
            notices={site.notices.filter((n) => !needsAction(n))}
            outlook={site.event_outlook}
          />
        </>
      ) : (
        <Empty>
          No notices supplied. Local electrical, structural and access
          conditions remain unverified.
        </Empty>
      )}
    </section>
  )
  const reports = (
    // Full width so reports sit side by side on wide screens.
    <section className={`${card} space-y-3 border border-line p-3`}>
      <SectionHead title="Reports at this site" />
      {site.reports.length ? (
        <Masonry
          label="Reports at this site"
          items={site.reports.map((r) => ({
            key: r.id,
            node: <ReportCard report={r} compact />,
          }))}
        />
      ) : (
        <Empty>No reports supplied.</Empty>
      )}
    </section>
  )
  const context = (
    <>
      <EventOutlooks
        cards={site.event_outlooks ?? []}
        tiles={persona === 'crew'}
      />
      {/* Read-only regional context for team sites; never feeds score or alerts. */}
      {site.assigned_team && <SpeciesSection site={site} />}
      <Suspense
        fallback={
          <p role="status" className="kicker">
            Loading advisory…
          </p>
        }
      >
        <Advisory site={site} demo={client.mode === 'demo'} />
      </Suspense>
    </>
  )

  // Crew home: what needs attention now. The evidence lives on My worksite.
  if (compact)
    return (
      <div className="pc-enter space-y-5">
        {header}
        {top.length > 0 && <AlertCard alerts={top} />}
        {!active.length && (
          <Empty>
            No active alerts reported. Worksite conditions still require
            verification.
          </Empty>
        )}
        {hazards}
        <div className="flex flex-wrap gap-3">
          <a
            className={control + ' w-full @lg:w-auto'}
            href={`#/${persona}/sites/${encodeURIComponent(site.id)}`}
          >
            <Icon name="sites" className="size-4" />
            Full worksite details
          </a>
          {refreshButton}
        </div>
      </div>
    )

  // Crew worksite: score breakdown, conditions, reports and context. Alerts,
  // hazards and instructions stay on Home; reporting and briefings have tabs.
  if (persona === 'crew')
    return (
      <DemoSiteContext.Provider value={demoSite}>
        <div className="pc-enter space-y-5">
          <div>
            {header}
            <p className="mt-1 text-sm text-ink-2">
              {siteKind} · {site.region ?? 'Region not supplied'}
            </p>
            {locationDetails}
          </div>
          {score}
          {factors}
          {conditions}
          {reports}
          {context}
          {refreshButton}
        </div>
      </DemoSiteContext.Provider>
    )

  return (
    <DemoSiteContext.Provider value={demoSite}>
      <div className="pc-enter space-y-5">
        <div className="grid gap-5 @3xl:grid-cols-12 @3xl:items-start">
          <div className="space-y-5 @3xl:col-span-7">
            <section className={`${card} p-5`}>
              <p className="kicker mb-1.5">{siteKind}</p>
              <h2 className="text-2xl font-bold tracking-tight">{site.name}</h2>
              <p className="mt-1 text-ink-2">
                {`${site.assigned_team?.name ?? 'No team assigned'} · ${site.region ?? 'Region not supplied'}`}
              </p>
              {locationDetails}
            </section>
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
              {refreshButton}
            </div>
            {score}
            {conditions}
            {factors}
          </div>
          <div className="space-y-5 @3xl:col-span-5">
            <section className="space-y-3">
              <SectionHead title="Alerts" />
              {site.alerts.length ? (
                visibleAlertGroups(site.alerts).map((g) => (
                  <AlertCard key={g[0].id} alerts={g} detail />
                ))
              ) : (
                <Empty>No alert record supplied for this site.</Empty>
              )}
            </section>
            {hazards}
          </div>
        </div>
        {reports}
        {context}
      </div>
    </DemoSiteContext.Provider>
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
          <CountUp value={value} />
        </span>
        <span className="text-sm text-ink-2">{label}</span>
        {onToggle && (
          <span className="mt-1.5 block text-xs font-semibold text-accent">
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
      className={`pc-press flex items-start gap-3 rounded-2xl border-2 p-4 text-left hover:border-line ${pressed ? 'border-accent bg-accent/10' : 'border-transparent bg-surface'}`}
    >
      {body}
    </button>
  ) : (
    <div className={`${card} flex items-start gap-3 p-4`}>{body}</div>
  )
}

const factorName = factorLabel

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
          {sites.length} locations · {counts.teams} with a team.
        </p>
        {client.mode === 'demo' && (
          <p className="max-w-3xl text-sm text-muted">
            Demo data: simulated sites and EIA reference power plants, with no
            live readings.
          </p>
        )}
      </div>
      <div className="grid grid-cols-2 gap-3 @3xl:grid-cols-4">
        <Stat
          value={counts.alerting}
          label="Active alerts"
          shape="stop"
          pressed={alerts}
          onToggle={() => setAlerts(!alerts)}
        />
        <Stat value={counts.high} label="Score 7.0 or higher" shape="warn" />
        <Stat
          value={counts.teams}
          label="Assigned worksites"
          shape="low"
          pressed={assignment === 'assigned'}
          onToggle={() =>
            setAssignment(assignment === 'assigned' ? 'all' : 'assigned')
          }
        />
        <Stat
          value={counts.unscored}
          label="Unscored or unknown"
          shape="nodata"
        />
      </div>
      <section
        aria-label="Location filters"
        className={`${card} border border-line bg-surface supports-[backdrop-filter]:bg-surface/70 shadow-[inset_0_1px_0_rgba(255,255,255,0.06),0_8px_32px_rgba(0,0,0,0.45)] ring-1 ring-white/5 backdrop-blur-2xl backdrop-saturate-[1.8] grid gap-3 p-4 @lg:grid-cols-2 @3xl:sticky @3xl:top-[3.75rem] @3xl:z-10 @3xl:grid-cols-[minmax(0,1.4fr)_repeat(3,minmax(0,1fr))_auto] @3xl:items-end`}
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
          State
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
          Hazard
          <select
            className={field}
            value={hazard}
            onChange={(e) => setHazard(e.target.value)}
          >
            <option value="all">All hazards</option>
            {[
              ...new Set(
                sites.flatMap((s) => s.top_factors.map((f) => f.factor)),
              ),
            ]
              .filter((f) => f !== 'model')
              .map((f) => (
                <option key={f} value={f}>
                  {factorName(f)}
                </option>
              ))}
          </select>
        </label>
        <label className="flex min-h-11 cursor-pointer items-center gap-3 rounded-xl border border-line bg-surface px-3 text-sm font-semibold text-ink">
          <input
            type="checkbox"
            className="size-5"
            checked={alerts}
            onChange={(e) => setAlerts(e.target.checked)}
          />
          Only sites with active alerts
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
                    {s.assigned_team?.name ?? 'No team assigned'}
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
                      <p className="text-sm text-muted tabular-nums">
                        Server value {s.risk_score} / 10 ·{' '}
                        {displayLabel(s.risk_level, 'Level unavailable')}
                      </p>
                    </>
                  ) : (
                    <>
                      <p className="text-lg leading-none font-bold tabular-nums">
                        <CountUp value={s.risk_score} decimals={1} />{' '}
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
                  <span className="@2xl:sr-only">Main factors: </span>
                  {s.top_factors.length
                    ? s.top_factors
                        .map((factor) =>
                          factor.factor === 'model'
                            ? 'legacy demo factor withheld'
                            : factor.data_state === 'observed'
                              ? factorLabel(factor.factor)
                              : `${factorLabel(factor.factor)} (${displayLabel(factor.data_state)})`,
                        )
                        .join('; ')
                    : 'No factors reported yet'}
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
                    {s.active_alerts
                      ? `${s.active_alerts} active alert${s.active_alerts === 1 ? '' : 's'}`
                      : 'No active alerts'}
                  </span>{' '}
                  · Data {Math.round(s.data_completeness * 100)}% ·{' '}
                  {s.updated_at ? (
                    <>
                      Updated <Timestamp value={s.updated_at} />
                    </>
                  ) : (
                    'Not scored yet'
                  )}
                </p>
              </li>
            ))}
          </ol>
        </div>
        <p className="text-sm text-muted">
          Data is the share of a site's inputs that are current. Missing inputs
          never count as zero risk.
        </p>
      </section>
    </div>
  )
}
function AlertsPage({ id }: { id: string | null }) {
  const { client, refresh, persona } = useApplication()
  const alerts = useResource(
    'alerts',
    useCallback(() => client.alerts(), [client]),
  )
  const demo = demoClient(client)
  if (!alerts.data) return <LoadState error={alerts.error} />
  const groups = visibleAlertGroups(alerts.data)
  // A link to an alert hidden under a more dangerous tier opens that site's top group.
  const linked = id ? alerts.data.find((a) => a.id === id) : undefined
  const rows = !id
    ? groups
    : groups
        .filter((g) => g.some((a) => a.id === id))
        .concat(
          linked && !groups.some((g) => g.some((a) => a.id === id))
            ? groups.filter((g) => g[0].site_id === linked.site_id).slice(0, 1)
            : [],
        )
  return (
    <div className="pc-enter space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <a href={`#/${persona}/overview`} className={control}>
          <Icon name="back" className="size-4" />
          Back to {persona === 'crew' ? 'home' : 'overview'}
        </a>

        <button type="button" className={control} onClick={refresh}>
          Refresh alerts
        </button>
      </div>
      <div className="grid gap-5 @3xl:grid-cols-2 @3xl:items-start">
        {rows.length ? (
          rows.map((g) => <AlertCard key={g[0].id} alerts={g} detail />)
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
const categories = reportCategories

const categoryIcon: Record<ReportCategory, IconName> = {
  broken_pole_downed_line: 'bolt',
  on_site_fire: 'spark',
  access_mat_deterioration: 'layers',
  wildlife: 'pin',
  flooding: 'layers',
  other: 'doc',
}
export function ReportForm({ site }: { site: SiteSummary }) {
  const { client, refresh } = useApplication()
  const [category, setCategory] = useState<ReportCategory>(
      'broken_pole_downed_line',
    ),
    [answer, setAnswer] = useState(''),
    // T034B: access mat reports ask for the crew's A-D grade instead of
    // present/absent. A is no hazard; B, C and D are hazard present.
    [condition, setCondition] = useState<MatCondition | ''>(''),
    [note, setNote] = useState(''),
    [photo, setPhoto] = useState<File | null>(null),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState('')
  const inFlight = useRef(false)
  const photoInput = useRef<HTMLInputElement>(null)
  const isMat = category === 'access_mat_deterioration'
  const presence = isMat
    ? condition && (condition === 'A' ? 'absent' : 'present')
    : answer
  // T034A: device location with the crew member's permission, else the site's
  // coordinates (approximate); editing the coordinates makes it a manual pin.
  const location = useReportLocation(site, client.mode)
  const point = location.location
  // Coordinates stay hidden unless the crew member enters a different spot.
  const [adjusting, setAdjusting] = useState(false)
  const showCoordinates =
    adjusting || location.status === 'pin' || location.status === 'unavailable'
  // The fields show the current location; typed values win only while pinning.
  const [typed, setTyped] = useState<{ lat: string; lon: string } | null>(null)
  const pinning =
    typed !== null &&
    (location.status === 'pin' || location.status === 'unavailable')
  const lat = pinning ? typed.lat : point ? String(point.lat) : ''
  const lon = pinning ? typed.lon : point ? String(point.lon) : ''
  function editCoordinates(nextLat: string, nextLon: string) {
    setTyped({ lat: nextLat, lon: nextLon })
    const number = (v: string) => (v.trim() === '' ? NaN : Number(v))
    location.setPin(number(nextLat), number(nextLon))
  }
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
    if (!file && photoInput.current) photoInput.current.value = ''
  }
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!presence || inFlight.current) return
    // Snapshot now, so a later device fix cannot change this request.
    const at = point
    if (!at) {
      setMessage('Enter a valid latitude and longitude before submitting.')
      return
    }
    inFlight.current = true
    setBusy(true)
    setMessage('')
    try {
      await client.submit(
        {
          site_id: site.id,
          category,
          hazard_present: presence === 'present',
          lat: at.lat,
          lon: at.lon,
          location_source: at.source,
          location_accuracy_m: at.source === 'device' ? at.accuracyM : null,
          mat_condition: isMat && condition ? condition : null,
          note: note || null,
        },
        photo,
      )
      setMessage(
        client.mode === 'demo'
          ? 'Simulated report stored in this browser only. Review is pending; no score changed.'
          : 'Report successful. Awaiting supervisor review.',
      )
      refresh()
    } catch (e) {
      setMessage(
        `Report failed. ${e instanceof Error ? e.message : 'Please try again.'}`,
      )
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
            ? 'Simulated report. Use a sample photo; photos disappear after a reload.'
            : 'Your supervisor reviews the report before confirming a hazard.'}{' '}
          Note is optional.
        </p>
      </div>
      <fieldset>
        <legend className={step}>1 · Hazard category</legend>
        <div className="grid grid-cols-2 gap-2 @lg:grid-cols-3 @4xl:grid-cols-6">
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
        {isMat ? (
          <fieldset>
            <legend className={step}>
              2 · What is the condition? (required)
            </legend>
            <div className="grid grid-cols-4 gap-2">
              {matGrades.map(([grade, hint]) => (
                <label
                  key={grade}
                  className={`relative flex min-h-16 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-line px-2 py-2 text-ink-2 transition-colors hover:border-line-strong has-[input:focus-visible]:outline-3 has-[input:focus-visible]:outline-offset-2 has-[input:focus-visible]:outline-focus ${matChoice}`}
                >
                  <input
                    type="radio"
                    name="mat-condition"
                    value={grade}
                    required
                    aria-label={`Condition ${grade}${hint ? `, ${hint}` : ''}`}
                    checked={condition === grade}
                    onChange={() => setCondition(grade)}
                    className="absolute inset-0 m-0 size-full cursor-pointer opacity-0"
                  />
                  <span className="text-xl font-bold leading-tight">
                    {grade}
                  </span>
                  {/* Every grade keeps the hint line so the letters align. */}
                  <span
                    aria-hidden={!hint}
                    className="min-h-5 text-sm font-semibold leading-5"
                  >
                    {hint}
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
        ) : (
          <fieldset>
            <legend className={step}>
              2 · Is the hazard present? (required)
            </legend>
            <div className="grid grid-cols-2 gap-2">
              {(
                [
                  ['present', 'Hazard present', presentChoice],
                  ['absent', 'Hazard absent', absentChoice],
                ] as const
              ).map(([value, label, look]) => (
                <label
                  key={value}
                  className={`relative flex min-h-16 cursor-pointer items-center justify-center rounded-xl border-2 border-line px-3 py-2 text-base font-bold text-ink-2 transition-colors hover:border-line-strong has-[input:focus-visible]:outline-3 has-[input:focus-visible]:outline-offset-2 has-[input:focus-visible]:outline-focus ${look}`}
                >
                  <input
                    type="radio"
                    name="presence"
                    value={value}
                    required
                    checked={answer === value}
                    onChange={() => setAnswer(value)}
                    className="absolute inset-0 m-0 size-full cursor-pointer opacity-0"
                  />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>
        )}
        <p className="mt-2 text-sm text-muted">
          {isMat && condition && (
            <>
              Grade {condition} counts as hazard{' '}
              {condition === 'A' ? 'absent' : 'present'}.{' '}
            </>
          )}
          {presence === 'present'
            ? 'Nearby teams receive a potential-hazard notice. Supervisor confirmation is required before instructions.'
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
            ref={photoInput}
            disabled={busy}
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
            <p className="min-w-0 flex-1 text-sm text-ink-2">
              <span className="break-all">{photo.name}</span> selected ·{' '}
              {Math.ceil(photo.size / 1024)} KB. Allowed JPEG/PNG/WebP, maximum
              5 MB.
            </p>
            <button
              type="button"
              className={`${control} w-20 shrink-0 px-2! text-xs! leading-tight [overflow-wrap:normal]`}
              aria-label="Remove image"
              disabled={busy}
              onClick={() => choosePhoto(null)}
            >
              <span className="whitespace-nowrap">
                Remove
                <br /> image
              </span>
            </button>
          </div>
        )}
      </div>
      <fieldset>
        <legend className={step}>
          <Icon name="pin" className="size-4" />4 · Location
        </legend>
        <p
          role="status"
          aria-live="polite"
          className="flex items-start gap-2 rounded-xl bg-surface-2 px-3 py-2.5"
        >
          <Icon name="pin" className="mt-0.5 size-4 shrink-0" />
          <span>
            <span className="block font-semibold text-ink">
              {locationChip[location.status]}
            </span>
            {locationDetail(location.status, location.reason, point) && (
              <span className="block text-sm text-ink-2">
                {locationDetail(location.status, location.reason, point)}
              </span>
            )}
          </span>
        </p>
        {!showCoordinates ? (
          <button
            type="button"
            className="mt-2 min-h-11 text-sm font-semibold text-link"
            onClick={() => setAdjusting(true)}
          >
            Enter a different spot
          </button>
        ) : (
          <div className="mt-3 grid gap-3 @lg:grid-cols-2">
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
                onChange={(e) => editCoordinates(e.target.value, lon)}
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
                onChange={(e) => editCoordinates(lat, e.target.value)}
              />
            </label>
          </div>
        )}
        <p className="mt-1 text-sm text-muted">
          Your location is used only for this report, and only with your
          permission.
        </p>
      </fieldset>
      <label className={labelText}>
        Optional note
        <textarea
          className={field}
          rows={3}
          maxLength={1000}
          value={note}
          placeholder={
            category === 'access_mat_deterioration'
              ? 'Describe the affected section, visible damage and your crew assessment.'
              : undefined
          }
          onChange={(e) => setNote(e.target.value)}
        />
      </label>
      <button
        className={primary + big}
        disabled={
          busy ||
          !presence ||
          !point ||
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
// T034B access mat grades. Only the ends of the scale are named: A is perfect,
// D is unusable.
const matGrades: [MatCondition, string][] = [
  ['A', 'Perfect'],
  ['B', ''],
  ['C', ''],
  ['D', 'Unusable'],
]
// Checked states for the present/absent choice (step 2), like the category step.
const presentChoice =
  'has-checked:border-stop has-checked:bg-stop has-checked:text-white'
const absentChoice =
  'has-checked:border-ink has-checked:bg-ink has-checked:text-bg'
// Every mat grade highlights the same way; the letter carries the meaning.
const matChoice = absentChoice
const locationChip = {
  closed: 'No location',
  locating: 'Finding your location…',
  device: 'Using your current location',
  site: 'Using the site’s location (approximate)',
  pin: 'Using the spot you entered',
  unavailable: 'Enter a valid latitude and longitude',
} as const
const fallbackReason: Partial<Record<LocationReason, string>> = {
  demo: 'Simulated report: device location is not requested.',
  denied: 'You declined location access.',
  timeout: 'Your location took too long to arrive.',
  unsupported: 'This browser can’t share its location.',
  unavailable: 'Your device location isn’t available.',
  invalid_device: 'Your device returned an invalid location.',
}
/** The short second line under the location status. */
function locationDetail(
  status: keyof typeof locationChip,
  reason: LocationReason | null,
  point: { accuracyM: number | null } | null,
) {
  if (status === 'device' && point?.accuracyM != null)
    return `Accurate to about ${Math.round(point.accuracyM)} m.`
  if (status === 'locating')
    return 'The site’s location is used if this takes too long.'
  if (status === 'site' && reason) return fallbackReason[reason] ?? null
  return null
}
/** T034A/T053A: where a report's coordinates came from, in words. */
function locationText(report: CrewReport) {
  const source =
    report.location_source === 'device'
      ? `Device location${report.location_accuracy_m !== null ? ` (±${Math.round(report.location_accuracy_m)} m)` : ''}`
      : report.location_source === 'pin'
        ? 'Pinned on the map by the crew member'
        : report.location_source === 'site'
          ? 'Approximate: the site’s own coordinates'
          : 'Location source not recorded'
  const distance =
    report.site_distance_miles === null
      ? ''
      : ` · ${report.site_distance_miles < 0.1 ? 'under 0.1' : report.site_distance_miles.toFixed(1)} mi from the site`
  return source + distance
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
/** A report's private photo, loaded with the session token (an <img> can't send one). */
function StoredPhoto({ id, alt }: { id: string; alt: string }) {
  const { client } = useApplication()
  const [state, setState] = useState<
    { url: string } | { error: string } | null
  >(null)
  useEffect(() => {
    let url: string | null = null
    let live = true
    client.reportPhoto?.(id).then(
      (blob) => {
        url = URL.createObjectURL(blob)
        if (live) setState({ url })
        else URL.revokeObjectURL(url)
      },
      (error: unknown) => {
        if (!live) return
        const missing =
          error instanceof Error && 'status' in error && error.status === 404
        setState({
          error: missing
            ? "This photo isn't in storage."
            : "The photo couldn't be loaded. Refresh to try again.",
        })
      },
    )
    return () => {
      live = false
      if (url) URL.revokeObjectURL(url)
    }
  }, [client, id])
  if (state === null)
    return <p className="text-sm text-muted">Loading photo…</p>
  if ('error' in state)
    return <p className="text-sm text-muted">{state.error}</p>
  return (
    <img
      className="max-h-48 max-w-full rounded-xl border border-line object-cover"
      src={state.url}
      alt={alt}
    />
  )
}

function ReportCard({
  report,
  compact = false,
}: {
  report: CrewReport
  compact?: boolean
}) {
  const { client, persona } = useApplication()
  const photo = demoClient(client)?.photo(report.id)
  const [reviewCategory, setReviewCategory] = useState<ReportCategory>(
    report.category,
  )
  const [severity, setSeverity] = useState<'' | 'low' | 'moderate' | 'high'>('')
  const look = reviewLook[report.review_status]
  if (compact)
    return (
      <article
        data-report-id={report.id}
        className={card + ' space-y-2 rounded-xl border border-line p-3'}
      >
        <h3 className="text-lg font-bold">{categories[report.category]}</h3>
        {report.review_status === 'pending' && (
          <p className="text-sm font-semibold text-warn-text">
            {report.hazard_present
              ? 'Action needed: supervisor confirmation of the hazard notice.'
              : 'Action needed: supervisor review of this report.'}
          </p>
        )}
        <Details
          title="View more"
          label={'View more about ' + categories[report.category] + ' report'}
        >
          <ReportCard report={report} />
        </Details>
      </article>
    )
  return (
    <article
      data-report-id={report.id}
      className={`${card} @container space-y-3 p-4`}
    >
      {/* T036A: the crew member's report as submitted, Gemini's analysis beside it. */}
      <div className="grid gap-4 @xl:grid-cols-2 @xl:items-start">
        <div className="min-w-0 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`chip inline-flex items-center gap-1.5 border ${look.cls}`}
            >
              <RiskShape kind={look.shape} className="size-3.5" />
              {look.text}
            </span>
            <span
              className={`chip inline-flex items-center gap-1.5 border ${report.hazard_present ? 'border-stop text-stop-text' : 'border-line-strong text-ink-2'}`}
            >
              {report.hazard_present ? 'Reported present' : 'Reported absent'}
            </span>
            {report.mat_condition && (
              <span className="chip inline-flex items-center border border-ink font-bold text-ink">
                Condition {report.mat_condition}
                {report.mat_condition === 'D' && ' · unusable'}
              </span>
            )}
          </div>
          <h3 className="text-lg font-bold">{categories[report.category]}</h3>
          <p className="text-sm text-muted">
            Reported <Timestamp value={report.created_at} />
          </p>
          <Details title="Report location and record">
            <p className="break-words font-mono text-sm text-muted">
              {report.site_id} · {report.lat}, {report.lon}
            </p>
            <p className="flex items-center gap-1.5 text-xs text-ink-2">
              <Icon name="pin" className="size-3.5" />
              {locationText(report)}
            </p>
            <p className="text-sm text-muted">Report {report.id}</p>
          </Details>
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
          ) : report.photo_url && client.reportPhoto ? (
            <StoredPhoto
              id={report.id}
              alt={`Crew photo for ${categories[report.category]}`}
            />
          ) : report.photo_url ? (
            <p className="text-sm text-muted">
              This report has a photo, but it can't be shown here.
            </p>
          ) : (
            <p className="text-sm text-muted">
              {client.mode === 'demo'
                ? 'No persisted photo. Demo photos are session-only.'
                : 'No photo reference supplied.'}
            </p>
          )}
        </div>
        <ReportAnalysis report={report} />
      </div>
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
                Confirm report
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
            Awaiting supervisor confirmation in the worksite's hazard notices.
          </p>
          {persona === 'supervisor' && (
            <a
              className={control}
              href={`#/supervisor/sites/${encodeURIComponent(report.site_id)}`}
            >
              Review worksite notice
            </a>
          )}
        </div>
      )}
      <p className="text-sm text-muted">
        Review does not authorize work. Pending/rejected reports are not
        confirmed hazards.
      </p>
    </article>
  )
}
/** Reports and briefings exist only for sites with a team, so supervisors pick from those. */
const teamSitesFirst = (sites: SiteSummary[]) =>
  sites.some((s) => s.assigned_team)
    ? sites.filter((s) => s.assigned_team)
    : sites

function ReportsPage({ sites }: { sites: SiteSummary[] }) {
  const { client, refresh } = useApplication()
  const choices = teamSitesFirst(sites)
  const result = useResource(
    'reports',
    useCallback(() => client.reports(), [client]),
  )
  const [siteId, setSiteId] = useState(choices[0].id)
  const site = choices.find((s) => s.id === siteId) ?? choices[0]
  return (
    // The hazard report is the main task: controls, then the form across the
    // full width, then the review queue with cards laid out left to right.
    <div className="pc-enter space-y-6">
      <div className="flex flex-wrap items-end gap-3">
        <label className={`${labelText} min-w-0 flex-1 @3xl:max-w-md`}>
          Report location
          <select
            aria-label="Report location"
            className={field}
            value={site.id}
            onChange={(e) => setSiteId(e.target.value)}
          >
            {choices.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className={control} onClick={refresh}>
          <Icon name="refresh" className="size-4" />
          Refresh reports
        </button>
      </div>
      {/* Its own container, so the form's controls size to the form. */}
      <div className="@container">
        <ReportForm key={site.id} site={site} />
      </div>
      <section className="space-y-3" aria-label="Submitted reports">
        <SectionHead kicker="Review queue" title="Reports and review" />
        {result.data ? (
          result.data.length ? (
            <Masonry
              label="Submitted reports"
              items={result.data
                .filter((r) => sites.some((s) => s.id === r.site_id))
                .map((r) => ({ key: r.id, node: <ReportCard report={r} /> }))}
            />
          ) : (
            <Empty>No reports returned.</Empty>
          )
        ) : (
          <LoadState error={result.error} />
        )}
      </section>
    </div>
  )
}
function BriefingsPage({ sites }: { sites: SiteSummary[] }) {
  return <StoredBriefings sites={teamSitesFirst(sites)} />
}
export function DemoClock() {
  const now = useClock()
  return (
    <span className="font-mono tracking-wide">
      Replay clock: <Timestamp value={new Date(now).toISOString()} />
    </span>
  )
}
