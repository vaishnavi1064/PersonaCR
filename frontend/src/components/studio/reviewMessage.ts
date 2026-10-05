import type { ChatMessage } from '../../store/useStore'
import { normalizeReview, type RawReview, type Review } from '../../lib/api'

type ReviewMessageData = RawReview & { code?: string; language?: string; repo_url?: string }

/** A review chat message → domain Review + the code's language. */
export function reviewFromMessage(messages: ChatMessage[], msg: ChatMessage): { review: Review; language: string } {
  const data = (msg.data ?? {}) as unknown as ReviewMessageData
  let code = data.code
  if (!code) {
    // Older review messages didn't store the code — it's the preceding user message
    const idx = messages.indexOf(msg)
    code = messages.slice(0, idx).reverse().find((m) => m.role === 'user')?.text ?? ''
  }
  return {
    review: normalizeReview(data, { code, repoUrl: data.repo_url }),
    language: data.language ?? 'python', // legacy chats always reviewed as Python
  }
}
