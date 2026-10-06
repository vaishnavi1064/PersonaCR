// Guests (Supabase anonymous sign-in): wipe the session's code-search collections
// on the server when the guest leaves. The backend only accepts the caller's own id.
import { request, sendKeepalive } from './http'

const cleanupPath = (guestSessionId: string) => `/api/cleanup-guest/${encodeURIComponent(guestSessionId)}`

/** Tab close: keepalive request, best effort. */
export function cleanupGuestOnUnload(guestSessionId: string): void {
  sendKeepalive(cleanupPath(guestSessionId))
}

/** Sign-out: awaited while the token is still valid. Never throws. */
export async function cleanupGuestSession(guestSessionId: string): Promise<void> {
  try {
    await request(cleanupPath(guestSessionId), { method: 'POST', timeoutMs: 10_000 })
  } catch { /* best effort — sign-out goes ahead regardless */ }
}
