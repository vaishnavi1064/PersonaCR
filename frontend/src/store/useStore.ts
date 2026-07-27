import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { PersistedMessage, ChatMeta } from '../lib/db'

// ── Re-export so consumers can import from one place ──────────────────────────
export type { PersistedMessage, ChatMeta }

// ── UI message shape (used by MessageList, BotMessage, UserMessage) ───────────
export interface ChatMessage {
  id:    string
  role:  'user' | 'bot'
  text?: string
  type?: 'text' | 'fingerprint' | 'review'
  data?: Record<string, unknown>
}

// Convert Supabase persisted message → UI message
export function toUI(m: PersistedMessage, idx: number): ChatMessage {
  return {
    id:   `msg-${idx}-${m.timestamp}`,
    role: m.role,
    text: m.content ?? undefined,
    type: m.type ?? 'text',
    data: m.data ?? undefined,
  }
}

// Convert UI message + text → persisted message for Supabase
export function toPersisted(
  m: ChatMessage,
  text?: string,
): PersistedMessage {
  return {
    role:      m.role,
    content:   text ?? m.text ?? null,
    type:      m.type ?? 'text',
    data:      m.data ?? null,
    timestamp: new Date().toISOString(),
  }
}

// ── Store types ───────────────────────────────────────────────────────────────
interface AppState {
  // Auth
  user:             Record<string, unknown> | null
  session:          Record<string, unknown> | null
  authLoading:      boolean
  isGuest:          boolean
  guestSessionId:   string | null   // temporary ID for isolated guest ChromaDB collections
  setSession:       (session: Record<string, unknown> | null) => void
  setUser:          (user: Record<string, unknown> | null) => void
  setAuthLoading:   (loading: boolean) => void
  setIsGuest:       (v: boolean) => void
  clearGuestSession:() => void

  // Chat metadata (sidebar list) — persisted to localStorage (metadata only, no messages)
  chats:           ChatMeta[]
  setChats:        (chats: ChatMeta[]) => void
  upsertChatMeta:  (meta: ChatMeta) => void
  updateChatTitle: (id: string, title: string) => void
  updateChatStar:  (id: string, starred: boolean) => void

  // Active chat
  activeChatId:    string | null
  setActiveChatId: (id: string | null) => void

  // In-memory message cache (NOT persisted — refetched from Supabase on hard refresh)
  activeMessages:    ChatMessage[]
  setActiveMessages: (msgs: ChatMessage[]) => void
  appendMessage:     (msg: ChatMessage) => void

  reviews:   Record<string, unknown>[]
  addReview: (review: Record<string, unknown>) => void

  // Repo selection per chat — single source of truth (index 0 = review target)
  selectedRepoUrlsByChatId: Record<string, string[]>
  setSelectedRepoUrls:     (chatId: string, urls: string[]) => void

  // UI
  sidebarOpen:   boolean
  toggleSidebar: () => void
  setSidebarOpen:(open: boolean) => void
  theme:         'dark' | 'light'
  toggleTheme:   () => void
  accent:        'purple' | 'blue' | 'teal' | 'coral'
  setAccent:     (a: 'purple' | 'blue' | 'teal' | 'coral') => void
}

export const useStore = create<AppState>()(
  persist(
    (set) => ({
      // Auth
      user:             null,
      session:          null,
      authLoading:      true,
      isGuest:          false,
      guestSessionId:   null,
      setSession:       (session) => set({ session }),
      setUser:          (user)    => set({ user }),
      setAuthLoading:   (loading) => set({ authLoading: loading }),
      setIsGuest: (v) => set((s) => {
        if (v && !s.guestSessionId) {
          // Generate a new guest session ID and persist it
          const gid = 'guest_' + crypto.randomUUID()
          return { isGuest: true, guestSessionId: gid }
        }
        if (!v) {
          // Real login — clear guest session
          return { isGuest: false, guestSessionId: null }
        }
        return { isGuest: true }
      }),
      clearGuestSession: () => set({ isGuest: false, guestSessionId: null }),

      // Chat metadata
      chats:    [],
      setChats: (chats) => set({ chats }),
      upsertChatMeta: (meta) =>
        set((s) => {
          const exists = s.chats.some((c) => c.id === meta.id)
          return {
            chats: exists
              ? s.chats.map((c) => (c.id === meta.id ? { ...c, ...meta } : c))
              : [meta, ...s.chats],
          }
        }),
      updateChatTitle: (id, title) =>
        set((s) => ({
          chats: s.chats.map((c) => (c.id === id ? { ...c, title } : c)),
        })),
      updateChatStar: (id, starred) =>
        set((s) => ({
          chats: s.chats.map((c) => (c.id === id ? { ...c, starred } : c)),
        })),

      // Active chat
      activeChatId:    null,
      setActiveChatId: (id) => set({ activeChatId: id }),

      // In-memory messages (not persisted)
      activeMessages:    [],
      setActiveMessages: (msgs) => set({ activeMessages: msgs }),
      appendMessage:     (msg)  => set((s) => ({ activeMessages: [...s.activeMessages, msg] })),

      // Review data
      reviews:   [],
      addReview: (review) => set((s) => ({ reviews: [review, ...s.reviews] })),

      // Repo selection per chat — single source of truth (index 0 = review target)
      selectedRepoUrlsByChatId: {},
      setSelectedRepoUrls: (chatId, urls) =>
        set((s) => ({
          selectedRepoUrlsByChatId: { ...s.selectedRepoUrlsByChatId, [chatId]: urls },
        })),

      // UI
      sidebarOpen:   true,
      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
      setSidebarOpen:(open) => set({ sidebarOpen: open }),
      theme:  'dark',
      toggleTheme: () =>
        set((s) => ({ theme: s.theme === 'dark' ? 'light' : 'dark' })),
      accent: 'purple',
      setAccent: (a) => set({ accent: a }),
    }),
    {
      name: 'personacr-store',
      partialize: (s) => ({
        theme:           s.theme,
        accent:          s.accent,
        chats:           s.chats,
        activeChatId:    s.activeChatId,
        reviews:         s.reviews,
        selectedRepoUrlsByChatId: s.selectedRepoUrlsByChatId,
        isGuest:         s.isGuest,
        guestSessionId:  s.guestSessionId,
      }),
    }
  )
)
