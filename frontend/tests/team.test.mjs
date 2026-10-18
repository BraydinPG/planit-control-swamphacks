// Join codes and the supervisor's team roster: client validation, demo mode and rendering.
import { after, test } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'vite'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

const server = await createServer({
  configFile: false,
  cacheDir: '.shell-check/team-cache',
  logLevel: 'silent',
  server: { middlewareMode: true, hmr: false, watch: null },
  appType: 'custom',
})
after(() => server.close())
const { validateAccount, validateJoinCode, validateTeams } =
  await server.ssrLoadModule('/src/api/validate.ts')
const { HttpClient } = await server.ssrLoadModule('/src/api/http-client.ts')
const { DemoClient } = await server.ssrLoadModule('/src/demo/client.ts')
const { ApplicationContext } = await server.ssrLoadModule(
  '/src/application/context.tsx',
)
const { JoinTeam } = await server.ssrLoadModule(
  '/src/components/data/TeamRoster.tsx',
)

const { attentionItems, highestRisk } = await server.ssrLoadModule(
  '/src/components/data/attention.ts',
)
const text = (html) => html.replace(/<[^>]+>/g, '').replaceAll('&#x27;', "'")
const storage = () => {
  const map = new Map()
  return {
    getItem: (k) => map.get(k) ?? null,
    setItem: (k, v) => map.set(k, v),
    removeItem: (k) => map.delete(k),
  }
}
const invalid = (e) => e.status === 502
const code = {
  code: 'GTR4-F7KM',
  team_id: 'team-a',
  created_at: '2026-10-17T18:00:00Z',
  expires_at: '2026-10-24T18:00:00Z',
}

test('join codes must look like XXXX-XXXX without confusable characters', () => {
  assert.equal(validateJoinCode(code).code, 'GTR4-F7KM')
  for (const bad of ['GTR4F7KM', 'GTR0-F7KM', 'gtr4-f7km', 'GTR4-F7K'])
    assert.throws(() => validateJoinCode({ ...code, code: bad }), invalid)
})

test('account and roster responses are validated', () => {
  assert.equal(
    validateAccount({
      role: 'crew',
      organization_id: null,
      organization_name: null,
      team_id: null,
      team_name: null,
      site_id: null,
    }).role,
    'crew',
  )
  assert.throws(() => validateAccount({ role: 'admin' }), invalid)
  const roster = {
    organization_id: 'org-1',
    organization_name: 'Sunbelt',
    supervisors: [],
    teams: [
      {
        id: 'team-a',
        name: 'Line Crew A',
        site_id: 'site-a',
        site_name: 'Alpha',
        members: [
          {
            user_id: 'auth0|x',
            name: 'Amy',
            email: null,
            role: 'crew',
            joined_at: null,
          },
        ],
        join_codes: [code],
      },
    ],
  }
  assert.equal(validateTeams(roster).teams[0].members[0].name, 'Amy')
  assert.throws(
    () =>
      validateTeams({
        ...roster,
        teams: [{ ...roster.teams[0], join_codes: [{ code: 'nope' }] }],
      }),
    invalid,
  )
})

test('the live client calls the team routes with the bearer token', async () => {
  const calls = []
  const reply = {
    '/api/me': {
      role: 'crew',
      organization_id: 'org-1',
      organization_name: 'Sunbelt',
      team_id: 'team-a',
      team_name: 'A',
      site_id: 'site-a',
    },
    '/api/join': {
      role: 'crew',
      organization_id: 'org-1',
      organization_name: 'Sunbelt',
      team_id: 'team-a',
      team_name: 'A',
      site_id: 'site-a',
    },
    '/api/teams/team-a/join-codes': code,
  }
  const api = new HttpClient(
    'http://localhost:8000',
    async () => ({ Authorization: 'Bearer t' }),
    async (url, options) => {
      const path = new URL(url).pathname
      calls.push([options.method ?? 'GET', path, options.body ?? null])
      return path.startsWith('/api/join-codes/')
        ? new Response(null, { status: 204 })
        : Response.json(reply[path])
    },
  )
  assert.equal((await api.me()).team_id, 'team-a')
  assert.equal((await api.join('gtr4-f7km')).site_id, 'site-a')
  assert.equal((await api.createJoinCode('team-a')).code, 'GTR4-F7KM')
  await api.revokeJoinCode('GTR4-F7KM')
  assert.deepEqual(
    calls.map(([m, p]) => `${m} ${p}`),
    [
      'GET /api/me',
      'POST /api/join',
      'POST /api/teams/team-a/join-codes',
      'DELETE /api/join-codes/GTR4-F7KM',
    ],
  )
  assert.equal(calls[1][2], JSON.stringify({ code: 'gtr4-f7km' }))
})

test('demo supervisors see a simulated roster and can create and revoke codes', async () => {
  const demo = new DemoClient(() => 'supervisor', storage())
  const roster = await demo.team()
  assert(roster.organization_name.includes('simulated'))
  const teamA = roster.teams[0]
  assert(
    teamA.members.length >= 1 &&
      teamA.members.every((m) => m.name.includes('simulated')),
  )
  const created = await demo.createJoinCode(teamA.id)
  assert.match(created.code, /^[A-Z2-9]{4}-[A-Z2-9]{4}$/)
  assert.equal(
    Date.parse(created.expires_at) - Date.parse(created.created_at),
    7 * 24 * 3600 * 1000,
  )
  assert.equal((await demo.team()).teams[0].join_codes[0].code, created.code)
  await demo.revokeJoinCode(created.code)
  assert.equal((await demo.team()).teams[0].join_codes.length, 0)
  await assert.rejects(
    () => new DemoClient(() => 'crew', storage()).team(),
    (e) => e.status === 403,
  )
})

test('a crew account with no team sees the join form', async () => {
  const client = {
    mode: 'live',
    capabilities: { team: true },
    me: async () => ({
      role: 'crew',
      organization_id: null,
      organization_name: null,
      team_id: null,
      team_name: null,
      site_id: null,
    }),
  }
  const value = {
    client,
    persona: 'crew',
    principalId: null,
    revision: 0,
    refresh: () => {},
  }
  const html = renderToStaticMarkup(
    React.createElement(
      ApplicationContext.Provider,
      { value },
      React.createElement(JoinTeam),
    ),
  )
  // The first render waits for /api/me; the form itself is covered in the browser check.
  assert(text(html).includes('Loading'))
})

// ---- supervisor Overview: what needs attention, and the highest risk ----

const site = (id, extra = {}) => ({
  id,
  name: `Site ${id}`,
  lat: 0,
  lon: 0,
  risk_score: null,
  risk_level: null,
  updated_at: null,
  assigned_team: null,
  active_alerts: 0,
  top_factors: [],
  data_completeness: 1,
  model_version: 'rules-0.2',
  ...extra,
})

test('the Overview lists active alerts, notices to confirm, then absent reports to review', () => {
  const sites = [site('a'), site('b')]
  const items = attentionItems(
    sites,
    [
      {
        id: 'al-1',
        site_id: 'a',
        rule: 'lightning_stop_work',
        state: 'active',
      },
      { id: 'al-2', site_id: 'a', rule: 'flood', state: 'cleared' },
    ],
    [
      {
        id: 'r-1',
        site_id: 'b',
        category: 'on_site_fire',
        hazard_present: false,
        review_status: 'pending',
      },
      {
        id: 'r-2',
        site_id: 'b',
        category: 'wildlife',
        hazard_present: true,
        review_status: 'pending',
      },
      {
        id: 'r-3',
        site_id: 'b',
        category: 'flooding',
        hazard_present: false,
        review_status: 'confirmed',
      },
    ],
    [
      {
        notice: { id: 'n-1', hazard_label: 'downed line', radius_miles: 1 },
        site: sites[1],
      },
    ],
  )
  assert.deepEqual(
    items.map((i) => [i.title, i.detail]),
    [
      ['Lightning stop-work alert', 'Site a'],
      ['Potential hazard: Downed line', 'Site b · within 1 mi'],
      ['Reported absent: On-site fire', 'Site b'],
    ],
  )
  assert.equal(items[0].href, '#/supervisor/alerts/al-1')
})

test('highest risk ignores unscored and no-evidence sites', () => {
  const sites = [
    site('low', { risk_score: 2, risk_level: 'low' }),
    site('high', { risk_score: 7.1, risk_level: 'high' }),
    site('none', { risk_score: 0, risk_level: 'low', data_completeness: 0 }),
    site('unscored'),
    site('mid', { risk_score: 4.5, risk_level: 'moderate' }),
    site('next', { risk_score: 3, risk_level: 'moderate' }),
  ]
  assert.deepEqual(
    highestRisk(sites).map((s) => s.id),
    ['high', 'mid', 'next'],
  )
})

test('every backend evidence kind is accepted, including event_start (T050A)', async () => {
  const { readFileSync } = await import('node:fs')
  const { validateNotice } = await server.ssrLoadModule('/src/api/validate.ts')
  const python = readFileSync(
    new URL('../../backend/app/schemas/common.py', import.meta.url),
    'utf8',
  )
  const kinds = [
    ...python
      .split('class EvidenceKind')[1]
      .split('class ')[0]
      .matchAll(/= "([a-z_]+)"/g),
  ].map((m) => m[1])
  assert(kinds.includes('event_start'))
  const notice = {
    id: 'n-1',
    hazard_label: 'flooding',
    source: 'feed',
    source_ref: 'nws-1',
    lat: 25,
    lon: -80,
    radius_miles: 5,
    radius_source: 'default',
    status: 'confirmed',
    created_at: '2026-10-17T16:00:00Z',
    confirmed_by: 'auth0|s',
    confirmed_at: '2026-10-17T16:10:00Z',
    suggested_instruction: null,
    instruction: null,
    instruction_sent_at: null,
    evidence: kinds.map((kind, i) => ({
      id: `e-${i}`,
      kind,
      label: kind,
      observed_at: null,
    })),
  }
  assert.equal(validateNotice(notice).id, 'n-1')
})

test('demo supervisors add, rename, move and remove teams; one team per site', async () => {
  const demo = new DemoClient(() => 'supervisor', storage())
  const sites = await demo.sites()
  const free = sites.find((s) => !s.assigned_team)
  const taken = sites.find((s) => s.assigned_team)
  const added = await demo.createTeam({
    name: ' Night Crew ',
    site_id: free.id,
  })
  assert.equal(added.name, 'Night Crew')
  assert.equal(added.site_name, free.name)
  await assert.rejects(
    () => demo.createTeam({ name: 'Dup', site_id: taken.id }),
    (e) => e.reason === 'site_taken',
  )
  const moved = await demo.updateTeam(added.id, {
    name: 'Nights',
    site_id: null,
  })
  assert.deepEqual([moved.name, moved.site_id], ['Nights', null])
  const crewTeam = (await demo.team()).teams.find((t) => t.members.length)
  await assert.rejects(
    () => demo.deleteTeam(crewTeam.id),
    (e) => e.reason === 'has_members',
  )
  await demo.deleteTeam(added.id)
  assert(!(await demo.team()).teams.some((t) => t.id === added.id))
})

test('the live client sends team changes to the team routes', async () => {
  const calls = []
  const roster = {
    id: 'team:1',
    name: 'Nights',
    site_id: null,
    site_name: null,
    members: [],
    join_codes: [],
  }
  const api = new HttpClient(
    'http://localhost:8000',
    async () => ({ Authorization: 'Bearer t' }),
    async (url, options) => {
      calls.push(
        `${options.method} ${new URL(url).pathname} ${options.body ?? ''}`,
      )
      return options.method === 'DELETE'
        ? new Response(null, { status: 204 })
        : Response.json(roster)
    },
  )
  await api.createTeam({ name: 'Nights', site_id: null })
  await api.updateTeam('team:1', { site_id: null })
  await api.deleteTeam('team:1')
  assert.deepEqual(calls, [
    'POST /api/teams {"name":"Nights","site_id":null}',
    'PATCH /api/teams/team%3A1 {"site_id":null}',
    'DELETE /api/teams/team%3A1 ',
  ])
})

test('supervisors rename their organization (demo and live)', async () => {
  const demo = new DemoClient(() => 'supervisor', storage())
  assert.equal(
    (await demo.renameOrganization(' Gator Power ')).organization_name,
    'Gator Power',
  )
  await assert.rejects(
    () => new DemoClient(() => 'crew', storage()).renameOrganization('X'),
    (e) => e.status === 403,
  )
  const calls = []
  const api = new HttpClient(
    'http://localhost:8000',
    async () => ({ Authorization: 'Bearer t' }),
    async (url, options) => {
      calls.push(`${options.method} ${new URL(url).pathname} ${options.body}`)
      return Response.json({
        organization_id: 'org-1',
        organization_name: 'Gator Power',
        supervisors: [],
        teams: [],
      })
    },
  )
  assert.equal(
    (await api.renameOrganization('Gator Power')).organization_name,
    'Gator Power',
  )
  assert.deepEqual(calls, ['PATCH /api/organization {"name":"Gator Power"}'])
})

test('report photos load as an authorized blob from the live API', async () => {
  const calls = []
  const api = new HttpClient(
    'http://localhost:8000',
    async () => ({ Authorization: 'Bearer t' }),
    async (url, options) => {
      calls.push(
        `${options.method ?? 'GET'} ${new URL(url).pathname} ${options.headers.Authorization}`,
      )
      return new Response(new Uint8Array([0xff, 0xd8, 0xff]), {
        headers: { 'Content-Type': 'image/jpeg' },
      })
    },
  )
  const blob = await api.reportPhoto('r 1')
  assert.equal(blob.type, 'image/jpeg')
  assert.equal(blob.size, 3)
  assert.deepEqual(calls, ['GET /api/reports/r%201/photo Bearer t'])
})

test('supervisors remove a member (demo and live)', async () => {
  const demo = new DemoClient(() => 'supervisor', storage())
  const [team] = (await demo.team()).teams
  const [member] = team.members
  await demo.removeMember(team.id, member.user_id)
  const after = (await demo.team()).teams.find((t) => t.id === team.id)
  assert.ok(!after.members.some((m) => m.user_id === member.user_id))
  await assert.rejects(
    () => demo.removeMember(team.id, member.user_id),
    (e) => e.status === 404,
  )
  const calls = []
  const api = new HttpClient(
    'http://localhost:8000',
    async () => ({ Authorization: 'Bearer t' }),
    async (url, options) => {
      calls.push(`${options.method} ${new URL(url).pathname}`)
      return new Response(null, { status: 204 })
    },
  )
  await api.removeMember('team-a', 'auth0|abc')
  assert.deepEqual(calls, ['DELETE /api/teams/team-a/members/auth0%7Cabc'])
})

test('supervisor keys: create, list, revoke, and redeem (demo and live)', async () => {
  const demo = new DemoClient(() => 'supervisor', storage())
  const key = await demo.createSupervisorInvite()
  assert.match(key.code, /^[A-Z2-9]{4}-[A-Z2-9]{4}$/)
  assert.deepEqual(
    (await demo.supervisorInvites()).map((k) => k.code),
    [key.code],
  )
  await demo.revokeSupervisorInvite(key.code)
  assert.deepEqual(await demo.supervisorInvites(), [])
  await assert.rejects(
    () => new DemoClient(() => 'crew', storage()).createSupervisorInvite(),
    (e) => e.status === 403,
  )
  await assert.rejects(
    () => demo.becomeSupervisor('ABCD-2345', 'X'),
    (e) => e.status === 409,
  )
  const calls = []
  const api = new HttpClient(
    'http://localhost:8000',
    async () => ({ Authorization: 'Bearer t' }),
    async (url, options) => {
      calls.push(
        `${options.method ?? 'GET'} ${new URL(url).pathname} ${options.body ?? ''}`,
      )
      const path = new URL(url).pathname
      if (path === '/api/onboarding/supervisor')
        return Response.json({
          role: 'supervisor',
          organization_id: 'org:1',
          organization_name: 'Gulf Line Co',
          team_id: null,
          team_name: null,
          site_id: null,
        })
      if (options.method === 'DELETE')
        return new Response(null, { status: 204 })
      const invite = {
        code: 'ABCD-2345',
        created_at: '2026-10-18T00:00:00Z',
        expires_at: '2026-10-25T00:00:00Z',
      }
      return Response.json(options.method === 'POST' ? invite : [invite])
    },
  )
  assert.equal((await api.createSupervisorInvite()).code, 'ABCD-2345')
  assert.equal((await api.supervisorInvites()).length, 1)
  await api.revokeSupervisorInvite('ABCD-2345')
  const account = await api.becomeSupervisor('abcd2345', 'Gulf Line Co')
  assert.equal(account.organization_name, 'Gulf Line Co')
  assert.deepEqual(calls, [
    'POST /api/supervisor-invites ',
    'GET /api/supervisor-invites ',
    'DELETE /api/supervisor-invites/ABCD-2345 ',
    'POST /api/onboarding/supervisor {"code":"abcd2345","organization_name":"Gulf Line Co"}',
  ])
})
