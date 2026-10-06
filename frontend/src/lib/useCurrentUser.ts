import { useCallback } from 'react'
import { useStore } from '../store/useStore'
import { cleanupGuestSession } from './api'
import { supabase } from './supabase'

interface SupabaseUserLike {
  id?: string
  is_anonymous?: boolean
  email?: string
  name?: string
  user_metadata?: { full_name?: string; name?: string; avatar_url?: string; user_name?: string }
  app_metadata?: { provider?: string }
}

/** Display info for the signed-in user (or guest) plus sign-out. */
export function useCurrentUser() {
  const user = useStore((s) => s.user) as SupabaseUserLike | null

  // Guests are Supabase anonymous sign-ins. Their id mirrors the backend's
  // (core/auth.py): guest_<uid>, so "has a saved account" checks stay false.
  const guestMode = !!user?.is_anonymous
  const userId = !user?.id ? 'anonymous' : guestMode ? `guest_${user.id}` : user.id

  const displayName = guestMode
    ? 'Guest'
    : user?.user_metadata?.full_name ?? user?.user_metadata?.name ?? user?.name ?? user?.email ?? 'Guest'

  const initials = guestMode
    ? 'G'
    : displayName.split(/[\s@]/).filter(Boolean).map((w) => w[0]).slice(0, 2).join('').toUpperCase() || 'G'

  const signOut = useCallback(async () => {
    // A signed-out guest can never come back, so wipe its server-side data first
    if (guestMode) await cleanupGuestSession(userId)
    // onAuthStateChange clears the session → AuthGuard redirects
    await supabase.auth.signOut()
  }, [guestMode, userId])

  return {
    /** Account uuid, guest_<uid>, or 'anonymous'. For client-side use — the backend reads the token. */
    userId,
    guestMode,
    displayName,
    initials,
    email: guestMode ? null : user?.email ?? null,
    avatarUrl: guestMode ? null : user?.user_metadata?.avatar_url ?? null,
    githubLogin: guestMode ? null : user?.user_metadata?.user_name ?? null,
    provider: guestMode ? null : user?.app_metadata?.provider ?? null,
    signOut,
  }
}
