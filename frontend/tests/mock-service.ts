/** Test-only HTTP state. No production import, identity provider, API or database. */
import detailJSON from '../src/fixtures/site-detail.json'
import sitesJSON from '../src/fixtures/sites.json'
import reportsJSON from '../src/fixtures/reports.json'
import alertsJSON from '../src/fixtures/alerts.json'
import type {
  CrewReport,
  HazardNotice,
  HazardConfirmResponse,
  SiteDetail,
} from '../src/types/api'

export function createMockService() {
  const assigned = sitesJSON[0].id
  const service = {
    reports: structuredClone(reportsJSON) as CrewReport[],
    notices: structuredClone(detailJSON.notices) as HazardNotice[],
    alerts: structuredClone(alertsJSON),
    draft:
      'Mocked Gemini draft: request qualified inspection before proceeding.' as
        string | null,
    denyMutation: false,
    mutationStatus: 200,
    conflict: false,
    confirmed: false,
    detail(role: string, id = assigned): SiteDetail {
      const summary = sitesJSON.find((s) => s.id === id)!
      const detail =
        id === assigned
          ? structuredClone(detailJSON)
          : {
              ...summary,
              location_type: 'power_plant',
              source: 'Mocked HTTP fixture',
              region: null,
              observations: [],
              score: null,
              risk_score: null,
              risk_level: null,
              updated_at: null,
              model_version: 'unscored',
              data_completeness: 0,
              top_factors: [],
              event_outlook: null,
            }
      // A deliberately supplied server response, not a frontend score calculation.
      return {
        ...detail,
        ...(service.confirmed && id === assigned
          ? {
              risk_score: 8.25,
              risk_level: 'critical',
              model_version: 'mock-server-score',
              updated_at: '2026-10-17T20:00:00Z',
              score: {
                ...detailJSON.score,
                risk_score: 8.25,
                risk_level: 'critical',
                model_version: 'mock-server-score',
                created_at: '2026-10-17T20:00:00Z',
              },
            }
          : {}),
        alerts: structuredClone(service.alerts.filter((a) => a.site_id === id)),
        reports: structuredClone(
          service.reports.filter((r) => r.site_id === id),
        ),
        notices:
          id === assigned
            ? structuredClone(service.notices).map((n) => ({
                ...n,
                suggested_instruction:
                  n.confirmed_by === `mock-${role}`
                    ? n.suggested_instruction
                    : null,
              }))
            : [],
      } as SiteDetail
    },
    async request(
      url: URL,
      options: RequestInit | undefined,
      role: string,
    ): Promise<Response> {
      const method = options?.method ?? 'GET'
      const parts = url.pathname.split('/').map(decodeURIComponent)
      const id = parts[3]
      if (method === 'POST' && service.mutationStatus !== 200)
        return new Response('', { status: service.mutationStatus })
      if (method === 'POST' && service.denyMutation)
        return new Response('', { status: 403 })
      if (method === 'POST' && service.conflict)
        return new Response('', { status: 409 })
      if (url.pathname === '/api/sites')
        return Response.json(role === 'crew' ? [sitesJSON[0]] : sitesJSON)
      if (url.pathname === '/api/reports' && method === 'GET')
        return Response.json(
          service.reports.filter(
            (r) => role !== 'crew' || r.site_id === assigned,
          ),
        )
      if (url.pathname === '/api/alerts')
        return Response.json(
          service.alerts.filter(
            (a) => role !== 'crew' || a.site_id === assigned,
          ),
        )
      if (parts[2] === 'alerts' && parts[4] === 'acknowledge') {
        const alert = service.alerts.find((a) => a.id === id)
        if (!alert) return new Response('', { status: 404 })
        if (alert.state !== 'active') return new Response('', { status: 409 })
        if (!alert.acknowledgements.some((a) => a.user_id === `mock-${role}`))
          alert.acknowledgements.push({
            id: 'mock-ack',
            alert_id: id,
            user_id: `mock-${role}`,
            acknowledged_at: new Date().toISOString(),
          })
        return Response.json(alert)
      }
      if (url.pathname === '/api/reports' && method === 'POST') {
        const form = options?.body as FormData
        if (!(form instanceof FormData))
          return new Response('', { status: 422 })
        const site = sitesJSON.find((s) => s.id === form.get('site_id'))
        if (!site) return new Response('', { status: 404 })
        if (role === 'crew' && site.id !== assigned)
          return new Response('', { status: 403 })
        const present = form.get('hazard_present') === 'true'
        if (present && !form.get('photo'))
          return new Response('', { status: 422 })
        const report: CrewReport = {
          id: `mock-report-${service.reports.length}`,
          site_id: site.id,
          organization_id: 'mock-org',
          team_id: 'mock-team',
          reporter_id: `mock-${role}`,
          category: String(form.get('category')) as CrewReport['category'],
          hazard_present: present,
          lat: Number(form.get('lat')),
          lon: Number(form.get('lon')),
          note: form.get('note') as string | null,
          photo_url: present ? 'private:mock-photo-reference' : null,
          review_status: 'pending',
          reviewed_by: null,
          reviewed_at: null,
          confirmed_category: null,
          confirmed_severity: null,
          // T053A: the backend defaults to `site` and computes the site distance.
          location_source: (form.get('location_source') ??
            'site') as CrewReport['location_source'],
          location_accuracy_m: form.get('location_accuracy_m')
            ? Number(form.get('location_accuracy_m'))
            : null,
          site_distance_miles: null,
          enrichment: null,
          notice_id: present ? `mock-notice-${service.reports.length}` : null,
          created_at: '2026-10-17T19:00:00Z',
        }
        service.reports.unshift(report)
        if (report.notice_id)
          service.notices.unshift({
            id: report.notice_id,
            hazard_label: 'broken pole / downed line',
            source: 'crew_report',
            source_ref: report.id,
            lat: report.lat,
            lon: report.lon,
            radius_miles: 1,
            radius_source: 'default',
            status: 'potential',
            confirmed_by: null,
            confirmed_at: null,
            created_at: report.created_at,
            suggested_instruction: null,
            instruction: null,
            instruction_sent_at: null,
            evidence: [
              {
                id: report.id,
                kind: 'report',
                label: 'Mock HTTP report evidence',
                observed_at: report.created_at,
              },
            ],
          })
        return Response.json(report, { status: 201 })
      }
      if (parts[2] === 'reports' && parts[4] === 'review') {
        if (role !== 'supervisor') return new Response('', { status: 403 })
        const report = service.reports.find((r) => r.id === id)
        if (!report) return new Response('', { status: 404 })
        if (report.organization_id !== 'mock-org')
          return new Response('', { status: 403 })
        if (report.hazard_present || report.review_status !== 'pending')
          return new Response('', { status: 409 })
        const input = JSON.parse(String(options?.body))
        report.review_status = input.decision
        report.reviewed_by = 'mock-supervisor'
        report.reviewed_at = '2026-10-17T20:00:00Z'
        report.confirmed_category =
          input.decision === 'confirmed'
            ? (input.category ?? report.category)
            : null
        report.confirmed_severity =
          input.decision === 'confirmed' ? (input.severity ?? null) : null
        return Response.json(report)
      }
      if (parts[2] === 'hazards') {
        if (role !== 'supervisor') return new Response('', { status: 403 })
        const notice = service.notices.find((n) => n.id === id)
        if (!notice) return new Response('', { status: 404 })
        if (parts[4] === 'confirm') {
          if (notice.status !== 'potential')
            return new Response('', { status: 409 })
          notice.status = 'confirmed'
          notice.confirmed_by = 'mock-supervisor'
          notice.confirmed_at = '2026-10-17T20:00:00Z'
          notice.suggested_instruction = service.draft
          const report = service.reports.find((r) => r.id === notice.source_ref)
          if (report) {
            report.review_status = 'confirmed'
            report.reviewed_by = notice.confirmed_by
            report.reviewed_at = notice.confirmed_at
            report.confirmed_category = report.category
          }
          service.confirmed = true
          const response: HazardConfirmResponse = {
            notice,
            suggested_instruction: service.draft,
            generated_by: service.draft ? 'gemini' : null,
          }
          return Response.json(response)
        }
        if (parts[4] === 'instruction') {
          if (notice.confirmed_by !== 'mock-supervisor')
            return new Response('', { status: 403 })
          if (notice.status !== 'confirmed' || notice.instruction_sent_at)
            return new Response('', { status: 409 })
          const text = String(
            JSON.parse(String(options?.body)).instruction,
          ).trim()
          if (!text || text.length > 500)
            return new Response('', { status: 422 })
          notice.instruction = text
          notice.instruction_sent_at = '2026-10-17T20:01:00Z'
          return Response.json(notice)
        }
      }
      if (parts[2] === 'sites') {
        if (!sitesJSON.some((s) => s.id === id))
          return new Response('', { status: 404 })
        if (role === 'crew' && id !== assigned)
          return new Response('', { status: 403 })
        return Response.json(service.detail(role, id))
      }
      return new Response('', { status: 404 })
    },
  }
  return service
}
