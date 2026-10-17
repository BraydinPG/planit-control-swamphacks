import {
  lazy,
  Suspense,
  useCallback,
  useMemo,
  useState,
  type FormEvent,
} from 'react'
import type { CrewReport, ReportCategory, SiteSummary } from '../types/api'
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
  control,
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
const Advisory = lazy(() =>
  import('../components/data/Advisory').then((m) => ({ default: m.Advisory })),
)
const SiteMap = lazy(() =>
  import('../components/data/SiteMap').then((m) => ({ default: m.SiteMap })),
)

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
      <p role="status">
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
      <p role="alert">
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
  const { client, persona } = useApplication()
  const result = useResource(
    `site:${id}`,
    useCallback(() => client.site(id), [client, id]),
  )
  if (dashboard) return <SitesPage sites={sites} />
  if (!result.data) return <LoadState error={result.error} />
  const site = result.data,
    active = site.alerts.filter((a) => a.state === 'active')
  return (
    <div className="space-y-5">
      {compact && active[0] && <AlertCard alert={active[0]} />}
      {compact && !active.length && (
        <p className="rounded border bg-white p-4">
          No active alerts supplied for this view. This does not establish safe
          conditions.
        </p>
      )}
      <section className="rounded-xl border bg-white p-4">
        <h2 className="text-xl font-semibold">{site.name}</h2>
        <p>
          {site.assigned_team?.name ?? 'No team assigned'} ·{' '}
          {site.region ?? 'Region not supplied'}
        </p>
        <p className="break-words text-xs">
          {site.id} · {site.lat}, {site.lon}
          <br />
          {site.source}
        </p>
      </section>
      <div className="flex flex-wrap gap-3">
        <a className={primary} href={`#/${persona}/reports`}>
          Report a hazard
        </a>
        <a className={control} href={`#/${persona}/briefings`}>
          View briefing
        </a>
      </div>
      <ScorePanel site={site} demo={client.mode === 'demo'} />
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">
          Potential notices and approved instructions
        </h2>
        {site.notices.length ? (
          site.notices.map((n) => (
            <NoticeCard
              key={`${n.id}:${n.confirmed_at ?? n.status}`}
              notice={n}
            />
          ))
        ) : (
          <p>
            No notices supplied. Local electrical, structural and access
            conditions remain unverified.
          </p>
        )}
      </section>
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">
          Observations and issued forecasts
        </h2>
        <Observations rows={site.observations} />
      </section>
      {!compact && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Alert details</h2>
          {site.alerts.map((a) => (
            <AlertCard key={a.id} alert={a} detail />
          ))}
        </section>
      )}
      <details>
        <summary className="min-h-11 cursor-pointer py-2 font-semibold">
          Score factors and source evidence
        </summary>
        <Factors factors={site.top_factors} />
      </details>
      <Suspense fallback={<p role="status">Loading advisory?</p>}>
        <Advisory site={site} demo={client.mode === 'demo'} />
      </Suspense>
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Reports at this site</h2>
        {site.reports.length ? (
          site.reports.map((r) => <ReportCard key={r.id} report={r} />)
        ) : (
          <p>No reports supplied.</p>
        )}
      </section>
    </div>
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
  return (
    <div className="space-y-5">
      <p>
        {sites.length}{' '}
        {client.mode === 'demo' ? 'sample/reference' : 'backend-authorized'}{' '}
        locations. Assigned teams first, then eligible supplied score. Unknown
        is never low risk.
      </p>
      {client.mode === 'demo' && (
        <p className="text-sm">
          Includes 50 reconciled EIA reference plants, not verified active jobs,
          plus five canonical simulated sites. Reference plants have no live
          readings or score. Legacy ML fixture scores are excluded from ranking.
        </p>
      )}
      <section aria-label="Location filters" className="flex flex-wrap gap-3">
        <label>
          Search locations
          <input
            className={control + ' block'}
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <label>
          Team assignment
          <select
            className={control + ' block'}
            value={assignment}
            onChange={(e) => setAssignment(e.target.value)}
          >
            <option value="all">All</option>
            <option value="assigned">Assigned</option>
            <option value="unassigned">Unassigned</option>
          </select>
        </label>
        <label>
          State / reference region
          <select
            className={control + ' block'}
            value={region}
            onChange={(e) => setRegion(e.target.value)}
          >
            <option value="all">All regions</option>
            {[...new Set(sites.map(state))].sort().map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <label>
          Supplied factor
          <select
            className={control + ' block'}
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
        <label className="flex min-h-11 items-center gap-2">
          <input
            type="checkbox"
            checked={alerts}
            onChange={(e) => setAlerts(e.target.checked)}
          />
          Active alerts supplied
        </label>
      </section>
      {shown.length ? (
        <Suspense fallback={<p role="status">Loading map?</p>}>
          <SiteMap sites={shown} select={select} />
        </Suspense>
      ) : (
        <p role="status">No locations match these filters.</p>
      )}
      {client.mode === 'demo' && (
        <div className="flex flex-wrap gap-2">
          <a className={control} href="#/supervisor/sites/eia860m-FL-59611">
            Flood advisory replay
          </a>
          <a className={control} href="#/supervisor/sites/eia860m-AZ-68414">
            Wind advisory replay
          </a>
        </div>
      )}
      <ol aria-label="Ranked locations" className="space-y-3">
        {shown.map((s) => (
          <li
            key={s.id}
            className="rounded-xl border border-slate-300 bg-white p-4"
          >
            <a
              className="inline-flex min-h-11 items-center text-lg font-semibold text-teal-900 underline"
              href={`#/${persona}/sites/${encodeURIComponent(s.id)}`}
            >
              {s.name}
            </a>
            <p>
              {s.assigned_team?.name ?? 'No team assigned'} · {s.id}
            </p>
            <p>
              {s.risk_score === null
                ? 'Not scored yet'
                : client.mode === 'demo' &&
                    s.top_factors.some((f) => f.factor === 'model')
                  ? 'Legacy fixture score withheld'
                  : `${s.risk_score} / 10 · ${s.risk_level ?? 'level unavailable'}`}
            </p>
            <p className="text-sm">
              {s.active_alerts} {client.mode === 'demo' ? 'demo' : 'supplied'}{' '}
              active alerts · Completeness{' '}
              {Math.round(s.data_completeness * 100)}% · Updated{' '}
              <Timestamp value={s.updated_at} />
            </p>
            <p className="text-sm">
              Top supplied factors:{' '}
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
          </li>
        ))}
      </ol>
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
    <div className="space-y-5">
      {demo && (
        <section
          className="flex flex-wrap gap-3 rounded border border-amber-400 p-3"
          aria-label="Simulated server updates"
        >
          <p className="w-full text-sm">
            Demo-only server-payload replay. No production rule is run or
            changed.
          </p>
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
        </section>
      )}
      {rows.length ? (
        rows.map((a) => <AlertCard key={a.id} alert={a} detail />)
      ) : (
        <p>No alert record supplied for this selection.</p>
      )}
    </div>
  )
}
const categories: Record<ReportCategory, string> = {
  broken_pole_downed_line: 'Broken pole / downed line',
  on_site_fire: 'On-site fire',
  wildlife: 'Wildlife',
  flooding: 'Flooding',
  other: 'Other',
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
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!presence) return
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
      setBusy(false)
    }
  }
  return (
    <form
      aria-label="Hazard report"
      onSubmit={submit}
      className="space-y-4 rounded-xl border border-slate-300 bg-white p-4"
    >
      <h2 className="text-xl font-semibold">Report a hazard</h2>
      <p className="text-sm">
        {client.mode === 'demo'
          ? 'Demo only. Avoid private photos; selected photos stay in memory and are not persisted across reload.'
          : 'Submitted to the configured backend only; server validates permissions and storage.'}{' '}
        Note is optional.
      </p>
      <label className="block">
        Hazard category
        <select
          className={control + ' block w-full'}
          value={category}
          onChange={(e) => setCategory(e.target.value as ReportCategory)}
        >
          {Object.entries(categories).map(([id, label]) => (
            <option key={id} value={id}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <label className="block">
        Hazard present or absent (required)
        <select
          required
          className={control + ' block w-full'}
          value={presence}
          onChange={(e) => setPresence(e.target.value)}
        >
          <option value="">Choose present or absent</option>
          <option value="present">Hazard present</option>
          <option value="absent">Hazard absent</option>
        </select>
      </label>
      <div className="grid gap-3 sm:grid-cols-2">
        <label>
          Latitude
          <input
            required
            type="number"
            min="-90"
            max="90"
            step="any"
            className={control + ' block w-full'}
            value={lat}
            onChange={(e) => setLat(e.target.value)}
          />
        </label>
        <label>
          Longitude
          <input
            required
            type="number"
            min="-180"
            max="180"
            step="any"
            className={control + ' block w-full'}
            value={lon}
            onChange={(e) => setLon(e.target.value)}
          />
        </label>
      </div>
      <p className="text-xs">
        Coordinates start at the selected reference location. Confirm the actual
        report location before submission.
      </p>
      <label className="block">
        {client.mode === 'demo'
          ? 'Photo (optional in demo)'
          : 'Photo (required when hazard present)'}
        <input
          type="file"
          required={client.mode === 'live' && presence === 'present'}
          accept="image/jpeg,image/png,image/webp"
          className={control + ' block w-full'}
          onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
        />
      </label>
      {photo && (
        <p>
          {photo.name} selected · {Math.ceil(photo.size / 1024)} KB. Allowed
          JPEG/PNG/WebP, maximum 5 MB.
        </p>
      )}
      <label className="block">
        Optional note
        <textarea
          className={control + ' block w-full'}
          maxLength={1000}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </label>
      <button
        className={primary}
        disabled={
          busy ||
          !presence ||
          !client.capabilities.reports ||
          (client.mode === 'live' && presence === 'present' && !photo)
        }
        type="submit"
      >
        {busy
          ? 'Submitting…'
          : client.mode === 'demo'
            ? 'Submit simulated report'
            : 'Submit report'}
      </button>
      {!client.capabilities.reports && (
        <p>
          Live report submission and photo storage are unavailable on this
          backend.
        </p>
      )}
      {message && (
        <p role="status" aria-live="polite">
          {message}
        </p>
      )}
    </form>
  )
}
function ReportCard({ report }: { report: CrewReport }) {
  const { client, persona } = useApplication()
  const photo = demoClient(client)?.photo(report.id)
  const [reviewCategory, setReviewCategory] = useState<ReportCategory>(
    report.category,
  )
  const [severity, setSeverity] = useState<'' | 'low' | 'moderate' | 'high'>('')
  return (
    <article
      data-report-id={report.id}
      className="space-y-2 rounded-xl border border-slate-300 bg-white p-4"
    >
      <h3 className="font-semibold">
        {categories[report.category]} ·{' '}
        {report.hazard_present ? 'present' : 'absent'} · {report.review_status}
      </h3>
      <p>
        {report.site_id} · {report.lat}, {report.lon}
      </p>
      <p className="text-xs">
        Report {report.id} · <Timestamp value={report.created_at} />
      </p>
      {report.note && <p>{report.note}</p>}
      {photo ? (
        <img
          className="max-h-40 max-w-full"
          src={photo}
          alt={`Selected demo evidence for ${categories[report.category]}`}
        />
      ) : report.photo_url ? (
        <p className="text-xs">
          Photo reference supplied; private photo retrieval is not connected.
        </p>
      ) : (
        <p className="text-xs">
          No persisted photo. Demo photos are session-only.
        </p>
      )}
      {report.enrichment && (
        <div className="rounded border border-amber-400 p-3">
          <strong>AI suggestion, needs human review</strong>
          <p>{report.enrichment.description}</p>
          <p>
            {report.enrichment.suggested_category};{' '}
            {report.enrichment.severity_suggestion}; not confirmed by this
            suggestion.
          </p>
        </div>
      )}
      {persona === 'supervisor' && report.review_status === 'pending' && (
        <div className="flex flex-wrap gap-3">
          <label>
            Reviewed category
            <select
              className={control + ' block'}
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
          <label>
            Reviewed severity (optional)
            <select
              className={control + ' block'}
              value={severity}
              onChange={(e) => setSeverity(e.target.value as typeof severity)}
            >
              <option value="">Not specified</option>
              <option value="low">Low</option>
              <option value="moderate">Moderate</option>
              <option value="high">High</option>
            </select>
          </label>
          <Action
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
      )}
      <p className="text-xs">
        Review does not authorize work. Pending/rejected reports are not
        confirmed hazards.
      </p>
    </article>
  )
}
function ReportsPage({ sites }: { sites: SiteSummary[] }) {
  const { client } = useApplication()
  const result = useResource(
    'reports',
    useCallback(() => client.reports(), [client]),
  )
  const [siteId, setSiteId] = useState(sites[0].id)
  const site = sites.find((s) => s.id === siteId) ?? sites[0]
  return (
    <div className="space-y-5">
      <label>
        Report location
        <select
          aria-label="Report location"
          className={control + ' block w-full'}
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
      <ReportForm key={site.id} site={site} />
      {result.data ? (
        <section className="space-y-3" aria-label="Submitted reports">
          <h2 className="text-xl font-semibold">Reports and review</h2>
          {result.data
            .filter((r) => sites.some((s) => s.id === r.site_id))
            .map((r) => (
              <ReportCard key={r.id} report={r} />
            ))}
          {!result.data.length && <p>No reports returned.</p>}
        </section>
      ) : (
        <LoadState error={result.error} />
      )}
    </div>
  )
}
function BriefingsPage({ sites }: { sites: SiteSummary[] }) {
  return <StoredBriefings sites={sites} />
}
export function DemoClock() {
  const now = useClock()
  return (
    <span>
      Replay clock: <Timestamp value={new Date(now).toISOString()} />
    </span>
  )
}
