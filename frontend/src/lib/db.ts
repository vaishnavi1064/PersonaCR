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
  id:            string
  title:         string
  starred:       boolean
  last_repo_url: string | null
  updated_at:    string
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
    .select('id, title, starred, last_repo_url, updated_at')
    .single()

  if (error) { console.warn('[db] createChat failed:', error.message); return null }
  return data as ChatMeta
}

export async function loadChats(userId: string): Promise<ChatMeta[]> {
  const { data, error } = await supabase
    .from('user_chats')
    .select('id, title, starred, last_repo_url, updated_at')
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
