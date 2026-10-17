import { useRef, useState, type ReactNode } from "react";
import { useApplication } from "../../application/context";
import { ApiError, type Client } from "../../api/contracts";

const base =
  "inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50";
/** Secondary button / link. */
export const control =
  base + " border border-line-strong bg-surface text-ink hover:bg-surface-2";
/** Primary action: inverse of the theme (bone on dark, ink on light). */
export const primary =
  base + " border border-ink bg-ink text-bg hover:opacity-90";
/** Large field action for gloved use (acknowledge, report). */
export const big = " min-h-[72px] w-full rounded-2xl px-6 text-lg font-bold";
/** Text inputs, selects and textareas. */
export const field =
  "mt-1.5 block min-h-11 w-full rounded-xl border border-line-strong bg-surface px-3 py-2 text-base text-ink placeholder:text-faint";
/** Form label text. */
export const labelText = "block text-sm font-semibold text-ink-2";
/** Card surface used across pages. */
export const card = "rounded-2xl border border-line bg-surface";

export function LoadState({ error }: { error: string | null }) {
  const { refresh } = useApplication();
  return error ? (
    <div
      role="alert"
      className="flex flex-col gap-3 rounded-2xl border-2 border-stop bg-surface p-5 sm:flex-row sm:items-center sm:justify-between"
    >
      <div>
        <p className="kicker text-stop-text!">Could not load</p>
        <p className="mt-1 text-base text-ink">{error}</p>
      </div>
      <button type="button" className={control} onClick={refresh}>
        Retry loading
      </button>
    </div>
  ) : (
    <div className="space-y-3">
      <p role="status" aria-live="polite" className="kicker">
        Loading workspace data…
      </p>
      <div className="pc-skeleton h-24 rounded-2xl" aria-hidden="true" />
      <div className="grid gap-3 sm:grid-cols-2" aria-hidden="true">
        <div className="pc-skeleton h-20 rounded-2xl" />
        <div className="pc-skeleton h-20 rounded-2xl" />
      </div>
    </div>
  );
}

export function Action({
  run,
  children,
  disabled = false,
  capability = "reviewReports",
  tone = "default",
}: {
  run: () => Promise<unknown>;
  children: ReactNode;
  disabled?: boolean;
  capability?: keyof Client["capabilities"];
  tone?: "default" | "primary" | "big";
}) {
  const { refresh, client } = useApplication();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const inFlight = useRef(false);
  const className =
    tone === "big" ? primary + big : tone === "primary" ? primary : control;
  return (
    <div className={tone === "big" ? "w-full" : undefined}>
      <button
        type="button"
        className={className}
        disabled={busy || disabled || !client.capabilities[capability]}
        onClick={async () => {
          if (inFlight.current) return;
          inFlight.current = true;
          setBusy(true);
          setMessage("");
          try {
            await run();
            refresh();
            setMessage("Action recorded.");
          } catch (e) {
            setMessage(e instanceof Error ? e.message : "Action unavailable");
            if (e instanceof ApiError && [403, 409, 502].includes(e.status))
              refresh();
          } finally {
            inFlight.current = false;
            setBusy(false);
          }
        }}
      >
        {busy ? "Working…" : children}
      </button>
      {!client.capabilities[capability] && (
        <p className="mt-2 text-sm text-muted">
          This action is unavailable on the current live backend.
        </p>
      )}
      {message && (
        <p
          role="status"
          className="mt-2 inline-flex items-center gap-1.5 text-sm font-semibold text-ink-2"
        >
          {message}
        </p>
      )}
    </div>
  );
}
