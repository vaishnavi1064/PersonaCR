import { useId, useMemo, useState, type ReactNode } from 'react'
import { ChevronRight } from 'lucide-react'
import { AGENT_LABEL, type AgentName, type TraceStep } from '../../lib/api'
import { cn } from '../../lib/cn'
import { formatMs, layoutTimeline } from '../../lib/timeline'

function agentLabel(agent: string): string {
  return AGENT_LABEL[agent as AgentName] ?? agent.replace(/_/g, ' ')
}

function agentColor(agent: string): string {
  if (agent === 'style_analyst') return 'var(--style-accent)'
  if (agent === 'defect_hunter') return 'var(--defect-accent)'
  if (agent.startsWith('quality_gate')) return 'var(--success)'
  return 'var(--accent)'
}

/** Collapsible agent timeline with duration bars; Style Analyst ∥ Defect Hunter drawn side by side in time. */
export default function TraceTimeline({ steps, actions }: { steps: TraceStep[]; actions?: ReactNode }) {
  const [open, setOpen] = useState(false)
  const panelId = useId()
  const { rows, total } = useMemo(() => layoutTimeline(steps), [steps])
  if (steps.length === 0) return actions ? <div className="flex justify-end">{actions}</div> : null
  const multiPass = steps.some((s) => s.iteration > 1)

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 rounded-md py-1 text-[13px] text-fg-2 cursor-pointer hover:text-fg"
      >
        <ChevronRight size={14} className={cn('transition-transform', open && 'rotate-90')} aria-hidden />
        Agent trace
        <span className="text-fg-3">· {steps.length} steps · {formatMs(total)}</span>
      </button>
      {actions}
      </div>

      {open && (
        <div id={panelId} className="mt-2">
          <ol className="flex flex-col gap-2.5">
            {rows.map((r, i) => {
              const pairedNext = rows[i + 1]?.step.parallel
              const inPair = r.step.parallel || pairedNext
              const left = total > 0 ? (r.start / total) * 100 : 0
              const width = total > 0 ? (r.duration / total) * 100 : 0
              const summary = [r.step.outputSummary, r.step.decision].filter(Boolean).join(' — ')
              return (
                <li key={i} className="grid grid-cols-[minmax(0,9.5rem)_1fr_3.5rem] items-center gap-x-3 gap-y-0.5 sm:grid-cols-[11rem_1fr_3.5rem]">
                  <span className="flex min-w-0 items-center gap-1.5 text-xs">
                    <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: agentColor(r.step.agent) }} aria-hidden />
                    <span className="truncate text-fg">{agentLabel(r.step.agent)}</span>
                    {multiPass && <span className="shrink-0 font-mono text-[10px] text-fg-3">#{r.step.iteration}</span>}
                    {inPair && <span className="shrink-0 rounded border border-line px-1 text-[10px] leading-4 text-fg-3" title="Ran in parallel">parallel</span>}
                  </span>
                  <span className="relative h-2 rounded-full bg-raised" aria-hidden>
                    {r.duration > 0 ? (
                      <span
                        className="absolute inset-y-0 rounded-full"
                        style={{ left: `${left}%`, width: `max(${width}%, 3px)`, background: agentColor(r.step.agent) }}
                      />
                    ) : (
                      <span className="absolute top-1/2 h-1.5 w-1.5 -translate-y-1/2 rounded-full border border-fg-3" style={{ left: `${left}%` }} />
                    )}
                  </span>
                  <span className="text-right font-mono text-[11px] tabular-nums text-fg-3">
                    <span className="sr-only">{agentLabel(r.step.agent)} took </span>{formatMs(r.duration)}
                  </span>
                  {summary && (
                    <span className="col-span-3 truncate pl-3.5 text-[11px] text-fg-3" title={summary}>{summary}</span>
                  )}
                </li>
              )
            })}
          </ol>
          <p className="mt-3 text-[11px] text-fg-3">
            Bars are placed from each agent’s reported duration (no timestamps are recorded). Style Analyst and Defect Hunter run in parallel.
          </p>
        </div>
      )}
    </div>
  )
}
