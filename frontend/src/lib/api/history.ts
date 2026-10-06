// Saved reviews and chats for one repo (Supabase, read with the user's session).
// Unlike the legacy db.ts helpers these throw on failure, so a page can show an
// error instead of a misleading "nothing here yet".
import { supabase } from '../supabase'
import type { ChatMeta, ReviewRow } from '../db'
import { chatRepoUrl } from './chats'
import { normalizeReview, type RawReview } from './reviews'
import type { Review } from './types'

/** Saved rows keep only the first 500 characters of the submitted code (db.ts saveReview). */
export const SAVED_CODE_LIMIT = 500

function urlVariants(url: string): string[] {
  const clean = url.replace(/\/+$/, '')
  return [clean, `${clean}/`]
}

export async function fetchRepoReviews(userId: string, repoUrl: string): Promise<ReviewRow[]> {
  const { data, error } = await supabase
    .from('user_reviews')
    .select('*')
    .eq('user_id', userId)
    .in('repo_url', urlVariants(repoUrl))
    .order('created_at', { ascending: false })
  if (error) throw new Error(error.message)
  return (data ?? []) as ReviewRow[]
}

export async function fetchRepoChats(userId: string, repoUrl: string): Promise<ChatMeta[]> {
  const { data, error } = await supabase
    .from('user_chats')
    .select('id, title, starred, last_repo_url, primary_repo_url, selected_repos, updated_at')
    .eq('user_id', userId)
    .order('updated_at', { ascending: false })
  if (error) throw new Error(error.message)
  const want = new Set(urlVariants(repoUrl))
  return ((data ?? []) as ChatMeta[]).filter((c) => {
    const u = chatRepoUrl(c)
    return u != null && want.has(u)
  })
}

/** One saved review; null when it doesn't exist or isn't this user's (RLS). */
export async function fetchSavedReview(id: string): Promise<ReviewRow | null> {
  const { data, error } = await supabase.from('user_reviews').select('*').eq('id', id).maybeSingle()
  if (error) throw new Error(error.message)
  return (data as ReviewRow | null) ?? null
}

/** Saved row → domain Review. Confidence and retrieval counts weren't saved, so they stay null. */
export function reviewFromRow(row: ReviewRow): { review: Review; codeTruncated: boolean } {
  const raw: RawReview = {
    overall_score: row.overall_score,
    status: row.status,
    iterations: row.iterations,
    issues: row.issues as RawReview['issues'],
    agent_trace: row.agent_trace as unknown as RawReview['agent_trace'],
    review_output: {
      style_score: row.style_score,
      defect_score: row.defect_score,
      quality_scores: { comprehensiveness: row.comprehensiveness, conciseness: row.conciseness, relevance: row.relevance },
    },
  }
  const code = row.submitted_code ?? ''
  return {
    review: normalizeReview(raw, { code, repoUrl: row.repo_url, id: row.id, createdAt: row.created_at }),
    codeTruncated: code.length >= SAVED_CODE_LIMIT,
  }
}
