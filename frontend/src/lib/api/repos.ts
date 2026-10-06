// Repos: list (GET /api/repos), analyze/reanalyze (POST /api/analyze-repo),
// and the normalizers that turn backend JSON into domain types.
import { saveRepo } from '../db'
import { pct } from '../format'
import { request } from './http'
import type { Fingerprint, NamingConvention, Repo, RepoAnalysis } from './types'

// ── URL parsing ───────────────────────────────────────────────────────────────

export interface ParsedRepoUrl { url: string; owner: string; name: string; fullName: string }

const GH_URL = /^(?:https?:\/\/)?(?:www\.)?github\.com\/([A-Za-z0-9-]+)\/([A-Za-z0-9._-]+?)(?:\.git)?(?:[/?#].*)?$/i
const SHORTHAND = /^([A-Za-z0-9-]+)\/([A-Za-z0-9._-]+?)(?:\.git)?$/

/** Accepts https://github.com/owner/name (+ .git, subpaths), github.com/owner/name, or owner/name. */
export function parseRepoUrl(input: string): ParsedRepoUrl | null {
  const s = input.trim()
  const m = GH_URL.exec(s) ?? SHORTHAND.exec(s)
  if (!m) return null
  const [, owner, name] = m
  if (name === '.' || name === '..') return null
  return { url: `https://github.com/${owner}/${name}`, owner, name, fullName: `${owner}/${name}` }
}

function splitUrl(url: string): ParsedRepoUrl {
  const clean = url.trim().replace(/\/+$/, '').replace(/\.git$/, '')
  const parsed = parseRepoUrl(clean)
  if (parsed) return parsed
  const parts = clean.split('/')
  const owner = parts.at(-2) ?? ''
  const name = parts.at(-1) ?? clean
  return { url: clean, owner, name, fullName: owner ? `${owner}/${name}` : name }
}

// ── Fingerprint ───────────────────────────────────────────────────────────────

const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null)
const NAMING: NamingConvention[] = ['snake_case', 'camelCase', 'PascalCase', 'unknown']

const KNOWN_KEYS = new Set([
  'total_functions', 'avg_function_length', 'max_function_length', 'docstring_coverage',
  'type_hint_usage', 'type_hint_functions', 'error_handling_rate', 'avg_complexity', 'naming_convention', 'languages',
  'language_distribution', 'comment_density', 'avg_line_length', 'primary_indent_depth',
  'common_patterns', 'pattern_frequency', 'repo_summary', 'repo_summary_generated_at',
])

export function normalizeFingerprint(raw: unknown): Fingerprint | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null
  const r = raw as Record<string, unknown>
  if (Object.keys(r).length === 0) return null

  const dist: Record<string, number> = {}
  if (r.language_distribution && typeof r.language_distribution === 'object') {
    for (const [k, v] of Object.entries(r.language_distribution as Record<string, unknown>)) {
      const n = num(v)
      if (n != null) dist[k] = n
    }
  }
  const languages = Array.isArray(r.languages)
    ? r.languages.filter((l): l is string => typeof l === 'string')
    : Object.keys(dist)

  const extra: Fingerprint['extra'] = {}
  for (const [k, v] of Object.entries(r)) {
    if (KNOWN_KEYS.has(k)) continue
    if (typeof v === 'number' || typeof v === 'string' || v === null) extra[k] = v
  }

  const patterns: Record<string, number> = {}
  if (r.pattern_frequency && typeof r.pattern_frequency === 'object') {
    for (const [k, v] of Object.entries(r.pattern_frequency as Record<string, unknown>)) {
      const n = num(v)
      if (n != null) patterns[k] = n
    }
  }

  const naming = typeof r.naming_convention === 'string' && NAMING.includes(r.naming_convention as NamingConvention)
    ? (r.naming_convention as NamingConvention)
    : null

  return {
    totalFunctions: num(r.total_functions),
    avgFunctionLength: num(r.avg_function_length),
    maxFunctionLength: num(r.max_function_length),
    docstringCoverage: num(r.docstring_coverage),
    typeHintUsage: num(r.type_hint_usage),
    typeHintFunctions: num(r.type_hint_functions),
    errorHandlingRate: num(r.error_handling_rate),
    avgComplexity: num(r.avg_complexity),
    namingConvention: naming,
    languages,
    languageDistribution: dist,
    commentDensity: num(r.comment_density),
    avgLineLength: num(r.avg_line_length),
    primaryIndentDepth: num(r.primary_indent_depth),
    patternFrequency: patterns,
    extra,
    raw: r,
  }
}

/** 2–3 headline chips for a repo card, e.g. ["79% type hints", "snake_case", "41% docstrings"]. */
/**
 * Whether the type-hint rate means something. Current fingerprints measure it on
 * Python/TypeScript functions only (null when there are none). Older ones counted
 * every non-Python function as typed, so for those it's only trusted when the
 * repo is all Python.
 */
export function typeHintsMeasured(fp: Fingerprint): boolean {
  if (fp.typeHintFunctions != null) return fp.typeHintUsage != null && fp.typeHintFunctions > 0
  const langs = Object.keys(fp.languageDistribution).length ? Object.keys(fp.languageDistribution) : fp.languages
  return langs.every((l) => l.toLowerCase() === 'python')
}

/**
 * The type-hint rate describes the repo only when most of its functions were
 * measured — e.g. 2 Python helpers in a Java repo don't make it "100% typed".
 */
export function typeHintsRepresentative(fp: Fingerprint): boolean {
  if (!typeHintsMeasured(fp)) return false
  if (fp.typeHintFunctions == null || fp.totalFunctions == null || fp.totalFunctions === 0) return true
  return fp.typeHintFunctions / fp.totalFunctions >= 0.5
}

export function fingerprintChips(fp: Fingerprint | null, max = 3): string[] {
  if (!fp) return []
  const chips: string[] = []
  if (fp.typeHintUsage != null && typeHintsRepresentative(fp)) chips.push(`${pct(fp.typeHintUsage)} type hints`)
  if (fp.namingConvention && fp.namingConvention !== 'unknown') chips.push(fp.namingConvention)
  if (fp.docstringCoverage != null) chips.push(`${pct(fp.docstringCoverage)} docstrings`)
  if (fp.errorHandlingRate != null) chips.push(`${pct(fp.errorHandlingRate)} error handling`)
  return chips.slice(0, max)
}

/** Languages ordered by how many functions use them. */
export function topLanguages(repo: Pick<Repo, 'languages' | 'fingerprint'>, max = 3): string[] {
  const dist = repo.fingerprint?.languageDistribution ?? {}
  const langs = repo.languages.length ? repo.languages : repo.fingerprint?.languages ?? []
  return [...new Set(langs)].sort((a, b) => (dist[b] ?? 0) - (dist[a] ?? 0)).slice(0, max)
}

/** One-line summary stored inside the fingerprint at analysis time (null if none was generated). */
export function repoSummaryOf(fp: Fingerprint | null): string | null {
  const v = fp?.raw.repo_summary
  return typeof v === 'string' && v.trim() ? v.trim() : null
}

// ── List ──────────────────────────────────────────────────────────────────────

interface AnalysisWire {
  job_id: string
  state: RepoAnalysis['state']
  message: string | null
  error: string | null
  started_at: string | null
  finished_at: string | null
}

export interface RepoListItem {
  repo_url: string
  repo_name: string
  languages: string[] | null
  functions_count: number | null
  analyzed_at: string | null
  last_commit_sha: string | null
  fingerprint: unknown
  analysis?: AnalysisWire | null
}

function analysisFromWire(a: AnalysisWire | null | undefined): RepoAnalysis | null {
  if (!a) return null
  return {
    jobId: a.job_id, state: a.state, message: a.message, error: a.error,
    startedAt: a.started_at, finishedAt: a.finished_at,
  }
}

export function isActiveAnalysis(a: RepoAnalysis | null | undefined): boolean {
  return !!a && (a.state === 'queued' || a.state === 'running')
}

/** Status from the saved fingerprint plus the latest background analysis. */
function statusOf(fingerprint: Fingerprint | null, analysis: RepoAnalysis | null): Repo['status'] {
  if (isActiveAnalysis(analysis)) return 'analyzing'
  if (analysis?.state === 'failed') return 'failed'
  return fingerprint ? 'ready' : 'added'
}

export function repoFromListItem(item: RepoListItem): Repo {
  const id = splitUrl(item.repo_url)
  const fingerprint = normalizeFingerprint(item.fingerprint)
  const analysis = analysisFromWire(item.analysis)
  return {
    url: id.url,
    fullName: id.fullName,
    owner: id.owner,
    name: id.name,
    status: statusOf(fingerprint, analysis),
    error: analysis?.state === 'failed' ? analysis.error : null,
    languages: item.languages ?? fingerprint?.languages ?? [],
    functionsCount: num(item.functions_count),
    analyzedAt: item.analyzed_at,
    lastCommitSha: item.last_commit_sha,
    fingerprint,
    summary: repoSummaryOf(fingerprint),
    analysis,
  }
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

/** True for real Supabase accounts; guests and "anonymous" have nothing saved. */
export function isAccountUserId(userId: string | null | undefined): userId is string {
  return !!userId && UUID.test(userId)
}

/** Account repos (saved list), or a guest's repos analyzed in the background this session. */
export async function listRepos(userId: string, signal?: AbortSignal): Promise<Repo[]> {
  const guest = userId.startsWith('guest_')
  if (!guest && !isAccountUserId(userId)) return []
  // The server lists the token's user's repos; userId only decides whether to ask.
  const res = await request<{ repos: RepoListItem[] }>('/api/repos', { timeoutMs: 30_000, signal })
  return res.repos.map(repoFromListItem)
}

// ── Analyze ───────────────────────────────────────────────────────────────────

interface AnalyzeResponse {
  repo_url: string
  repo_name: string
  fingerprint: unknown
  num_functions: number
  last_commit_sha: string
  /** When the returned analysis was made (the cached row's time on a cache hit). */
  analyzed_at?: string | null
  cache_status: 'fresh' | 'new' | string
  message: string
  embedding: { status: 'ok' | 'failed' | 'skipped' | 'cached' | string; collection: string | null; chunks_embedded: number; error: string | null }
}

export interface AnalyzeResult {
  repo: Repo
  /** 'fresh' = unchanged since the cached analysis, 'new' = just analyzed. */
  cacheStatus: string
  /** Code-search index failed: reviews still run, without similar-code examples. */
  indexError: string | null
}

function resultFromResponse(r: AnalyzeResponse, url: string): AnalyzeResult {
  const id = splitUrl(r.repo_url || url)
  const fingerprint = normalizeFingerprint(r.fingerprint)
  return {
    repo: {
      url: id.url,
      fullName: id.fullName,
      owner: id.owner,
      name: id.name,
      status: fingerprint ? 'ready' : 'added',
      error: null,
      languages: fingerprint?.languages ?? [],
      functionsCount: num(r.num_functions),
      analyzedAt: r.analyzed_at ?? null,
      lastCommitSha: r.last_commit_sha || null,
      fingerprint,
      summary: repoSummaryOf(fingerprint),
      analysis: null,
    },
    cacheStatus: r.cache_status,
    indexError: r.embedding?.status === 'failed' ? r.embedding.error ?? 'Indexing failed' : null,
  }
}

/**
 * Synchronous analysis (waits for the whole run). Fallback when the background
 * queue is unavailable. Records the repo in the user's list itself.
 */
export async function analyzeRepo(
  url: string,
  userId: string,
  opts: { force?: boolean } = {},
): Promise<AnalyzeResult> {
  const r = await request<AnalyzeResponse>('/api/analyze-repo', {
    method: 'POST',
    body: { repo_url: url, force_refresh: !!opts.force },
    // Synchronous on the backend: big repos can take several minutes.
    timeoutMs: 15 * 60_000,
  })
  const result = resultFromResponse(r, url)
  if (isAccountUserId(userId)) {
    // user_repos is what GET /api/repos lists; saveRepo logs and never throws.
    await saveRepo({
      userId, repoUrl: result.repo.url, repoName: result.repo.fullName,
      functionsCount: result.repo.functionsCount ?? 0, languages: result.repo.languages,
    })
  }
  return result
}

// ── Background analysis (capability analyzeJobs) ─────────────────────────────

export interface AnalyzeJobStatus {
  jobId: string
  state: 'queued' | 'running' | 'completed' | 'failed'
  progress: number
  message: string | null
  error: string | null
  createdAt: string | null
  result: AnalyzeResult | null
}

/** Queue an analysis; an analysis already queued/running for this repo is reused. */
export async function startAnalyzeJob(
  url: string,
  opts: { force?: boolean } = {},
): Promise<{ jobId: string; startedAt: string | null }> {
  const r = await request<{ job_id: string; analysis: AnalysisWire | null }>('/api/analyze-jobs', {
    method: 'POST',
    body: { repo_url: url, force_refresh: !!opts.force },
    timeoutMs: 20_000,
  })
  return { jobId: r.job_id, startedAt: r.analysis?.started_at ?? null }
}

export async function getAnalyzeJob(jobId: string, url: string): Promise<AnalyzeJobStatus> {
  const r = await request<{
    job_id: string; state: AnalyzeJobStatus['state']; progress: number; message: string | null
    error: string | null; created_at: string | null; result: AnalyzeResponse | null
  }>(`/api/analyze-jobs/${encodeURIComponent(jobId)}`, { timeoutMs: 15_000 })
  return {
    jobId: r.job_id,
    state: r.state,
    progress: r.progress,
    message: r.message,
    error: r.error,
    createdAt: r.created_at,
    result: r.state === 'completed' && r.result ? resultFromResponse(r.result, url) : null,
  }
}
