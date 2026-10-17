import type { EventOutlook } from '../../types/api'
import { durationSentence, NO_ESTIMATE } from './duration-text'
import { Icon } from '../shell/Icon'
import { Timestamp } from './Status'

/** T036B: how long a confirmed hazard is expected to last, in plain words. */
export function ExpectedDuration({ outlook }: { outlook: EventOutlook }) {
  const sentence = durationSentence(outlook)
  return (
    <div className="rounded-xl bg-surface-2 p-3 text-sm">
      <p className="kicker flex items-center gap-1.5">
        <Icon name="clock" className="size-3.5" />
        Expected duration · estimate
      </p>
      {sentence ? (
        <>
          <p className="mt-1 text-base font-semibold text-ink">
            {outlook.is_simulated && 'Simulated replay: '}
            {sentence}
          </p>
          <p className="mt-1 text-ink-2">
            Estimate from past recorded events, as of{' '}
            <Timestamp value={outlook.as_of_utc} />. Not an all-clear: alerts
            and instructions still apply.
          </p>
        </>
      ) : (
        <p className="mt-1 text-ink-2">
          {NO_ESTIMATE}
          {outlook.limitations[0] && (
            <span className="text-muted"> ({outlook.limitations[0]})</span>
          )}
        </p>
      )}
      <details className="mt-2">
        <summary className="flex min-h-11 cursor-pointer items-center font-semibold text-ink">
          How this is estimated
        </summary>
        <ul className="list-disc space-y-1 pl-5 text-ink-2">
          {Object.entries(outlook.ongoing_probability).map(([horizon, p]) => (
            <li key={horizon}>
              Chance the recorded event is still ongoing after {horizon}:{' '}
              {Math.round(p * 100)}%
            </li>
          ))}
          <li>
            Model {outlook.model_version}; trend {outlook.trend}.
          </li>
          {outlook.limitations.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
          <li>{outlook.advisory_notice}</li>
        </ul>
      </details>
    </div>
  )
}
