import { describe, expect, it } from 'vitest'
import type { TraceStep } from '../../lib/api'
import { layoutTimeline } from './timeline'

const step = (agent: string, durationMs: number | null, parallel = false, iteration = 1): TraceStep => ({
  agent, iteration, durationMs, parallel, inputSummary: null, outputSummary: null, decision: null,
})

describe('layoutTimeline', () => {
  it('runs steps back to back', () => {
    const { rows, total } = layoutTimeline([step('planner', 100), step('qa_checker', 50)])
    expect(rows.map((r) => [r.start, r.duration])).toEqual([[0, 100], [100, 50]])
    expect(total).toBe(150)
  })

  it('starts a parallel step with its partner and waits for the longer one', () => {
    const { rows, total } = layoutTimeline([
      step('planner', 100),
      step('style_analyst', 400),
      step('defect_hunter', 250, true),
      step('qa_checker', 50),
    ])
    expect(rows.map((r) => r.start)).toEqual([0, 100, 100, 500])
    expect(total).toBe(550)
  })

  it('a longer parallel partner extends the group', () => {
    const { rows, total } = layoutTimeline([step('style_analyst', 100), step('defect_hunter', 300, true), step('qa_checker', 10)])
    expect(rows[2].start).toBe(300)
    expect(total).toBe(310)
  })

  it('missing durations count as 0', () => {
    const { rows, total } = layoutTimeline([step('loop1_skip', null), step('planner', 20)])
    expect(rows.map((r) => [r.start, r.duration])).toEqual([[0, 0], [0, 20]])
    expect(total).toBe(20)
  })
})
