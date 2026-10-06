import { describe, expect, it } from 'vitest'
import { normalizeReview, type RawReview } from './api/reviews'
import { computeDashboard, percentile } from './dashboardStats'

const review = (over: Partial<RawReview> & { repo?: string; at?: string; id?: string } = {}) => {
  const { repo = 'https://github.com/a/api', at = '2026-10-01T00:00:00Z', id = Math.random().toString(36), ...raw } = over
  return normalizeReview({ overall_score: 70, status: 'passed', issues: [], agent_trace: [], review_output: {}, ...raw }, {
    code: 'x = 1', repoUrl: repo, id, createdAt: at,
  })
}

describe('computeDashboard', () => {
  it('averages scored reviews only; degraded/error are counted, never averaged as 0', () => {
    const s = computeDashboard([
      review({ overall_score: 80 }),
      review({ overall_score: 60, status: 'low_confidence' }),
      review({ overall_score: null, status: 'degraded' }),
      review({ overall_score: null, status: 'error' }),
    ])
    expect(s).toMatchObject({ total: 4, scored: 2, unscored: 2, avgScore: 70 })
    expect(s.trend.map((p) => p.score)).toEqual([80, 60])
  })

  it('no reviews → nulls, not zeros', () => {
    const s = computeDashboard([])
    expect(s.avgScore).toBeNull()
    expect(s.reviewTime).toEqual({ p50: null, p95: null })
    expect(s.loops.confidentFirstPass).toBeNull()
    expect(s.crScore.relevance).toBeNull()
  })

  it('trend is chronological', () => {
    const s = computeDashboard([review({ at: '2026-10-03T00:00:00Z', overall_score: 30 }), review({ at: '2026-10-01T00:00:00Z', overall_score: 90 })])
    expect(s.trend.map((p) => p.score)).toEqual([90, 30])
  })

  it('review time counts Style ∥ Defect once (the longer of the two)', () => {
    const s = computeDashboard([review({
      agent_trace: [
        { agent_name: 'planner', execution_time_ms: 1000, iteration: 1 },
        { agent_name: 'style_analyst', execution_time_ms: 4000, iteration: 1 },
        { agent_name: 'defect_hunter', execution_time_ms: 3000, iteration: 1 },
        { agent_name: 'qa_checker', execution_time_ms: 500, iteration: 1 },
      ],
    })])
    expect(s.reviewTime.p50).toBe(5500) // not the 8500 ms sum
    expect(s.agentTime[0]).toEqual({ agent: 'style_analyst', avgMs: 4000, runs: 1 })
  })

  it('loop health from trace summaries', () => {
    const s = computeDashboard([
      review({ agent_trace: [
        { agent_name: 'confidence_evaluator', output_summary: 'Confidence=0.4, Confident=False', iteration: 1 },
        { agent_name: 'confidence_evaluator', output_summary: 'Confidence=0.8, Confident=True', iteration: 2 },
        { agent_name: 'quality_gate', output_summary: 'Passed=False', iteration: 1 },
        { agent_name: 'quality_gate', output_summary: 'Passed=True', iteration: 2 },
      ] }),
      review({ agent_trace: [{ agent_name: 'confidence_evaluator', output_summary: 'Confident=True', iteration: 1 }] }),
    ])
    expect(s.loops.confidentFirstPass).toBe(0.5)
    expect(s.loops.qualityGatePassed).toBe(1)
    expect(s.loops.samples).toEqual({ confidence: 2, gate: 1 })
  })

  it('rolls up per repo (newest first) without mixing repos', () => {
    const s = computeDashboard([
      review({ repo: 'https://github.com/a/api', overall_score: 80, at: '2026-10-01T00:00:00Z' }),
      review({ repo: 'https://github.com/a/api', overall_score: null, status: 'error', at: '2026-10-02T00:00:00Z' }),
      review({ repo: 'https://github.com/a/web', overall_score: 40, at: '2026-10-05T00:00:00Z' }),
    ])
    expect(s.byRepo).toEqual([
      { repoUrl: 'https://github.com/a/web', reviews: 1, scored: 1, avgScore: 40, lastAt: '2026-10-05T00:00:00Z' },
      { repoUrl: 'https://github.com/a/api', reviews: 2, scored: 1, avgScore: 80, lastAt: '2026-10-02T00:00:00Z' },
    ])
  })

  it('category shares come from scored reviews', () => {
    const s = computeDashboard([
      review({ issues: [{ type: 'defect', category: 'bug' }, { type: 'defect', category: 'bug' }, { type: 'style', category: 'naming' }] }),
      review({ overall_score: null, status: 'degraded', issues: [{ type: 'defect', category: 'security' }] }),
    ])
    expect(s.categories).toEqual([
      { category: 'bug', count: 2, share: 2 / 3 },
      { category: 'naming', count: 1, share: 1 / 3 },
    ])
  })
})

describe('percentile', () => {
  it('interpolates', () => {
    expect(percentile([10, 20, 30, 40], 50)).toBe(25)
    expect(percentile([], 50)).toBeNull()
  })
})
