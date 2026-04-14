const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export async function analyzeRepo(repoUrl: string, userId = 'anonymous') {
  const res = await fetch(`${API}/api/analyze-repo`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_url: repoUrl, user_id: userId }),
  })
  if (!res.ok) throw new Error(`Analyze failed: ${res.status}`)
  return res.json()
}

export async function reviewCode(
  repoUrl: string,
  code: string,
  userId = 'anonymous',
  language = 'python'
) {
  const res = await fetch(`${API}/api/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_url: repoUrl, code, language, user_id: userId }),
  })
  if (!res.ok) throw new Error(`Review failed: ${res.status}`)
  return res.json()
}

export async function healthCheck() {
  const res = await fetch(`${API}/health`)
  if (!res.ok) throw new Error('Backend unreachable')
  return res.json()
}

/** Called via sendBeacon on tab close to wipe guest ChromaDB collection. */
export function cleanupGuestSession(guestSessionId: string) {
  const url = `${API}/api/cleanup-guest/${encodeURIComponent(guestSessionId)}`
  // sendBeacon works even when the tab is closing — fetch would be cancelled
  navigator.sendBeacon(url)
}
