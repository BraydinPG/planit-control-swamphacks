/** Acceptance orchestration only. App requests use its existing HttpClient. */
export const REQUIRED_ROUTES = [
  ['/api/sites', 'get'],
  ['/api/sites/{site_id}', 'get'],
  ['/api/alerts', 'get'],
  ['/api/alerts/{alert_id}/acknowledge', 'post'],
  ['/api/reports', 'get'],
  ['/api/reports', 'post'],
  ['/api/reports/{report_id}/review', 'post'],
  ['/api/hazards/{hazard_id}/confirm', 'post'],
  ['/api/hazards/{hazard_id}/instruction', 'post'],
  ['/api/sites/{site_id}/briefing', 'get'],
  ['/api/briefings', 'get'],
]

export function origin(value) {
  const url = new URL(value)
  if (
    !['http:', 'https:'].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.pathname !== '/' ||
    url.search ||
    url.hash
  )
    throw new Error('Use an HTTP(S) origin without credentials, path or query')
  if (!['localhost', '127.0.0.1', '[::1]'].includes(url.hostname))
    throw new Error(
      'This local acceptance runner accepts loopback services only',
    )
  return url.origin
}

export function routeInventory(paths) {
  // Compare path shape; parameter names belong to the canonical API, not the test.
  const normalize = (s) => s.replace(/\{[^}]+\}/g, '{}')
  return REQUIRED_ROUTES.map(([path, method]) => ({
    path,
    method,
    available: Object.entries(paths ?? {}).some(
      ([candidate, operations]) =>
        normalize(candidate) === normalize(path) && Boolean(operations[method]),
    ),
  }))
}

export function tokenIdentity(token, role, config, now = Date.now()) {
  try {
    if (typeof token !== 'string' || token.length > 20000 || /\s/.test(token))
      throw new Error()
    const parts = token.split('.')
    if (parts.length !== 3 || !parts[2]) throw new Error()
    const header = JSON.parse(Buffer.from(parts[0], 'base64url'))
    const claims = JSON.parse(Buffer.from(parts[1], 'base64url'))
    const rawRoles = claims[config.rolesClaim]
    const assigned = Array.isArray(rawRoles)
      ? rawRoles
          .filter((r) => typeof r === 'string')
          .map((r) => r.trim().toLowerCase())
      : null
    const audiences = Array.isArray(claims.aud) ? claims.aud : [claims.aud]
    if (
      header.alg !== 'RS256' ||
      typeof claims.sub !== 'string' ||
      !claims.sub ||
      claims.iss !== config.issuer ||
      !audiences.includes(config.audience) ||
      !Number.isFinite(claims.exp) ||
      claims.exp * 1000 <= now + 30000 ||
      (claims.nbf && claims.nbf * 1000 > now) ||
      !Array.isArray(assigned) ||
      !assigned.includes(role) ||
      (role === 'crew' && assigned.includes('supervisor'))
    )
      throw new Error()
    // This inspects claims; only the real backend validates the signature/permissions.
    return { subject: claims.sub, role }
  } catch {
    throw new Error(
      'Access token claims are missing, expired or incompatible; use the real Auth0 access token for that role',
    )
  }
}

export async function runAcceptance({
  request,
  makeClient,
  accounts = {},
  config,
  readiness,
  inventory = [],
  allowAcknowledge = false,
  alertId,
  evidenceType = 'real_http',
}) {
  const checks = []
  const snapshots = {
    sites: [],
    details: [],
    alerts: [],
    reports: [],
    briefings: [],
  }
  const sessions = {}
  const add = (id, status, detail) => checks.push({ id, status, detail })
  for (const [id, path, options] of [
    ['anonymous_sites', '/api/sites', {}],
    ['anonymous_alerts', '/api/alerts?state=all', {}],
    [
      'anonymous_acknowledgement',
      '/api/alerts/__planit_denial_probe__/acknowledge',
      { method: 'POST' },
    ],
    [
      'development_header',
      '/api/sites',
      { headers: { 'X-Dev-Role': 'supervisor' } },
    ],
  ]) {
    const result = await request(path, options)
    add(
      id,
      result.status === 401
        ? 'passed'
        : result.status === 0
          ? 'blocked'
          : 'failed',
      `HTTP ${result.status}; expected 401`,
    )
  }
  const invalid = await request('/api/sites', {
    headers: { Authorization: 'Bearer not-a-valid-token' },
  })
  add(
    'invalid_token',
    invalid.status === 401
      ? 'passed'
      : invalid.status === 503 || invalid.status === 0
        ? 'blocked'
        : 'failed',
    invalid.status === 503
      ? 'Auth service unavailable; token validation not verified'
      : `HTTP ${invalid.status}; expected 401`,
  )
  let guardsPassed = checks.every((c) => c.status === 'passed')
  const reportsPublished = inventory.some(
    (r) => r.path === '/api/reports' && r.method === 'get' && r.available,
  )
  if (reportsPublished) {
    const response = await request('/api/reports')
    guardsPassed = guardsPassed && response.status === 401
    add(
      'anonymous_reports',
      response.status === 401
        ? 'passed'
        : response.status === 0
          ? 'blocked'
          : 'failed',
      `HTTP ${response.status}; expected 401`,
    )
  } else
    add(
      'anonymous_reports',
      'blocked',
      'Report listing not published by running backend',
    )
  // A missing optional route is blocked, not permission proof. Every published
  // protected route must reject anonymous requests before any account token is used.
  for (const [id, template, path, method, body] of [
    [
      'review',
      '/api/reports/{report_id}/review',
      '/api/reports/__planit_denial_probe__/review',
      'POST',
      { decision: 'rejected' },
    ],
    [
      'confirm',
      '/api/hazards/{hazard_id}/confirm',
      '/api/hazards/__planit_denial_probe__/confirm',
      'POST',
      null,
    ],
    [
      'instruction',
      '/api/hazards/{hazard_id}/instruction',
      '/api/hazards/__planit_denial_probe__/instruction',
      'POST',
      { instruction: 'Denied probe only' },
    ],
    [
      'site_briefing',
      '/api/sites/{site_id}/briefing',
      '/api/sites/__planit_denial_probe__/briefing',
      'GET',
      null,
    ],
    ['organization_briefings', '/api/briefings', '/api/briefings', 'GET', null],
  ]) {
    if (
      !inventory.some(
        (r) =>
          r.path === template &&
          r.method === method.toLowerCase() &&
          r.available,
      )
    ) {
      add(
        `anonymous_${id}`,
        'blocked',
        'Route not published; no missing-route denial counted as permission proof',
      )
      continue
    }
    const response = await request(path, {
      method,
      ...(body
        ? {
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
          }
        : {}),
    })
    guardsPassed = guardsPassed && response.status === 401
    add(
      `anonymous_${id}`,
      response.status === 401
        ? 'passed'
        : response.status === 0 || response.status === 503
          ? 'blocked'
          : 'failed',
      `HTTP ${response.status}; expected 401`,
    )
  }
  const configured =
    readiness?.auth?.configured &&
    !readiness.auth.dev_auth_bypass &&
    readiness.auth.domain_matches_spa &&
    readiness.auth.audience_matches_spa
  for (const role of ['crew', 'supervisor']) {
    if (!configured || !guardsPassed) {
      add(
        `${role}_session`,
        'blocked',
        'Matching Auth0 settings, disabled bypass and actual anonymous rejection are required',
      )
      continue
    }
    if (!accounts[role]) {
      add(
        `${role}_session`,
        'blocked',
        'Real account access token not supplied through private stdin',
      )
      continue
    }
    try {
      const identity = tokenIdentity(accounts[role], role, config)
      const client = makeClient(accounts[role])
      const sites = await client.sites()
      if (!sites.length) {
        add(
          `${role}_sites`,
          'blocked',
          'No authorized site returned; check membership and seed',
        )
        continue
      }
      if (role === 'crew' && sites.length > 1) {
        add(
          'crew_site_scope',
          'failed',
          'One-team crew unexpectedly received more than one assigned site',
        )
        continue
      }
      const detail = await client.site(sites[0].id)
      const alerts = await client.alerts()
      if (
        !Array.isArray(alerts) ||
        (role === 'crew' &&
          alerts.some((a) => !sites.some((s) => s.id === a.site_id)))
      )
        throw new Error()
      snapshots.sites.push(...sites)
      snapshots.details.push(detail)
      snapshots.alerts.push(...alerts)
      if (reportsPublished) {
        const reports = await client.reports()
        if (
          !Array.isArray(reports) ||
          (role === 'crew' &&
            reports.some((r) => !sites.some((s) => s.id === r.site_id)))
        )
          throw new Error()
        snapshots.reports.push(...reports)
        add(
          `${role}_report_list`,
          'passed',
          `${reports.length} authorized report(s) read; no report write performed`,
        )
      }
      sessions[role] = { client, identity, sites, alerts }
      add(
        `${role}_sites`,
        'passed',
        `${sites.length} authorized site(s), detail and ${alerts.length} alert(s); no payload or subject retained in report`,
      )
      add(
        `${role}_account`,
        'passed',
        'Expected access-token claims inspected and reads accepted by backend; browser sign-in still requires separate verification',
      )
    } catch (error) {
      add(
        `${role}_sites`,
        'failed',
        Number.isInteger(error?.status)
          ? `HTTP ${error.status}; no fixtures substituted`
          : 'Token, response contract or authorized read failed; details suppressed',
      )
    }
  }
  // T067 stored reads are independently reported; absence is not an API outage.
  for (const role of ['crew', 'supervisor']) {
    const session = sessions[role]
    if (!session) {
      add(
        `${role}_stored_briefings`,
        'blocked',
        'Authorized account reads required',
      )
      continue
    }
    for (const [id, template, load] of [
      [
        'site_briefing',
        '/api/sites/{site_id}/briefing',
        () => session.client.briefing(session.sites[0].id),
      ],
      [
        'organization_briefings',
        '/api/briefings',
        () => session.client.briefings(),
      ],
    ]) {
      if (
        !inventory.some(
          (r) => r.path === template && r.method === 'get' && r.available,
        )
      ) {
        add(`${role}_${id}`, 'blocked', 'Stored briefing route not published')
        continue
      }
      try {
        const value = await load()
        const rows = Array.isArray(value) ? value : value ? [value] : []
        snapshots.briefings.push(...rows)
        add(
          `${role}_${id}`,
          'passed',
          rows.length
            ? `${rows.length} stored briefing(s) validated; content omitted`
            : 'No stored briefing yet; scheduled empty state; no generation request sent',
        )
      } catch (error) {
        add(
          `${role}_${id}`,
          'failed',
          Number.isInteger(error?.status)
            ? `HTTP ${error.status}; no fixtures substituted`
            : 'Stored response validation failed; private details omitted',
        )
      }
    }
  }
  const crew = sessions.crew,
    supervisor = sessions.supervisor
  if (crew && supervisor) {
    const unrelated = supervisor.sites.find(
      (s) => !crew.sites.some((c) => c.id === s.id),
    )
    if (!unrelated)
      add(
        'crew_unrelated_site',
        'blocked',
        'Supervisor must have another real site for a meaningful scope check',
      )
    else {
      try {
        await crew.client.site(unrelated.id)
        add(
          'crew_unrelated_site',
          'failed',
          'Crew read an unrelated existing site',
        )
      } catch (error) {
        add(
          'crew_unrelated_site',
          error?.status === 403 ? 'passed' : 'failed',
          `HTTP ${error?.status ?? 0}; expected 403 for another existing site`,
        )
      }
    }
    add(
      'supervisor_visibility',
      crew.sites.every((c) => supervisor.sites.some((s) => s.id === c.id))
        ? 'passed'
        : 'failed',
      'Compared actual authorized site identities in memory',
    )
    const review = inventory.find(
      (r) => r.path === '/api/reports/{report_id}/review',
    )
    if (review?.available) {
      const response = await request(
        '/api/reports/__planit_denial_probe__/review',
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${accounts.crew}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ decision: 'rejected' }),
        },
      )
      add(
        'crew_review_denied',
        response.status === 403 ? 'passed' : 'failed',
        `HTTP ${response.status}; expected supervisor-only denial before record lookup`,
      )
    } else
      add(
        'crew_review_denied',
        'blocked',
        'Report review endpoint not published; 404 is not proof of role enforcement',
      )
  } else add('cross_role_scope', 'blocked', 'Both real account reads required')
  if (crew)
    for (const [id, template, path, body] of [
      [
        'confirm',
        '/api/hazards/{hazard_id}/confirm',
        '/api/hazards/__planit_denial_probe__/confirm',
        null,
      ],
      [
        'instruction',
        '/api/hazards/{hazard_id}/instruction',
        '/api/hazards/__planit_denial_probe__/instruction',
        { instruction: 'Denied probe only' },
      ],
    ]) {
      if (
        !inventory.some(
          (r) => r.path === template && r.method === 'post' && r.available,
        )
      ) {
        add(
          `crew_${id}_denied`,
          'blocked',
          'Route not published; no 404 role proof',
        )
        continue
      }
      const response = await request(path, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${accounts.crew}`,
          ...(body ? { 'Content-Type': 'application/json' } : {}),
        },
        ...(body ? { body: JSON.stringify(body) } : {}),
      })
      add(
        `crew_${id}_denied`,
        response.status === 403 ? 'passed' : 'failed',
        `HTTP ${response.status}; expected supervisor-only denial before record lookup`,
      )
    }
  if (!allowAcknowledge)
    add(
      'acknowledgement_persistence',
      'not_run',
      'Read-only default; requires --acknowledge and a deliberately selected test alert ID in stdin',
    )
  else if (
    !crew ||
    !supervisor ||
    readiness?.database?.status !== 'passed' ||
    !guardsPassed ||
    checks.some((c) => c.status === 'failed')
  )
    add(
      'acknowledgement_persistence',
      'blocked',
      'Real account reads, read-only remote database/seed verification and permission checks required before this write',
    )
  else {
    const before = crew.alerts.find(
      (a) =>
        a.id === alertId &&
        a.state === 'active' &&
        a.simulated === true &&
        crew.sites.some((s) => s.id === a.site_id),
    )
    if (!before)
      add(
        'acknowledgement_persistence',
        'blocked',
        'Selected test alert must be active, explicitly simulated and belong to the real crew assignment; no automatic alert selection',
      )
    else {
      try {
        await crew.client.acknowledge(alertId)
        // New client means no local shared-state object can masquerade as server persistence.
        const reloaded = await makeClient(accounts.crew).alerts()
        const alert = reloaded.find((a) => a.id === alertId)
        const ack = alert?.acknowledgements.find(
          (a) => a.user_id === crew.identity.subject,
        )
        const observer = (await makeClient(accounts.supervisor).alerts()).find(
          (a) => a.id === alertId,
        )
        if (
          !ack?.id ||
          !Number.isFinite(Date.parse(ack.acknowledged_at)) ||
          !observer?.acknowledgements.some(
            (a) =>
              a.id === ack.id &&
              a.alert_id === ack.alert_id &&
              a.user_id === ack.user_id &&
              a.acknowledged_at === ack.acknowledged_at,
          )
        )
          throw new Error()
        add(
          'acknowledgement_persistence',
          'passed',
          'Server acknowledgement/time survived new crew client and was visible to supervisor; no local timer or state mutation',
        )
      } catch {
        add(
          'acknowledgement_persistence',
          'failed',
          'Acknowledgement or independent server read-back failed; no simulated persistence substituted',
        )
      }
    }
  }
  add(
    'real_browser_roles',
    'not_run',
    'Existing Auth0 login/logout, both role screens and reload must also be verified in browser; tokens are not a browser-login substitute',
  )
  const status = checks.some((c) => c.status === 'failed')
    ? 'failed'
    : checks.some((c) => c.status === 'blocked' || c.status === 'not_run')
      ? 'partial'
      : 'passed'
  return {
    report: {
      status,
      evidence_type: evidenceType,
      live_acceptance_complete: false,
      checks,
      task_checkboxes_changed: [],
    },
    snapshots,
  }
}
