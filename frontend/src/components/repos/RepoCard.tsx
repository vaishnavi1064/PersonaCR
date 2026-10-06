import { Link } from 'react-router-dom'
import { Braces, Loader2, Ruler } from 'lucide-react'
import { fingerprintChips, topLanguages, type Repo } from '../../lib/api'
import type { RepoJob } from '../../store/useRepoJobs'
import { absoluteTime, count, elapsed, relativeTime } from '../../lib/format'
import { useNow } from '../../lib/useNow'
import Card, { CardDivider } from '../ui/Card'
import Button from '../ui/Button'
import Chip from '../ui/Chip'
import StatTile from '../ui/StatTile'
import GitHubMark from '../ui/GitHubMark'
import { buttonClass } from '../ui/styles'
import RepoStatusPill from './RepoStatusPill'
import { activeAnalysis, stuckHint } from './analysisStatus'
import { languageColor, languageLabel } from './languages'

interface RepoCardProps {
  repo: Repo
  job?: RepoJob
  /** Failed first import that was never saved — offer Dismiss instead of Open. */
  placeholder?: boolean
  onAnalyze: (repo: Repo, force: boolean) => void
  onStartChat: (repo: Repo) => void
  onDismiss: (repo: Repo) => void
}

export default function RepoCard({ repo, job, placeholder, onAnalyze, onStartChat, onDismiss }: RepoCardProps) {
  const analyzing = repo.status === 'analyzing'
  const active = activeAnalysis(repo, job)
  const now = useNow(analyzing)
  const chips = fingerprintChips(repo.fingerprint)
  const langs = topLanguages(repo)
  const hasFingerprint = repo.fingerprint != null
  const detailPath = `/repos/${encodeURIComponent(repo.owner)}/${encodeURIComponent(repo.name)}`
  const lastForce = job && job.state !== 'done' ? job.force : hasFingerprint

  return (
    <Card className="flex flex-col" aria-busy={analyzing || undefined}>
      {/* Header + summary */}
      <div className="flex flex-col gap-2.5 p-4 pb-3.5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="truncate text-[15px] font-semibold leading-snug text-fg" title={repo.fullName}>
              {placeholder ? repo.name : <Link to={detailPath} className="hover:underline">{repo.name}</Link>}
            </h3>
            <p className="mt-0.5 flex min-w-0 items-center gap-1.5 text-xs text-fg-3">
              <GitHubMark size={11} />
              <span className="truncate">{repo.owner}</span>
            </p>
          </div>
          <RepoStatusPill status={repo.status} />
        </div>

        <div className="min-h-10 text-[13px] leading-5">
          {analyzing && active ? (
            <div role="status">
              <p className="flex items-center gap-2 text-fg-2">
                <Loader2 size={13} className="shrink-0 animate-spin text-accent" aria-hidden />
                <span className="truncate">{active.message}</span>
                {active.startedAt > 0 && <span className="shrink-0 tabular-nums text-fg-3">· {elapsed(now - active.startedAt)}</span>}
              </p>
              {stuckHint(active, now) && <p className="mt-0.5 text-xs text-warning">{stuckHint(active, now)}</p>}
            </div>
          ) : repo.status === 'failed' && repo.error ? (
            <p className="line-clamp-2 text-danger" title={repo.error}>{repo.error}</p>
          ) : repo.summary ? (
            <p className="line-clamp-2 text-fg-2" title={repo.summary}>{repo.summary}</p>
          ) : (
            <p className="text-xs text-fg-3">{hasFingerprint ? 'No summary yet — reanalyze to generate one.' : 'Summary appears after analysis.'}</p>
          )}
        </div>
      </div>

      <CardDivider />

      {/* Stats, chips, meta */}
      <div className="flex flex-1 flex-col gap-3.5 p-4">
        <div className="grid grid-cols-2 gap-3">
          <StatTile icon={<Braces size={16} />} value={repo.functionsCount != null ? count(repo.functionsCount) : null} label="Functions analyzed" />
          <StatTile
            icon={<Ruler size={16} />}
            value={repo.fingerprint?.avgFunctionLength != null ? `${Math.round(repo.fingerprint.avgFunctionLength)} lines` : null}
            label="Avg function"
          />
        </div>

        {chips.length > 0 ? (
          <div className="flex flex-wrap gap-1.5" aria-label="Fingerprint">
            {chips.map((c) => <Chip key={c}>{c}</Chip>)}
          </div>
        ) : (
          <p className="text-xs text-fg-3">{analyzing ? 'Learning conventions…' : 'No fingerprint yet — analyze to learn this repo’s style.'}</p>
        )}

        <div className="mt-auto flex items-center justify-between gap-3 text-xs text-fg-3">
          <span className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
            {langs.length > 0 ? langs.map((l) => (
              <span key={l} className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: languageColor(l) }} aria-hidden />
                {languageLabel(l)}
              </span>
            )) : <span>—</span>}
          </span>
          <span className="shrink-0" title={absoluteTime(repo.analyzedAt)}>
            {repo.analyzedAt ? `Analyzed ${relativeTime(repo.analyzedAt)}` : 'Not analyzed'}
          </span>
        </div>
      </div>

      <CardDivider />

      {/* Actions */}
      <div className="grid grid-cols-3 gap-2 p-3">
        {placeholder ? (
          <Button size="sm" variant="ghost" className="px-1.5" onClick={() => onDismiss(repo)}>Dismiss</Button>
        ) : (
          <Link to={detailPath} className={buttonClass('outline', 'sm', 'px-1.5')}>Open</Link>
        )}
        <Button
          size="sm"
          className="px-1.5"
          disabled={!hasFingerprint || analyzing}
          title={hasFingerprint ? `Start a chat about ${repo.fullName}` : 'Analyze the repo first'}
          onClick={() => onStartChat(repo)}
        >
          Start chat
        </Button>
        <Button
          size="sm"
          className="px-1.5"
          loading={analyzing}
          aria-label={analyzing ? 'Analyzing' : undefined}
          onClick={() => onAnalyze(repo, lastForce)}
          title={hasFingerprint ? 'Re-run analysis on the latest commit' : undefined}
        >
          {analyzing ? null : repo.status === 'failed' ? 'Retry' : hasFingerprint ? 'Reanalyze' : 'Analyze'}
        </Button>
      </div>
    </Card>
  )
}

export function RepoCardSkeleton() {
  return (
    <Card className="flex flex-col" aria-hidden>
      <div className="flex flex-col gap-3 p-4">
        <div className="flex justify-between"><div className="h-4 w-32 animate-pulse rounded bg-raised" /><div className="h-5 w-14 animate-pulse rounded-full bg-raised" /></div>
        <div className="h-3 w-20 animate-pulse rounded bg-raised" />
        <div className="h-3 w-full animate-pulse rounded bg-raised" />
      </div>
      <CardDivider />
      <div className="flex flex-col gap-3 p-4">
        <div className="grid grid-cols-2 gap-3">
          <div className="h-9 animate-pulse rounded-lg bg-raised" /><div className="h-9 animate-pulse rounded-lg bg-raised" />
        </div>
        <div className="flex gap-1.5"><div className="h-5 w-24 animate-pulse rounded bg-raised" /><div className="h-5 w-20 animate-pulse rounded bg-raised" /></div>
      </div>
      <CardDivider />
      <div className="h-14" />
    </Card>
  )
}
