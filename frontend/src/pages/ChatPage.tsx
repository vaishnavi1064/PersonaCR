import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Code2, PanelLeft, Plus, X } from 'lucide-react'
import { useStore } from '../store/useStore'
import type { ChatMessage, PersistedMessage } from '../store/useStore'
import { toUI, toPersisted } from '../store/useStore'
import {
  ApiError, askQuestion, chatRepoUrl, cleanupGuestOnUnload, historyFor, isAccountUserId, repoShortName, reviewCode,
  REVIEW_LANGUAGES, topLanguages, type ChatMode, type Finding,
} from '../lib/api'
import {
  createChat, generateTitle, loadChatMessages, loadChats, saveChatMessages, saveReview, updateChatSelectedRepos,
} from '../lib/db'
import { useCurrentUser } from '../lib/useCurrentUser'
import { useUserRepos } from '../lib/useUserRepos'
import Button from '../components/ui/Button'
import IconButton from '../components/ui/IconButton'
import ThreadList from '../components/studio/ThreadList'
import RepoPicker from '../components/studio/RepoPicker'
import MessageStream, { type Pending } from '../components/studio/MessageStream'
import Composer from '../components/studio/Composer'
import CodePanel from '../components/studio/CodePanel'
import { reviewFromMessage } from '../components/studio/reviewMessage'

// Chat/Review Studio: threads grouped by repo | messages | code panel.
// One repo per chat: selectedRepoUrls holds at most one URL (older chats may
// hold several — index 0 is the chat's repo and the review target).

const GUEST_KEY = '__guest'

function uid() { return Math.random().toString(36).slice(2, 9) }

function makeUserMsg(text: string, data: Record<string, unknown>): ChatMessage {
  return { id: uid(), role: 'user', text, type: 'text', data }
}
function makeBotMsg(type: 'text' | 'review', text?: string, data?: Record<string, unknown>): ChatMessage {
  return { id: uid(), role: 'bot', type, text, data }
}

function errorText(err: unknown, action: 'ask' | 'review'): string {
  if (err instanceof ApiError) {
    if (err.kind === 'network') return 'Could not reach the PersonaCR server. Is the backend running?'
    if (err.kind === 'timeout') return `${err.message}. Try a smaller piece of code.`
    if (action === 'review' && err.status === 503) {
      return 'Reviews are unavailable right now — the background job queue is offline. Try again shortly.'
    }
    if (err.status === 404 && /fingerprint/i.test(err.message)) {
      return 'This repo has no saved analysis on the server, so it can’t be reviewed yet. Reanalyze it from Repositories while signed in.'
    }
    return `${action === 'review' ? 'Review' : 'Answer'} failed: ${err.message}`
  }
  return err instanceof Error ? err.message : String(err)
}

const isWide = () => window.matchMedia('(min-width: 1280px)').matches

export default function ChatPage() {
  const {
    activeChatId, setActiveChatId,
    activeMessages, setActiveMessages, appendMessage,
    chats, setChats, upsertChatMeta,
    selectedRepoUrlsByChatId, setSelectedRepoUrls,
    clearNewChatRequest,
  } = useStore()
  const { userId, guestMode } = useCurrentUser()
  const account = isAccountUserId(userId)
  const { repos, loading: reposLoading } = useUserRepos(userId)

  const [initDone, setInitDone] = useState(() => !account)
  const [loadingChat, setLoadingChat] = useState(false)
  const [pending, setPending] = useState<Pending | null>(null)
  const [selectedRepoUrls, setSelectedRepoUrlsLocal] = useState<string[]>(
    () => (account ? [] : selectedRepoUrlsByChatId[GUEST_KEY] ?? []),
  )
  const [mode, setMode] = useState<ChatMode>('ask')
  const [panelReviewId, setPanelReviewId] = useState<string | null>(null)
  const [activeFindingId, setActiveFindingId] = useState<string | null>(null)
  const [threadsOpen, setThreadsOpen] = useState(false)
  const [codeOpen, setCodeOpen] = useState(false)
  const [composerKey, setComposerKey] = useState(0)

  const persistedRef = useRef<PersistedMessage[]>([])
  const chatIdRef = useRef<string | null>(null)
  const pendingRef = useRef(false)
  useEffect(() => { pendingRef.current = pending != null }, [pending])

  const repoUrl = selectedRepoUrls[0] ?? null
  const repo = repos.find((r) => r.url === repoUrl) ?? null
  const locked = activeMessages.some((m) => m.role === 'user')

  // Wipe guest ChromaDB collections when the tab closes
  useEffect(() => {
    if (!guestMode) return
    const cleanup = () => cleanupGuestOnUnload(userId)
    window.addEventListener('beforeunload', cleanup)
    return () => window.removeEventListener('beforeunload', cleanup)
  }, [guestMode, userId])

  // ── Loading / switching chats ───────────────────────────────────────────────
  const resetView = useCallback(() => {
    setMode('ask')
    setPanelReviewId(null)
    setActiveFindingId(null)
    setComposerKey((k) => k + 1)
  }, [])

  const loadInto = useCallback(async (id: string, list: typeof chats) => {
    setActiveChatId(id)
    chatIdRef.current = id
    const meta = list.find((c) => c.id === id)
    const persisted = await loadChatMessages(id)
    if (chatIdRef.current !== id) return
    persistedRef.current = persisted
    setActiveMessages(persisted.map(toUI))
    const selected = meta?.selected_repos?.length ? meta.selected_repos : [meta && chatRepoUrl(meta)].filter((u): u is string => !!u)
    setSelectedRepoUrlsLocal(selected)
    resetView()
  }, [setActiveChatId, setActiveMessages, resetView])

  const startNewChat = useCallback((initialRepoUrl?: string | null) => {
    chatIdRef.current = null
    persistedRef.current = []
    setActiveChatId(null)
    setActiveMessages([])
    const next = initialRepoUrl ? [initialRepoUrl] : []
    setSelectedRepoUrlsLocal(next)
    if (!account) setSelectedRepoUrls(GUEST_KEY, next)
    resetView()
  }, [account, setActiveChatId, setActiveMessages, setSelectedRepoUrls, resetView])

  // Init: account users get their saved chats; open the active (or most recent) one
  useEffect(() => {
    if (!account) return
    let cancelled = false
    async function init() {
      const fetched = await loadChats(userId)
      if (cancelled) return
      setChats(fetched)
      const target = activeChatId && fetched.some((c) => c.id === activeChatId) ? activeChatId : fetched[0]?.id ?? null
      if (target) await loadInto(target, fetched)
      else startNewChat()
      if (!cancelled) setInitDone(true)
    }
    init()
    return () => { cancelled = true }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [account, userId])

  // "New chat" from the app rail / a repo card
  useEffect(() => {
    if (!initDone) return
    const handle = (requested: boolean) => {
      if (!requested) return
      const url = useStore.getState().newChatRepoUrl
      clearNewChatRequest()
      if (pendingRef.current) return
      startNewChat(url)
    }
    queueMicrotask(() => handle(useStore.getState().newChatRequested))
    return useStore.subscribe((s, prev) => {
      if (s.newChatRequested && !prev.newChatRequested) handle(true)
    })
  }, [initDone, clearNewChatRequest, startNewChat])

  function openChat(id: string) {
    setThreadsOpen(false)
    if (pending || id === chatIdRef.current) return
    setLoadingChat(true)
    loadInto(id, chats).finally(() => setLoadingChat(false))
  }

  function newChatFromPane(url?: string) {
    setThreadsOpen(false)
    if (!pending) startNewChat(url ?? null)
  }

  // ── Persistence ────────────────────────────────────────────────────────────
  const ensureChat = useCallback(async (url: string): Promise<string | null> => {
    if (chatIdRef.current || !account) return chatIdRef.current
    const meta = await createChat(userId, url)
    if (meta) {
      upsertChatMeta(meta)
      setActiveChatId(meta.id)
      chatIdRef.current = meta.id
      setSelectedRepoUrls(meta.id, [url])
    }
    return chatIdRef.current
  }, [account, userId, upsertChatMeta, setActiveChatId, setSelectedRepoUrls])

  const addMessage = useCallback(async (msg: ChatMessage, rawText?: string) => {
    appendMessage(msg)
    persistedRef.current = [...persistedRef.current, toPersisted(msg, rawText)]
    const cid = chatIdRef.current
    if (!cid) return
    const messages = persistedRef.current
    await saveChatMessages(cid, messages)
    const meta = useStore.getState().chats.find((c) => c.id === cid)
    if (meta) upsertChatMeta({ ...meta, title: generateTitle(messages), updated_at: new Date().toISOString() })
  }, [appendMessage, upsertChatMeta])

  // ── Actions ────────────────────────────────────────────────────────────────
  function selectRepo(url: string) {
    if (locked) return
    setSelectedRepoUrlsLocal([url])
    if (!account) setSelectedRepoUrls(GUEST_KEY, [url])
    const cid = chatIdRef.current
    if (cid) { setSelectedRepoUrls(cid, [url]); updateChatSelectedRepos(cid, [url]) }
    setComposerKey((k) => k + 1) // default review language follows the repo
  }

  async function handleAsk(text: string) {
    if (!repoUrl || pending) return
    setPending({ kind: 'ask', startedAt: Date.now() })
    try {
      // This chat's turns before the new question (the server adds earlier chats about this repo)
      const history = historyFor(useStore.getState().activeMessages)
      const cid = await ensureChat(repoUrl)
      await addMessage(makeUserMsg(text, { mode: 'ask' }), text)
      const answer = await askQuestion(text, repoUrl, cid, history)
      await addMessage(makeBotMsg('text', answer.text, { snippetsUsed: answer.snippetsUsed, memory: answer.memory }))
    } catch (err) {
      await addMessage(makeBotMsg('text', errorText(err, 'ask'), { error: true }))
    } finally {
      setPending(null)
    }
  }

  async function runReview(code: string, language: string, opts: { retryOf?: string } = {}) {
    // The chat's repo is the review target (selected[0])
    const reviewTarget = selectedRepoUrls[0] ?? null
    if (!reviewTarget || pending) return
    setPending({ kind: 'review', startedAt: Date.now() })
    try {
      await ensureChat(reviewTarget)
      // A retry re-runs the code already in the chat — no second copy of it
      if (!opts.retryOf) await addMessage(makeUserMsg(code, { mode: 'review', language }), code)
      // Runs on the background worker; show "queued" until a worker picks it up
      const raw = await reviewCode(reviewTarget, code, language, {
        onProgress: ({ state }) => setPending((p) => p && p.kind === 'review'
          ? { ...p, queued: state === 'queued', queuedAt: state === 'queued' ? p.queuedAt ?? Date.now() : p.queuedAt }
          : p),
      })
      const msg = makeBotMsg('review', undefined, { ...raw, code, language, repo_url: reviewTarget, retry_of: opts.retryOf ?? null })
      await addMessage(msg)
      setPanelReviewId(msg.id)
      setActiveFindingId(null)
      // Degraded/error reviews are skipped inside saveReview
      if (account) saveReview({ userId, repoUrl: reviewTarget, code, result: raw as Parameters<typeof saveReview>[0]['result'] })
    } catch (err) {
      await addMessage(makeBotMsg('text', errorText(err, 'review'), { error: true }))
    } finally {
      setPending(null)
    }
  }

  function handleReview(code: string, language: string) {
    return runReview(code, language)
  }

  function handleRetryReview(messageId: string) {
    const msg = activeMessages.find((m) => m.id === messageId)
    if (!msg) return
    const { review, language } = reviewFromMessage(activeMessages, msg)
    if (review.code) runReview(review.code, language, { retryOf: messageId })
  }

  // ── Code panel data ─────────────────────────────────────────────────────────
  const reviewMessages = useMemo(() => activeMessages.filter((m) => m.type === 'review'), [activeMessages])
  const panelMsg = reviewMessages.find((m) => m.id === panelReviewId) ?? reviewMessages.at(-1) ?? null

  const panel = useMemo(() => (panelMsg ? reviewFromMessage(activeMessages, panelMsg) : null), [panelMsg, activeMessages])

  const reviewOptions = reviewMessages.map((m, i) => ({ id: m.id, label: `Review ${i + 1} of ${reviewMessages.length}` }))

  function showReview(id: string) {
    setPanelReviewId(id)
    setActiveFindingId(null)
    if (!isWide()) setCodeOpen(true)
  }

  function selectFinding(f: Finding) {
    setActiveFindingId((cur) => (cur === f.id ? null : f.id))
  }

  const defaultLanguage = useMemo(() => {
    const top = repo ? topLanguages(repo, 1)[0]?.toLowerCase() : undefined
    return REVIEW_LANGUAGES.some((l) => l.value === top) ? top! : 'python'
  }, [repo])

  const busyReason = pending ? 'Wait for the current answer or review to finish' : null
  const findingsCount = panel?.review.findings.length ?? 0

  const codePanelProps = {
    review: panel?.review ?? null,
    language: panel?.language ?? null,
    options: reviewOptions,
    selectedId: panelMsg?.id ?? null,
    onSelectReview: (id: string) => { setPanelReviewId(id); setActiveFindingId(null) },
    activeFindingId,
    onSelectFinding: selectFinding,
  }

  const threadsPane = (
    <>
      <div className="flex h-12 shrink-0 items-center justify-between border-b border-line px-4">
        <h2 className="text-sm font-semibold text-fg">Chats</h2>
        <IconButton label="New chat" icon={<Plus size={16} />} size="sm" onClick={() => newChatFromPane()} disabled={!!pending} />
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-1.5 py-3">
        {account ? (
          chats.length > 0
            ? <ThreadList chats={chats} activeChatId={activeChatId} onOpen={openChat} onNewInRepo={newChatFromPane} disabledReason={busyReason} />
            : <p className="px-3 text-xs text-fg-3">{initDone ? 'No chats yet. Pick a repo and ask something.' : 'Loading chats…'}</p>
        ) : (
          <p className="px-3 text-xs text-fg-3">Guest chats aren’t saved — this one lasts until you leave the page.</p>
        )}
      </div>
    </>
  )

  return (
    <div className="flex h-full min-h-0">
      {/* Threads, grouped by repo */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-line bg-sidebar md:flex" aria-label="Chat threads">
        {threadsPane}
      </aside>
      {threadsOpen && (
        <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true" aria-label="Chat threads">
          <div className="absolute inset-0 bg-black/50" onClick={() => setThreadsOpen(false)} aria-hidden />
          <aside className="relative flex h-full w-72 max-w-[85vw] flex-col border-r border-line bg-sidebar shadow-pop">
            <div className="absolute right-2 top-2"><IconButton label="Close chats" icon={<X size={16} />} size="sm" onClick={() => setThreadsOpen(false)} /></div>
            {threadsPane}
          </aside>
        </div>
      )}

      {/* Messages */}
      <section className="flex min-w-0 flex-1 flex-col" aria-label="Conversation">
        <div className="flex h-12 shrink-0 items-center gap-2 border-b border-line px-3 sm:px-4">
          <IconButton label="Show chats" icon={<PanelLeft size={16} />} size="sm" className="md:hidden" onClick={() => setThreadsOpen(true)} />
          <RepoPicker repos={repos} value={repoUrl} onChange={selectRepo} locked={locked} loading={reposLoading} />
          {selectedRepoUrls.length > 1 && (
            <span className="hidden text-xs text-fg-3 sm:inline" title={selectedRepoUrls.map(repoShortName).join(', ')}>
              Older chat — only {repoShortName(selectedRepoUrls[0])} is used
            </span>
          )}
          <div className="ml-auto xl:hidden">
            <Button size="sm" icon={<Code2 size={14} />} onClick={() => setCodeOpen(true)}>
              Code{findingsCount > 0 ? ` · ${findingsCount}` : ''}
            </Button>
          </div>
        </div>

        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
          <MessageStream
            messages={activeMessages}
            pending={pending}
            repoName={repoUrl ? repoShortName(repoUrl) : null}
            activeReviewId={panelMsg?.id ?? null}
            onShowReview={showReview}
            onRetryReview={handleRetryReview}
            onSuggestion={(s) => handleAsk(s)}
            loading={!initDone || loadingChat}
          />
        </div>

        <Composer
          key={`${composerKey}:${repoUrl ?? ''}`}
          mode={mode}
          onModeChange={setMode}
          repoName={repoUrl ? repoShortName(repoUrl) : null}
          busy={!!pending || !initDone || loadingChat}
          defaultLanguage={defaultLanguage}
          onAsk={handleAsk}
          onReview={handleReview}
          guest={!account}
        />
        {guestMode && (
          <p className="border-t border-line bg-canvas px-4 py-1.5 text-center text-[11px] text-fg-3">Guest session — this chat isn’t saved.</p>
        )}
      </section>

      {/* Code panel */}
      <CodePanel className="hidden w-[min(46%,620px)] shrink-0 border-l border-line xl:flex" {...codePanelProps} />
      {codeOpen && (
        <div className="fixed inset-0 z-40 xl:hidden" role="dialog" aria-modal="true" aria-label="Code panel">
          <div className="absolute inset-0 bg-black/50" onClick={() => setCodeOpen(false)} aria-hidden />
          <CodePanel className="absolute inset-y-0 right-0 flex w-full max-w-2xl border-l border-line shadow-pop" {...codePanelProps} onClose={() => setCodeOpen(false)} />
        </div>
      )}
    </div>
  )
}
