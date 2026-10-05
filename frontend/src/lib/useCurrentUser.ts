import { useCallback } from 'react'
import { useStore } from '../store/useStore'
import { supabase } from './supabase'

interface SupabaseUserLike {
  email?: string
  name?: string
  user_metadata?: { full_name?: string; name?: string; avatar_url?: string; user_name?: string }
  app_metadata?: { provider?: string }
}

/** Display info for the signed-in user (or guest) plus sign-out. */
export function useCurrentUser() {
  const user = useStore((s) => s.user) as SupabaseUserLike | null
  const session = useStore((s) => s.session)
  const isGuest = useStore((s) => s.isGuest)
  const setIsGuest = useStore((s) => s.setIsGuest)

  const guestMode = isGuest && !session

  const displayName = guestMode
    ? 'Guest'
    : user?.user_metadata?.full_name ?? user?.user_metadata?.name ?? user?.name ?? user?.email ?? 'Guest'

  const initials = guestMode
    ? 'G'
    : displayName.split(/[\s@]/).filter(Boolean).map((w) => w[0]).slice(0, 2).join('').toUpperCase() || 'G'

  const signOut = useCallback(async () => {
    if (guestMode) {
      // Guest: clearing the flag sends AuthGuard back to /login
      setIsGuest(false)
    } else {
      // onAuthStateChange clears the session → AuthGuard redirects
      await supabase.auth.signOut()
    }
  }, [guestMode, setIsGuest])

  return {
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
