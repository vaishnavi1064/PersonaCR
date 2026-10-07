import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../db', () => ({ saveRepo: vi.fn() }))

import { askQuestion } from './chats'
import { cleanupGuestOnUnload } from './guest'
import { ApiError, isRateLimited, request, resolveApiBase, setAuthTokenProvider } from './http'
import { listRepos, startAnalyzeJob } from './repos'

const USER = '3f2b8c1e-9a4d-4e57-8b1a-2c6d9e0f1a2b'

let fetchMock: ReturnType<typeof vi.fn>

function lastCall(): { url: string; init: RequestInit; headers: Record<string, string>; body: Record<string, unknown> | null } {
  const [url, init = {}] = fetchMock.mock.calls.at(-1) as [string, RequestInit?]
  const body = typeof init.body === 'string' ? JSON.parse(init.body) : null
  return { url, init, headers: (init.headers ?? {}) as Record<string, string>, body }
}

beforeEach(() => {
  fetchMock = vi.fn(async () => new Response(JSON.stringify({ repos: [], job_id: 'j', answer: 'a', analysis: null }), { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  setAuthTokenProvider(null)
  vi.unstubAllGlobals()
})

describe('auth header', () => {
  it('attaches the current access token to every call', async () => {
    setAuthTokenProvider(async () => 'tok-1')
    await request('/api/repos')
    expect(lastCall().headers.Authorization).toBe('Bearer tok-1')
  })

  it('asks the provider each time, so refreshed tokens are used', async () => {
    let token = 'old'
    setAuthTokenProvider(async () => token)
    await request('/api/repos')
    token = 'refreshed'
    await request('/api/repos')
    expect(lastCall().headers.Authorization).toBe('Bearer refreshed')
  })

  it('sends no Authorization header when signed out', async () => {
    setAuthTokenProvider(async () => null)
    await request('/api/repos')
    expect(lastCall().headers.Authorization).toBeUndefined()
  })

  it('tab-close cleanup is a keepalive POST carrying the last token', async () => {
    setAuthTokenProvider(async () => 'tok-2')
    await request('/api/repos')
    cleanupGuestOnUnload(`guest_${USER}`)
    const { url, init, headers } = lastCall()
    expect(url).toMatch(new RegExp(`/api/cleanup-guest/guest_${USER}$`))
    expect(init.method).toBe('POST')
    expect(init.keepalive).toBe(true)
    expect(headers.Authorization).toBe('Bearer tok-2')
  })
})

describe('the user is never sent — the server reads the token', () => {
  it('listRepos has no user_id query param', async () => {
    await listRepos(USER)
    expect(lastCall().url).toMatch(/\/api\/repos$/)
  })

  it('analyze and chat bodies carry no user_id', async () => {
    await startAnalyzeJob('https://github.com/acme/api')
    expect(lastCall().body).not.toHaveProperty('user_id')
    await askQuestion('q', 'https://github.com/acme/api', null)
    expect(lastCall().body).not.toHaveProperty('user_id')
  })
})

describe('API base URL', () => {
  it('same-origin builds ("." or "/") call /api from the site root on any route', () => {
    expect(resolveApiBase('.')).toBe('')
    expect(resolveApiBase('/')).toBe('')
    // With base "" a call on /repos/owner/name goes to /api/repos, not /repos/owner/api/repos
    expect(new URL(`${resolveApiBase('.')}/api/repos`, 'http://app/repos/owner/name').pathname).toBe('/api/repos')
  })

  it('unset → local dev backend; explicit URLs lose a trailing slash', () => {
    expect(resolveApiBase(undefined)).toBe('http://localhost:8000')
    expect(resolveApiBase('')).toBe('http://localhost:8000')
    expect(resolveApiBase('https://api.example.com/')).toBe('https://api.example.com')
  })
})

describe('rate limits (429)', () => {
  it('keeps the server’s message and is recognised as rate limited', async () => {
    const detail = "You've reached the demo limit of 5 reviews per hour. Try again in 12 minutes."
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ detail }), { status: 429, headers: { 'Retry-After': '700' } }))
    const err = await request('/api/reviews', { method: 'POST', body: {} }).catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(isRateLimited(err)).toBe(true)
    expect((err as ApiError).message).toBe(detail)
  })

  it('a 429 without a body still reads as a friendly message', async () => {
    fetchMock.mockResolvedValueOnce(new Response('', { status: 429 }))
    const err = await request('/api/chat').catch((e: unknown) => e)
    expect(isRateLimited(err)).toBe(true)
    expect((err as ApiError).message).toBe('Too many requests — wait a few minutes and try again.')
  })

  it('other errors are not rate limits', async () => {
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'nope' }), { status: 503 }))
    const err = await request('/api/reviews').catch((e: unknown) => e)
    expect(isRateLimited(err)).toBe(false)
    expect(isRateLimited(new Error('x'))).toBe(false)
  })
})
