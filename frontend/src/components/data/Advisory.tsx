import advisories from '../../demo/generated/advisories.json'
import type { SiteRecord } from '../../api/contracts'
import { Timestamp } from './Status'
export function Advisory({ site, demo }: { site: SiteRecord; demo: boolean }) {
  const replay = demo ? advisories.find((a) => a.site.id === site.id) : null
  const compact = site.event_outlook
  return (
    <section
      className="space-y-3 rounded-xl border border-slate-300 bg-white p-4"
      aria-labelledby="advisory-title"
    >
      <h2 id="advisory-title" className="text-xl font-semibold">
        Event outlook and site evidence
      </h2>
      <p className="font-semibold">
        Research advisory only. Recorded event end is not worksite clearance. No
        local injury/hazard probabilities are validated.
      </p>
      {replay ? (
        <>
          <p>
            Developer/demo advisory · contract {replay.contract_version} ·
            hypothetical {replay.event_type} activation at this exact reference
            plant.
          </p>
          <p>
            As of <Timestamp value={replay.as_of_utc} /> · source currency
            evaluated at that replay time.
          </p>
          <p>
            Layer A: {replay.event_outlook.status} ·{' '}
            {replay.event_outlook.model_version} · {replay.event_outlook.target}
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
          <h3 className="font-semibold">
            Layer B — accepted and rejected evidence
          </h3>
          <details>
            <summary className="min-h-11 cursor-pointer py-2">
              Inspect {replay.evidence.length} source assessments
            </summary>
            <ul className="space-y-3">
              {replay.evidence.map((a) => (
                <li
                  key={a.evidence.evidence_id}
                  className="break-words border-t pt-2"
                >
                  <strong>
                    {a.accepted ? 'Accepted' : 'Rejected'}:{' '}
                    {a.evidence.variable}
                  </strong>{' '}
                  · {a.evidence.value ?? 'unknown'} {a.evidence.unit}
                  <p>
                    {a.evidence.publisher} · {a.evidence.method} · {a.freshness}{' '}
                    · {a.spatial_match.kind}
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
                  {h.hazard_id}: {h.status}; local probability: unknown (null);
                  field verification required.
                </li>
              ))}
          </ul>
        </>
      ) : compact ? (
        <>
          <p>
            {compact.is_simulated
              ? 'Replay'
              : 'Confirmed-event backend advisory'}{' '}
            · {compact.event_type ?? 'event unavailable'} · {compact.status}
          </p>
          <p>
            As of <Timestamp value={compact.as_of_utc} /> · generated{' '}
            <Timestamp value={compact.generated_at_utc} />
          </p>
          <p>
            Model: {compact.model_version} · Trend: {compact.trend}
          </p>
          <p>
            Regional persistence: {JSON.stringify(compact.ongoing_probability)}
          </p>
          <p>
            Remaining hours p10 / median / p90:{' '}
            {compact.remaining_hours_p10 ?? 'unknown'} /{' '}
            {compact.remaining_hours_median ?? 'unknown'} /{' '}
            {compact.remaining_hours_p90 ?? 'unknown'}
          </p>
          <ul>
            {compact.limitations.map((x, i) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
        </>
      ) : (
        <p>
          No supported event outlook was supplied for this site. Never infer
          event absence or zero risk. Comprehensive 2.1 live evidence still
          needs an approved backend endpoint.
        </p>
      )}
      <p>
        Electrical, structural, chemical and access conditions require verified
        field/utility evidence. ML never changes scores, alerts or
        acknowledgement state.
      </p>
    </section>
  )
}
