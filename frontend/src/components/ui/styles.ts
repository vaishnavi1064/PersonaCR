import { cn } from '../../lib/cn'

export type ButtonVariant = 'primary' | 'outline' | 'ghost' | 'danger'
export type ButtonSize = 'sm' | 'md'

const base =
  'inline-flex items-center justify-center gap-2 rounded-lg font-medium whitespace-nowrap ' +
  'cursor-pointer select-none disabled:cursor-not-allowed disabled:opacity-50'

const variants: Record<ButtonVariant, string> = {
  primary: 'bg-accent-strong text-on-accent hover:brightness-110 shadow-[0_0_0_1px_var(--accent-glow),0_4px_16px_var(--accent-glow)]',
  outline: 'border border-line bg-transparent text-fg hover:border-line-strong hover:bg-surface-hover',
  ghost: 'bg-transparent text-fg-2 hover:bg-surface-hover hover:text-fg',
  danger: 'border border-line bg-transparent text-danger hover:border-danger/40 hover:bg-danger/10',
}

const sizes: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-[13px]',
  md: 'h-9 px-4 text-sm',
}

/** Button classes — shared by <Button> and router <Link>s styled as buttons. */
export function buttonClass(variant: ButtonVariant = 'outline', size: ButtonSize = 'md', extra?: string) {
  return cn(base, variants[variant], sizes[size], extra)
}
