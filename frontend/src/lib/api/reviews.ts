// Reviews: POST /api/review and the normalizer that turns its JSON (also what
// chat messages persist) into the Review domain type.
import { request } from './http'
import type { AgentName, BackendReviewStatus, Finding, Review, ReviewState, Severity, TraceStep } from './types'

/** Raw /api/review response — persisted as-is in review chat messages. */
export interface RawReview {
  repo_url?: string
  language?: string
  overall_score: number | null
  status: BackendReviewStatus | string
  iterations?: number
  issues_count?: number
  issues?: RawIssue[]
  review_output?: Record<string, unknown>
  agent_trace?: Record<string, unknown>[]
}

export interface RawIssue {
  type?: string
  category?: string
  severity?: string
  description?: string
  line_hint?: string
  line?: number
  fingerprint_value?: unknown
  submitted_value?: unknown
}

export const REVIEW_LANGUAGES = [
  { value: 'python', label: 'Python' },
  { value: 'javascript', label: 'JavaScript' },
  { value: 'typescript', label: 'TypeScript' },
  { value: 'java', label: 'Java' },
  { value: 'go', label: 'Go' },
  { value: 'rust', label: 'Rust' },
  { value: 'kotlin', label: 'Kotlin' },
  { value: 'cpp', label: 'C++' },
  { value: 'c', label: 'C' },
  { value: 'csharp', label: 'C#' },
  { value: 'ruby', label: 'Ruby' },
] as const

export type ReviewLanguage = typeof REVIEW_LANGUAGES[number]['value']

export async function reviewCode(repoUrl: string, code: string, language: string): Promise<RawReview> {
  return request<RawReview>('/api/review', {
    method: 'POST',
    body: { repo_url: repoUrl, code, language },
    // Six agents + two self-correction loops; several LLM calls.
    timeoutMs: 10 * 60_000,
  })
}

// ── Normalization ─────────────────────────────────────────────────────────────

const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null)
const str = (v: unknown): string | null => (typeof v === 'string' && v.trim() ? v.trim() : null)

/**
 * "line 12", "Line 12", "lines 12-15", "L12", "12" → 12. Out-of-range or
 * missing → null (the finding shows as "line n/a", not a guess).
 */
export function parseLineHint(hint: unknown, lineCount?: number): number | null {
  let n: number | null = null
  if (typeof hint === 'number' && Number.isInteger(hint)) n = hint
  else if (typeof hint === 'string') {
    const m = /\b(?:lines?|l)\s*:?\s*(\d+)/i.exec(hint) ?? /^\s*(\d+)\s*$/.exec(hint)
    if (m) n = Number(m[1])
  }
  if (n == null || n < 1) return null
  if (lineCount != null && n > lineCount) return null
  return n
}

const SEVERITIES: Severity[] = ['critical', 'high', 'medium', 'low']

function severity(v: unknown): Severity {
  const s = typeof v === 'string' ? v.toLowerCase() : ''
  return (SEVERITIES as string[]).includes(s) ? (s as Severity) : 'low'
}

function evidence(v: unknown): string | null {
  if (v == null) return null
  if (typeof v === 'number') return String(v)
  return str(v)
}

export function normalizeFinding(raw: RawIssue, index: number, lineCount?: number): Finding {
  const kind = raw.type === 'style' ? 'style' : 'defect'
  return {
    id: String(index),
    kind,
    agent: kind === 'style' ? 'style_analyst' : 'defect_hunter',
    category: str(raw.category) ?? kind,
    severity: severity(raw.severity),
    description: str(raw.description) ?? '',
    // An integer `line` (future backend) wins over the free-text hint.
    line: parseLineHint(raw.line, lineCount) ?? parseLineHint(raw.line_hint, lineCount),
    repoValue: evidence(raw.fingerprint_value),
    codeValue: evidence(raw.submitted_value),
  }
}

function reviewState(status: string, score: number | null): ReviewState {
  if (status === 'error') return 'error'
  if (status === 'degraded') return 'degraded'
  // No score without a degraded status is still not a trustworthy review.
  if (score == null) return 'degraded'
  if (status === 'low_confidence') return 'low_confidence'
  return 'ok'
}

const PARALLEL_PAIR = new Set(['style_analyst', 'defect_hunter'])

function normalizeTrace(raw: Record<string, unknown>[] | undefined): TraceStep[] {
  if (!Array.isArray(raw)) return []
  return raw.map((t, i) => {
    const agent = str(t.agent_name) ?? 'unknown'
    const iteration = num(t.iteration) ?? 1
    const prev = i > 0 ? raw[i - 1] : null
    return {
      agent,
      iteration,
      inputSummary: str(t.input_summary),
      outputSummary: str(t.output_summary) ?? str(t.summary),
      decision: str(t.decision),
      durationMs: num(t.execution_time_ms) ?? num(t.elapsed_ms),
      // Style Analyst and Defect Hunter run together (asyncio.gather).
      parallel: !!prev && PARALLEL_PAIR.has(agent) && PARALLEL_PAIR.has(String(prev.agent_name))
        && agent !== prev.agent_name && (num(prev.iteration) ?? 1) === iteration,
    }
  })
}

export function normalizeReview(
  raw: RawReview,
  ctx: { code: string; repoUrl?: string; id?: string | null; createdAt?: string | null },
): Review {
  const out = (raw.review_output ?? {}) as Record<string, unknown>
  const conf = (out.confidence ?? {}) as Record<string, unknown>
  const qs = (out.quality_scores ?? {}) as Record<string, unknown>
  const score = num(raw.overall_score)
  const status = typeof raw.status === 'string' ? raw.status : 'passed'
  const state = reviewState(status, score)
  const lineCount = ctx.code ? ctx.code.replace(/\n$/, '').split('\n').length : undefined

  return {
    id: ctx.id ?? null,
    repoUrl: ctx.repoUrl ?? raw.repo_url ?? '',
    code: ctx.code,
    state,
    backendStatus: status,
    score: state === 'degraded' || state === 'error' ? null : score,
    styleScore: num(out.style_score),
    defectScore: num(out.defect_score),
    findings: (raw.issues ?? []).map((iss, i) => normalizeFinding(iss, i, lineCount)),
    confidence: {
      score: num(conf.confidence_score),
      confident: conf.is_confident === true,
      reason: str(conf.reason),
      suggestion: str(conf.suggestion),
    },
    degradedReason: str(out.degraded_reason)
      ?? (state === 'degraded' || state === 'error' ? 'The review finished without a trustworthy score.' : null),
    qualityGatePassed: typeof out.quality_gate_passed === 'boolean' ? out.quality_gate_passed : null,
    crScore: {
      comprehensiveness: num(qs.comprehensiveness),
      conciseness: num(qs.conciseness),
      relevance: num(qs.relevance),
    },
    iterations: num(raw.iterations) ?? 1,
    trace: normalizeTrace(raw.agent_trace),
    createdAt: ctx.createdAt ?? null,
  }
}

export const AGENT_LABEL: Record<AgentName, string> = {
  planner: 'Planner',
  style_analyst: 'Style Analyst',
  defect_hunter: 'Defect Hunter',
  qa_checker: 'QA Checker',
  confidence_evaluator: 'Confidence Evaluator',
  loop1_skip: 'Loop 1 skip',
  pseudo_ref_generator: 'Pseudo-ref Generator',
  sts_scorer: 'STS Scorer',
  quality_gate: 'Quality Gate',
  quality_gate_reloop: 'Quality Gate re-review',
}
