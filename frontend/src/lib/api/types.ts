// Domain types for the redesigned UI. Pages consume these, never raw backend
// JSON. Normalizers (added slice by slice) map backend responses onto them.
// Source of truth for the backend shapes: backend/src/api/*_routes.py,
// backend/src/models.py, backend/src/agents/orchestrator.py.

// ── Repos ─────────────────────────────────────────────────────────────────────

/**
 * Added     — row exists, never analyzed (or analysis state unknown)
 * Analyzing — an analyze request is in flight (this session) / job running
 * Ready     — a fingerprint exists
 * Failed    — the last analyze attempt failed
 * Persisted status needs the background analyze job (capability `analyzeJobs`).
 */
export type RepoStatus = 'added' | 'analyzing' | 'ready' | 'failed'

export type NamingConvention = 'snake_case' | 'camelCase' | 'PascalCase' | 'unknown'

/**
 * Subset of backend FingerprintData (models.py). Rates are 0–1 fractions.
 * Every field is nullable: older cached rows can be partial, and a missing
 * value must render as "—", never as 0.
 */
export interface Fingerprint {
  totalFunctions: number | null
  avgFunctionLength: number | null
  maxFunctionLength: number | null
  docstringCoverage: number | null
  typeHintUsage: number | null
  /** Functions type hints were measured on (Python/TypeScript); null on fingerprints from before that field existed. */
  typeHintFunctions: number | null
  errorHandlingRate: number | null
  avgComplexity: number | null
  namingConvention: NamingConvention | null
  languages: string[]
  /** language → number of functions */
  languageDistribution: Record<string, number>
  commentDensity: number | null
  avgLineLength: number | null
  primaryIndentDepth: number | null
  /** Pattern → number of functions where it was detected. */
  patternFrequency: Record<string, number>
  /** Every other scalar field, kept for the Convention Atlas. */
  extra: Record<string, number | string | null>
  /** The backend record as received (Convention Atlas reads exact values from it). */
  raw: Record<string, unknown>
}

export interface Repo {
  /** Canonical https://github.com/owner/name (no trailing slash). */
  url: string
  /** owner/name */
  fullName: string
  owner: string
  name: string
  status: RepoStatus
  /** Error message when status is 'failed'. */
  error: string | null
  languages: string[]
  functionsCount: number | null
  analyzedAt: string | null
  /** Commit the fingerprint was built from. */
  lastCommitSha: string | null
  fingerprint: Fingerprint | null
  /** One-line summary — null until capability `repoSummary` ships. */
  summary: string | null
}

// ── Reviews ───────────────────────────────────────────────────────────────────

/** Backend `status` field (models.py:255). */
export type BackendReviewStatus = 'passed' | 'low_confidence' | 'quality_gate_failed' | 'degraded' | 'error'

/**
 * UI state for the Review Result:
 * ok             — score + findings (passed or quality_gate_failed)
 * low_confidence — score + findings + badge with the confidence reason
 * degraded       — some LLM calls failed: score is null ("—"), reason + retry
 * error          — no LLM call succeeded: score is null ("—"), reason + retry
 */
export type ReviewState = 'ok' | 'low_confidence' | 'degraded' | 'error'

export type Severity = 'critical' | 'high' | 'medium' | 'low'

export type AgentName =
  | 'planner' | 'style_analyst' | 'defect_hunter' | 'qa_checker'
  | 'confidence_evaluator' | 'loop1_skip' | 'pseudo_ref_generator'
  | 'sts_scorer' | 'quality_gate' | 'quality_gate_reloop'

export interface Finding {
  id: string
  kind: 'style' | 'defect'
  /** Agent that produced it (derived from kind until the backend sends it). */
  agent: AgentName
  category: string
  severity: Severity
  description: string
  /** 1-based line in the submitted code; null when unknown. */
  line: number | null
  /** Style evidence. Text today; numbers once capability `styleMetrics` ships. */
  repoValue: string | null
  codeValue: string | null
}

export interface TraceStep {
  agent: string
  iteration: number
  inputSummary: string | null
  outputSummary: string | null
  decision: string | null
  durationMs: number | null
  /** Ran concurrently with the previous step (Style ∥ Defect). */
  parallel: boolean
}

export interface CRScore {
  comprehensiveness: number | null
  conciseness: number | null
  relevance: number | null
}

export interface Review {
  id: string | null
  repoUrl: string
  code: string
  state: ReviewState
  backendStatus: BackendReviewStatus | string
  /** 0–100, or null for degraded/error. Render null as "—", never 0. */
  score: number | null
  styleScore: number | null
  defectScore: number | null
  findings: Finding[]
  confidence: { score: number | null; confident: boolean; reason: string | null; suggestion: string | null }
  /** Why the review is degraded/error (backend `degraded_reason`). */
  degradedReason: string | null
  qualityGatePassed: boolean | null
  crScore: CRScore
  /** Similar functions from the repo the Style Analyst compared against (0 = fingerprint only). */
  retrievalExamples: number | null
  iterations: number
  trace: TraceStep[]
  createdAt: string | null
}

// ── Chats ─────────────────────────────────────────────────────────────────────

export type ChatMode = 'ask' | 'review'

export interface Chat {
  id: string
  title: string
  starred: boolean
  /** The one repo this chat is scoped to (null for legacy multi-repo chats). */
  repoUrl: string | null
  updatedAt: string
}
