import { useEffect, useMemo, useRef } from 'react'
import { Code2, History, Loader2, TriangleAlert } from 'lucide-react'
import type { ChatMessage } from '../../store/useStore'
import { REVIEW_LANGUAGES, type ChatMemory } from '../../lib/api'
import { elapsed } from '../../lib/format'
import { useNow } from '../../lib/useNow'
import { cn } from '../../lib/cn'
import { LogoMark } from '../ui/Logo'
import ReviewSummary from '../review/ReviewSummary'
import { reviewFromMessage } from './reviewMessage'
import FingerprintCard from '../chat/FingerprintCard'
import RichText from './RichText'

export interface Pending { kind: 'ask' | 'review'; startedAt: number }

interface MessageStreamProps {
  messages: ChatMessage[]
  pending: Pending | null
  repoName: string | null
  /** Review message shown in the code panel. */
  activeReviewId: string | null
  onShowReview: (messageId: string) => void
  /** Re-run a degraded/error review. */
  onRetryReview: (messageId: string) => void
  onSuggestion: (text: string) => void
  loading?: boolean
}

const SUGGESTIONS = [
  'What naming conventions does this repo follow?',
  'How does this repo usually handle errors?',
  'Where are docstrings and type hints used most?',
]

export default function MessageStream({
  messages, pending, repoName, activeReviewId, onShowReview, onRetryReview, onSuggestion, loading,
}: MessageStreamProps) {
  const bottom = useRef<HTMLDivElement>(null)
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [messages.length, pending])

  if (loading) {
    return (
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-6 sm:px-6" aria-busy>
        {[0, 1, 2].map((i) => <div key={i} className={cn('h-14 animate-pulse rounded-xl bg-surface', i % 2 ? 'ml-auto w-2/3' : 'w-3/4')} />)}
      </div>
    )
  }

  if (messages.length === 0 && !pending) {
    return (
      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center px-4 py-10 text-center sm:px-6">
        <LogoMark size={34} innerFill="var(--bg-primary)" />
        <h2 className="mt-4 text-xl font-semibold tracking-tight text-fg">
          {repoName ? `Ask about ${repoName}, or review code against its style` : 'Choose a repo to start'}
        </h2>
        <p className="mt-1.5 max-w-md text-sm text-fg-3">
          {repoName
            ? 'Answers draw on the repo’s fingerprint, your past reviews, and matching code. Reviews run six agents and show findings next to the lines they’re about.'
            : 'Each chat is about one repo you’ve imported. Pick it above — it’s locked once the chat starts.'}
        </p>
        {repoName && (
          <div className="mt-5 flex flex-wrap justify-center gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => onSuggestion(s)}
                className="rounded-full border border-line bg-surface px-3 py-1.5 text-[13px] text-fg-2 cursor-pointer hover:border-line-strong hover:text-fg"
              >
                {s}
              </button>
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-5 px-4 py-6 sm:px-6" role="log" aria-live="polite" aria-relevant="additions">
      {messages.map((m) => (m.role === 'user'
        ? <UserBubble key={m.id} message={m} />
        : (
          <BotBubble
            key={m.id}
            message={m}
            messages={messages}
            active={m.id === activeReviewId}
            onShowReview={onShowReview}
            onRetryReview={onRetryReview}
            busy={pending != null}
          />
        )))}
      {pending && <PendingBubble pending={pending} />}
      <div ref={bottom} />
    </div>
  )
}

function UserBubble({ message }: { message: ChatMessage }) {
  const data = (message.data ?? {}) as { mode?: string; language?: string }
  const text = message.text ?? ''
  // Legacy chats: multi-line code pastes had no mode
  const isCode = data.mode === 'review' || (!data.mode && text.includes('\n') && /\b(def|function|class|import|const|public)\b/.test(text))
  if (isCode) {
    const lines = text.replace(/\n$/, '').split('\n')
    const lang = REVIEW_LANGUAGES.find((l) => l.value === data.language)?.label
    return (
      <div className="ml-auto w-full max-w-[85%] overflow-hidden rounded-xl border border-line bg-surface">
        <p className="flex items-center gap-1.5 border-b border-line px-3 py-1.5 text-xs text-fg-3">
          <Code2 size={12} aria-hidden /> Code for review{lang ? ` · ${lang}` : ''} · {lines.length} line{lines.length === 1 ? '' : 's'}
        </p>
        <pre className="relative max-h-40 overflow-hidden px-3 py-2 font-mono text-[12.5px] leading-6 text-fg-2">
          {lines.slice(0, 8).join('\n')}
          {lines.length > 8 && <span className="pointer-events-none absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-surface to-transparent" />}
        </pre>
      </div>
    )
  }
  return (
    <div className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-raised px-3.5 py-2 text-sm leading-6 text-fg whitespace-pre-wrap break-words">
      {text}
    </div>
  )
}

function BotAvatar() {
  return (
    <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-line bg-surface" aria-hidden>
      <LogoMark size={13} innerFill="var(--bg-card)" />
    </span>
  )
}

function BotBubble({ message, messages, active, onShowReview, onRetryReview, busy }: {
  message: ChatMessage
  messages: ChatMessage[]
  active: boolean
  onShowReview: (id: string) => void
  onRetryReview: (id: string) => void
  busy: boolean
}) {
  const data = (message.data ?? {}) as Record<string, unknown>
  return (
    <div className="flex gap-3">
      <BotAvatar />
      <div className="min-w-0 flex-1">
        {message.type === 'review' ? (
          <ReviewCard message={message} messages={messages} active={active} onShowReview={onShowReview} onRetryReview={onRetryReview} busy={busy} />
        ) : message.type === 'fingerprint' ? (
          <FingerprintCard data={data as never} />
        ) : data.error ? (
          <p className="flex items-start gap-2 rounded-xl border border-danger/30 bg-danger/10 px-3.5 py-2.5 text-sm text-fg-2" role="alert">
            <TriangleAlert size={15} className="mt-0.5 shrink-0 text-danger" aria-hidden />
            <span>{message.text}</span>
          </p>
        ) : (
          <>
            <RichText text={message.text ?? ''} />
            <MemoryNote memory={(data.memory ?? null) as ChatMemory | null} />
          </>
        )}
      </div>
    </div>
  )
}

function ReviewCard({ message, messages, active, onShowReview, onRetryReview, busy }: {
  message: ChatMessage
  messages: ChatMessage[]
  active: boolean
  onShowReview: (id: string) => void
  onRetryReview: (id: string) => void
  busy: boolean
}) {
  const { review } = useMemo(() => reviewFromMessage(messages, message), [messages, message])
  const unscored = review.state === 'degraded' || review.state === 'error'
  return (
    <div className={cn('rounded-xl border bg-surface p-4', active ? 'border-accent/50' : 'border-line')}>
      <ReviewSummary
        review={review}
        active={active}
        onOpenCode={() => onShowReview(message.id)}
        onRetry={unscored && review.code ? () => onRetryReview(message.id) : undefined}
        retryDisabled={busy}
      />
    </div>
  )
}

/** What an answer remembered — so "it knew that from last week" is never a mystery. */
function MemoryNote({ memory }: { memory: ChatMemory | null }) {
  if (!memory || (memory.pastChats === 0 && memory.currentTurns === 0)) return null
  const parts: string[] = []
  if (memory.pastChats > 0) parts.push(`${memory.pastChats} earlier chat${memory.pastChats === 1 ? '' : 's'} about this repo`)
  if (memory.currentTurns > 0) parts.push('earlier messages in this chat')
  return (
    <p className="mt-1.5 inline-flex items-center gap-1.5 text-[11px] text-fg-3">
      <History size={11} aria-hidden /> Remembered {parts.join(' and ')}
    </p>
  )
}

function PendingBubble({ pending }: { pending: Pending }) {
  const now = useNow(true)
  return (
    <div className="flex gap-3" role="status">
      <BotAvatar />
      <div className="text-sm text-fg-2">
        <p className="flex items-center gap-2">
          <Loader2 size={14} className="animate-spin text-accent" aria-hidden />
          {pending.kind === 'review' ? 'Reviewing' : 'Thinking'}… {elapsed(now - pending.startedAt)} elapsed
        </p>
        {pending.kind === 'review' && (
          <p className="mt-1 text-xs text-fg-3">
            Planner → Style Analyst ∥ Defect Hunter → QA Checker → Confidence → CRScore quality gate.
          </p>
        )}
      </div>
    </div>
  )
}
