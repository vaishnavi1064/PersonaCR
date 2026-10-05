// Chats: Q&A (POST /api/chat) and helpers for the one-repo-per-chat model.
// Chat rows live in Supabase user_chats (see lib/db.ts).
import type { ChatMeta } from '../db'
import { request } from './http'

interface InsightsResponse {
  answer: string
  repos_used: string[]
  code_chunks_retrieved: number
}

export interface Answer {
  text: string
  /** How many repo snippets the answer drew on (0 = fingerprint + review history only). */
  snippetsUsed: number
}

/** Ask a question about one repo. The backend ignores chatId today (capability repoChatMemory). */
export async function askQuestion(question: string, repoUrl: string, userId: string, chatId: string | null): Promise<Answer> {
  const r = await request<InsightsResponse>('/api/chat', {
    method: 'POST',
    body: { message: question, selected_repo_urls: [repoUrl], user_id: userId, chat_id: chatId },
    timeoutMs: 3 * 60_000,
  })
  return { text: r.answer, snippetsUsed: r.code_chunks_retrieved ?? 0 }
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
