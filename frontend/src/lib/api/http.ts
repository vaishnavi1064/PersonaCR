// Single fetch wrapper for the FastAPI backend: base URL, timeout, typed errors,
// and the hook where the Supabase access token gets attached (backend auth slice).

export const API_BASE: string = import.meta.env.VITE_API_URL || 'http://localhost:8000'

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

type TokenProvider = () => Promise<string | null>
let tokenProvider: TokenProvider | null = null

/** Register how to get the current access token. Wired up when backend auth lands. */
export function setAuthTokenProvider(provider: TokenProvider | null): void {
  tokenProvider = provider
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

  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const token = tokenProvider ? await tokenProvider() : null
  if (token) headers.Authorization = `Bearer ${token}`

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
    throw new ApiError('http', detailMessage(payload) ?? `Request failed (${res.status})`, res.status)
  }
  return payload as T
}
