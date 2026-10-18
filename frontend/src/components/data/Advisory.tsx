import advisories from '../../demo/generated/advisories.json'
import type { SiteRecord } from '../../api/contracts'
import { Timestamp } from './Status'
import { ExpectedDuration } from './Duration'
import { NO_ESTIMATE } from './duration-text'
import { displayLabel } from '../../presentation/display'
import { Details } from './Details'
export function Advisory({
  site,
  demo,
  showAll = false,
}: {
  site: SiteRecord
  demo: boolean
  showAll?: boolean
}) {
  const replay = demo ? advisories.find((a) => a.site.id === site.id) : null
  const compact = site.event_outlook
  return (
    <section
      className="space-y-2 rounded-2xl border border-line bg-surface p-3 text-sm leading-relaxed text-ink-2 [&_h3]:text-ink [&_li]:break-words [&_ul]:list-disc [&_ul]:space-y-1 [&_ul]:pl-5"
      aria-labelledby="advisory-title"
    >
      <h2 id="advisory-title" className="text-base font-bold text-ink">
        Unverified worksite conditions
      </h2>
      <Details inline={showAll} title="View more" label="View more about unverified worksite conditions">
      <p className="text-sm text-ink-2">
        Electrical, structural, chemical and access conditions remain unknown
        without verified field or utility evidence.
      </p>
      {replay ? (
        <>
          <p>
            Simulated research replay. Local hazard probabilities are
            unavailable; no work clearance is provided.
          </p>
          <Details title="Research replay and source assessments">
            <p>
              Developer/demo advisory · contract {replay.contract_version} ·
              hypothetical {replay.event_type} activation at this exact
              reference plant.
            </p>
            <p>
              As of <Timestamp value={replay.as_of_utc} /> · source currency
              evaluated at that replay time.
            </p>
            <p>
              Layer A: {replay.event_outlook.status} ·{' '}
              {replay.event_outlook.model_version} ·{' '}
              {replay.event_outlook.target}
            </p>
            <p>
              Regional recorded-event persistence by horizon:{' '}
              {JSON.stringify(replay.event_outlook.ongoing_probability)}
            </p>
            <p>
              Remaining recorded-duration quantiles (hours):{' '}
              {JSON.stringify(replay.event_outlook.remaining_duration_hours)}
            </p>
            <p>Trend: {replay.event_outlook.trend}</p>
            <ul>
              {replay.event_outlook.limitations.map((x, i) => (
                <li key={i}>{x}</li>
              ))}
            </ul>
            <h3 className="pt-2 font-bold">
              Layer B — accepted and rejected evidence
            </h3>
            <details>
              <summary className="flex min-h-11 cursor-pointer items-center font-semibold text-ink">
                Inspect {replay.evidence.length} source assessments
              </summary>
              <ul className="space-y-3">
                {replay.evidence.map((a) => (
                  <li
                    key={a.evidence.evidence_id}
                    className="break-words border-t border-line pt-2"
                  >
                    <strong>
                      {a.accepted ? 'Accepted' : 'Rejected'}:{' '}
                      {displayLabel(a.evidence.variable)}
                    </strong>{' '}
                    · {a.evidence.value ?? 'unknown'} {a.evidence.unit}
                    <p>
                      {a.evidence.publisher} · {displayLabel(a.evidence.method)}{' '}
                      · {displayLabel(a.freshness)} ·{' '}
                      {displayLabel(a.spatial_match.kind)}
                    </p>
                    <p className="text-xs">
                      Record: {a.evidence.evidence_id}
                      <br />
                      Observed / issued:{' '}
                      {a.evidence.observed_at ??
                        a.evidence.issued_at ??
                        'unknown'}
                      <br />
                      Available: {a.evidence.available_at ?? 'unknown'} · Valid:{' '}
                      {a.evidence.valid_from} / {a.evidence.valid_to}
                      <br />
                      Source: {a.evidence.origin_url}
                      <br />
                      Reasons: {a.reasons.join(', ') || 'qualified at snapshot'}
                    </p>
                  </li>
                ))}
              </ul>
            </details>
            <p>Critical worker hazards remain unknown:</p>
            <ul>
              {replay.worksite_hazards
                .filter((h) =>
                  [
                    'downed_lines',
                    'energized_floodwater',
                    'structural_collapse',
                    'blocked_egress',
                    'chemical_release',
                    'wildlife',
                  ].includes(h.hazard_id),
                )
                .map((h) => (
                  <li key={h.hazard_id}>
                    {displayLabel(h.hazard_id)}: {displayLabel(h.status)}; local
                    probability: unknown (null); field verification required.
                  </li>
                ))}
            </ul>
          </Details>
        </>
      ) : compact ? (
        // T036B: the plain-language estimate; the numbers sit behind its disclosure.
        <ExpectedDuration outlook={compact} />
      ) : (
        <p>
          {NO_ESTIMATE} This does not mean an event has ended or the site is
          safe.
        </p>
      )}
      <p>ML never changes scores, alerts or acknowledgement state.</p>
      </Details>
    </section>
  )
}
