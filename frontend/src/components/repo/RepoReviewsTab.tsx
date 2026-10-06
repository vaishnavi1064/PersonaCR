import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight, ClipboardCheck } from 'lucide-react'
import { reviewFromRow } from '../../lib/api'
import type { ReviewRow } from '../../lib/db'
import { absoluteTime, relativeTime } from '../../lib/format'
import Button from '../ui/Button'
import Card from '../ui/Card'
import EmptyState from '../ui/EmptyState'
import StatusPill from '../ui/StatusPill'
import { scoreColor, statePill } from '../review/reviewMeta'
import type { Loadable } from './loadable'

interface RepoReviewsTabProps {
  state: Loadable<ReviewRow[]>
  guest: boolean
  onRetry: () => void
}

export default function RepoReviewsTab({ state, guest, onRetry }: RepoReviewsTabProps) {
  const rows = useMemo(
    () => (state.status === 'ok' ? state.data.map((row) => ({ row, ...reviewFromRow(row) })) : []),
    [state],
  )

  if (guest) {
    return <EmptyState icon={<ClipboardCheck size={20} />} title="Guest reviews aren’t saved" description="Sign in with GitHub to keep a history of reviews for this repo." />
  }
  if (state.status === 'loading') {
    return <div className="flex flex-col gap-2" aria-busy>{[0, 1, 2].map((i) => <div key={i} className="h-16 animate-pulse rounded-xl bg-surface" />)}</div>
  }
  if (state.status === 'error') {
    return <EmptyState title="Couldn’t load reviews" description={state.message} action={<Button onClick={onRetry}>Retry</Button>} />
  }
  if (rows.length === 0) {
    return (
      <EmptyState
        icon={<ClipboardCheck size={20} />}
        title="No saved reviews for this repo"
        description="Reviews you run in a chat are saved here. Reviews that couldn’t produce a score (degraded or error) aren’t saved."
      />
    )
  }
  return (
    <Card className="overflow-hidden p-0">
      <ul className="divide-y divide-line">
        {rows.map(({ row, review }) => {
          const pill = statePill(review)
          const firstLine = review.code.split('\n').find((l) => l.trim())?.trim() ?? ''
          return (
            <li key={row.id}>
              <Link to={`/reviews/${row.id}`} className="flex items-center gap-4 px-4 py-3 hover:bg-surface-hover">
                <span className="w-10 shrink-0 text-right text-lg font-bold tabular-nums" style={{ color: scoreColor(review.score) }}>
                  {review.score == null ? '—' : Math.round(review.score)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-mono text-[13px] text-fg">{firstLine || '(empty)'}</span>
                  <span className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-fg-3">
                    <span title={absoluteTime(row.created_at)}>{relativeTime(row.created_at)}</span>
                    <span>{review.findings.length} finding{review.findings.length === 1 ? '' : 's'}</span>
                    {review.iterations > 1 && <span>{review.iterations} passes</span>}
                  </span>
                </span>
                <StatusPill tone={pill.tone}>{pill.label}</StatusPill>
                <ChevronRight size={16} className="shrink-0 text-fg-3" aria-hidden />
              </Link>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}
