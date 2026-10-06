import { isActiveAnalysis, type Repo } from '../../lib/api'
import type { RepoJob } from '../../store/useRepoJobs'

export interface ActiveAnalysis {
  /** ms epoch; 0 when unknown */
  startedAt: number
  message: string
  queued: boolean
  /** Runs on the server — leaving the page doesn't stop it. */
  background: boolean
}

/** This tab's job if it's watching one, otherwise the server's record for the repo. */
export function activeAnalysis(repo: Repo, job?: RepoJob): ActiveAnalysis | null {
  if (job?.state === 'analyzing') {
    return { startedAt: job.startedAt, message: job.message, queued: job.message.startsWith('Queued'), background: job.background }
  }
  const a = repo.analysis
  if (a && isActiveAnalysis(a)) {
    const queued = a.state === 'queued'
    return {
      startedAt: a.startedAt ? Date.parse(a.startedAt) || 0 : 0,
      message: queued ? 'Queued — waiting for a worker' : a.message ?? 'Analyzing',
      queued,
      background: true,
    }
  }
  return null
}

/** After this long in the queue, say that no worker may be running. */
export const STUCK_QUEUED_MS = 30_000

export function stuckHint(a: ActiveAnalysis, now: number): string | null {
  return a.queued && a.startedAt > 0 && now - a.startedAt > STUCK_QUEUED_MS
    ? 'No worker has picked this up yet — is the analysis worker running?'
    : null
}
