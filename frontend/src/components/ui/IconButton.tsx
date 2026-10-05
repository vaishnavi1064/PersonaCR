import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { cn } from '../../lib/cn'

interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> {
  /** Accessible name; also shown as the tooltip. */
  label: string
  icon: ReactNode
  variant?: 'ghost' | 'outline'
  size?: 'sm' | 'md'
}

export default function IconButton({
  label, icon, variant = 'ghost', size = 'md', className, type = 'button', ...rest
}: IconButtonProps) {
  return (
    <button
      type={type}
      aria-label={label}
      title={label}
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-lg text-fg-2 cursor-pointer',
        'hover:bg-surface-hover hover:text-fg disabled:cursor-not-allowed disabled:opacity-50',
        variant === 'outline' && 'border border-line hover:border-line-strong',
        size === 'sm' ? 'h-8 w-8' : 'h-9 w-9',
        className,
      )}
      {...rest}
    >
      {icon}
    </button>
  )
}
