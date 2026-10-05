import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import { analyzeRepo, ApiError, type AnalyzeResult, type Repo } from '../lib/api'

// Analyze runs synchronously on the backend, so "Analyzing" only exists while
// this tab's request is in flight — jobs are memory-only; after a reload the
// server list is the truth. Persisted status needs the background analyze job
// (capability analyzeJobs). sessionRepos lives in sessionStorage: it survives a
// reload but not closing the tab, which is the promise made to guests.

export type RepoJob =
  | { state: 'analyzing'; url: string; fullName: string; startedAt: number; force: boolean }
  | { state: 'failed'; url: string; fullName: string; startedAt: number; finishedAt: number; error: string; force: boolean }
  | { state: 'done'; url: string; fullName: string; startedAt: number; finishedAt: number; result: AnalyzeResult }

interface RepoJobsState {
  jobs: Record<string, RepoJob>
  /** Repos analyzed in this session — the only list guests have. */
  sessionRepos: Record<string, Repo>
  /** Bumped whenever a job finishes successfully, so lists can refetch. */
  completedCount: number
  startAnalyze: (repo: { url: string; fullName: string }, userId: string, opts?: { force?: boolean }) => Promise<void>
  dismissJob: (url: string) => void
}

function errorMessage(err: unknown, fullName: string): string {
  if (err instanceof ApiError) {
    if (err.kind === 'network') return 'Could not reach the PersonaCR server. Is the backend running?'
    if (err.kind === 'timeout') return `${err.message}. The repo may be too large to analyze in one request.`
    // Ingestion errors embed GitHub's raw response, e.g. "Could not access repo x/y: 404 {...}"
    if (/Could not access repo .*: 404\b/.test(err.message)) {
      return `GitHub couldn’t find ${fullName}. Check the URL — private repos aren’t supported yet.`
    }
    if (/: (403|429)\b/.test(err.message) && /rate limit/i.test(err.message)) {
      return 'GitHub’s API rate limit was hit. Wait a few minutes and retry.'
    }
    return err.message
  }
  return err instanceof Error ? err.message : String(err)
}

export const useRepoJobs = create<RepoJobsState>()(persist((set, get) => ({
  jobs: {},
  sessionRepos: {},
  completedCount: 0,

  startAnalyze: async ({ url, fullName }, userId, opts = {}) => {
    if (get().jobs[url]?.state === 'analyzing') return
    const force = !!opts.force
    const startedAt = Date.now()
    set((s) => ({ jobs: { ...s.jobs, [url]: { state: 'analyzing', url, fullName, startedAt, force } } }))
    try {
      const result = await analyzeRepo(url, userId, { force })
      set((s) => ({
        jobs: { ...s.jobs, [url]: { state: 'done', url, fullName, startedAt, finishedAt: Date.now(), result } },
        sessionRepos: { ...s.sessionRepos, [result.repo.url]: result.repo },
        completedCount: s.completedCount + 1,
      }))
    } catch (err) {
      set((s) => ({
        jobs: {
          ...s.jobs,
          [url]: { state: 'failed', url, fullName, startedAt, finishedAt: Date.now(), error: errorMessage(err, fullName), force },
        },
      }))
    }
  },

  dismissJob: (url) => set((s) => {
    const jobs = { ...s.jobs }
    delete jobs[url]
    return { jobs }
  }),
}), {
  name: 'personacr-session-repos',
  storage: createJSONStorage(() => sessionStorage),
  partialize: (s) => ({ sessionRepos: s.sessionRepos }),
}))
