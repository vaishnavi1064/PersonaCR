import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

interface StatTileProps {
  icon: ReactNode
  /** null renders as "—" (unknown), never 0. */
  value: ReactNode | null
  label: string
  className?: string
}

/** Icon square + value + label, as in the reference card's "1,452 Functions". */
export default function StatTile({ icon, value, label, className }: StatTileProps) {
  return (
    <div className={cn('flex min-w-0 items-center gap-2.5', className)}>
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-line bg-raised text-accent" aria-hidden>
        {icon}
      </span>
      <span className="min-w-0">
        <span className="block truncate text-lg font-semibold leading-tight text-fg tabular-nums">
          {value ?? '—'}
        </span>
        <span className="block truncate text-xs text-fg-3">{label}</span>
      </span>
    </div>
  )
}
