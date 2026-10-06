import { lazy, Suspense, useRef, useState, type KeyboardEvent } from 'react'
import { ArrowUp, Code2, History, MessageSquare } from 'lucide-react'
import { capabilities, REVIEW_LANGUAGES, type ChatMode } from '../../lib/api'
import { cn } from '../../lib/cn'
import Button from '../ui/Button'
import FilterSelect from '../ui/FilterSelect'
import ComingSoon from '../ui/ComingSoon'

const CodeEditor = lazy(() => import('../ui/CodeEditor'))

interface ComposerProps {
  mode: ChatMode
  onModeChange: (mode: ChatMode) => void
  repoName: string | null
  /** Busy (answer/review running) or not ready (no repo). */
  busy: boolean
  defaultLanguage: string
  onAsk: (question: string) => void
  onReview: (code: string, language: string) => void
  /** Guests have no saved chats, so memory covers this chat only. */
  guest?: boolean
}

/** Bottom composer: "Ask a question" textarea or "Review code" editor. */
export default function Composer({ mode, onModeChange, repoName, busy, defaultLanguage, onAsk, onReview, guest }: ComposerProps) {
  const [question, setQuestion] = useState('')
  const [code, setCode] = useState('')
  const [language, setLanguage] = useState(defaultLanguage)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const noRepo = !repoName
  const canAsk = !busy && !noRepo && question.trim().length > 0
  const canReview = !busy && !noRepo && code.trim().length > 0
  const lines = code ? code.replace(/\n$/, '').split('\n').length : 0

  function ask() {
    if (!canAsk) return
    onAsk(question.trim())
    setQuestion('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  function review() {
    if (!canReview) return
    onReview(code, language)
    setCode('')
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); ask() }
  }

  function autoGrow() {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`
  }

  return (
    <div className="border-t border-line bg-canvas px-4 pb-4 pt-3 sm:px-6">
      <div className="mx-auto w-full max-w-3xl">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <div role="radiogroup" aria-label="Mode" className="inline-flex rounded-lg border border-line p-0.5">
            {([['ask', 'Ask a question', MessageSquare], ['review', 'Review code', Code2]] as const).map(([m, label, Icon]) => (
              <button
                key={m}
                type="button"
                role="radio"
                aria-checked={mode === m}
                onClick={() => onModeChange(m)}
                className={cn(
                  'flex h-7 items-center gap-1.5 rounded-md px-2.5 text-[13px] cursor-pointer',
                  mode === m ? 'bg-surface-hover font-medium text-fg shadow-[inset_0_0_0_1px_var(--border)]' : 'text-fg-3 hover:text-fg',
                )}
              >
                <Icon size={13} aria-hidden /> {label}
              </button>
            ))}
          </div>
          {capabilities.repoChatMemory.level !== 'available' ? (
            <ComingSoon compact feature="Remembers past chats for this repo" />
          ) : (
            <span className="inline-flex items-center gap-1.5 text-xs text-fg-3" title="Answers use this chat and your earlier chats about the same repo — never other repos">
              <History size={12} aria-hidden />
              {guest ? 'Remembers this chat (guest chats aren’t saved)' : 'Remembers earlier chats about this repo'}
            </span>
          )}
        </div>

        {mode === 'ask' ? (
          <div className={cn('flex items-end gap-2 rounded-xl border bg-surface py-2 pl-3.5 pr-2', noRepo ? 'border-line opacity-70' : 'border-line focus-within:border-accent')}>
            <label htmlFor="ask-input" className="sr-only">Question</label>
            <textarea
              id="ask-input"
              ref={textareaRef}
              rows={1}
              value={question}
              onChange={(e) => { setQuestion(e.target.value); autoGrow() }}
              onKeyDown={onKeyDown}
              disabled={noRepo}
              placeholder={noRepo ? 'Choose a repo above to start' : `Ask about ${repoName}’s code and conventions…`}
              className="max-h-[200px] min-h-[24px] flex-1 resize-none bg-transparent py-1 text-sm leading-6 text-fg placeholder:text-fg-3 focus:outline-none disabled:cursor-not-allowed"
            />
            <button
              type="button"
              onClick={ask}
              disabled={!canAsk}
              aria-label="Send question"
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent-strong text-on-accent cursor-pointer hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ArrowUp size={16} aria-hidden />
            </button>
          </div>
        ) : (
          <div className={cn('overflow-hidden rounded-xl border bg-canvas', noRepo ? 'border-line opacity-70' : 'border-line focus-within:border-accent')}>
            <Suspense fallback={<div className="h-[168px] animate-pulse bg-surface" aria-hidden />}>
              <CodeEditor
                value={code}
                onChange={setCode}
                language={language}
                onSubmit={review}
                disabled={noRepo || busy}
                ariaLabel="Code to review"
                placeholder={noRepo ? 'Choose a repo above to start' : `Paste code to review against ${repoName}’s style…`}
              />
            </Suspense>
            <div className="flex flex-wrap items-center gap-2 border-t border-line bg-surface px-2.5 py-2">
              <FilterSelect label="Language" value={language} options={[...REVIEW_LANGUAGES]} onChange={setLanguage} />
              <span className="hidden text-xs text-fg-3 sm:inline">
                {lines > 0 ? `${lines} line${lines === 1 ? '' : 's'} · ` : ''}Ctrl+Enter to review · Esc then Tab leaves the editor
              </span>
              <Button variant="primary" size="sm" className="ml-auto" onClick={review} disabled={!canReview}>
                Review code
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
