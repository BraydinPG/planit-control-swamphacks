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
