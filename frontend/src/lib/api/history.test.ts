import { describe, expect, it, vi } from 'vitest'
import type { ReviewRow } from '../db'

vi.mock('../supabase', () => ({ supabase: {} }))
const { reviewFromRow, SAVED_CODE_LIMIT } = await import('./history')

const row = (over: Partial<ReviewRow> = {}): ReviewRow => ({
  id: 'r1', user_id: 'u', repo_url: 'https://github.com/a/b', repo_name: 'a/b',
  submitted_code: 'def f():\n    pass', overall_score: 72, style_score: 80, defect_score: 64,
  comprehensiveness: 0.7, conciseness: 0.9, relevance: 0.8, issues_count: 1,
  issues: [{ type: 'defect', category: 'bug', severity: 'high', description: 'x', line_hint: 'line 2' } as never],
  status: 'passed', agent_trace: [], iterations: 1, created_at: '2026-10-01T00:00:00Z', ...over,
})

describe('reviewFromRow', () => {
  it('maps a saved row; unsaved fields stay unknown', () => {
    const { review, codeTruncated } = reviewFromRow(row())
    expect(review).toMatchObject({ id: 'r1', state: 'ok', score: 72, styleScore: 80, retrievalExamples: null })
    expect(review.confidence.score).toBeNull()
    expect(review.crScore.relevance).toBe(0.8)
    expect(review.findings[0].line).toBe(2)
    expect(codeTruncated).toBe(false)
  })

  it('flags code cut at the save limit and drops lines past it', () => {
    const code = 'x = 1\n'.repeat(200).slice(0, SAVED_CODE_LIMIT)
    const { review, codeTruncated } = reviewFromRow(row({
      submitted_code: code,
      issues: [{ type: 'defect', severity: 'low', description: 'far away', line_hint: 'line 150' } as never],
    }))
    expect(codeTruncated).toBe(true)
    expect(review.findings[0].line).toBeNull() // line 150 is beyond the saved code
  })

  it('an old null-score row is not shown as 0', () => {
    expect(reviewFromRow(row({ overall_score: null, status: 'error' })).review.score).toBeNull()
  })
})
