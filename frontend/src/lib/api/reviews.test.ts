import { describe, expect, it } from 'vitest'
import { explainDegraded, normalizeReview, parseLineHint, type RawReview } from './reviews'

const CODE = 'def f(x):\n    try:\n        return 1 / x\n    except:\n        pass\n'

function raw(over: Partial<RawReview> = {}): RawReview {
  return {
    overall_score: 72.5,
    status: 'passed',
    iterations: 1,
    issues: [],
    review_output: {},
    agent_trace: [],
    ...over,
  }
}

describe('parseLineHint', () => {
  it.each([
    ['line 12', 12], ['Line 3', 3], ['lines 4-9', 4], ['L7', 7], ['line: 2', 2], ['5', 5], [8, 8],
  ])('%j → %d', (hint, expected) => {
    expect(parseLineHint(hint)).toBe(expected)
  })

  it.each([[''], ['near the top'], [null], [undefined], ['line 0'], [2.5]])('%j → null', (hint) => {
    expect(parseLineHint(hint)).toBeNull()
  })

  it('rejects lines past the end of the code', () => {
    expect(parseLineHint('line 6', 5)).toBeNull()
    expect(parseLineHint('line 5', 5)).toBe(5)
  })
})

describe('normalizeReview — states', () => {
  it('passed → ok with score', () => {
    const r = normalizeReview(raw(), { code: CODE })
    expect(r.state).toBe('ok')
    expect(r.score).toBe(72.5)
  })

  it('quality_gate_failed is still a scored review', () => {
    const r = normalizeReview(raw({ status: 'quality_gate_failed' }), { code: CODE })
    expect(r.state).toBe('ok')
    expect(r.qualityGatePassed).toBeNull()
  })

  it('low_confidence keeps the score and the reason', () => {
    const r = normalizeReview(raw({
      status: 'low_confidence',
      review_output: { confidence: { confidence_score: 0.4, is_confident: false, reason: 'Only 0 similar functions retrieved' } },
    }), { code: CODE })
    expect(r.state).toBe('low_confidence')
    expect(r.score).toBe(72.5)
    expect(r.confidence).toEqual({ score: 0.4, confident: false, reason: 'Only 0 similar functions retrieved', suggestion: null })
  })

  it.each(['degraded', 'error'] as const)('%s → no score (never 0) + reason', (status) => {
    const r = normalizeReview(raw({
      status, overall_score: null,
      review_output: { degraded_reason: '2 LLM call(s) failed (style_analyst: rate_limit)' },
    }), { code: CODE })
    expect(r.state).toBe(status)
    expect(r.score).toBeNull()
    expect(r.degradedReason).toMatch(/LLM call/)
  })

  it('a null score with a normal status is treated as degraded', () => {
    const r = normalizeReview(raw({ overall_score: null }), { code: CODE })
    expect(r.state).toBe('degraded')
    expect(r.score).toBeNull()
    expect(r.degradedReason).toBeTruthy()
  })

  it('reads how many repo functions were compared against', () => {
    expect(normalizeReview(raw({ review_output: { retrieval_examples: 4 } }), { code: CODE }).retrievalExamples).toBe(4)
    expect(normalizeReview(raw({ review_output: { similar_functions_used: 2 } }), { code: CODE }).retrievalExamples).toBe(2)
    expect(normalizeReview(raw(), { code: CODE }).retrievalExamples).toBeNull() // legacy message: unknown, not 0
  })

  it('degraded drops a stray score', () => {
    const r = normalizeReview(raw({ status: 'degraded', overall_score: 40 }), { code: CODE })
    expect(r.score).toBeNull()
  })
})

describe('normalizeReview — findings', () => {
  const r = normalizeReview(raw({
    issues: [
      { type: 'defect', category: 'bug', severity: 'HIGH', description: 'Bare except', line_hint: 'line 4' },
      { type: 'defect', category: 'smell', severity: 'weird', description: 'Out of range', line_hint: 'line 99' },
      { type: 'style', category: 'type_hints', severity: 'medium', description: 'No type hints',
        fingerprint_value: '79% of functions use type hints', submitted_value: 'none' },
    ],
  }), { code: CODE })

  it('maps agent from kind and parses line hints within the code', () => {
    expect(r.findings.map((f) => [f.agent, f.line])).toEqual([
      ['defect_hunter', 4], ['defect_hunter', null], ['style_analyst', null],
    ])
  })

  it('normalizes severity and keeps style evidence', () => {
    expect(r.findings[0].severity).toBe('high')
    expect(r.findings[1].severity).toBe('low')
    expect(r.findings[2]).toMatchObject({ repoValue: '79% of functions use type hints', codeValue: 'none' })
  })

  it('prefers an integer line field when the backend sends one', () => {
    const withLine = normalizeReview(raw({ issues: [{ type: 'style', line: 2, line_hint: 'line 5' }] }), { code: CODE })
    expect(withLine.findings[0].line).toBe(2)
  })
})

describe('normalizeReview — trace', () => {
  it('marks Style Analyst ∥ Defect Hunter in the same iteration as parallel', () => {
    const r = normalizeReview(raw({
      agent_trace: [
        { agent_name: 'planner', execution_time_ms: 900, iteration: 1 },
        { agent_name: 'style_analyst', execution_time_ms: 4000, iteration: 1 },
        { agent_name: 'defect_hunter', execution_time_ms: 3500, iteration: 1 },
        { agent_name: 'style_analyst', execution_time_ms: 3800, iteration: 2 },
      ],
    }), { code: CODE })
    expect(r.trace.map((t) => t.parallel)).toEqual([false, false, true, false])
    expect(r.trace[1].durationMs).toBe(4000)
  })
})

describe('explainDegraded', () => {
  it('splits the backend reason into summary, hint and raw detail', () => {
    const r = explainDegraded("5 LLM call(s) failed (planner: not_found) — Anthropic model not found (claude-x): Error code: 404 - {'type': 'error'}")
    expect(r.summary).toBe('5 LLM call(s) failed (planner: not_found)')
    expect(r.hint).toMatch(/model isn’t available/)
    expect(r.detail).toMatch(/^Anthropic model not found/)
  })

  it('unknown kinds keep the summary without a hint', () => {
    expect(explainDegraded('1 LLM call(s) failed (style: weird) — boom')).toEqual({
      summary: '1 LLM call(s) failed (style: weird)', hint: null, detail: 'boom',
    })
  })

  it('passes through reasons in another format, and handles none', () => {
    expect(explainDegraded('Something else')).toEqual({ summary: 'Something else', hint: null, detail: null })
    expect(explainDegraded(null).summary).toMatch(/without a trustworthy score/)
  })
})
