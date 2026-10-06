import { useMemo } from 'react'
import { Code2, TriangleAlert, X } from 'lucide-react'
import { capabilityLevel, explainDegraded, REVIEW_LANGUAGES, type Finding, type Review } from '../../lib/api'
import { cn } from '../../lib/cn'
import CodeView from '../ui/CodeView'
import FilterSelect from '../ui/FilterSelect'
import IconButton from '../ui/IconButton'
import EmptyState from '../ui/EmptyState'
import ComingSoon from '../ui/ComingSoon'
import FindingCard from './FindingCard'
import { SEVERITY_RANK, severityColor } from './severity'

export interface ReviewOption { id: string; label: string }

interface CodePanelProps {
  review: Review | null
  language: string | null
  options: ReviewOption[]
  selectedId: string | null
  onSelectReview: (id: string) => void
  activeFindingId: string | null
  onSelectFinding: (f: Finding) => void
  /** Drawer mode (below xl): show a close button. */
  onClose?: () => void
  className?: string
}

/** Right pane: the reviewed code with agent findings next to their lines. */
export default function CodePanel({
  review, language, options, selectedId, onSelectReview, activeFindingId, onSelectFinding, onClose, className,
}: CodePanelProps) {
  const byLine = useMemo(() => {
    const m = new Map<number, Finding[]>()
    for (const f of review?.findings ?? []) {
      if (f.line == null) continue
      m.set(f.line, [...(m.get(f.line) ?? []), f])
    }
    for (const list of m.values()) list.sort((a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity])
    return m
  }, [review])

  const unlined = (review?.findings ?? []).filter((f) => f.line == null)
  const active = review?.findings.find((f) => f.id === activeFindingId) ?? null
  const langLabel = REVIEW_LANGUAGES.find((l) => l.value === language)?.label ?? language
  const lineCount = review ? review.code.replace(/\n$/, '').split('\n').length : 0
  const styleCount = review?.findings.filter((f) => f.kind === 'style').length ?? 0
  const defectCount = (review?.findings.length ?? 0) - styleCount

  return (
    <aside className={cn('flex min-h-0 flex-col bg-sidebar', className)} aria-label="Code panel">
      <div className="flex h-12 shrink-0 items-center gap-2 border-b border-line px-4">
        <Code2 size={15} className="text-fg-3" aria-hidden />
        <h2 className="text-sm font-semibold text-fg">Reviewed code</h2>
        {review && <span className="truncate text-xs text-fg-3">{[langLabel, `${lineCount} lines`].filter(Boolean).join(' · ')}</span>}
        <div className="ml-auto flex items-center gap-1.5">
          {options.length > 1 && selectedId && (
            <FilterSelect label="Review" value={selectedId} options={options.map((o) => ({ value: o.id, label: o.label }))} onChange={onSelectReview} className="max-w-44" />
          )}
          {onClose && <IconButton label="Close code panel" icon={<X size={16} />} size="sm" onClick={onClose} />}
        </div>
      </div>

      {!review ? (
        <div className="flex flex-1 items-center p-6">
          <EmptyState
            className="w-full"
            icon={<Code2 size={20} />}
            title="No code reviewed in this chat yet"
            description="Switch to “Review code”, paste a function, and the agents’ findings appear here next to their lines."
          />
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-line px-4 py-2 text-xs text-fg-3">
            <span><span className="font-medium text-style">Style Analyst</span> {styleCount}</span>
            <span><span className="font-medium text-defect">Defect Hunter</span> {defectCount}</span>
            <span className="ml-auto">{review.findings.length - unlined.length} on a line · {unlined.length} not tied to a line</span>
          </div>

          {(review.state === 'degraded' || review.state === 'error') && (
            <p className="flex items-start gap-2 border-b border-line bg-warning/10 px-4 py-2 text-xs text-fg-2" role="status">
              <TriangleAlert size={13} className="mt-0.5 shrink-0 text-warning" aria-hidden />
              <span>No score — {explainDegraded(review.degradedReason).hint ?? explainDegraded(review.degradedReason).summary} Findings below may be incomplete.</span>
            </p>
          )}

          <div className="min-h-0 flex-1 overflow-auto">
            <CodeView
              code={review.code}
              language={language ?? undefined}
              highlightLine={active?.line ?? null}
              marker={(n) => {
                const list = byLine.get(n)
                return list ? <span className="block h-2 w-2 rounded-full" style={{ background: severityColor(list[0].severity) }} /> : null
              }}
              onLineClick={(n) => { const first = byLine.get(n)?.[0]; if (first) onSelectFinding(first) }}
              annotation={(n) => {
                const list = byLine.get(n)
                if (!list) return null
                return (
                  <div className="flex max-w-lg flex-col gap-1.5">
                    {list.map((f) => <FindingCard key={f.id} finding={f} active={f.id === activeFindingId} onSelect={onSelectFinding} />)}
                  </div>
                )
              }}
            />

            {unlined.length > 0 && (
              <section className="border-t border-line px-4 py-4" aria-label="Findings not tied to a line">
                <h3 className="text-xs font-medium uppercase tracking-wider text-fg-3">Not tied to a line ({unlined.length})</h3>
                <div className="mt-2 flex flex-col gap-1.5">
                  {unlined.map((f) => <FindingCard key={f.id} finding={f} showLine />)}
                </div>
                {capabilityLevel('findingLines') !== 'available' && (
                  <ComingSoon compact feature="Line numbers for style findings" className="mt-3" />
                )}
              </section>
            )}

            {review.findings.length === 0 && (
              <p className="border-t border-line px-4 py-4 text-sm text-fg-3">
                {review.state === 'ok' || review.state === 'low_confidence'
                  ? 'The agents found nothing to flag in this code.'
                  : 'No findings — the review did not complete reliably.'}
              </p>
            )}
          </div>
        </div>
      )}
    </aside>
  )
}
