/**
 * Supabase database helpers — reviews and repos persistence.
 * All functions are fire-and-forget safe: they log errors but never throw,
 * so a Supabase failure never crashes the chat UI.
 */
import { supabase } from './supabase'

// ── Types ─────────────────────────────────────────────────────────────────────

export interface ReviewRow {
  id: string
  user_id: string
  repo_url: string
  repo_name: string
  submitted_code: string
  overall_score: number
  style_score: number
  defect_score: number
  comprehensiveness: number
  conciseness: number
  relevance: number
  issues_count: number
  issues: IssueRow[]
  status: string
  agent_trace: AgentTraceRow[]
  iterations: number
  created_at: string
}

export interface IssueRow {
  type: string
  category?: string
  severity?: string
  description: string
}

export interface AgentTraceRow {
  agent_name: string
  output_summary?: string
  execution_time_ms?: number
  iteration?: number
}

export interface RepoRow {
  id: string
  user_id: string
  repo_url: string
  repo_name: string
  functions_count: number
  languages: string[]
  analyzed_at: string
}

// ── Write ─────────────────────────────────────────────────────────────────────

export async function saveReview(params: {
  userId: string
  repoUrl: string
  code: string
  result: {
    overall_score: number
    status: string
    iterations: number
    issues: IssueRow[]
    issues_count?: number
    review_output?: {
      style_score?: number
      defect_score?: number
      quality_scores?: {
        comprehensiveness?: number
        conciseness?: number
        relevance?: number
      }
    }
    agent_trace?: AgentTraceRow[]
  }
}): Promise<void> {
  const { userId, repoUrl, code, result } = params
  const repoName = repoUrl.replace(/\/$/, '').split('/').slice(-2).join('/')
  const qs = result.review_output?.quality_scores ?? {}

  const { error } = await supabase.from('user_reviews').insert({
    user_id:           userId,
    repo_url:          repoUrl,
    repo_name:         repoName,
    submitted_code:    code.substring(0, 500),
    overall_score:     result.overall_score,
    style_score:       result.review_output?.style_score  ?? 0,
    defect_score:      result.review_output?.defect_score ?? 0,
    comprehensiveness: qs.comprehensiveness ?? 0,
    conciseness:       qs.conciseness       ?? 0,
    relevance:         qs.relevance         ?? 0,
    issues_count:      result.issues_count ?? result.issues?.length ?? 0,
    issues:            result.issues   ?? [],
    status:            result.status   ?? 'passed',
    agent_trace:       result.agent_trace ?? [],
    iterations:        result.iterations  ?? 1,
  })

  if (error) console.warn('[db] saveReview failed:', error.message)
}

export async function saveRepo(params: {
  userId: string
  repoUrl: string
  repoName: string
  functionsCount: number
  languages: string[]
}): Promise<void> {
  const { error } = await supabase.from('user_repos').insert({
    user_id:         params.userId,
    repo_url:        params.repoUrl,
    repo_name:       params.repoName,
    functions_count: params.functionsCount,
    languages:       params.languages,
  })

  if (error) console.warn('[db] saveRepo failed:', error.message)
}

// ── Read ──────────────────────────────────────────────────────────────────────

export async function fetchReviews(userId: string): Promise<ReviewRow[]> {
  const { data, error } = await supabase
    .from('user_reviews')
    .select('*')
    .eq('user_id', userId)
    .order('created_at', { ascending: false })

  if (error) {
    console.warn('[db] fetchReviews failed:', error.message)
    return []
  }
  return (data ?? []) as ReviewRow[]
}

export async function fetchRepos(userId: string): Promise<RepoRow[]> {
  const { data, error } = await supabase
    .from('user_repos')
    .select('*')
    .eq('user_id', userId)
    .order('analyzed_at', { ascending: false })
    .limit(20)

  if (error) {
    console.warn('[db] fetchRepos failed:', error.message)
    return []
  }
  return (data ?? []) as RepoRow[]
}

// ── Derived metrics ───────────────────────────────────────────────────────────

export function computeDashboardStats(reviews: ReviewRow[]) {
  if (reviews.length === 0) {
    return {
      avgScore:    null as number | null,
      totalReviews: 0,
      topIssue:    null as string | null,
      trendData:   [] as { date: string; score: number }[],
      breakdown:   [] as { label: string; pct: number; color: string }[],
    }
  }

  // Average score
  const avgScore = reviews.reduce((s, r) => s + r.overall_score, 0) / reviews.length

  // Top issue category
  const catCount: Record<string, number> = {}
  for (const review of reviews) {
    for (const issue of review.issues ?? []) {
      const cat = issue.category ?? issue.type ?? 'other'
      catCount[cat] = (catCount[cat] ?? 0) + 1
    }
  }
  const topIssue = Object.entries(catCount).sort((a, b) => b[1] - a[1])[0]?.[0] ?? null

  // Quality trend (oldest → newest)
  const trendData = [...reviews]
    .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
    .map((r) => ({
      date:  new Date(r.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      score: Math.round(r.overall_score),
    }))

  // Issue breakdown
  const COLORS: Record<string, string> = {
    documentation:  '#8B7CF6',
    doc:            '#8B7CF6',
    style:          '#8B7CF6',
    error_handling: '#D85A30',
    bug:            '#D85A30',
    defect:         '#D85A30',
    naming:         '#1D9E75',
    complexity:     '#BA7517',
    smell:          '#BA7517',
    security:       '#E25555',
    other:          '#5C5C5B',
  }
  const total = Object.values(catCount).reduce((s, n) => s + n, 0) || 1
  const breakdown = Object.entries(catCount)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([label, count]) => ({
      label: label.replace(/_/g, ' '),
      pct:   Math.round((count / total) * 100),
      color: COLORS[label.toLowerCase()] ?? COLORS.other,
    }))

  return { avgScore, totalReviews: reviews.length, topIssue, trendData, breakdown }
}

// ── Advanced dashboard metrics ─────────────────────────────────────────────────

export interface LatencyStats {
  p50: number | null   // milliseconds
  p95: number | null   // milliseconds
}

export interface CRScoreStats {
  comprehensiveness: number | null  // 0–100
  conciseness: number | null        // 0–100
  relevance: number | null          // 0–100
}

export interface AgentLatencyEntry {
  agent: string
  avgMs: number
  count: number
}

export interface LoopHealthStats {
  confidencePassRate: number | null  // 0–100
  qualityGatePassRate: number | null // 0–100
}

export interface AdvancedStats {
  latency: LatencyStats
  crScore: CRScoreStats
  agentLatency: AgentLatencyEntry[]
  loopHealth: LoopHealthStats
}

/** Safely parse agent_trace — handles null, undefined, strings, or non-arrays */
function parseAgentTrace(raw: unknown): AgentTraceRow[] {
  if (!raw) return []
  let arr = raw
  if (typeof arr === 'string') {
    try { arr = JSON.parse(arr) } catch { return [] }
  }
  if (!Array.isArray(arr)) return []
  return arr as AgentTraceRow[]
}

function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0
  const idx = (p / 100) * (sorted.length - 1)
  const lo = Math.floor(idx)
  const hi = Math.ceil(idx)
  if (lo === hi) return sorted[lo]
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo)
}

export function computeAdvancedStats(reviews: ReviewRow[]): AdvancedStats {
  // ── Latency p50/p95 ──
  const totalLatencies: number[] = []
  for (const r of reviews) {
    const trace = parseAgentTrace(r.agent_trace)
    if (trace.length === 0) continue
    let sum = 0
    for (const t of trace) {
      sum += (t.execution_time_ms ?? 0)
    }
    if (sum > 0) totalLatencies.push(sum)
  }
  totalLatencies.sort((a, b) => a - b)
  const latency: LatencyStats = totalLatencies.length > 0
    ? { p50: percentile(totalLatencies, 50), p95: percentile(totalLatencies, 95) }
    : { p50: null, p95: null }

  // ── CRScore averages ──
  const compVals: number[] = []
  const concVals: number[] = []
  const relVals: number[] = []
  for (const r of reviews) {
    if (r.comprehensiveness != null) compVals.push(r.comprehensiveness)
    if (r.conciseness != null) concVals.push(r.conciseness)
    if (r.relevance != null) relVals.push(r.relevance)
  }
  const avg = (arr: number[]) => arr.length > 0 ? arr.reduce((s, v) => s + v, 0) / arr.length : null
  const crScore: CRScoreStats = {
    comprehensiveness: compVals.length > 0 ? (avg(compVals)! * 100) : null,
    conciseness: concVals.length > 0 ? (avg(concVals)! * 100) : null,
    relevance: relVals.length > 0 ? (avg(relVals)! * 100) : null,
  }

  // ── Per-agent latency ──
  const agentAcc: Record<string, { totalMs: number; count: number }> = {}
  for (const r of reviews) {
    const trace = parseAgentTrace(r.agent_trace)
    for (const t of trace) {
      if (!t.agent_name || t.execution_time_ms == null) continue
      if (!agentAcc[t.agent_name]) agentAcc[t.agent_name] = { totalMs: 0, count: 0 }
      agentAcc[t.agent_name].totalMs += t.execution_time_ms
      agentAcc[t.agent_name].count += 1
    }
  }
  const agentLatency: AgentLatencyEntry[] = Object.entries(agentAcc)
    .map(([agent, { totalMs, count }]) => ({ agent, avgMs: Math.round(totalMs / count), count }))
    .sort((a, b) => b.avgMs - a.avgMs)

  // ── Agentic loop health ──
  const confidenceRegex = /Confident=(True|False)/
  const passedRegex = /Passed=(True|False)/

  let confidentFirstTotal = 0
  let confidentFirstPassed = 0
  let qualityGateTotal = 0
  let qualityGatePassed = 0

  for (const r of reviews) {
    const trace = parseAgentTrace(r.agent_trace)

    // Confidence on iteration 1
    const confEntry = trace.find(
      (t) => t.agent_name === 'confidence_evaluator' && t.iteration === 1
    )
    if (confEntry?.output_summary) {
      const m = confidenceRegex.exec(confEntry.output_summary)
      if (m) {
        confidentFirstTotal++
        if (m[1] === 'True') confidentFirstPassed++
      }
    }

    // Quality gate — last entry (highest iteration)
    const qgEntries = trace
      .filter((t) => t.agent_name === 'quality_gate')
      .sort((a, b) => (a.iteration ?? 0) - (b.iteration ?? 0))
    const lastQG = qgEntries[qgEntries.length - 1]
    if (lastQG?.output_summary) {
      const m = passedRegex.exec(lastQG.output_summary)
      if (m) {
        qualityGateTotal++
        if (m[1] === 'True') qualityGatePassed++
      }
    }
  }

  const loopHealth: LoopHealthStats = {
    confidencePassRate: confidentFirstTotal > 0
      ? Math.round((confidentFirstPassed / confidentFirstTotal) * 100)
      : null,
    qualityGatePassRate: qualityGateTotal > 0
      ? Math.round((qualityGatePassed / qualityGateTotal) * 100)
      : null,
  }

  return { latency, crScore, agentLatency, loopHealth }
}

// ── Chat persistence ───────────────────────────────────────────────────────────

/** Shape stored in Supabase user_chats.messages jsonb */
export interface PersistedMessage {
  role:      'user' | 'bot'
  content:   string | null       // plain text or null for card types
  type:      'text' | 'fingerprint' | 'review'
  data?:     Record<string, unknown> | null
  timestamp: string
}

export interface ChatMeta {
  id:              string
  title:           string
  starred:         boolean
  last_repo_url:   string | null
  selected_repos?: string[]
  updated_at:      string
}

/** Title from first meaningful user message */
export function generateTitle(messages: PersistedMessage[]): string {
  const repo = messages.find(
    (m) => m.role === 'user' && m.content?.match(/github\.com/)
  )
  if (repo) {
    const parts = (repo.content ?? '').trim().replace(/\/$/, '').split('/')
    return parts.slice(-2).join('/')
  }
  const code = messages.find(
    (m) => m.role === 'user' && (m.content ?? '').includes('\n')
  )
  if (code) {
    const first = (code.content ?? '').split('\n')[0].trim()
    return 'Review: ' + first.substring(0, 40)
  }
  return 'New review'
}

export async function createChat(userId: string): Promise<ChatMeta | null> {
  const welcome: PersistedMessage = {
    role:      'bot',
    content:   'Paste a GitHub repo URL to learn your coding style, or paste code for a personalized review.',
    type:      'text',
    timestamp: new Date().toISOString(),
  }
  const { data, error } = await supabase
    .from('user_chats')
    .insert({
      user_id:  userId,
      title:    'New review',
      messages: [welcome],
      starred:  false,
    })
    .select('id, title, starred, last_repo_url, selected_repos, updated_at')
    .single()

  if (error) { console.warn('[db] createChat failed:', error.message); return null }
  return data as ChatMeta
}

export async function loadChats(userId: string): Promise<ChatMeta[]> {
  const { data, error } = await supabase
    .from('user_chats')
    .select('id, title, starred, last_repo_url, selected_repos, updated_at')
    .eq('user_id', userId)
    .order('updated_at', { ascending: false })

  if (error) { console.warn('[db] loadChats failed:', error.message); return [] }
  return (data ?? []) as ChatMeta[]
}

export async function loadChatMessages(chatId: string): Promise<PersistedMessage[]> {
  const { data, error } = await supabase
    .from('user_chats')
    .select('messages')
    .eq('id', chatId)
    .single()

  if (error) { console.warn('[db] loadChatMessages failed:', error.message); return [] }
  return (data?.messages ?? []) as PersistedMessage[]
}

export async function saveChatMessages(
  chatId: string,
  messages: PersistedMessage[],
  lastRepoUrl: string | null,
): Promise<void> {
  const { error } = await supabase
    .from('user_chats')
    .update({
      messages:      messages,
      title:         generateTitle(messages),
      last_repo_url: lastRepoUrl,
      updated_at:    new Date().toISOString(),
    })
    .eq('id', chatId)

  if (error) console.warn('[db] saveChatMessages failed:', error.message)
}

export async function toggleChatStar(chatId: string, starred: boolean): Promise<void> {
  const { error } = await supabase
    .from('user_chats')
    .update({ starred })
    .eq('id', chatId)

  if (error) console.warn('[db] toggleChatStar failed:', error.message)
}

// ── Repo selector helpers ──────────────────────────────────────────────────────

export interface AnalyzedRepo {
  repo_url:  string
  repo_name: string
  languages: string[]
}

export async function getUserAnalyzedRepos(userId: string): Promise<AnalyzedRepo[]> {
  const { data, error } = await supabase
    .from('user_repos')
    .select('repo_url, repo_name, languages')
    .eq('user_id', userId)
    .order('analyzed_at', { ascending: false })

  if (error) { console.warn('[db] getUserAnalyzedRepos failed:', error.message); return [] }
  return (data ?? []) as AnalyzedRepo[]
}

export async function updateChatSelectedRepos(
  chatId: string,
  repoUrls: string[],
): Promise<void> {
  const { error } = await supabase
    .from('user_chats')
    .update({ selected_repos: repoUrls, updated_at: new Date().toISOString() })
    .eq('id', chatId)

  if (error) console.warn('[db] updateChatSelectedRepos failed:', error.message)
}

export async function loadChatSelectedRepos(chatId: string): Promise<string[]> {
  const { data, error } = await supabase
    .from('user_chats')
    .select('selected_repos')
    .eq('id', chatId)
    .single()

  if (error) { console.warn('[db] loadChatSelectedRepos failed:', error.message); return [] }
  const repos = data?.selected_repos
  if (Array.isArray(repos)) return repos as string[]
  return []
}
