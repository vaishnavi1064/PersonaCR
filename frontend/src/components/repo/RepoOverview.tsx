import { Braces, Bug, FileText, GitBranch, Ruler, Sigma, Type } from 'lucide-react'
import { typeHintsMeasured, typeHintsRepresentative, type Repo } from '../../lib/api'
import { absoluteTime, count, pct, relativeTime } from '../../lib/format'
import Card from '../ui/Card'
import StatTile from '../ui/StatTile'
import LanguageBar from './LanguageBar'

interface RepoOverviewProps {
  repo: Repo
  chats: number | null
  reviews: number | null
  onTab: (tab: 'atlas' | 'chats' | 'reviews') => void
}

export default function RepoOverview({ repo, chats, reviews, onTab }: RepoOverviewProps) {
  const fp = repo.fingerprint
  return (
    <div className="flex flex-col gap-5">
      <Card className="p-5">
        <h3 className="text-xs font-medium uppercase tracking-wider text-fg-3">Summary</h3>
        {repo.summary ? (
          <p className="mt-1.5 text-[15px] leading-6 text-fg">{repo.summary}</p>
        ) : (
          <p className="mt-1.5 text-sm text-fg-3">
            {fp ? 'No summary yet — this repo was analyzed before summaries existed. Reanalyze to generate one.' : 'A summary is written when the repo is analyzed.'}
          </p>
        )}
        {repo.summary && <p className="mt-2 text-xs text-fg-3">Written by the model from the repo’s description, README and file names at analysis time.</p>}
      </Card>

      {fp ? (
        <Card className="p-5">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 className="text-sm font-semibold text-fg">Key conventions</h3>
            <button type="button" onClick={() => onTab('atlas')} className="text-xs text-accent-fg cursor-pointer hover:underline">
              Full Convention Atlas →
            </button>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-5 sm:grid-cols-3 lg:grid-cols-4">
            <StatTile icon={<Braces size={16} />} value={fp.totalFunctions != null ? count(fp.totalFunctions) : null} label="Functions measured" />
            <StatTile icon={<Ruler size={16} />} value={fp.avgFunctionLength != null ? `${fp.avgFunctionLength} lines` : null} label="Avg function length" />
            <StatTile icon={<Type size={16} />} value={fp.namingConvention && fp.namingConvention !== 'unknown' ? fp.namingConvention : null} label="Naming" />
            <StatTile icon={<FileText size={16} />} value={fp.docstringCoverage != null ? pct(fp.docstringCoverage) : null} label="Docstrings" />
            <StatTile icon={<Bug size={16} />} value={fp.errorHandlingRate != null ? pct(fp.errorHandlingRate) : null} label="Error handling" />
            <StatTile
              icon={<Type size={16} />}
              value={fp.typeHintUsage != null && typeHintsMeasured(fp) ? pct(fp.typeHintUsage) : null}
              label={!typeHintsMeasured(fp) ? 'Type hints (not measured)' : typeHintsRepresentative(fp) || fp.typeHintFunctions == null ? 'Type hints' : `Type hints (${fp.typeHintFunctions} of ${fp.totalFunctions} fn)`}
            />
            <StatTile icon={<Sigma size={16} />} value={fp.avgComplexity != null ? fp.avgComplexity.toFixed(1) : null} label="Est. complexity" />
          </div>
          <div className="mt-6">
            <h4 className="mb-2 text-xs font-medium uppercase tracking-wider text-fg-3">Languages</h4>
            <LanguageBar distribution={fp.languageDistribution} />
          </div>
        </Card>
      ) : (
        <Card className="p-5 text-sm text-fg-3">No fingerprint yet — analyze this repo to learn its conventions.</Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <Card className="p-5">
          <h3 className="text-sm font-semibold text-fg">Analysis</h3>
          <dl className="mt-3 flex flex-col gap-2 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-fg-3">Last analyzed</dt>
              <dd className="text-fg" title={absoluteTime(repo.analyzedAt)}>{relativeTime(repo.analyzedAt) ?? '—'}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-fg-3">Commit</dt>
              <dd>
                {repo.lastCommitSha ? (
                  <a href={`${repo.url}/commit/${repo.lastCommitSha}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-mono text-xs text-fg hover:underline">
                    <GitBranch size={12} aria-hidden /> {repo.lastCommitSha.slice(0, 7)}
                  </a>
                ) : <span className="text-fg-3">—</span>}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-fg-3">Chunks analyzed</dt>
              <dd className="tabular-nums text-fg">{count(repo.functionsCount)}</dd>
            </div>
          </dl>
          <p className="mt-3 text-xs text-fg-3">The fingerprint is reused until you reanalyze, even if the repo has new commits.</p>
        </Card>
        <Card className="p-5">
          <h3 className="text-sm font-semibold text-fg">Activity</h3>
          <div className="mt-3 grid grid-cols-2 gap-3">
            <button type="button" onClick={() => onTab('chats')} className="rounded-lg border border-line px-3 py-2.5 text-left cursor-pointer hover:border-line-strong">
              <span className="block text-xl font-semibold tabular-nums text-fg">{chats ?? '—'}</span>
              <span className="text-xs text-fg-3">Chats</span>
            </button>
            <button type="button" onClick={() => onTab('reviews')} className="rounded-lg border border-line px-3 py-2.5 text-left cursor-pointer hover:border-line-strong">
              <span className="block text-xl font-semibold tabular-nums text-fg">{reviews ?? '—'}</span>
              <span className="text-xs text-fg-3">Saved reviews</span>
            </button>
          </div>
        </Card>
      </div>
    </div>
  )
}
