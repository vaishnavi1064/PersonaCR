import { Link } from 'react-router-dom'
import { parseRepoUrl, repoShortName } from '../../lib/api'
import type { RepoRollup } from '../../lib/dashboardStats'
import { absoluteTime, relativeTime } from '../../lib/format'
import Card from '../ui/Card'
import GitHubMark from '../ui/GitHubMark'
import { scoreColor } from '../review/reviewMeta'

/** One row per repo — each repo is measured against its own fingerprint, never a blend. */
export default function RepoRollupTable({ rows, onFilter }: { rows: RepoRollup[]; onFilter: (repoUrl: string) => void }) {
  return (
    <Card className="overflow-hidden p-0">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs text-fg-3">
              <th scope="col" className="px-4 py-2.5 font-medium">Repository</th>
              <th scope="col" className="px-4 py-2.5 text-right font-medium">Reviews</th>
              <th scope="col" className="px-4 py-2.5 text-right font-medium">Avg score</th>
              <th scope="col" className="px-4 py-2.5 font-medium">Last review</th>
              <th scope="col" className="px-4 py-2.5"><span className="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((r) => {
              const parsed = parseRepoUrl(r.repoUrl)
              return (
                <tr key={r.repoUrl}>
                  <td className="max-w-[16rem] px-4 py-2.5">
                    <button type="button" onClick={() => onFilter(r.repoUrl)} className="inline-flex max-w-full items-center gap-1.5 text-fg cursor-pointer hover:underline">
                      <GitHubMark size={12} /> <span className="truncate">{repoShortName(r.repoUrl)}</span>
                    </button>
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-fg-2">
                    {r.reviews}{r.scored < r.reviews && <span className="text-fg-3"> ({r.reviews - r.scored} unscored)</span>}
                  </td>
                  <td className="px-4 py-2.5 text-right font-semibold tabular-nums" style={{ color: scoreColor(r.avgScore) }}>
                    {r.avgScore == null ? '—' : r.avgScore.toFixed(1)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-fg-2" title={absoluteTime(r.lastAt)}>{relativeTime(r.lastAt) ?? '—'}</td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-right">
                    {parsed && <Link to={`/repos/${parsed.owner}/${parsed.name}?tab=atlas`} className="text-xs text-accent-fg hover:underline">Conventions →</Link>}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
