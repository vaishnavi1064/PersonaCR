import { Code2, Gauge, GitCompare, RotateCcw, ShieldCheck, TriangleAlert } from 'lucide-react'
import { explainDegraded, type Review, type Severity } from '../../lib/api'
import { pct } from '../../lib/format'
import { cn } from '../../lib/cn'
import Button from '../ui/Button'
import StatusPill, { type PillTone } from '../ui/StatusPill'
import { severityColor } from '../studio/severity'
import TraceTimeline from './TraceTimeline'

interface ReviewSummaryProps {
  review: Review
  /** This review is the one shown in the code panel. */
  active: boolean
  onOpenCode: () => void
  /** Re-run the same code (degraded/error only). Omit to hide the button. */
  onRetry?: () => void
  retryDisabled?: boolean
}

const SEVERITIES: Severity[] = ['critical', 'high', 'medium', 'low']

function scoreColor(score: number): string {
  if (score >= 70) return 'var(--success)'
  if (score >= 50) return 'var(--warning)'
  return 'var(--error)'
}

function statePill(r: Review): { tone: PillTone; label: string } {
  if (r.state === 'error') return { tone: 'danger', label: 'Error' }
  if (r.state === 'degraded') return { tone: 'warning', label: 'Degraded' }
  if (r.state === 'low_confidence') return { tone: 'warning', label: 'Low confidence' }
  if (r.backendStatus === 'quality_gate_failed') return { tone: 'warning', label: 'Quality gate failed' }
  return { tone: 'success', label: 'Passed' }
}

const fmt2 = (v: number | null) => (v == null ? '—' : v.toFixed(2))

/**
 * Compact Review Result for the message stream: score (or "—"), state,
 * counts, and context. The full findings live in the code panel.
 */
export default function ReviewSummary({ review: r, active, onOpenCode, onRetry, retryDisabled }: ReviewSummaryProps) {
  const pill = statePill(r)
  const unscored = r.state === 'degraded' || r.state === 'error'
  const why = explainDegraded(r.degradedReason)
  const counts = SEVERITIES.map((s) => [s, r.findings.filter((f) => f.severity === s).length] as const).filter(([, n]) => n > 0)
  const style = r.findings.filter((f) => f.kind === 'style').length
  const defect = r.findings.length - style

  return (
    <div className="flex flex-col gap-3.5">
      {/* Score + state */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <p className="flex items-baseline gap-1" aria-label={r.score == null ? 'No score' : `Score ${Math.round(r.score)} out of 100`}>
          <span
            className="text-[34px] font-bold leading-none tracking-tight tabular-nums"
            style={{ color: r.score == null ? 'var(--text-tertiary)' : scoreColor(r.score) }}
            aria-hidden
          >
            {r.score == null ? '—' : Math.round(r.score)}
          </span>
          {r.score != null && <span className="text-sm text-fg-3" aria-hidden>/100</span>}
        </p>
        <StatusPill tone={pill.tone}>{pill.label}</StatusPill>
        {r.iterations > 1 && <StatusPill tone="neutral">Re-reviewed · {r.iterations} passes</StatusPill>}
        {!unscored && (r.styleScore != null || r.defectScore != null) && (
          <span className="ml-auto text-xs text-fg-3 tabular-nums">
            Style {r.styleScore == null ? '—' : Math.round(r.styleScore)} · Defects {r.defectScore == null ? '—' : Math.round(r.defectScore)}
          </span>
        )}
      </div>

      {/* State banners */}
      {r.state === 'low_confidence' && (
        <div className="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2.5 text-[13px]" role="note">
          <p className="flex items-center gap-1.5 font-medium text-warning">
            <TriangleAlert size={14} aria-hidden /> Low confidence{r.confidence.score != null && ` (${pct(r.confidence.score)})`} — treat these findings as a starting point
          </p>
          {r.confidence.reason && <p className="mt-1 text-fg-2">{r.confidence.reason}</p>}
          {r.confidence.suggestion && <p className="mt-1 text-fg-3">Try: {r.confidence.suggestion}</p>}
        </div>
      )}
      {unscored && (
        <div
          className={cn('rounded-lg border px-3 py-2.5 text-[13px]', r.state === 'error' ? 'border-danger/30 bg-danger/10' : 'border-warning/30 bg-warning/10')}
          role="alert"
        >
          <p className={cn('flex items-center gap-1.5 font-medium', r.state === 'error' ? 'text-danger' : 'text-warning')}>
            <TriangleAlert size={14} aria-hidden />
            {r.state === 'error' ? 'The review couldn’t run — no score' : 'Some agents failed — this review is incomplete, so there’s no score'}
          </p>
          {why.hint && <p className="mt-1 text-fg">{why.hint}</p>}
          <p className="mt-0.5 text-fg-2">{why.summary}</p>
          {why.detail && (
            <details className="mt-1 text-xs text-fg-3">
              <summary className="cursor-pointer select-none hover:text-fg-2">Technical details</summary>
              <p className="mt-1 break-words font-mono">{why.detail}</p>
            </details>
          )}
          {onRetry && (
            <Button size="sm" className="mt-2.5" icon={<RotateCcw size={14} />} onClick={onRetry} disabled={retryDisabled}>
              Retry review
            </Button>
          )}
        </div>
      )}

      {/* Counts */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[13px]">
        {r.findings.length === 0 ? (
          <span className="text-fg-3">{unscored ? 'No findings returned' : 'No findings — nothing to flag'}</span>
        ) : (
          <>
            <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
              {counts.map(([s, n]) => (
                <span key={s} className="inline-flex items-center gap-1.5 text-fg-2">
                  <span className="h-2 w-2 rounded-full" style={{ background: severityColor(s) }} aria-hidden />
                  <span className="tabular-nums font-medium text-fg">{n}</span> {s}
                </span>
              ))}
            </span>
            <span className="text-fg-3">
              <span className="text-style">Style Analyst</span> {style} · <span className="text-defect">Defect Hunter</span> {defect}
            </span>
          </>
        )}
      </div>

      {/* Context */}
      <ul className="flex flex-col gap-1 text-xs text-fg-3">
        {r.retrievalExamples != null && (
          <li className="flex items-start gap-1.5">
            <GitCompare size={13} className="mt-px shrink-0" aria-hidden />
            {r.retrievalExamples > 0
              ? <>Compared against {r.retrievalExamples} of your functions</>
              : <>No similar functions from this repo were found — compared against its fingerprint only</>}
          </li>
        )}
        {!unscored && r.confidence.score != null && r.state !== 'low_confidence' && (
          <li className="flex items-center gap-1.5"><Gauge size={13} aria-hidden /> Confidence {pct(r.confidence.score)}</li>
        )}
        {!unscored && (r.crScore.comprehensiveness != null || r.crScore.relevance != null) && (
          <li className="flex items-start gap-1.5" title="CRScore-style review quality: how much of the code's issues the review covers, how focused it is, and their balance">
            <ShieldCheck size={13} className="mt-px shrink-0" aria-hidden />
            <span>
              Review quality — coverage {fmt2(r.crScore.comprehensiveness)} · focus {fmt2(r.crScore.conciseness)} · relevance {fmt2(r.crScore.relevance)}
              {r.qualityGatePassed != null && <> · quality gate {r.qualityGatePassed ? 'passed' : 'not passed'}</>}
            </span>
          </li>
        )}
      </ul>

      {/* Trace + link to the code panel */}
      <div className="border-t border-line pt-3">
        <TraceTimeline
          steps={r.trace}
          actions={
            <Button size="sm" variant={active ? 'ghost' : 'outline'} icon={<Code2 size={14} />} onClick={onOpenCode} aria-pressed={active}>
              {active ? 'Shown in code panel' : r.findings.length > 0 ? `View ${r.findings.length} finding${r.findings.length === 1 ? '' : 's'} in code` : 'View code'}
            </Button>
          }
        />
      </div>
    </div>
  )
}
