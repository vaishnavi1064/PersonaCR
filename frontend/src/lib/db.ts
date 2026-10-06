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
  /** null for degraded/error reviews (older rows may still have them). */
  overall_score: number | null
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

/** Backend statuses where the pipeline could not produce a trustworthy score. */
const UNSCORED_STATUSES = new Set(['degraded', 'error'])

/** A review that has a real score and belongs in averages and trends. */
export function isScoredReview(r: { overall_score: number | null | undefined; status?: string | null }): boolean {
  return typeof r.overall_score === 'number'
    && Number.isFinite(r.overall_score)
    && !UNSCORED_STATUSES.has((r.status ?? '').toLowerCase())
}

export async function saveReview(params: {
  userId: string
  repoUrl: string
  code: string
  result: {
    overall_score: number | null
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
  // Degraded/error reviews have no trustworthy score — keep them out of history
  // and the dashboard. The chat still shows them with a retry.
  if (!isScoredReview(result)) return
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
  primary_repo_url:string | null
  selected_repos?: string[]
  updated_at:      string
}

/** Title from the first user message: the question, or "Review: <first line>". */
export function generateTitle(messages: PersistedMessage[]): string {
  const first = messages.find((m) => m.role === 'user' && (m.content ?? '').trim())
  if (!first) return 'New chat'
  const content = (first.content ?? '').trim()
  const mode = (first.data as { mode?: string } | null | undefined)?.mode

  // Legacy chats started by pasting a repo URL
  if (!mode && /^https?:\/\/github\.com\/\S+$/.test(content)) {
    return content.replace(/\/$/, '').split('/').slice(-2).join('/')
  }
  // Review: explicit mode, or a legacy multi-line code paste
  if (mode === 'review' || (!mode && content.includes('\n'))) {
    const firstLine = content.split('\n').find((l) => l.trim())?.trim() ?? ''
    return 'Review: ' + firstLine.substring(0, 40)
  }
  const oneLine = content.replace(/\s+/g, ' ')
  return oneLine.length > 60 ? oneLine.substring(0, 57) + '…' : oneLine
}

/** Create a chat scoped to one repo. Messages are saved as they arrive. */
export async function createChat(userId: string, repoUrl: string): Promise<ChatMeta | null> {
  const { data, error } = await supabase
    .from('user_chats')
    .insert({
      user_id:          userId,
      title:            'New chat',
      messages:         [],
      starred:          false,
      selected_repos:   [repoUrl],
      primary_repo_url: repoUrl,
      last_repo_url:    repoUrl,
    })
    .select('id, title, starred, last_repo_url, primary_repo_url, selected_repos, updated_at')
    .single()

  if (error) { console.warn('[db] createChat failed:', error.message); return null }
  return data as ChatMeta
}

export async function loadChats(userId: string): Promise<ChatMeta[]> {
  const { data, error } = await supabase
    .from('user_chats')
    .select('id, title, starred, last_repo_url, primary_repo_url, selected_repos, updated_at')
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
  messages: PersistedMessage[]
): Promise<void> {
  const { error } = await supabase
    .from('user_chats')
    .update({
      messages:      messages,
      title:         generateTitle(messages),
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
