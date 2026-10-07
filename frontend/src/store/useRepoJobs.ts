import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import {
  analyzeRepo, ApiError, capabilities, isRateLimited, getAnalyzeJob, startAnalyzeJob, type AnalyzeResult, type Repo,
} from '../lib/api'

// Analysis runs as a background job on the server (capability analyzeJobs):
// this store starts it and polls it while the page is open. The server keeps
// the status too, so after a reload the repo list shows it (GET /api/repos).
// If the job queue is offline (503) the synchronous endpoint is used instead.
// sessionRepos lives in sessionStorage: it survives a reload but not closing
// the tab, which is the promise made to guests.

export type RepoJob =
  | { state: 'analyzing'; url: string; fullName: string; startedAt: number; force: boolean; message: string; background: boolean }
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

const POLL_MS = 2000
/** Consecutive failed polls before giving up on watching (the job itself may still finish). */
const MAX_POLL_ERRORS = 5

/** Make backend/GitHub error text readable. */
function humanize(detail: string, fullName: string): string {
  // Ingestion errors embed GitHub's raw response, e.g. "Could not access repo x/y: 404 {...}"
  if (/Could not access repo .*: 404\b/.test(detail)) {
    return `GitHub couldn’t find ${fullName}. Check the URL — private repos aren’t supported yet.`
  }
  if (/: (403|429)\b/.test(detail) && /rate limit/i.test(detail)) {
    return 'GitHub’s API rate limit was hit. Wait a few minutes and retry.'
  }
  return detail
}

function errorMessage(err: unknown, fullName: string): string {
  if (err instanceof ApiError) {
    if (err.kind === 'network') return 'Could not reach the PersonaCR server. Is the backend running?'
    if (err.kind === 'timeout') return `${err.message}. The repo may be too large to analyze in one request.`
    if (isRateLimited(err)) return err.message
    return humanize(err.message, fullName)
  }
  return err instanceof Error ? err.message : String(err)
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

export const useRepoJobs = create<RepoJobsState>()(persist((set, get) => {
  const setJob = (url: string, job: RepoJob) => set((s) => ({ jobs: { ...s.jobs, [url]: job } }))

  function succeed(url: string, fullName: string, startedAt: number, result: AnalyzeResult) {
    set((s) => ({
      jobs: { ...s.jobs, [url]: { state: 'done', url, fullName, startedAt, finishedAt: Date.now(), result } },
      sessionRepos: { ...s.sessionRepos, [result.repo.url]: result.repo },
      completedCount: s.completedCount + 1,
    }))
  }

  function fail(url: string, fullName: string, startedAt: number, force: boolean, error: string) {
    setJob(url, { state: 'failed', url, fullName, startedAt, finishedAt: Date.now(), error, force })
  }

  async function runInBackground(url: string, fullName: string, force: boolean): Promise<boolean> {
    let jobId: string
    let startedAt = Date.now()
    try {
      const started = await startAnalyzeJob(url, { force })
      jobId = started.jobId
      if (started.startedAt) startedAt = Date.parse(started.startedAt) || startedAt
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) return false // queue offline → sync fallback
      fail(url, fullName, startedAt, force, errorMessage(err, fullName))
      return true
    }
    setJob(url, { state: 'analyzing', url, fullName, startedAt, force, message: 'Queued — waiting for a worker', background: true })

    let errors = 0
    for (;;) {
      await sleep(POLL_MS)
      try {
        const job = await getAnalyzeJob(jobId, url)
        errors = 0
        if (job.state === 'completed' && job.result) { succeed(url, fullName, startedAt, job.result); return true }
        if (job.state === 'failed') { fail(url, fullName, startedAt, force, humanize(job.error ?? 'Analysis failed', fullName)); return true }
        const message = job.state === 'queued' ? 'Queued — waiting for a worker' : job.message ?? 'Analyzing'
        setJob(url, { state: 'analyzing', url, fullName, startedAt, force, message, background: true })
      } catch (err) {
        if (++errors >= MAX_POLL_ERRORS) {
          fail(url, fullName, startedAt, force,
            `Lost contact with the server (${errorMessage(err, fullName)}). The analysis may still finish — reload the page to check.`)
          return true
        }
      }
    }
  }

  return {
    jobs: {},
    sessionRepos: {},
    completedCount: 0,

    startAnalyze: async ({ url, fullName }, userId, opts = {}) => {
      if (get().jobs[url]?.state === 'analyzing') return
      const force = !!opts.force
      if (capabilities.analyzeJobs.level === 'available' && (await runInBackground(url, fullName, force))) return

      // Synchronous fallback: the request stays open for the whole analysis
      const startedAt = Date.now()
      setJob(url, { state: 'analyzing', url, fullName, startedAt, force, message: 'Analyzing (waiting for the server)', background: false })
      try {
        succeed(url, fullName, startedAt, await analyzeRepo(url, userId, { force }))
      } catch (err) {
        fail(url, fullName, startedAt, force, errorMessage(err, fullName))
      }
    },

    dismissJob: (url) => set((s) => {
      const jobs = { ...s.jobs }
      delete jobs[url]
      return { jobs }
    }),
  }
}, {
  name: 'personacr-session-repos',
  storage: createJSONStorage(() => sessionStorage),
  partialize: (s) => ({ sessionRepos: s.sessionRepos }),
}))
