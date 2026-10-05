import { Bug, Palette } from 'lucide-react'
import { AGENT_LABEL, type Finding } from '../../lib/api'
import { cn } from '../../lib/cn'
import StatusPill from '../ui/StatusPill'
import { SEVERITY_TONE } from './severity'

interface FindingCardProps {
  finding: Finding
  active?: boolean
  /** Shown when the finding is listed apart from the code (no line context). */
  showLine?: boolean
  onSelect?: (finding: Finding) => void
}

/** One agent finding. Findings come from agents (Style Analyst / Defect Hunter), not people. */
export default function FindingCard({ finding: f, active, showLine, onSelect }: FindingCardProps) {
  const AgentIcon = f.kind === 'style' ? Palette : Bug
  const clickable = !!onSelect && f.line != null
  const body = (
    <>
      <div className="flex flex-wrap items-center gap-1.5">
        <span className={cn('inline-flex items-center gap-1 text-xs font-medium', f.kind === 'style' ? 'text-style' : 'text-defect')}>
          <AgentIcon size={12} aria-hidden /> {AGENT_LABEL[f.agent]}
        </span>
        <StatusPill tone={SEVERITY_TONE[f.severity]} className="!py-0 text-[11px]">{f.severity}</StatusPill>
        <span className="text-[11px] text-fg-3">{f.category.replace(/_/g, ' ')}</span>
        {showLine && (
          <span className="ml-auto font-mono text-[11px] text-fg-3">{f.line != null ? `line ${f.line}` : 'line n/a'}</span>
        )}
      </div>
      <p className="mt-1 text-[13px] leading-5 text-fg">{f.description}</p>
      {f.kind === 'style' && (f.repoValue || f.codeValue) && (
        <p className="mt-1 text-xs text-fg-3">
          {f.repoValue && <>Your repo: <span className="text-fg-2">{f.repoValue}</span></>}
          {f.repoValue && f.codeValue && ' · '}
          {f.codeValue && <>This code: <span className="text-fg-2">{f.codeValue}</span></>}
        </p>
      )}
    </>
  )

  const cls = cn(
    'block w-full rounded-lg border px-3 py-2 text-left',
    active ? 'border-accent bg-accent-soft' : 'border-line bg-surface',
    clickable && 'cursor-pointer hover:border-line-strong',
  )

  return clickable ? (
    <button type="button" className={cls} aria-pressed={active} onClick={() => onSelect!(f)}>{body}</button>
  ) : (
    <div className={cls}>{body}</div>
  )
}
