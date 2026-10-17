import {
  validateAlert,
  validateSiteDetail,
  validateSiteSummary,
  validateUniqueRows,
} from './live-read-validation'
import {
  validateAccount,
  validateBriefing,
  validateJoinCode,
  validateReport,
  validateNotice,
  validateConfirmation,
  validateTeamRoster,
  validateTeams,
} from './validate'
import type {
  ReportCreate,
  ReportReview,
  TeamCreate,
  TeamUpdate,
} from '../types/api'
import { ApiError, type Client } from './contracts'

export class HttpClient implements Client {
  mode = 'live' as const
  // Published T048/T053/T054/T054A and T058A. Server permissions remain authoritative.
  capabilities = {
    acknowledge: true,
    reports: true,
    reviewReports: true,
    hazards: true,
    briefings: true,
    team: true,
  }
  private base: URL
  private headers: () => Promise<Record<string, string>>
  private fetcher: typeof fetch
  private timeout: number
  private clockOffset = 0
  constructor(
    base: string,
    headers: () => Promise<Record<string, string>>,
    // Wrapped, not bare `fetch`: calling it as `this.fetcher(...)` would throw "Illegal
    // invocation" in browsers, which surfaced as "Network request failed".
    fetcher: typeof fetch = (input, init) => fetch(input, init),
    timeout = 12000,
  ) {
    this.headers = headers
    this.fetcher = fetcher
    this.timeout = timeout
    this.base = new URL(base)
    if (
      this.base.username ||
      this.base.password ||
      !['http:', 'https:'].includes(this.base.protocol)
    )
      throw new ApiError(0, 'Invalid API destination')
    if (
      this.base.protocol === 'http:' &&
      !['localhost', '127.0.0.1', '[::1]'].includes(this.base.hostname)
    )
      throw new ApiError(0, 'HTTPS is required for non-local APIs')
  }
  async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const controller = new AbortController()
    const deadline = setTimeout(() => controller.abort(), this.timeout)
    try {
      const headers = await new Promise<Record<string, string>>(
        (resolve, reject) => {
          const abort = () =>
            reject(
              new ApiError(0, 'Session acquisition timed out. Sign in again.'),
            )
          controller.signal.addEventListener('abort', abort, { once: true })
          Promise.resolve()
            .then(() => this.headers())
            .then(resolve, () =>
              reject(
                new ApiError(
                  401,
                  'Auth0 token acquisition failed. Sign in again.',
                ),
              ),
            )
            .finally(() =>
              controller.signal.removeEventListener('abort', abort),
            )
        },
      )
      if (!headers.Authorization?.startsWith('Bearer '))
        throw new ApiError(
          401,
          'A valid Auth0 session is required. Sign in again.',
        )
      const started = Date.now()
      const response = await this.fetcher(new URL(path, this.base), {
        ...options,
        signal: controller.signal,
        credentials: 'omit',
        redirect: 'error',
        headers: {
          ...headers,
          ...(options.body && !(options.body instanceof FormData)
            ? { 'Content-Type': 'application/json' }
            : {}),
        },
      })
      const serverTime = Date.parse(response.headers.get('Date') ?? '')
      if (Number.isFinite(serverTime))
        this.clockOffset = serverTime + (Date.now() - started) / 2 - Date.now()
      if (!response.ok) {
        const message: Record<number, string> = {
          401: 'Session expired or token rejected. Sign in again.',
          403: 'Permission denied by the backend.',
          404: 'This endpoint or record is unavailable.',
          409: 'The server state changed or this operation was already completed. Refresh before retrying.',
          422: 'The backend rejected the submitted fields.',
          503: 'The service or database is unavailable.',
        }
        throw new ApiError(
          response.status,
          message[response.status] ??
            `Backend request failed (${response.status}).`,
          await serverReason(response),
        )
      }
      if (response.status === 204) return undefined as T
      try {
        return (await response.json()) as T
      } catch {
        throw new ApiError(502, 'Backend response was not valid JSON.')
      }
    } catch (error) {
      if (error instanceof ApiError) throw error
      throw new ApiError(
        0,
        controller.signal.aborted
          ? 'Request timed out. Outcome unknown; refresh before retrying. No demo data was substituted.'
          : 'Network request failed. No demo data was substituted.',
      )
    } finally {
      clearTimeout(deadline)
    }
  }
  now() {
    return Date.now() + this.clockOffset
  }
  sites() {
    return this.request<unknown>('/api/sites').then((rows) =>
      validateUniqueRows(rows, validateSiteSummary, 'site-list'),
    )
  }
  site(id: string) {
    return this.request<unknown>(`/api/sites/${encodeURIComponent(id)}`).then(
      (value) => validateSiteDetail(value, id),
    )
  }
  alerts() {
    return this.request<unknown>('/api/alerts?state=all').then((rows) =>
      validateUniqueRows(rows, validateAlert, 'alert-list'),
    )
  }
  reports() {
    return this.request<unknown>('/api/reports').then((rows) => {
      if (!Array.isArray(rows))
        throw new ApiError(502, 'Invalid report-list response')
      return rows.map((row) => validateReport(row))
    })
  }
  acknowledge(id: string) {
    return this.request(`/api/alerts/${encodeURIComponent(id)}/acknowledge`, {
      method: 'POST',
    }).then((value) => {
      const alert = validateAlert(value, id)
      if (!alert.acknowledgements.length)
        throw new ApiError(
          502,
          'Acknowledgement was not present in the server response. Refresh before retrying.',
        )
      return alert
    })
  }
  submit(input: ReportCreate, photo: File | null) {
    const body = new FormData()
    Object.entries(input).forEach(([k, v]) => {
      if (v !== undefined && v !== null) body.append(k, String(v))
    })
    if (photo) body.append('photo', photo)
    return this.request<unknown>('/api/reports', { method: 'POST', body }).then(
      (value) => {
        const report = validateReport(value)
        if (
          report.site_id !== input.site_id ||
          report.hazard_present !== input.hazard_present ||
          report.category !== input.category
        )
          throw new ApiError(
            502,
            'Report response does not match the submitted fields. Refresh before retrying.',
          )
        return report
      },
    )
  }
  review(id: string, input: ReportReview) {
    return this.request<unknown>(
      `/api/reports/${encodeURIComponent(id)}/review`,
      { method: 'POST', body: JSON.stringify(input) },
    ).then((value) => {
      const report = validateReport(value, id)
      if (
        report.hazard_present ||
        report.review_status !== input.decision ||
        !report.reviewed_by ||
        !report.reviewed_at
      )
        throw new ApiError(
          502,
          'Invalid absent-report review response. Refresh before retrying.',
        )
      return report
    })
  }
  confirm(id: string) {
    return this.request<unknown>(
      `/api/hazards/${encodeURIComponent(id)}/confirm`,
      {
        method: 'POST',
      },
    ).then((value) => validateConfirmation(value, id))
  }
  async instruct(id: string, instruction: string) {
    const finalText = instruction.trim()
    if (!finalText || finalText.length > 500)
      throw new ApiError(
        422,
        'Enter an instruction of 1-500 nonblank characters',
      )
    return this.request<unknown>(
      `/api/hazards/${encodeURIComponent(id)}/instruction`,
      {
        method: 'POST',
        body: JSON.stringify({ instruction: finalText }),
      },
    ).then((value) => {
      const notice = validateNotice(value, id)
      if (
        notice.status !== 'confirmed' ||
        !notice.instruction_sent_at ||
        notice.instruction !== finalText
      )
        throw new ApiError(
          502,
          'Invalid instruction delivery response. Refresh before retrying.',
        )
      return notice
    })
  }
  async briefing(id: string) {
    try {
      return validateBriefing(
        await this.request<unknown>(
          `/api/sites/${encodeURIComponent(id)}/briefing`,
        ),
        id,
      )
    } catch (error) {
      // A plain "not generated yet" 404 is the normal empty state. Any other reason
      // (no team, no supervisor, ...) is rethrown so the view can show it.
      if (
        error instanceof ApiError &&
        error.status === 404 &&
        (!error.reason || error.reason === 'not_generated')
      )
        return null
      throw error
    }
  }
  async briefings() {
    const rows = await this.request<unknown>('/api/briefings')
    if (!Array.isArray(rows))
      throw new ApiError(502, 'Invalid organization briefing response')
    return rows.map((row) => validateBriefing(row))
  }
  me() {
    return this.request<unknown>('/api/me').then(validateAccount)
  }
  team() {
    return this.request<unknown>('/api/team').then(validateTeams)
  }
  createJoinCode(teamId: string) {
    return this.request<unknown>(
      `/api/teams/${encodeURIComponent(teamId)}/join-codes`,
      { method: 'POST' },
    ).then(validateJoinCode)
  }
  async revokeJoinCode(code: string) {
    await this.request(`/api/join-codes/${encodeURIComponent(code)}`, {
      method: 'DELETE',
    })
  }
  join(code: string) {
    return this.request<unknown>('/api/join', {
      method: 'POST',
      body: JSON.stringify({ code }),
    }).then(validateAccount)
  }
  createTeam(input: TeamCreate) {
    return this.request<unknown>('/api/teams', {
      method: 'POST',
      body: JSON.stringify(input),
    }).then(validateTeamRoster)
  }
  updateTeam(id: string, input: TeamUpdate) {
    return this.request<unknown>(`/api/teams/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify(input),
    }).then(validateTeamRoster)
  }
  async deleteTeam(id: string) {
    await this.request(`/api/teams/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    })
  }
}

/** The backend's `{detail: {reason, message}}` explanation, when it sent one. */
async function serverReason(
  response: Response,
): Promise<{ reason: string; detail: string } | undefined> {
  try {
    const body: unknown = await response.json()
    const detail =
      body && typeof body === 'object' && 'detail' in body ? body.detail : null
    if (
      detail &&
      typeof detail === 'object' &&
      'reason' in detail &&
      'message' in detail &&
      typeof detail.reason === 'string' &&
      typeof detail.message === 'string'
    )
      return { reason: detail.reason, detail: detail.message }
  } catch {
    // No JSON body: keep the generic status message.
  }
  return undefined
}
