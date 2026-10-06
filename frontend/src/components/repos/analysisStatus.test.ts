import { describe, expect, it, vi } from 'vitest'

vi.mock('../../lib/db', () => ({ saveRepo: vi.fn() }))
vi.mock('../../lib/supabase', () => ({ supabase: {} }))
const { repoFromListItem } = await import('../../lib/api/repos')
const { activeAnalysis, stuckHint, STUCK_QUEUED_MS } = await import('./analysisStatus')

const item = (over: object = {}) => ({
  repo_url: 'https://github.com/acme/api', repo_name: 'acme/api', languages: [], functions_count: 2,
  analyzed_at: null, last_commit_sha: null, fingerprint: { total_functions: 2 }, analysis: null, ...over,
})
const analysis = (state: string, extra: object = {}) => ({
  job_id: 'j1', state, message: 'Fetching files 3/9', error: null, started_at: '2026-10-06T00:00:00Z', finished_at: null, ...extra,
})

describe('repo status from the server', () => {
  it('ready with a fingerprint and no active analysis', () => {
    expect(repoFromListItem(item()).status).toBe('ready')
    expect(repoFromListItem(item({ analysis: analysis('completed') })).status).toBe('ready')
  })
  it('analyzing while queued or running — even with an older fingerprint', () => {
    expect(repoFromListItem(item({ analysis: analysis('queued') })).status).toBe('analyzing')
    expect(repoFromListItem(item({ analysis: analysis('running') })).status).toBe('analyzing')
  })
  it('failed carries the reason; added when never analyzed', () => {
    const r = repoFromListItem(item({ fingerprint: null, analysis: analysis('failed', { error: 'GitHub 404' }) }))
    expect(r.status).toBe('failed')
    expect(r.error).toBe('GitHub 404')
    expect(repoFromListItem(item({ fingerprint: null })).status).toBe('added')
  })
})

describe('activeAnalysis / stuckHint', () => {
  it('shows the server stage for analyses this tab is not watching', () => {
    const a = activeAnalysis(repoFromListItem(item({ analysis: analysis('running') })))
    expect(a).toMatchObject({ message: 'Fetching files 3/9', queued: false, background: true })
    expect(a!.startedAt).toBe(Date.parse('2026-10-06T00:00:00Z'))
  })
  it('flags a job left in the queue', () => {
    const a = activeAnalysis(repoFromListItem(item({ analysis: analysis('queued') })))!
    expect(stuckHint(a, a.startedAt + 5_000)).toBeNull()
    expect(stuckHint(a, a.startedAt + STUCK_QUEUED_MS + 1)).toMatch(/worker running/)
  })
  it('nothing active → null', () => {
    expect(activeAnalysis(repoFromListItem(item()))).toBeNull()
  })
})
