// Single fetch wrapper for the FastAPI backend: base URL, timeout, typed errors,
// and the Supabase access token on every call — the backend rejects /api/* without
// one and takes the user from it (never from the body or query string).

/**
 * Base URL for API calls. "." or "/" (the nginx images) means same origin from
 * the site root — "./api/…" would resolve against the current route, so on
 * /repos/owner/name it hit /repos/owner/api/… and got index.html back.
 * Unset falls back to the local dev backend.
 */
export function resolveApiBase(raw: string | undefined): string {
  if (!raw) return 'http://localhost:8000'
  if (raw === '.' || raw === '/') return ''
  return raw.replace(/\/+$/, '')
}

export const API_BASE: string = resolveApiBase(import.meta.env.VITE_API_URL)

export type ApiErrorKind = 'network' | 'timeout' | 'http' | 'parse'

export class ApiError extends Error {
  readonly kind: ApiErrorKind
  readonly status: number | null

  constructor(kind: ApiErrorKind, message: string, status: number | null = null) {
    super(message)
    this.name = 'ApiError'
    this.kind = kind
    this.status = status
  }
}

const TOO_MANY_REQUESTS = 'Too many requests — wait a few minutes and try again.'

/**
 * HTTP 429: a per-user demo limit (backend core/rate_limit.py). The message is
 * the server's, written for the user ("…limit of 5 reviews per hour. Try again
 * in 12 minutes.") — show it as is, without a "failed:" prefix.
 */
export function isRateLimited(err: unknown): boolean {
  return err instanceof ApiError && err.status === 429
}

type TokenProvider = () => Promise<string | null>
let tokenProvider: TokenProvider | null = null
/** Last token sent — for keepalive requests on tab close, which can't await the provider. */
let lastToken: string | null = null

/** Register how to get the current access token (App wires in the Supabase session). */
export function setAuthTokenProvider(provider: TokenProvider | null): void {
  tokenProvider = provider
  lastToken = null
}

async function authHeaders(): Promise<Record<string, string>> {
  lastToken = tokenProvider ? await tokenProvider() : null
  return lastToken ? { Authorization: `Bearer ${lastToken}` } : {}
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  /** Reviews and repo analysis are slow; default is generous. */
  timeoutMs?: number
  signal?: AbortSignal
}

/** FastAPI errors look like {"detail": "..."} or {"detail": [{msg, ...}]}. */
function detailMessage(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object') return null
  const detail = (payload as { detail?: unknown }).detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const msgs = detail.map((d) => (d && typeof d === 'object' ? (d as { msg?: string }).msg : null)).filter(Boolean)
    return msgs.length ? msgs.join('; ') : null
  }
  return null
}

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, timeoutMs = 180_000, signal } = opts

  const headers: Record<string, string> = await authHeaders()
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort('timeout'), timeoutMs)
  signal?.addEventListener('abort', () => controller.abort(signal.reason), { once: true })

  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    })
  } catch (err) {
    if (controller.signal.aborted && controller.signal.reason === 'timeout') {
      throw new ApiError('timeout', `Request timed out after ${Math.round(timeoutMs / 1000)}s`)
    }
    throw new ApiError('network', err instanceof Error ? err.message : 'Network error')
  } finally {
    clearTimeout(timer)
  }

  let payload: unknown = null
  const text = await res.text()
  if (text) {
    try { payload = JSON.parse(text) } catch {
      if (res.ok) throw new ApiError('parse', 'Server returned invalid JSON', res.status)
    }
  }

  if (!res.ok) {
    const fallback = res.status === 429 ? TOO_MANY_REQUESTS : `Request failed (${res.status})`
    throw new ApiError('http', detailMessage(payload) ?? fallback, res.status)
  }
  return payload as T
}

/**
 * Fire-and-forget POST that outlives the page (tab close). Unlike sendBeacon it
 * can carry the Authorization header; uses the token from the last request.
 */
export function sendKeepalive(path: string): void {
  try {
    void fetch(`${API_BASE}${path}`, {
      method: 'POST',
      keepalive: true,
      headers: lastToken ? { Authorization: `Bearer ${lastToken}` } : {},
    }).catch(() => {})
  } catch { /* best effort — the page is going away */ }
}
