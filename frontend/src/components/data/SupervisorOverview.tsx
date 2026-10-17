import { useCallback } from 'react'
import type { SiteSummary } from '../../types/api'
import { useApplication, useResource } from '../../application/context'
import { Icon } from '../shell/Icon'
import { card, LoadState } from './Interaction'
import { RiskBadge, RiskShape } from './Risk'
import { evidenceOf } from './evidence'
import { attentionItems, highestRisk, type Shape } from './attention'
import { factorLabel } from '../../presentation/display'

/**
 * Supervisor home: what needs a decision now, and the riskiest sites. The full map, list
 * and filters live on Worksites (spec.md sections 3 and 7).
 */
export function SupervisorOverview({ sites }: { sites: SiteSummary[] }) {
  const { client } = useApplication()
  const teamSites = sites.filter((s) => s.assigned_team).slice(0, 20)
  const ids = teamSites.map((s) => s.id).join(',')
  const data = useResource(
    'supervisor-overview',
    useCallback(async () => {
      const [alerts, reports, details] = await Promise.all([
        client.alerts(),
        client.reports(),
        Promise.all((ids ? ids.split(',') : []).map((id) => client.site(id))),
      ])
      // Potential notices reach a site's detail; a notice covering two sites shows once.
      const seen = new Set<string>()
      const notices = details.flatMap((d) =>
        d.notices
          .filter((n) => n.status === 'potential' && !seen.has(n.id))
          .map((notice) => {
            seen.add(notice.id)
            return { notice, site: d }
          }),
      )
      return { alerts, reports, notices }
    }, [client, ids]),
  )
  if (!data.data) return <LoadState error={data.error} />
  const items = attentionItems(
    sites,
    data.data.alerts,
    data.data.reports,
    data.data.notices,
  )
  const count = (prefix: string) =>
    items.filter((i) => i.key.startsWith(prefix)).length
  const top = highestRisk(sites)
  return (
    <div className="pc-enter space-y-6">
      <div className="grid grid-cols-2 gap-3 @3xl:grid-cols-4">
        <Tile
          value={count('alert:')}
          label="Active alerts"
          shape="stop"
          href="#/supervisor/alerts"
        />
        <Tile
          value={count('notice:')}
          label="Hazards to confirm"
          shape="caution"
          href="#/supervisor/sites"
        />
        <Tile
          value={count('report:')}
          label="Reports to review"
          shape="nodata"
          href="#/supervisor/reports"
        />
        <Tile
          value={teamSites.length}
          label="Assigned worksites"
          shape="low"
          href="#/supervisor/team"
        />
      </div>

      <section className="space-y-3" aria-labelledby="attention-title">
        <h2
          id="attention-title"
          className="text-lg font-bold tracking-tight @lg:text-xl"
        >
          Needs your attention
        </h2>
        {items.length ? (
          <ul className={`${card} divide-y divide-line`}>
            {items.map((item) => (
              <li key={item.key}>
                <a
                  href={item.href}
                  className="flex min-h-14 items-center gap-3 px-4 py-3 hover:bg-hover"
                >
                  <RiskShape kind={item.shape} className="size-5" />
                  <span className="min-w-0 flex-1">
                    <span className="block font-semibold text-ink">
                      {item.title}
                    </span>
                    <span className="block truncate text-sm text-ink-2">
                      {item.detail}
                    </span>
                  </span>
                  <span className="hidden shrink-0 text-sm font-semibold text-link @lg:inline">
                    {item.action}
                  </span>
                  <Icon name="arrow" className="size-4 shrink-0 text-muted" />
                </a>
              </li>
            ))}
          </ul>
        ) : (
          <p
            className={`${card} flex items-center gap-2.5 p-4 text-sm text-ink-2`}
          >
            <Icon name="check" className="size-4 text-ok" />
            No items awaiting review. New alerts and reports will appear here.
          </p>
        )}
      </section>

      <section className="space-y-3" aria-labelledby="risk-title">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <h2
            id="risk-title"
            className="text-lg font-bold tracking-tight @lg:text-xl"
          >
            Highest risk
          </h2>
          <a
            href="#/supervisor/sites"
            className="inline-flex min-h-11 items-center gap-1.5 text-sm font-semibold text-link"
          >
            All worksites <Icon name="arrow" className="size-4" />
          </a>
        </div>
        {top.length ? (
          <ol className="grid gap-3 @3xl:grid-cols-3">
            {top.map((s) => (
              <li key={s.id}>
                <a
                  href={`#/supervisor/sites/${encodeURIComponent(s.id)}`}
                  className={`${card} pc-press flex h-full flex-col gap-2 p-4 hover:bg-hover`}
                >
                  <span className="font-bold text-ink">{s.name}</span>
                  <span className="text-sm text-ink-2">
                    {s.assigned_team?.name ?? 'No team assigned'}
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="text-2xl font-bold tabular-nums">
                      {s.risk_score?.toFixed(1)}
                      <span className="text-sm font-semibold text-muted">
                        {' '}
                        / 10
                      </span>
                    </span>
                    <RiskBadge level={s.risk_level} evidence={evidenceOf(s)} />
                  </span>
                  {s.top_factors[0] && (
                    <span className="text-sm text-ink-2">
                      Main factor: {factorLabel(s.top_factors[0].factor)}
                    </span>
                  )}
                </a>
              </li>
            ))}
          </ol>
        ) : (
          <p className={`${card} p-4 text-sm text-ink-2`}>
            No site has a score with current evidence yet.
          </p>
        )}
      </section>
    </div>
  )
}

function Tile({
  value,
  label,
  shape,
  href,
}: {
  value: number
  label: string
  shape: Shape
  href: string
}) {
  return (
    <a
      href={href}
      className={`${card} pc-press flex items-start gap-3 p-4 hover:bg-hover`}
    >
      <RiskShape kind={shape} className="mt-1.5 size-4" />
      <span className="leading-tight">
        <span className="block text-3xl font-bold tabular-nums tracking-tight">
          {value}
        </span>
        <span className="text-sm text-ink-2">{label}</span>
      </span>
    </a>
  )
}
