import { useCallback, useState, type FormEvent } from 'react'
import type {
  Account,
  JoinCode,
  SiteSummary,
  TeamMember,
  TeamRoster,
} from '../../types/api'
import { useApplication, useResource } from '../../application/context'
import { ApiError } from '../../api/contracts'
import { Icon } from '../shell/Icon'
import {
  Action,
  big,
  card,
  control,
  field,
  labelText,
  LoadState,
  primary,
} from './Interaction'

const day = (iso: string) =>
  new Date(iso).toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  })

/** Supervisor: who is on each team, and the join codes that add crew. */
export function TeamPage() {
  const { client } = useApplication()
  const result = useResource(
    'team',
    useCallback(() => Promise.all([client.team(), client.sites()]), [client]),
  )
  if (!result.data) return <LoadState error={result.error} />
  const [org, sites] = result.data
  // A site has at most one team, so new or moved teams pick from sites without one.
  const taken = new Set(org.teams.map((t) => t.site_id))
  const free = sites.filter((s) => !s.assigned_team && !taken.has(s.id))
  return (
    <div className="pc-enter space-y-5">
      <section className={`${card} p-5`}>
        <p className="kicker mb-1">Organization</p>
        <h2 className="text-2xl font-bold tracking-tight">
          {org.organization_name}
        </h2>
        <p className="mt-1 text-sm text-ink-2">
          {org.teams.length} {org.teams.length === 1 ? 'team' : 'teams'} ·
          Supervisor{org.supervisors.length === 1 ? '' : 's'}:{' '}
          {org.supervisors.map(display).join(', ') || 'none linked'}
        </p>
      </section>
      {org.teams.map((team) => (
        <TeamCard key={team.id} team={team} free={free} />
      ))}
      {!org.teams.length && (
        <p className="rounded-2xl border border-dashed border-line-strong p-4 text-sm text-ink-2">
          No teams in this organization yet.
        </p>
      )}
      <AddTeam free={free} />
    </div>
  )
}

/** Run a team change and show the backend's own explanation when it refuses. */
function useTeamChange() {
  const { refresh } = useApplication()
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  async function run(change: () => Promise<unknown>) {
    if (busy) return false
    setBusy(true)
    setMessage('')
    try {
      await change()
      refresh()
      return true
    } catch (e) {
      setMessage(
        e instanceof ApiError && e.detail
          ? e.detail
          : e instanceof Error
            ? e.message
            : 'Team changes are unavailable',
      )
      return false
    } finally {
      setBusy(false)
    }
  }
  return { busy, message, run }
}

function SitePicker({
  value,
  onChange,
  free,
  current,
}: {
  value: string
  onChange: (id: string) => void
  free: SiteSummary[]
  current?: { id: string; name: string } | null
}) {
  return (
    <label className={labelText}>
      Site
      <select
        className={field}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">No site yet</option>
        {current && (
          <option value={current.id}>{current.name} (current)</option>
        )}
        {free.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </select>
    </label>
  )
}

function AddTeam({ free }: { free: SiteSummary[] }) {
  const { client } = useApplication()
  const [name, setName] = useState('')
  const [site, setSite] = useState('')
  const change = useTeamChange()
  return (
    <form
      aria-label="Add a team"
      className={`${card} space-y-3 p-5`}
      onSubmit={async (event: FormEvent) => {
        event.preventDefault()
        const done = await change.run(() =>
          client.createTeam({ name, site_id: site || null }),
        )
        if (done) {
          setName('')
          setSite('')
        }
      }}
    >
      <p className="kicker">Add a team</p>
      <div className="grid gap-3 @lg:grid-cols-2">
        <label className={labelText}>
          Team name
          <input
            className={field}
            value={name}
            maxLength={80}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </label>
        <SitePicker value={site} onChange={setSite} free={free} />
      </div>
      <button
        type="submit"
        className={primary}
        disabled={change.busy || !name.trim()}
      >
        <Icon name="team" className="size-4" />
        Add team
      </button>
      {change.message && (
        <p role="alert" className="text-sm font-semibold text-stop-text">
          {change.message}
        </p>
      )}
    </form>
  )
}

function ManageTeam({ team, free }: { team: TeamRoster; free: SiteSummary[] }) {
  const { client } = useApplication()
  const [name, setName] = useState(team.name)
  const [site, setSite] = useState(team.site_id ?? '')
  const change = useTeamChange()
  const current = team.site_id
    ? { id: team.site_id, name: team.site_name ?? team.site_id }
    : null
  return (
    <details className="border-t border-line pt-3">
      <summary className="flex min-h-11 cursor-pointer items-center text-sm font-semibold text-link">
        Manage team
      </summary>
      <div className="mt-2 space-y-3">
        <div className="grid gap-3 @lg:grid-cols-2">
          <label className={labelText}>
            Team name
            <input
              className={field}
              value={name}
              maxLength={80}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <SitePicker
            value={site}
            onChange={setSite}
            free={free}
            current={current}
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className={primary}
            disabled={
              change.busy ||
              !name.trim() ||
              (name.trim() === team.name && site === (team.site_id ?? ''))
            }
            onClick={() =>
              change.run(() =>
                client.updateTeam(team.id, {
                  name: name.trim(),
                  site_id: site || null,
                }),
              )
            }
          >
            Save changes
          </button>
          <button
            type="button"
            className={control}
            disabled={change.busy || team.members.length > 0}
            onClick={() => change.run(() => client.deleteTeam(team.id))}
          >
            Remove team
          </button>
        </div>
        {team.members.length > 0 && (
          <p className="text-xs text-muted">
            A team can be removed once nobody is on it.
          </p>
        )}
        {change.message && (
          <p role="alert" className="text-sm font-semibold text-stop-text">
            {change.message}
          </p>
        )}
      </div>
    </details>
  )
}

function TeamCard({ team, free }: { team: TeamRoster; free: SiteSummary[] }) {
  const { client } = useApplication()
  return (
    <section
      className={`${card} space-y-5 p-5`}
      aria-labelledby={`team-${team.id}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2
            id={`team-${team.id}`}
            className="text-xl font-bold tracking-tight"
          >
            {team.name}
          </h2>
          {team.site_id ? (
            <a
              href={`#/supervisor/sites/${encodeURIComponent(team.site_id)}`}
              className="mt-1 inline-flex min-h-11 items-center gap-1.5 text-sm font-semibold text-link"
            >
              <Icon name="pin" className="size-4" />
              {team.site_name ?? team.site_id}
            </a>
          ) : (
            <p className="mt-1 text-sm text-muted">No site assigned</p>
          )}
        </div>
        <span className="chip border border-line-strong text-ink-2">
          {team.members.length}{' '}
          {team.members.length === 1 ? 'member' : 'members'}
        </span>
      </div>

      {team.members.length ? (
        <ul
          className="divide-y divide-line"
          aria-label={`${team.name} members`}
        >
          {team.members.map((m) => (
            <li
              key={m.user_id}
              className="flex items-center justify-between gap-3 py-2.5"
            >
              <div className="min-w-0">
                <p className="truncate font-semibold">{display(m)}</p>
                {m.name && m.email && (
                  <p className="truncate text-sm text-ink-2">{m.email}</p>
                )}
              </div>
              <span className="shrink-0 text-xs text-muted">
                {m.joined_at ? `Joined ${day(m.joined_at)}` : 'Added by admin'}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-ink-2">
          No crew yet. Share a join code to add people.
        </p>
      )}

      <div className="space-y-3 border-t border-line pt-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="kicker">Join codes</p>
            <p className="text-xs text-muted">
              A code adds a new crew account to this team for 7 days.
            </p>
          </div>
          <Action capability="team" run={() => client.createJoinCode(team.id)}>
            <Icon name="team" className="size-4" />
            Create join code
          </Action>
        </div>
        {team.join_codes.map((code) => (
          <CodeRow key={code.code} code={code} />
        ))}
      </div>
      <ManageTeam
        key={`${team.name}:${team.site_id}`}
        team={team}
        free={free}
      />
    </section>
  )
}

function CodeRow({ code }: { code: JoinCode }) {
  const { client } = useApplication()
  const [copied, setCopied] = useState(false)
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-surface-2 px-3 py-2">
      <div>
        <p className="font-mono text-xl font-bold tracking-[0.15em]">
          {code.code}
        </p>
        <p className="text-xs text-muted">Expires {day(code.expires_at)}</p>
      </div>
      <div className="flex flex-wrap items-start gap-2">
        <button
          type="button"
          className={control}
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(code.code)
              setCopied(true)
            } catch {
              setCopied(false)
            }
          }}
        >
          {copied ? 'Copied' : 'Copy'}
        </button>
        <Action capability="team" run={() => client.revokeJoinCode(code.code)}>
          Revoke
        </Action>
      </div>
    </div>
  )
}

function display(m: TeamMember) {
  return m.name ?? m.email ?? 'Name not shared yet'
}

/** Crew account with no team: enter the supervisor's code. */
export function JoinTeam() {
  const { client, refresh } = useApplication()
  const account = useResource(
    'me',
    useCallback(() => client.me(), [client]),
  )
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  if (!account.data) return <LoadState error={account.error} />
  if (account.data.team_id) return <NoSite account={account.data} />

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setMessage('')
    try {
      await client.join(code)
      refresh()
    } catch (e) {
      setMessage(
        e instanceof ApiError && e.detail
          ? e.detail
          : e instanceof Error
            ? e.message
            : 'Joining is unavailable',
      )
    } finally {
      setBusy(false)
    }
  }
  return (
    <form
      onSubmit={submit}
      aria-label="Join your team"
      className={`${card} mx-auto max-w-md space-y-4 p-5`}
    >
      <div>
        <p className="kicker mb-1">Join your team</p>
        <h2 className="text-2xl font-bold tracking-tight">
          Enter your join code
        </h2>
        <p className="mt-1 text-sm text-ink-2">
          Your supervisor gives you an 8-character code, like ABCD-2345.
        </p>
      </div>
      <label className={labelText}>
        Join code
        <input
          className={`${field} min-h-14 text-center font-mono text-2xl font-bold uppercase tracking-[0.2em]`}
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          autoComplete="off"
          autoCapitalize="characters"
          spellCheck={false}
          maxLength={9}
          placeholder="XXXX-XXXX"
          required
        />
      </label>
      <button
        type="submit"
        className={primary + big}
        disabled={busy || code.replace(/[^A-Za-z0-9]/g, '').length !== 8}
      >
        {busy ? 'Joining…' : 'Join team'}
      </button>
      {message && (
        <p role="alert" className="text-sm font-semibold text-stop-text">
          {message}
        </p>
      )}
    </form>
  )
}

function NoSite({ account }: { account: Account }) {
  return (
    <p role="status" className={`${card} p-5 text-ink-2`}>
      You're on {account.team_name ?? 'a team'}, which has no site assigned yet.
      Ask your supervisor.
    </p>
  )
}
