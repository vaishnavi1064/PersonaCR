import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, ClipboardCheck, Scissors } from 'lucide-react'
import { fetchSavedReview, parseRepoUrl, reviewFromRow, SAVED_CODE_LIMIT, type Finding } from '../lib/api'
import type { ReviewRow } from '../lib/db'
import { absoluteTime, relativeTime } from '../lib/format'
import Card from '../components/ui/Card'
import EmptyState from '../components/ui/EmptyState'
import GitHubMark from '../components/ui/GitHubMark'
import { buttonClass } from '../components/ui/styles'
import ReviewSummary from '../components/review/ReviewSummary'
import CodePanel from '../components/studio/CodePanel'

type State = { status: 'loading' } | { status: 'ok'; row: ReviewRow | null } | { status: 'error'; message: string }

/** A saved review (/reviews/:id), deep-linked from a repo's Reviews tab. */
export default function ReviewPage() {
  const { id = '' } = useParams()
  const [state, setState] = useState<State>({ status: 'loading' })
  const [activeFindingId, setActiveFindingId] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    fetchSavedReview(id).then(
      (row) => { if (alive) setState({ status: 'ok', row }) },
      (err) => { if (alive) setState({ status: 'error', message: err instanceof Error ? err.message : String(err) }) },
    )
    return () => { alive = false }
  }, [id])

  const row = state.status === 'ok' ? state.row : null
  const mapped = useMemo(() => (row ? reviewFromRow(row) : null), [row])
  const repo = row ? parseRepoUrl(row.repo_url) : null
  const repoPath = repo ? `/repos/${repo.owner}/${repo.name}` : '/repos'

  if (state.status === 'loading') {
    return <div className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6"><div className="h-64 animate-pulse rounded-xl bg-surface" aria-busy /></div>
  }
  if (state.status === 'error' || !row || !mapped) {
    return (
      <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 lg:py-10">
        <EmptyState
          icon={<ClipboardCheck size={20} />}
          title={state.status === 'error' ? 'Couldn’t load this review' : 'Review not found'}
          description={state.status === 'error' ? state.message : 'It may have been deleted, or it belongs to another account.'}
          action={<Link to="/repos" className={buttonClass('outline')}>Back to repositories</Link>}
        />
      </div>
    )
  }

  const { review, codeTruncated } = mapped
  const selectFinding = (f: Finding) => setActiveFindingId((cur) => (cur === f.id ? null : f.id))

  return (
    <div className="mx-auto w-full max-w-[1400px] px-4 py-8 sm:px-6 lg:py-10">
      <Link to={`${repoPath}?tab=reviews`} className="mb-4 inline-flex items-center gap-1.5 text-sm text-fg-3 hover:text-fg">
        <ArrowLeft size={14} aria-hidden /> {repo ? `${repo.fullName} reviews` : 'Repositories'}
      </Link>
      <h1 className="text-[28px] font-bold leading-tight tracking-tight text-fg">Review</h1>
      <p className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-fg-3">
        {repo && <Link to={repoPath} className="inline-flex items-center gap-1.5 hover:text-fg hover:underline"><GitHubMark size={13} /> {repo.fullName}</Link>}
        <span title={absoluteTime(row.created_at)}>{relativeTime(row.created_at)}</span>
      </p>

      <div className="mt-6 grid items-start gap-5 xl:grid-cols-[minmax(0,26rem)_1fr]">
        <Card className="p-4">
          <ReviewSummary review={review} active onOpenCode={() => document.getElementById('saved-code')?.scrollIntoView({ behavior: 'smooth' })} />
          <p className="mt-4 border-t border-line pt-3 text-xs text-fg-3">
            Saved reviews keep the score, findings and agent trace; confidence details and the number of repo functions compared weren’t saved.
          </p>
        </Card>
        <div id="saved-code" className="flex flex-col overflow-hidden rounded-xl border border-line">
          {codeTruncated && (
            <p className="flex items-start gap-2 border-b border-line bg-warning/10 px-4 py-2 text-xs text-fg-2">
              <Scissors size={13} className="mt-0.5 shrink-0 text-warning" aria-hidden />
              Only the first {SAVED_CODE_LIMIT} characters of the code were saved. Findings on later lines are listed under “Not tied to a line”.
            </p>
          )}
          <CodePanel
            className="flex max-h-[75vh] min-h-[24rem]"
            review={review}
            language={null}
            options={[]}
            selectedId={null}
            onSelectReview={() => {}}
            activeFindingId={activeFindingId}
            onSelectFinding={selectFinding}
          />
        </div>
      </div>
    </div>
  )
}
