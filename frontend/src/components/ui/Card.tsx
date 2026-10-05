import type { HTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** Hover lift for cards that act as a whole (e.g. a repo card). */
  interactive?: boolean
}

export default function Card({ interactive, className, ...rest }: CardProps) {
  return (
    <div
      className={cn(
        'rounded-xl border border-line bg-surface',
        interactive && 'hover:border-line-strong hover:bg-surface-hover',
        className,
      )}
      {...rest}
    />
  )
}

/** Hairline divider used inside cards between sections. */
export function CardDivider({ className }: { className?: string }) {
  return <div className={cn('h-px bg-line', className)} role="presentation" />
}
