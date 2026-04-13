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
  user:           Record<string, unknown> | null
  session:        Record<string, unknown> | null
  authLoading:    boolean
  isGuest:        boolean
  setSession:     (session: Record<string, unknown> | null) => void
  setUser:        (user: Record<string, unknown> | null) => void
  setAuthLoading: (loading: boolean) => void
  setIsGuest:     (v: boolean) => void

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

  // Review data
  lastAnalyzedRepo:    string | null
  setLastAnalyzedRepo: (url: string | null) => void

  reviews:   Record<string, unknown>[]
  addReview: (review: Record<string, unknown>) => void

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
      user:           null,
      session:        null,
      authLoading:    true,   // true until getSession() resolves on mount
      isGuest:        false,
      setSession:     (session) => set({ session }),
      setUser:        (user)    => set({ user }),
      setAuthLoading: (loading) => set({ authLoading: loading }),
      setIsGuest:     (v)       => set({ isGuest: v }),

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
      lastAnalyzedRepo:    null,
      setLastAnalyzedRepo: (url) => set({ lastAnalyzedRepo: url }),
      reviews:   [],
      addReview: (review) => set((s) => ({ reviews: [review, ...s.reviews] })),

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
        chats:           s.chats,       // metadata only — no message content
        activeChatId:    s.activeChatId,
        lastAnalyzedRepo:s.lastAnalyzedRepo,
        reviews:         s.reviews,
        isGuest:         s.isGuest,
      }),
    }
  )
)
