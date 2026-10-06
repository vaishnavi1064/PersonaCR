import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, setAuthTokenProvider } from './http'
import { reviewCode, type ReviewProgress } from './reviews'

const RESULT = { overall_score: 72, status: 'passed', issues: [], issues_count: 0 }

type Reply = { status?: number; body: unknown } | Error

let replies: Reply[]
let calls: { url: string; method: string; body: unknown }[]

function respond(r: Reply): Response {
  if (r instanceof Error) throw r
  return new Response(JSON.stringify(r.body), { status: r.status ?? 200 })
}

beforeEach(() => {
  calls = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
    calls.push({ url, method: init.method ?? 'GET', body: typeof init.body === 'string' ? JSON.parse(init.body) : null })
    const next = replies.shift()
    if (!next) throw new Error('unexpected request')
    return respond(next)
  }))
  setAuthTokenProvider(async () => 'tok')
})

afterEach(() => {
  setAuthTokenProvider(null)
  vi.unstubAllGlobals()
})

const job = (state: string, extra: Record<string, unknown> = {}) => ({ job_id: 'j1', state, message: state, error: null, result: null, ...extra })

describe('reviewCode — runs on the background worker', () => {
  it('enqueues on /api/reviews (not the sync /api/review) and polls until completed', async () => {
    replies = [
      { status: 202, body: job('queued') },
      { body: job('running') },
      { body: job('completed', { result: RESULT }) },
    ]
    const progress: ReviewProgress[] = []
    const raw = await reviewCode('https://github.com/acme/api', 'x = 1', 'python', { pollMs: 0, onProgress: (p) => progress.push(p) })

    expect(raw).toEqual(RESULT)
    expect(calls[0]).toMatchObject({ method: 'POST', body: { repo_url: 'https://github.com/acme/api', code: 'x = 1', language: 'python' } })
    expect(calls[0].url).toMatch(/\/api\/reviews$/)
    expect(calls.slice(1).map((c) => c.url)).toEqual([expect.stringMatching(/\/api\/reviews\/j1$/), expect.stringMatching(/\/api\/reviews\/j1$/)])
    expect(calls.every((c) => !/\/api\/review$/.test(c.url))).toBe(true)
    expect(progress.map((p) => p.state)).toEqual(['queued', 'running'])
  })

  it('a failed job throws the server reason (e.g. the worker stopped)', async () => {
    replies = [
      { status: 202, body: job('queued') },
      { body: job('failed', { error: 'The background worker stopped while this was running (restart or crash). Try again.' }) },
    ]
    await expect(reviewCode('r', 'x', 'python', { pollMs: 0 })).rejects.toMatchObject({ message: expect.stringMatching(/worker stopped/) })
  })

  it('enqueue errors surface as-is (no fingerprint → 404, queue offline → 503)', async () => {
    replies = [{ status: 404, body: { detail: 'No fingerprint found for acme/api.' } }]
    await expect(reviewCode('r', 'x', 'python', { pollMs: 0 })).rejects.toMatchObject({ status: 404 })
    replies = [{ status: 503, body: { detail: 'Could not enqueue job' } }]
    const err = await reviewCode('r', 'x', 'python', { pollMs: 0 }).catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).status).toBe(503)
    expect(calls.filter((c) => /\/api\/review$/.test(c.url))).toHaveLength(0) // never falls back to the sync endpoint
  })

  it('rides out a transient polling error', async () => {
    replies = [
      { status: 202, body: job('queued') },
      new TypeError('network down'),
      { status: 502, body: { detail: 'bad gateway' } },
      { body: job('completed', { result: RESULT }) },
    ]
    await expect(reviewCode('r', 'x', 'python', { pollMs: 0 })).resolves.toEqual(RESULT)
  })

  it('a non-transient polling error stops the poll', async () => {
    replies = [{ status: 202, body: job('queued') }, { status: 404, body: { detail: 'Unknown job_id' } }]
    await expect(reviewCode('r', 'x', 'python', { pollMs: 0 })).rejects.toMatchObject({ status: 404 })
  })
})
