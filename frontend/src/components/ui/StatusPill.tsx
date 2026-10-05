import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

export type PillTone = 'success' | 'neutral' | 'accent' | 'warning' | 'danger'

const toneVar: Record<PillTone, string> = {
  success: 'var(--success)',
  neutral: 'var(--text-tertiary)',
  accent:  'var(--accent)',
  warning: 'var(--warning)',
  danger:  'var(--error)',
}

interface StatusPillProps {
  tone: PillTone
  children: ReactNode
  /** Pulsing dot for in-progress states (e.g. Analyzing). */
  pulse?: boolean
  className?: string
}

/** Tinted outline pill, as on the reference repo cards (Active / Archived / Building). */
export default function StatusPill({ tone, children, pulse, className }: StatusPillProps) {
  const c = toneVar[tone]
  return (
    <span
      className={cn('inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium leading-5', className)}
      style={{
        color: tone === 'neutral' ? 'var(--text-secondary)' : c,
        borderColor: `color-mix(in srgb, ${c} 40%, transparent)`,
        background: `color-mix(in srgb, ${c} 12%, transparent)`,
      }}
    >
      {pulse && (
        <span className="relative flex h-1.5 w-1.5" aria-hidden>
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60" style={{ background: c }} />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full" style={{ background: c }} />
        </span>
      )}
      {children}
    </span>
  )
}
