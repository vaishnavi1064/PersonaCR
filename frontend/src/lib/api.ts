const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export async function analyzeRepo(repoUrl: string) {
  const res = await fetch(`${API}/api/analyze-repo`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_url: repoUrl }),
  })
  if (!res.ok) throw new Error(`Analyze failed: ${res.status}`)
  return res.json()
}

export async function reviewCode(
  repoUrl: string,
  code: string,
  language = 'python'
) {
  const res = await fetch(`${API}/api/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_url: repoUrl, code, language }),
  })
  if (!res.ok) throw new Error(`Review failed: ${res.status}`)
  return res.json()
}

export async function healthCheck() {
  const res = await fetch(`${API}/health`)
  if (!res.ok) throw new Error('Backend unreachable')
  return res.json()
}
