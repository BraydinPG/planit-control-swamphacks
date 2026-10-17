import { useEffect } from 'react'
import type {
  AnalysisPoint,
  AnalysisVerdict,
  CrewReport,
  ReportCategory,
} from '../../types/api'
import { useApplication, useClock } from '../../application/context'
import { Icon } from '../shell/Icon'
import { RiskShape } from './Risk'

/**
 * T036A: Gemini's analysis of a crew report, shown beside the report. A suggestion for the
 * supervisor; it never changes the report, its review, or the score (spec.md section 6).
 */
const verdicts: Record<
  AnalysisVerdict,
  { text: string; shape: 'warn' | 'nodata' | null }
> = {
  supports: { text: 'Supports the report', shape: null },
  contradicts: { text: 'Contradicts the report', shape: 'warn' },
  inconclusive: {
    text: "Inconclusive: the data can't confirm or rule it out",
    shape: 'nodata',
  },
}
const categoryNames: Record<ReportCategory, string> = {
  broken_pole_downed_line: 'Broken pole / downed line',
  on_site_fire: 'On-site fire',
  access_mat_deterioration: 'Access mat deterioration',
  wildlife: 'Wildlife',
  flooding: 'Flooding',
  other: 'Other',
}
const unavailableReasons: Record<string, string> = {
  missing_config: 'Gemini is not configured on this server',
  timeout: 'Gemini did not answer in time',
  invalid_output: 'the answer failed the safety and evidence checks',
  error: 'Gemini returned an error',
}
// A new live report is analyzed in the background; poll briefly until it arrives.
const ANALYSIS_WAIT_MS = 2 * 60 * 1000
const POLL_MS = 5000

export function ReportAnalysis({ report }: { report: CrewReport }) {
  const { client, refresh } = useApplication()
  const now = useClock()
  const analysis = report.enrichment
  const analyzing =
    !analysis &&
    client.mode === 'live' &&
    now - Date.parse(report.created_at) < ANALYSIS_WAIT_MS
  useEffect(() => {
    if (!analyzing) return
    const timer = setTimeout(refresh, POLL_MS)
    return () => clearTimeout(timer)
  }, [analyzing, refresh, report])
  const labels = new Map(analysis?.evidence.map((e) => [e.id, e.label]))
  return (
    <aside
      aria-label="Gemini analysis of this report"
      className="space-y-3 rounded-xl border border-dashed border-sim p-3 text-sm"
    >
      <p className="kicker flex items-center gap-1.5 text-sim!">
        <Icon name="spark" className="size-3.5" />
        Gemini analysis · suggestion only
      </p>
      {!analysis ? (
        <p role="status" className="text-ink-2">
          {analyzing
            ? 'Analyzing the photo and site data… this takes a few seconds.'
            : client.mode === 'demo'
              ? 'Simulated report: Gemini analyzes reports on the live backend only.'
              : 'No analysis recorded for this report.'}
        </p>
      ) : analysis.status === 'unavailable' ? (
        <p className="text-ink-2">
          <strong className="text-ink">Photo analysis unavailable.</strong> The
          report stands on its own
          {analysis.unavailable_reason &&
            ` (${unavailableReasons[analysis.unavailable_reason] ?? analysis.unavailable_reason})`}
          .
        </p>
      ) : (
        <>
          <Verdict verdict={analysis.verdict ?? 'inconclusive'} />
          {analysis.summary && <p className="text-ink">{analysis.summary}</p>}
          <Points
            title="Backs up the report"
            points={analysis.supporting}
            labels={labels}
          />
          <Points
            title="Points against the report"
            points={analysis.contradicting}
            labels={labels}
          />
          {analysis.also_visible.length > 0 && (
            <List
              title="Also visible in the photo"
              items={analysis.also_visible}
            />
          )}
          <p className="text-ink-2">
            Suggested category:{' '}
            <strong className="text-ink">
              {analysis.suggested_category
                ? categoryNames[analysis.suggested_category]
                : 'none'}
            </strong>{' '}
            · severity:{' '}
            <strong className="text-ink">
              {analysis.severity_suggestion ?? 'none'}
            </strong>
            {analysis.confidence !== null &&
              ` · confidence ${Math.round(analysis.confidence * 100)}%`}
          </p>
          {analysis.unknowns.length > 0 && (
            <List title="Could not tell" items={analysis.unknowns} />
          )}
        </>
      )}
      <p className="text-xs text-muted">
        The supervisor makes the final call. This analysis never changes the
        report, its review, or the score.
      </p>
    </aside>
  )
}

function Verdict({ verdict }: { verdict: AnalysisVerdict }) {
  const look = verdicts[verdict]
  return (
    <p className="flex items-center gap-2 text-base font-bold text-ink">
      {look.shape ? (
        <RiskShape kind={look.shape} className="size-5" />
      ) : (
        <Icon name="check" className="size-5" />
      )}
      {look.text}
    </p>
  )
}

function Points({
  title,
  points,
  labels,
}: {
  title: string
  points: AnalysisPoint[]
  labels: Map<string, string>
}) {
  if (!points.length) return null
  return (
    <div>
      <p className="kicker">{title}</p>
      <ul className="mt-1 space-y-1.5">
        {points.map((p, i) => (
          <li key={i} className="rounded-lg bg-surface-2 px-2.5 py-2">
            <span className="text-ink">{p.statement}</span>
            <span className="mt-0.5 block text-xs text-muted">
              Based on:{' '}
              {p.evidence_ids.map((id) => labels.get(id) ?? id).join(' · ')}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function List({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <p className="kicker">{title}</p>
      <ul className="mt-1 list-disc space-y-0.5 pl-5 text-ink-2">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  )
}
