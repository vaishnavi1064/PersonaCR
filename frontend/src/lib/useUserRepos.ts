import { useEffect, useMemo, useState } from 'react'
import { listRepos, type Repo } from './api'
import { useRepoJobs } from '../store/useRepoJobs'

/** The user's saved repos merged with ones analyzed this session (all guests have). */
export function useUserRepos(userId: string): { repos: Repo[]; loading: boolean; error: string | null } {
  const sessionRepos = useRepoJobs((s) => s.sessionRepos)
  const jobs = useRepoJobs((s) => s.jobs)
  const completedCount = useRepoJobs((s) => s.completedCount)
  const [state, setState] = useState<{ repos: Repo[]; loading: boolean; error: string | null }>({ repos: [], loading: true, error: null })

  useEffect(() => {
    const ctrl = new AbortController()
    listRepos(userId, ctrl.signal).then(
      (repos) => setState({ repos, loading: false, error: null }),
      (err) => { if (!ctrl.signal.aborted) setState((s) => ({ ...s, loading: false, error: err instanceof Error ? err.message : String(err) })) },
    )
    return () => ctrl.abort()
  }, [userId, completedCount])

  const repos = useMemo(() => {
    const byUrl = new Map<string, Repo>()
    for (const r of state.repos) byUrl.set(r.url, r)
    for (const r of Object.values(sessionRepos)) byUrl.set(r.url, { ...byUrl.get(r.url), ...r })
    return [...byUrl.values()]
      .map((r) => (jobs[r.url]?.state === 'analyzing' ? { ...r, status: 'analyzing' as const } : r))
      .sort((a, b) => a.fullName.localeCompare(b.fullName))
  }, [state.repos, sessionRepos, jobs])

  return { repos, loading: state.loading, error: state.error }
}
