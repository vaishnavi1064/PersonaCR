import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { repoShortName, type Review } from '../../lib/api'
import { absoluteTime } from '../../lib/format'
import Card from '../ui/Card'
import Button from '../ui/Button'
import StatusPill from '../ui/StatusPill'
import { scoreColor, statePill } from '../review/reviewMeta'

const PAGE = 15

/** Saved reviews, newest first; every row opens /reviews/:id. Doubles as the table view of the trend chart. */
export default function ReviewHistoryTable({ reviews, showRepo }: { reviews: Review[]; showRepo: boolean }) {
  const navigate = useNavigate()
  const [all, setAll] = useState(false)
  const rows = all ? reviews : reviews.slice(0, PAGE)

  return (
    <Card className="overflow-hidden p-0">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs text-fg-3">
              <th scope="col" className="px-4 py-2.5 font-medium">Date</th>
              {showRepo && <th scope="col" className="px-4 py-2.5 font-medium">Repository</th>}
              <th scope="col" className="px-4 py-2.5 font-medium">Code</th>
              <th scope="col" className="px-4 py-2.5 text-right font-medium">Score</th>
              <th scope="col" className="px-4 py-2.5 text-right font-medium">Findings</th>
              <th scope="col" className="px-4 py-2.5 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((r) => {
              const pill = statePill(r)
              const to = `/reviews/${r.id}`
              const firstLine = r.code.split('\n').find((l) => l.trim())?.trim() ?? ''
              return (
                <tr key={r.id} className="cursor-pointer hover:bg-surface-hover" onClick={() => navigate(to)}>
                  <td className="whitespace-nowrap px-4 py-2.5">
                    <Link to={to} className="text-fg hover:underline" title={absoluteTime(r.createdAt)} onClick={(e) => e.stopPropagation()}>
                      {r.createdAt ? new Date(r.createdAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'}
                    </Link>
                  </td>
                  {showRepo && <td className="max-w-[14rem] truncate px-4 py-2.5 text-fg-2">{repoShortName(r.repoUrl)}</td>}
                  <td className="max-w-[18rem] truncate px-4 py-2.5 font-mono text-xs text-fg-2">{firstLine}</td>
                  <td className="px-4 py-2.5 text-right font-semibold tabular-nums" style={{ color: scoreColor(r.score) }}>
                    {r.score == null ? '—' : Math.round(r.score)}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-fg-2">{r.findings.length}</td>
                  <td className="px-4 py-2.5"><StatusPill tone={pill.tone}>{pill.label}</StatusPill></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {reviews.length > PAGE && (
        <div className="border-t border-line px-4 py-2.5 text-right">
          <Button size="sm" variant="ghost" onClick={() => setAll((v) => !v)}>
            {all ? 'Show fewer' : `Show all ${reviews.length}`}
          </Button>
        </div>
      )}
    </Card>
  )
}
