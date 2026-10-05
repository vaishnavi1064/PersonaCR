import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: ReactNode
  action?: ReactNode
  className?: string
}

export default function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center rounded-xl border border-dashed border-line px-6 py-14 text-center', className)}>
      {icon && (
        <span className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl border border-line bg-raised text-accent" aria-hidden>
          {icon}
        </span>
      )}
      <h2 className="text-base font-semibold text-fg">{title}</h2>
      {description && <p className="mt-1.5 max-w-md text-sm text-fg-3">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}
