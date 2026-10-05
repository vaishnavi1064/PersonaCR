import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

interface ChipProps {
  children: ReactNode
  icon?: ReactNode
  title?: string
  className?: string
}

/** Small neutral label, e.g. fingerprint stats ("79% type hints", "snake_case"). */
export default function Chip({ children, icon, title, className }: ChipProps) {
  return (
    <span
      title={title}
      className={cn(
        'inline-flex items-center gap-1 rounded-md border border-line bg-raised px-2 py-0.5 text-xs text-fg-2 whitespace-nowrap',
        className,
      )}
    >
      {icon}
      {children}
    </span>
  )
}
