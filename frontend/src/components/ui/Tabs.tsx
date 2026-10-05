import { useRef, type KeyboardEvent } from 'react'
import { cn } from '../../lib/cn'

interface TabItem { id: string; label: string; count?: number }

interface TabsProps {
  items: TabItem[]
  value: string
  onChange: (id: string) => void
  /** Accessible name for the tab list. */
  label: string
  className?: string
}

/** Underlined tab bar with arrow-key navigation. Panels are rendered by the caller. */
export default function Tabs({ items, value, onChange, label, className }: TabsProps) {
  const refs = useRef<Array<HTMLButtonElement | null>>([])

  function onKeyDown(e: KeyboardEvent, idx: number) {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
    e.preventDefault()
    const next = (idx + (e.key === 'ArrowRight' ? 1 : -1) + items.length) % items.length
    onChange(items[next].id)
    refs.current[next]?.focus()
  }

  return (
    <div role="tablist" aria-label={label} className={cn('flex gap-1 overflow-x-auto border-b border-line', className)}>
      {items.map((t, i) => {
        const active = t.id === value
        return (
          <button
            key={t.id}
            ref={(el) => { refs.current[i] = el }}
            role="tab"
            type="button"
            aria-selected={active}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(t.id)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={cn(
              '-mb-px inline-flex items-center gap-2 whitespace-nowrap border-b-2 px-3 py-2.5 text-sm cursor-pointer',
              active ? 'border-accent text-fg font-medium' : 'border-transparent text-fg-3 hover:text-fg-2',
            )}
          >
            {t.label}
            {t.count != null && (
              <span className="rounded-full bg-raised px-1.5 text-[11px] tabular-nums text-fg-3">{t.count}</span>
            )}
          </button>
        )
      })}
    </div>
  )
}
