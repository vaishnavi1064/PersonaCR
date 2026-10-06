import type { TraceStep } from './api'

export interface TimelineRow {
  step: TraceStep
  /** ms from the start of the review (derived — the backend sends durations, not timestamps). */
  start: number
  duration: number
}

/**
 * Lay trace steps out on a time axis. Steps run in order; a step marked
 * `parallel` starts together with the step before it (Style Analyst ∥ Defect
 * Hunter), and the next sequential step waits for the longer of the two.
 */
export function layoutTimeline(steps: TraceStep[]): { rows: TimelineRow[]; total: number } {
  let cursor = 0
  let groupStart = 0
  let groupEnd = 0
  const rows = steps.map((step) => {
    const duration = Math.max(0, step.durationMs ?? 0)
    const start = step.parallel ? groupStart : cursor
    if (!step.parallel) groupStart = start
    groupEnd = step.parallel ? Math.max(groupEnd, start + duration) : start + duration
    cursor = groupEnd
    return { step, start, duration }
  })
  return { rows, total: cursor }
}

export function formatMs(ms: number): string {
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`
}
