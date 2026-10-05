import { cn } from '../../lib/cn'

interface LogoMarkProps {
  size?: number
  /** Fill of the inner diamond — match the surface the mark sits on. */
  innerFill?: string
  className?: string
}

/** The PersonaCR diamond mark. */
export function LogoMark({ size = 24, innerFill = 'var(--bg-secondary)', className }: LogoMarkProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" className={className} aria-hidden>
      <rect x="7" y="7" width="14" height="14" rx="2" transform="rotate(45 14 14)" fill="var(--accent)" opacity="0.9" />
      <rect x="10" y="10" width="8" height="8" rx="1" transform="rotate(45 14 14)" fill={innerFill} opacity="0.7" />
      <rect x="12" y="12" width="4" height="4" rx="0.5" transform="rotate(45 14 14)" fill="var(--accent)" />
    </svg>
  )
}

/** Mark + wordmark, used in the app shell. */
export default function Logo({ className }: { className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-2', className)}>
      <LogoMark size={26} />
      <span className="text-[17px] font-semibold tracking-tight text-fg">PersonaCR</span>
    </span>
  )
}
