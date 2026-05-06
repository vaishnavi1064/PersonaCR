import { useState, useCallback, useEffect, useRef } from 'react'
import { useStore } from '../store/useStore'
import type { ChatMessage, PersistedMessage } from '../store/useStore'
import { toUI, toPersisted } from '../store/useStore'
import Sidebar from '../components/layout/Sidebar'
import TopBar from '../components/layout/TopBar'
import MessageList from '../components/chat/MessageList'
import ChatInput from '../components/chat/ChatInput'
import RepoSelector from '../components/chat/RepoSelector'
import { analyzeRepo, reviewCode, cleanupGuestSession, chatWithInsights } from '../lib/api'
import { saveReview, saveRepo } from '../lib/db'
import {
  createChat, loadChats, loadChatMessages,
  saveChatMessages, generateTitle,
  updateChatSelectedRepos, loadChatSelectedRepos,
} from '../lib/db'
import { supabase } from '../lib/supabase'

// ── Constants ─────────────────────────────────────────────────────────────────
const GH_REGEX = /https?:\/\/github\.com\/[\w-]+\/[\w.-]+/

function isCodeSnippet(text: string) {
  return (
    text.includes('\n') &&
    /\b(def |function |class |import |const |let |var |public |private )\b/.test(text)
  )
}

function uid() { return Math.random().toString(36).slice(2, 9) }

function makeUserMsg(text: string): ChatMessage {
  return { id: uid(), role: 'user', text, type: 'text' }
}
function makeBotMsg(
  type: 'text' | 'fingerprint' | 'review',
  text?: string,
  data?: Record<string, unknown>,
): ChatMessage {
  return { id: uid(), role: 'bot', type, text, data }
}

/** Generate a chat title from the selected repo URLs (simple rule, no LLM). */
function repoSelectionTitle(urls: string[]): string | null {
  if (urls.length === 0) return null
  const names = urls.map((u) => {
    const parts = u.replace(/\/$/, '').split('/')
    return parts[parts.length - 1] || parts.slice(-2).join('/')
  })
  if (names.length === 1) return names[0]
  if (names.length === 2) return `${names[0]} + ${names[1]}`
  return `${names[0]} + ${names.length - 1} more`
}

// ── Main component ────────────────────────────────────────────────────────────
export default function ChatPage() {
  const {
    activeChatId, setActiveChatId,
    activeMessages, setActiveMessages, appendMessage,
    lastAnalyzedRepo, setLastAnalyzedRepo,
    chats, setChats, upsertChatMeta, updateChatTitle,
    user, isGuest, guestSessionId,
    selectedRepoUrlsByChatId, setSelectedRepoUrls,
  } = useStore()

  // Resolve user ID: real Supabase UUID for logged-in users, guest session ID for guests
  const userId = (user as { id?: string } | null)?.id ?? guestSessionId ?? 'anonymous'

  const [loading,    setLoading]    = useState(false)
  const [initDone,   setInitDone]   = useState(false)
  const [selectedRepoUrls, setSelectedRepoUrlsLocal] = useState<string[]>([])

  // Track persisted messages for the active chat (mirrors activeMessages but in Supabase shape)
  const persistedRef = useRef<PersistedMessage[]>([])
  const chatIdRef    = useRef<string | null>(null)

  // Wipe guest ChromaDB collection when tab closes
  useEffect(() => {
    if (!isGuest || !guestSessionId) return
    const cleanup = () => cleanupGuestSession(guestSessionId)
    window.addEventListener('beforeunload', cleanup)
    return () => window.removeEventListener('beforeunload', cleanup)
  }, [isGuest, guestSessionId])

  // ── Init: load chats on mount ───────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false

    async function init() {
      const { data: { session } } = await supabase.auth.getSession()

      // Dev mode — no real session. Show welcome only, no Supabase calls.
      if (!session?.user?.id) {
        if (activeMessages.length === 0) {
          setActiveMessages([makeBotMsg('text', 'Paste a GitHub repo URL to learn your coding style, or paste code for a personalized review.')])
        }
        setInitDone(true)
        return
      }

      const userId = session.user.id

      // Fetch chat list
      const fetchedChats = await loadChats(userId)
      if (cancelled) return
      setChats(fetchedChats)

      // Determine which chat to show
      let targetId = activeChatId

      // If saved activeChatId is valid, use it. Otherwise use most recent.
      if (!targetId || !fetchedChats.find((c) => c.id === targetId)) {
        targetId = fetchedChats[0]?.id ?? null
      }

      if (!targetId) {
        // No chats at all — create one
        const meta = await createChat(userId)
        if (cancelled || !meta) { setInitDone(true); return }
        upsertChatMeta(meta)
        setActiveChatId(meta.id)
        chatIdRef.current = meta.id
        const welcome = makeBotMsg('text', 'Paste a GitHub repo URL to learn your coding style, or paste code for a personalized review.')
        setActiveMessages([welcome])
        persistedRef.current = [toPersisted(welcome)]
        setSelectedRepoUrlsLocal(meta.selected_repos ?? [])
        setInitDone(true)
        return
      }

      // Load messages for the target chat
      setActiveChatId(targetId)
      chatIdRef.current = targetId

      // If we already have messages in memory for this chat, reuse them
      if (activeChatId === targetId && activeMessages.length > 0) {
        // Restore selected repos from Zustand cache or Supabase
        const cached = selectedRepoUrlsByChatId[targetId]
        if (cached) {
          setSelectedRepoUrlsLocal(cached)
        } else {
          const fromDb = await loadChatSelectedRepos(targetId)
          if (!cancelled) setSelectedRepoUrlsLocal(fromDb)
        }
        setInitDone(true)
        return
      }

      const persisted = await loadChatMessages(targetId)
      if (cancelled) return

      persistedRef.current = persisted
      setActiveMessages(persisted.length > 0
        ? persisted.map(toUI)
        : [makeBotMsg('text', 'Paste a GitHub repo URL to learn your coding style, or paste code for a personalized review.')]
      )

      // Restore last repo from chat metadata
      const chatMeta = fetchedChats.find((c) => c.id === targetId)
      if (chatMeta?.last_repo_url && !lastAnalyzedRepo) {
        setLastAnalyzedRepo(chatMeta.last_repo_url)
      }

      // Restore selected repos
      const selectedFromMeta = chatMeta?.selected_repos
      if (Array.isArray(selectedFromMeta) && selectedFromMeta.length > 0) {
        setSelectedRepoUrlsLocal(selectedFromMeta)
      } else {
        const cached = selectedRepoUrlsByChatId[targetId!]
        if (cached) {
          setSelectedRepoUrlsLocal(cached)
        } else {
          const fromDb = await loadChatSelectedRepos(targetId!)
          if (!cancelled) setSelectedRepoUrlsLocal(fromDb)
        }
      }

      setInitDone(true)
    }

    init()
    return () => { cancelled = true }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Switch chat when activeChatId changes (sidebar click) ──────────────────
  useEffect(() => {
    if (!initDone) return
    if (!activeChatId || activeChatId === chatIdRef.current) return

    chatIdRef.current = activeChatId
    setLoading(true)

    // Restore selected repos for this chat
    const cached = selectedRepoUrlsByChatId[activeChatId]
    if (cached) {
      setSelectedRepoUrlsLocal(cached)
    } else {
      loadChatSelectedRepos(activeChatId).then((urls) => {
        setSelectedRepoUrlsLocal(urls)
      })
    }

    loadChatMessages(activeChatId).then((persisted) => {
      persistedRef.current = persisted
      setActiveMessages(persisted.length > 0
        ? persisted.map(toUI)
        : [makeBotMsg('text', 'Paste a GitHub repo URL to learn your coding style, or paste code for a personalized review.')]
      )

      // Restore last repo for this chat
      const meta = chats.find((c) => c.id === activeChatId)
      if (meta?.last_repo_url) setLastAnalyzedRepo(meta.last_repo_url)
      else setLastAnalyzedRepo(null)

      setLoading(false)
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeChatId, initDone])

  // ── Helper: add message to UI + persisted buffer + save to Supabase ──────────
  const addMessage = useCallback(async (msg: ChatMessage, rawText?: string) => {
    appendMessage(msg)
    const pm = toPersisted(msg, rawText)
    persistedRef.current = [...persistedRef.current, pm]

    const cid = chatIdRef.current
    if (!cid) return

    // Fire-and-forget save
    saveChatMessages(cid, persistedRef.current, lastAnalyzedRepo ?? null).then(() => {
      // Update title in store after save
      const newTitle = generateTitle(persistedRef.current)
      updateChatTitle(cid, newTitle)
    })
  }, [appendMessage, lastAnalyzedRepo, updateChatTitle])

  // ── Helper: create a new chat (UI only — saved on first message) ────────
  const startNewChat = useCallback(() => {
    setLastAnalyzedRepo(null)
    setSelectedRepoUrlsLocal([])
    const welcome = makeBotMsg('text', 'Paste a GitHub repo URL to learn your coding style, or paste code for a personalized review.')

    // Clear everything immediately without hitting DB (like ChatGPT)
    chatIdRef.current = null
    setActiveChatId(null)
    setActiveMessages([welcome])
    persistedRef.current = []
  }, [setLastAnalyzedRepo, setActiveChatId, setActiveMessages])

  // ── Handle repo selection changes ─────────────────────────────────────────
  const handleSelectionChange = useCallback((urls: string[]) => {
    setSelectedRepoUrlsLocal(urls)

    const cid = chatIdRef.current
    if (cid) {
      // Persist to Zustand
      setSelectedRepoUrls(cid, urls)
      // Persist to Supabase (fire-and-forget)
      updateChatSelectedRepos(cid, urls)
      // Update chat title based on selection
      const selTitle = repoSelectionTitle(urls)
      if (selTitle) {
        updateChatTitle(cid, selTitle)
      }
    }
  }, [setSelectedRepoUrls, updateChatTitle])

  // ── Input handler ─────────────────────────────────────────────────────────
  const handleSubmit = useCallback(async (text: string) => {
    // If there is no active chat (because we clicked + New review), create it now before saving the message.
    if (!chatIdRef.current && userId !== 'anonymous') {
      const meta = await createChat(userId)
      if (meta) {
        upsertChatMeta(meta)
        setActiveChatId(meta.id)
        chatIdRef.current = meta.id

        // Persist current selection to the new chat
        if (selectedRepoUrls.length > 0) {
          setSelectedRepoUrls(meta.id, selectedRepoUrls)
          updateChatSelectedRepos(meta.id, selectedRepoUrls)
        }
      }
    }

    await addMessage(makeUserMsg(text), text)
    setLoading(true)

    try {
      if (GH_REGEX.test(text)) {
        // ── Analyze repo ────────────────────────────────────────────
        const repoUrl = text.match(GH_REGEX)![0]
        const r = await analyzeRepo(repoUrl, userId)
        setLastAnalyzedRepo(repoUrl)

        const fp = r.fingerprint ?? {}
        const data: Record<string, unknown> = {
          functions_analyzed:  r.num_functions ?? 0,
          files_analyzed:      Object.keys(fp.language_distribution ?? {}).length || (r.num_functions ?? 0),
          avg_function_length: fp.avg_function_length ?? 0,
          error_handling_rate: fp.error_handling_rate ?? 0,
          docstring_coverage:  fp.docstring_coverage  ?? 0,
          naming_convention:   fp.naming_convention   ?? 'snake_case',
          type_hint_usage:     fp.type_hint_usage     ?? 0,
          avg_complexity:      fp.avg_complexity      ?? 0,
          cache_status:        r.cache_status,
          repo_name:           r.repo_name,
        }
        await addMessage(makeBotMsg('fingerprint', undefined, data))

        // Save repo to Supabase
        supabase.auth.getSession().then(({ data: { session } }) => {
          if (!session?.user?.id) return
          saveRepo({
            userId:         session.user.id,
            repoUrl,
            repoName:       r.repo_name ?? repoUrl.split('/').slice(-2).join('/'),
            functionsCount: r.num_functions ?? 0,
            languages:      Object.keys(fp.language_distribution ?? {}),
          })
        })

      } else if (isCodeSnippet(text)) {
        // ── Review code ─────────────────────────────────────────────
        if (!lastAnalyzedRepo) {
          await addMessage(makeBotMsg('text', 'Please analyze a GitHub repo first by pasting its URL.'))
          return
        }

        const r = await reviewCode(lastAnalyzedRepo, text, userId)
        const data: Record<string, unknown> = {
          overall_score: r.overall_score,
          status:        r.status,
          iterations:    r.iterations,
          issues:        r.issues        ?? [],
          review_output: r.review_output ?? {},
          agent_trace:   r.agent_trace   ?? [],
        }
        await addMessage(makeBotMsg('review', undefined, data))

        // Save review to Supabase
        supabase.auth.getSession().then(({ data: { session } }) => {
          if (!session?.user?.id) return
          saveReview({ userId: session.user.id, repoUrl: lastAnalyzedRepo!, code: text, result: r })
        })

      } else {
        // ── Free-form Q&A ───────────────────────────────────────────
        if (selectedRepoUrls.length === 0) {
          await addMessage(makeBotMsg('text', 'Select at least one repo above to ask questions about your code.'))
        } else {
          try {
            const result = await chatWithInsights(
              text,
              selectedRepoUrls,
              userId,
              chatIdRef.current ?? undefined,
            )
            await addMessage(makeBotMsg('text', result.answer))
          } catch (err) {
            await addMessage(makeBotMsg('text', `Error: ${err instanceof Error ? err.message : String(err)}`))
          }
        }
      }
    } catch (err) {
      await addMessage(makeBotMsg('text', `Error: ${err instanceof Error ? err.message : String(err)}`))
    } finally {
      setLoading(false)
    }
  }, [addMessage, lastAnalyzedRepo, setLastAnalyzedRepo, selectedRepoUrls, userId, upsertChatMeta, setActiveChatId, setSelectedRepoUrls])

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      background: 'var(--bg-primary)',
      color: 'var(--text-primary)',
      overflow: 'hidden',
    }}>
      <Sidebar onNewChat={startNewChat} />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
        <TopBar title={chats.find((c) => c.id === activeChatId)?.title ?? 'New review'} />

        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
          <div style={{
            maxWidth: 680,
            width: '100%',
            margin: '0 auto',
            padding: '0 20px',
            display: 'flex',
            flexDirection: 'column',
            flex: 1,
          }}>
            <RepoSelector
              userId={userId}
              selectedUrls={selectedRepoUrls}
              onSelectionChange={handleSelectionChange}
            />
            <MessageList messages={activeMessages} loading={loading} />
            <ChatInput onSubmit={handleSubmit} disabled={loading || !initDone} />
          </div>
        </div>
      </div>
    </div>
  )
}
