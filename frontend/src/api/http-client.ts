import { validateBriefing } from './validate'
import type {
  Alert,
  CrewReport,
  ReportCreate,
  ReportReview,
  SiteSummary,
} from '../types/api'
import { ApiError, type Client, type SiteRecord } from './contracts'

export class HttpClient implements Client {
  mode = 'live' as const
  // Published T048/T053. Review, notice instructions and AI remain separate owner dependencies.
  capabilities = {
    acknowledge: true,
    reports: true,
    reviewReports: false,
    hazards: false,
    briefings: true,
  }
  private base: URL
  private headers: () => Promise<Record<string, string>>
  private fetcher: typeof fetch
  private timeout: number
  private clockOffset = 0
  constructor(
    base: string,
    headers: () => Promise<Record<string, string>>,
    fetcher: typeof fetch = fetch,
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
          409: 'Alert state changed. Refresh before acknowledging.',
          422: 'The backend rejected the submitted fields.',
          503: 'The service or database is unavailable.',
        }
        throw new ApiError(
          response.status,
          message[response.status] ??
            `Backend request failed (${response.status}).`,
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
          ? 'Request timed out. No demo data was substituted.'
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
    return this.request<SiteSummary[]>('/api/sites').then((rows) => {
      if (
        !Array.isArray(rows) ||
        rows.some(
          (r) =>
            !r ||
            typeof r.id !== 'string' ||
            !Number.isFinite(r.lat) ||
            !Number.isFinite(r.lon) ||
            !Array.isArray(r.top_factors),
        )
      )
        throw new ApiError(502, 'Invalid site-list response')
      return rows
    })
  }
  site(id: string) {
    return this.request<SiteRecord>(
      `/api/sites/${encodeURIComponent(id)}`,
    ).then((r) => {
      if (
        !r ||
        r.id !== id ||
        !Array.isArray(r.observations) ||
        !Array.isArray(r.alerts) ||
        !Array.isArray(r.notices)
      )
        throw new ApiError(502, 'Invalid site-detail response')
      return r
    })
  }
  alerts() {
    return this.request<Alert[]>('/api/alerts?state=all')
  }
  reports() {
    return this.request<CrewReport[]>('/api/reports')
  }
  acknowledge(id: string) {
    return this.request(`/api/alerts/${encodeURIComponent(id)}/acknowledge`, {
      method: 'POST',
    })
  }
  submit(input: ReportCreate, photo: File | null) {
    const body = new FormData()
    Object.entries(input).forEach(([k, v]) => {
      if (v !== undefined && v !== null) body.append(k, String(v))
    })
    if (photo) body.append('photo', photo)
    return this.request<CrewReport>('/api/reports', { method: 'POST', body })
  }
  review(id: string, input: ReportReview) {
    return this.request<CrewReport>(
      `/api/reports/${encodeURIComponent(id)}/review`,
      { method: 'POST', body: JSON.stringify(input) },
    )
  }
  confirm(id: string) {
    return this.request(`/api/hazards/${encodeURIComponent(id)}/confirm`, {
      method: 'POST',
    })
  }
  instruct(id: string, instruction: string) {
    return this.request(`/api/hazards/${encodeURIComponent(id)}/instruction`, {
      method: 'POST',
      body: JSON.stringify({ instruction }),
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
      if (error instanceof ApiError && error.status === 404) return null
      throw error
    }
  }
  async briefings() {
    const rows = await this.request<unknown>('/api/briefings')
    if (!Array.isArray(rows))
      throw new ApiError(502, 'Invalid organization briefing response')
    return rows.map((row) => validateBriefing(row))
  }
}
