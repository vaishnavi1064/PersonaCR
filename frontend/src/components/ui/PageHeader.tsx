import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

interface PageHeaderProps {
  title: string
  description?: ReactNode
  /** Right-aligned filters / actions. */
  actions?: ReactNode
  className?: string
}

/** Large bold page title with actions on the right, as on the reference Repositories page. */
export default function PageHeader({ title, description, actions, className }: PageHeaderProps) {
  return (
    <div className={cn('flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between', className)}>
      <div className="min-w-0">
        <h1 className="text-[28px] font-bold leading-tight tracking-tight text-fg sm:text-[34px]">{title}</h1>
        {description && <p className="mt-1.5 text-sm text-fg-3">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}
