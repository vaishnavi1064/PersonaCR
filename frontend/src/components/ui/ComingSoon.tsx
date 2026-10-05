import { Clock } from 'lucide-react'
import { cn } from '../../lib/cn'
import StatusPill from './StatusPill'

interface ComingSoonProps {
  /** What the feature is, e.g. "Repo summary". */
  feature: string
  /** Why it isn't here yet / what it will do. */
  description?: string
  /** Inline one-liner instead of a block. */
  compact?: boolean
  className?: string
}

/**
 * Honest placeholder for a feature whose backend doesn't exist yet.
 * Never render mock data in its place — render this.
 */
export default function ComingSoon({ feature, description, compact, className }: ComingSoonProps) {
  if (compact) {
    return (
      <span className={cn('inline-flex items-center gap-1.5 text-xs text-fg-3', className)}>
        <Clock size={12} aria-hidden />
        {feature} — coming soon
      </span>
    )
  }
  return (
    <div className={cn('flex items-start gap-3 rounded-xl border border-dashed border-line bg-surface/50 p-4', className)}>
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-line bg-raised text-fg-3" aria-hidden>
        <Clock size={15} />
      </span>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-fg">{feature}</span>
          <StatusPill tone="neutral">Coming soon</StatusPill>
        </div>
        {description && <p className="mt-1 text-[13px] text-fg-3">{description}</p>}
      </div>
    </div>
  )
}
