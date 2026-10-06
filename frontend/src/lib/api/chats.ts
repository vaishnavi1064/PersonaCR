// Chats: Q&A (POST /api/chat) and helpers for the one-repo-per-chat model.
// Chat rows live in Supabase user_chats (see lib/db.ts).
import type { ChatMeta } from '../db'
import { request } from './http'

interface InsightsResponse {
  answer: string
  repos_used: string[]
  code_chunks_retrieved: number
  memory?: { current_turns: number; past_chats: number; past_turns: number }
  error?: string | null
}

export interface ChatMemory { currentTurns: number; pastChats: number; pastTurns: number }

export interface Answer {
  text: string
  /** How many repo snippets the answer drew on (0 = fingerprint + review history only). */
  snippetsUsed: number
  /** What the answer remembered: this chat's turns, and earlier chats about the same repo. */
  memory: ChatMemory
}

export interface HistoryTurn { role: 'user' | 'assistant'; content: string }

const MAX_HISTORY = 8

interface MessageLike { role: 'user' | 'bot'; type?: string; text?: string; data?: Record<string, unknown> }

/**
 * This chat's recent turns for follow-up questions (the server adds earlier chats
 * about the same repo). Code sent for review is described, not resent.
 */
export function historyFor(messages: MessageLike[]): HistoryTurn[] {
  const turns: HistoryTurn[] = []
  for (const m of messages) {
    const data = (m.data ?? {}) as { mode?: string; error?: boolean; overall_score?: number | null; issues?: unknown[] }
    if (m.role === 'user') {
      if (data.mode === 'review') {
        const lines = (m.text ?? '').split('\n').length
        turns.push({ role: 'user', content: `[Submitted ${lines} lines of code for review]` })
      } else if (m.text?.trim()) {
        turns.push({ role: 'user', content: m.text })
      }
    } else if (m.type === 'review') {
      const score = data.overall_score
      turns.push({
        role: 'assistant',
        content: `[Review result: ${score == null ? 'no score' : `score ${Math.round(score)}/100`}, ${(data.issues ?? []).length} findings]`,
      })
    } else if (m.type === 'text' && !data.error && m.text?.trim()) {
      turns.push({ role: 'assistant', content: m.text })
    }
  }
  return turns.slice(-MAX_HISTORY)
}

/** Ask a question about one repo, with this chat's history. */
export async function askQuestion(
  question: string,
  repoUrl: string,
  chatId: string | null,
  history: HistoryTurn[] = [],
): Promise<Answer> {
  const r = await request<InsightsResponse>('/api/chat', {
    method: 'POST',
    body: { message: question, selected_repo_urls: [repoUrl], chat_id: chatId, history },
    timeoutMs: 3 * 60_000,
  })
  if (r.error) throw new Error(r.error)
  return {
    text: r.answer,
    snippetsUsed: r.code_chunks_retrieved ?? 0,
    memory: {
      currentTurns: r.memory?.current_turns ?? 0,
      pastChats: r.memory?.past_chats ?? 0,
      pastTurns: r.memory?.past_turns ?? 0,
    },
  }
}

/** The repo a chat is scoped to. Older chats could select several; the first was the review target. */
export function chatRepoUrl(chat: Pick<ChatMeta, 'selected_repos' | 'primary_repo_url' | 'last_repo_url'>): string | null {
  return chat.selected_repos?.[0] ?? chat.primary_repo_url ?? chat.last_repo_url ?? null
}

export interface ChatGroup {
  repoUrl: string | null
  chats: ChatMeta[]
  /** Most recent activity in the group, for ordering. */
  updatedAt: string
}

/** Group chats by repo, most recently active group first, chats newest first. */
export function groupChatsByRepo(chats: ChatMeta[]): ChatGroup[] {
  const groups = new Map<string, ChatGroup>()
  for (const c of chats) {
    const repoUrl = chatRepoUrl(c)
    const key = repoUrl ?? ''
    const g = groups.get(key) ?? { repoUrl, chats: [], updatedAt: c.updated_at }
    g.chats.push(c)
    if (c.updated_at > g.updatedAt) g.updatedAt = c.updated_at
    groups.set(key, g)
  }
  const list = [...groups.values()]
  for (const g of list) g.chats.sort((a, b) => b.updated_at.localeCompare(a.updated_at))
  return list.sort((a, b) => {
    if (!a.repoUrl !== !b.repoUrl) return a.repoUrl ? -1 : 1 // "No repo" last
    return b.updatedAt.localeCompare(a.updatedAt)
  })
}

export function repoShortName(url: string): string {
  return url.replace(/\/+$/, '').split('/').slice(-2).join('/')
}
