import { useCallback, useState, type FormEvent } from 'react'
import type {
  Account,
  JoinCode,
  OrganizationTeams,
  SiteSummary,
  TeamMember,
  TeamRoster,
} from '../../types/api'
import { useApplication, useResource } from '../../application/context'
import { ApiError } from '../../api/contracts'
import { useOptionalAuth } from '../../auth'
import { formatTimestamp } from '../../presentation/display'
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

/** The organization: its owner's supervision controls, the supervisor's sites and
 * teams, and every team's crew. The owner and the supervisor both open it. */
export function TeamPage() {
  const { client, persona } = useApplication()
  const result = useResource(
    'team',
    useCallback(async () => {
      // An account with no organization creates one or redeems a code first.
      if (!(await client.me()).organization_id)
        return { linked: false as const }
      const [org, sites] = await Promise.all([
        client.team(),
        persona === 'supervisor' ? client.sites() : Promise.resolve([]),
      ])
      return { linked: true as const, org, sites }
    }, [client, persona]),
  )
  if (!result.data) return <LoadState error={result.error} />
  if (!result.data.linked)
    return <Welcome supervisorAccount={persona === 'supervisor'} />
  const { org, sites } = result.data
  // Servers from before owners existed send no flags: a supervisor account supervises.
  const supervising = org.is_supervisor ?? persona === 'supervisor'
  // Teams go only on sites the organization claimed that have no team yet.
  const open = new Set(
    (org.claimed_sites ?? []).filter((c) => !c.team_id).map((c) => c.site_id),
  )
  const free = sites.filter((s) => open.has(s.id))
  return (
    <div className="pc-enter space-y-5">
      <OrganizationHeader key={org.organization_name} org={org} />
      {org.is_owner && <Supervision org={org} />}
      {supervising && <ClaimedSites org={org} sites={sites} />}
      {supervising && <AddTeam free={free} />}
      {org.teams.map((team) => (
        <TeamCard
          key={team.id}
          team={team}
          free={free}
          supervising={supervising}
        />
      ))}
      {!org.teams.length && (
        <p className="rounded-2xl border border-dashed border-line-strong p-4 text-sm text-ink-2">
          No teams in this organization yet.{' '}
          {supervising
            ? 'Claim a site, then add a team above.'
            : 'The supervisor adds teams.'}
        </p>
      )}
    </div>
  )
}

/** Owner only: who supervises, the supervisor code, and handing supervision over. */
function Supervision({ org }: { org: OrganizationTeams }) {
  const { client, principalId } = useApplication()
  const auth = useOptionalAuth()
  const codes = useResource(
    'supervisor-invites',
    useCallback(() => client.supervisorInvites(), [client]),
  )
  const change = useTeamChange()
  const [confirming, setConfirming] = useState(false)
  const [copied, setCopied] = useState(false)
  const supervisor = org.supervisors[0]
  const self = !!supervisor && supervisor.user_id === principalId
  const active = codes.data?.[0]
  // The new role reaches this browser only with a fresh sign-in.
  const signInAgain = async () => {
    if (auth) await auth.login({ returnTo: window.location.pathname })
  }
  return (
    <section
      className={`${card} space-y-4 p-5`}
      aria-labelledby="supervision-title"
    >
      <div>
        <p className="kicker mb-1">Owner</p>
        <h2 id="supervision-title" className="text-xl font-bold tracking-tight">
          Supervision
        </h2>
        <p className="mt-1 text-sm text-ink-2">
          Your organization has one supervisor. They claim sites, run teams,
          make join codes, and confirm hazards. You choose who it is.
        </p>
      </div>
      {supervisor ? (
        <div className="space-y-3 rounded-xl bg-surface-2 p-3">
          <p className="font-semibold">
            {self ? 'You supervise this organization.' : `Supervisor: ${display(supervisor)}`}
          </p>
          {!confirming ? (
            <button
              type="button"
              className={control}
              onClick={() => setConfirming(true)}
            >
              {self ? 'Step down as supervisor' : 'Remove supervisor'}
            </button>
          ) : (
            <div
              role="group"
              aria-label="Confirm removing the supervisor"
              className="flex flex-wrap items-center gap-3"
            >
              <p className="min-w-0 flex-1 text-sm">
                {self
                  ? 'Step down? You stay the owner, and you can make a new supervisor code for someone else or for yourself.'
                  : `Remove ${display(supervisor)} as supervisor? They lose the supervisor role. Teams, crew and records stay.`}
              </p>
              <button
                type="button"
                className={primary}
                disabled={change.busy}
                onClick={() =>
                  void change.run(async () => {
                    await client.removeSupervisor()
                    if (self) await signInAgain()
                  })
                }
              >
                {change.busy ? 'Removing…' : self ? 'Step down' : 'Remove'}
              </button>
              <button
                type="button"
                className={control}
                disabled={change.busy}
                onClick={() => setConfirming(false)}
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-sm font-semibold">No supervisor yet.</p>
          <button
            type="button"
            className={primary}
            disabled={change.busy}
            onClick={() =>
              void change.run(async () => {
                const code = active ?? (await client.createSupervisorInvite())
                await client.becomeSupervisor(code.code)
                await signInAgain()
              })
            }
          >
            <Icon name="team" className="size-4" />
            {change.busy ? 'Setting up…' : 'Make me the supervisor'}
          </button>
          <p className="text-sm text-muted">
            Or give a supervisor code to the person who will supervise. It works
            once and expires after 7 days.
          </p>
        </div>
      )}
      <div className="space-y-2 border-t border-line pt-4">
        <p className="kicker">Supervisor code</p>
        {active ? (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-surface-2 px-3 py-2">
            <div>
              <p className="font-mono text-xl font-bold tracking-[0.1em]">
                {active.code}
              </p>
              <p className="text-sm text-muted">
                Expires {formatTimestamp(active.expires_at)}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className={control}
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(active.code)
                    setCopied(true)
                  } catch {
                    setCopied(false)
                  }
                }}
              >
                {copied ? 'Copied' : 'Copy'}
              </button>
              <button
                type="button"
                className={control}
                disabled={change.busy}
                onClick={() =>
                  void change.run(() => client.revokeSupervisorInvite(active.code))
                }
                aria-label={`Revoke supervisor code ${active.code}`}
              >
                Revoke
              </button>
            </div>
          </div>
        ) : codes.error ? (
          <LoadState error={codes.error} />
        ) : (
          <p className="text-sm text-ink-2">No active supervisor code.</p>
        )}
        <button
          type="button"
          className={control}
          disabled={change.busy}
          onClick={() => void change.run(() => client.createSupervisorInvite())}
        >
          {active ? 'Replace code' : 'Create supervisor code'}
        </button>
        {supervisor && (
          <p className="text-sm text-muted">
            A code can be used only while the organization has no supervisor.
          </p>
        )}
      </div>
      {change.message && (
        <p role="alert" className="text-sm font-semibold text-stop-text">
          {change.message}
        </p>
      )}
    </section>
  )
}

/** Supervisor: the sites the organization claimed, and claiming more. */
function ClaimedSites({
  org,
  sites,
}: {
  org: OrganizationTeams
  sites: SiteSummary[]
}) {
  const { client } = useApplication()
  const change = useTeamChange()
  const [search, setSearch] = useState('')
  const [pick, setPick] = useState('')
  const claimed = org.claimed_sites ?? []
  const teamName = new Map(org.teams.map((t) => [t.id, t.name]))
  const unavailable = new Set([
    ...(org.unavailable_site_ids ?? []),
    ...claimed.map((c) => c.site_id),
  ])
  const query = search.trim().toLowerCase()
  const options = sites
    .filter((s) => !unavailable.has(s.id))
    .filter((s) => !query || `${s.name} ${s.id}`.toLowerCase().includes(query))
    .slice(0, 50)
  return (
    <section className={`${card} space-y-4 p-5`} aria-labelledby="sites-title">
      <div>
        <p className="kicker mb-1">Supervisor</p>
        <h2 id="sites-title" className="text-xl font-bold tracking-tight">
          Claimed sites
        </h2>
        <p className="mt-1 text-sm text-ink-2">
          Claim the sites your organization works at, then put a team on each.
          A site belongs to one organization at a time.
        </p>
      </div>
      {claimed.length ? (
        <ul className="divide-y divide-line" aria-label="Claimed sites">
          {claimed.map((c) => (
            <li
              key={c.site_id}
              className="flex flex-wrap items-center justify-between gap-3 py-2.5"
            >
              <div className="min-w-0">
                <p className="font-semibold [overflow-wrap:anywhere]">
                  {c.site_name}
                </p>
                <p className="text-sm text-muted">
                  {c.team_id
                    ? `Team: ${teamName.get(c.team_id) ?? c.team_id}`
                    : 'No team yet'}
                </p>
              </div>
              <button
                type="button"
                className={control}
                disabled={change.busy || !!c.team_id}
                onClick={() => void change.run(() => client.releaseSite(c.site_id))}
                aria-label={`Release ${c.site_name}`}
              >
                Release
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-ink-2">No sites claimed yet.</p>
      )}
      <form
        aria-label="Claim a site"
        className="grid gap-3 border-t border-line pt-4 @lg:grid-cols-[1fr_1fr_auto] @lg:items-end"
        onSubmit={async (event: FormEvent) => {
          event.preventDefault()
          if (pick && (await change.run(() => client.claimSite(pick)))) setPick('')
        }}
      >
        <label className={labelText}>
          Find a site
          <input
            className={field}
            value={search}
            placeholder="Name or ID"
            onChange={(e) => {
              setSearch(e.target.value)
              setPick('')
            }}
          />
        </label>
        <label className={labelText}>
          Site to claim
          <select
            className={field}
            value={pick}
            onChange={(e) => setPick(e.target.value)}
          >
            <option value="">Choose a site</option>
            {options.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <button
          type="submit"
          className={primary}
          disabled={change.busy || !pick}
        >
          <Icon name="pin" className="size-4" />
          Claim site
        </button>
      </form>
      {change.message && (
        <p role="alert" className="text-sm font-semibold text-stop-text">
          {change.message}
        </p>
      )}
    </section>
  )
}

/** Redeem the owner's supervisor code, then sign in again so the new role reaches this
 * browser. */
function RedeemSupervisorCode() {
  const { client } = useApplication()
  const auth = useOptionalAuth()
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setMessage('')
    try {
      await client.becomeSupervisor(code)
      if (auth) await auth.login({ returnTo: window.location.pathname })
    } catch (e) {
      setMessage(
        e instanceof ApiError && e.detail
          ? e.detail
          : e instanceof Error
            ? e.message
            : 'Supervisor sign-up is unavailable',
      )
      setBusy(false)
    }
  }
  return (
    <form
      onSubmit={submit}
      aria-label="Become a supervisor"
      className={`${card} space-y-4 p-5`}
    >
      <div>
        <p className="kicker mb-1">Supervisor</p>
        <h2 className="text-2xl font-bold tracking-tight">
          Enter a supervisor code
        </h2>
        <p className="mt-1 text-sm text-ink-2">
          The organization's owner gives you this code to make you its
          supervisor.
        </p>
      </div>
      <label className={labelText}>
        Supervisor code
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
        {busy ? 'Setting up…' : 'Become the supervisor'}
      </button>
      {message && (
        <p role="alert" className="text-sm font-semibold text-stop-text">
          {message}
        </p>
      )}
    </form>
  )
}

/** Anyone with no organization creates one and becomes its owner. */
function CreateOrganization() {
  const { client, refresh } = useApplication()
  const [first, setFirst] = useState('')
  const [last, setLast] = useState('')
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setMessage('')
    try {
      await client.createOrganization({
        first_name: first.trim(),
        last_name: last.trim(),
        organization_name: name.trim(),
      })
      refresh()
    } catch (e) {
      setMessage(
        e instanceof ApiError && e.detail
          ? e.detail
          : e instanceof Error
            ? e.message
            : 'Creating an organization is unavailable',
      )
    } finally {
      setBusy(false)
    }
  }
  return (
    <form
      onSubmit={submit}
      aria-label="Create an organization"
      className={`${card} space-y-4 p-5`}
    >
      <div>
        <p className="kicker mb-1">Owner</p>
        <h2 className="text-2xl font-bold tracking-tight">
          Create an organization
        </h2>
        <p className="mt-1 text-sm text-ink-2">
          You'll own it and choose its supervisor, which can be you.
        </p>
      </div>
      <div className="grid gap-3 @lg:grid-cols-2">
        <label className={labelText}>
          First name
          <input
            className={field}
            value={first}
            onChange={(e) => setFirst(e.target.value)}
            autoComplete="given-name"
            maxLength={80}
            required
          />
        </label>
        <label className={labelText}>
          Last name
          <input
            className={field}
            value={last}
            onChange={(e) => setLast(e.target.value)}
            autoComplete="family-name"
            maxLength={80}
            required
          />
        </label>
      </div>
      <label className={labelText}>
        Organization name
        <input
          className={field}
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoComplete="organization"
          maxLength={80}
          required
        />
      </label>
      <button
        type="submit"
        className={primary + big}
        disabled={busy || !first.trim() || !last.trim() || !name.trim()}
      >
        {busy ? 'Creating…' : 'Create organization'}
      </button>
      {message && (
        <p role="alert" className="text-sm font-semibold text-stop-text">
          {message}
        </p>
      )}
    </form>
  )
}

/** The organization's name, which its supervisor can change, and who runs it. */
function OrganizationHeader({ org }: { org: OrganizationTeams }) {
  const { client } = useApplication()
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(org.organization_name)
  const change = useTeamChange()
  return (
    <section className={`${card} p-5`}>
      <p className="kicker mb-1">Organization</p>
      {editing ? (
        <form
          aria-label="Rename organization"
          className="flex flex-wrap items-end gap-2"
          onSubmit={async (event: FormEvent) => {
            event.preventDefault()
            if (await change.run(() => client.renameOrganization(name.trim())))
              setEditing(false)
          }}
        >
          <label className={`${labelText} min-w-0 flex-1`}>
            Organization name
            <input
              className={field}
              value={name}
              maxLength={80}
              onChange={(e) => setName(e.target.value)}
              autoFocus
              required
            />
          </label>
          <button
            type="submit"
            className={primary}
            disabled={change.busy || !name.trim()}
          >
            Save
          </button>
          <button
            type="button"
            className={control}
            onClick={() => {
              setName(org.organization_name)
              setEditing(false)
            }}
          >
            Cancel
          </button>
        </form>
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-2xl font-bold tracking-tight">
            {org.organization_name}
          </h2>
          <button
            type="button"
            className={control}
            onClick={() => setEditing(true)}
          >
            Rename
          </button>
        </div>
      )}
      <p className="mt-1 text-sm text-ink-2">
        {org.teams.length} {org.teams.length === 1 ? 'team' : 'teams'} ·
        Supervisor: {org.supervisors.map(display).join(', ') || 'none yet'}
      </p>
      {client.mode === 'demo' && (
        <p className="mt-2 text-sm text-sim">
          Simulated roster. Team and join-code changes reset on reload.
        </p>
      )}
      {change.message && (
        <p role="alert" className="mt-2 text-sm font-semibold text-stop-text">
          {change.message}
        </p>
      )}
    </section>
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
          <p className="text-sm text-muted">
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

/** One crew member, with a two-step Remove (they can rejoin with a new code). */
function MemberRow({ team, member }: { team: TeamRoster; member: TeamMember }) {
  const { client } = useApplication()
  const { busy, message, run } = useTeamChange()
  const [confirming, setConfirming] = useState(false)
  return (
    <li className="space-y-2 py-2.5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="font-semibold [overflow-wrap:anywhere]">
            {display(member)}
          </p>
          {member.name && member.email && (
            <p className="truncate text-sm text-ink-2">{member.email}</p>
          )}
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-3">
          <span className="text-sm text-muted">
            {member.joined_at
              ? `Joined ${day(member.joined_at)}`
              : 'Added by admin'}
          </span>
          {!confirming && (
            <button
              type="button"
              className={control}
              onClick={() => setConfirming(true)}
              aria-label={`Remove ${display(member)} from ${team.name}`}
            >
              Remove
            </button>
          )}
        </div>
      </div>
      {confirming && (
        <div
          role="group"
          aria-label={`Confirm removing ${display(member)}`}
          className="flex flex-wrap items-center gap-3 rounded-xl border border-line-strong p-3"
        >
          <p className="min-w-0 flex-1 text-sm">
            Remove {display(member)} from {team.name}? Their reports stay on
            record, and they can rejoin with a new join code.
          </p>
          <button
            type="button"
            className={primary}
            disabled={busy}
            onClick={() =>
              void run(() => client.removeMember(team.id, member.user_id))
            }
          >
            {busy ? 'Removing…' : 'Remove'}
          </button>
          <button
            type="button"
            className={control}
            disabled={busy}
            onClick={() => setConfirming(false)}
          >
            Cancel
          </button>
        </div>
      )}
      {message && (
        <p role="alert" className="text-sm font-semibold text-stop-text">
          {message}
        </p>
      )}
    </li>
  )
}

function TeamCard({
  team,
  free,
  supervising,
}: {
  team: TeamRoster
  free: SiteSummary[]
  /** The supervisor manages codes and sites; the owner only removes. */
  supervising: boolean
}) {
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
          {team.site_id && !supervising ? (
            <p className="mt-1 inline-flex min-h-11 items-center gap-1.5 text-sm text-ink-2">
              <Icon name="pin" className="size-4" />
              {team.site_name ?? team.site_id}
            </p>
          ) : team.site_id ? (
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
            <MemberRow key={m.user_id} team={team} member={m} />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-ink-2">
          No crew yet.{' '}
          {supervising
            ? 'Share a join code to add people.'
            : 'The supervisor shares join codes.'}
        </p>
      )}

      {supervising ? (
        <>
      <div className="space-y-3 border-t border-line pt-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="kicker">Join codes</p>
            <p className="text-sm text-muted">
              Share with your crew. Each code expires after 7 days.
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
        </>
      ) : (
        <RemoveTeam team={team} />
      )}
    </section>
  )
}

/** Owner: remove an empty team. */
function RemoveTeam({ team }: { team: TeamRoster }) {
  const { client } = useApplication()
  const change = useTeamChange()
  return (
    <div className="space-y-2 border-t border-line pt-3">
      <button
        type="button"
        className={control}
        disabled={change.busy || team.members.length > 0}
        onClick={() => void change.run(() => client.deleteTeam(team.id))}
      >
        Remove team
      </button>
      {team.members.length > 0 && (
        <p className="text-sm text-muted">
          A team can be removed once nobody is on it.
        </p>
      )}
      {change.message && (
        <p role="alert" className="text-sm font-semibold text-stop-text">
          {change.message}
        </p>
      )}
    </div>
  )
}

function CodeRow({ code }: { code: JoinCode }) {
  const { client } = useApplication()
  const [copied, setCopied] = useState(false)
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-surface-2 px-3 py-2">
      <div>
        <p className="break-all font-mono text-xl font-bold tracking-[0.1em]">
          {code.code}
        </p>
        <p className="text-sm text-muted">
          Expires {formatTimestamp(code.expires_at)}
        </p>
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
          Revoke code
        </Action>
      </div>
    </div>
  )
}

function display(m: TeamMember) {
  return m.name ?? m.email ?? 'Name not shared yet'
}

/** An account with no team: the owner's organization page, or the welcome choices. */
export function JoinTeam() {
  const { client, persona } = useApplication()
  const account = useResource(
    'me',
    useCallback(() => client.me(), [client]),
  )
  if (!account.data) return <LoadState error={account.error} />
  if (account.data.team_id) return <NoSite account={account.data} />
  // An owner who doesn't supervise runs the organization from here.
  if (account.data.is_owner) return <TeamPage />
  return <Welcome supervisorAccount={persona === 'supervisor'} />
}

/** Join a team, become an organization's supervisor, or create an organization. */
function Welcome({ supervisorAccount }: { supervisorAccount: boolean }) {
  return (
    <div className="pc-enter space-y-4">
      <div className="mx-auto max-w-5xl">
        <h1 className="text-2xl font-bold tracking-tight">
          Welcome to FORESITE
        </h1>
        <p className="mt-1 text-ink-2">
          Choose how you'll use it. Crew join a team with a join code. A
          supervisor uses the code their organization's owner gives them.
          Anyone can create an organization.
        </p>
      </div>
      <div
        className={`mx-auto grid max-w-5xl gap-4 ${supervisorAccount ? '@3xl:grid-cols-2' : '@3xl:grid-cols-2 @6xl:grid-cols-3'}`}
      >
        {!supervisorAccount && <JoinCodeForm />}
        <RedeemSupervisorCode />
        <CreateOrganization />
      </div>
    </div>
  )
}

/** Crew: enter the supervisor's join code. */
function JoinCodeForm() {
  const { client, refresh } = useApplication()
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
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
      className={`${card} space-y-4 p-5`}
    >
      <div>
        <p className="kicker mb-1">Crew member</p>
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
