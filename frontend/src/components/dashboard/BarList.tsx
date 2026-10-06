import { useState } from 'react'

export interface BarItem {
  key: string
  label: string
  value: number
  /** Text at the bar tip. */
  display: string
  /** Extra line in the hover tooltip. */
  detail?: string
}

/**
 * One-series horizontal bars: one color for every bar (no hue per category),
 * ≤ 24px thick with a rounded data end, value at the tip, hover tooltip.
 */
export default function BarList({ items, label }: { items: BarItem[]; label: string }) {
  const [hover, setHover] = useState<string | null>(null)
  const max = Math.max(...items.map((i) => i.value), 0)
  return (
    <ul className="flex flex-col gap-3" aria-label={label}>
      {items.map((it) => (
        <li
          key={it.key}
          className="relative"
          onMouseEnter={() => setHover(it.key)}
          onMouseLeave={() => setHover(null)}
        >
          <div className="mb-1 flex items-baseline justify-between gap-3 text-[13px]">
            <span className="truncate text-fg-2">{it.label}</span>
          </div>
          {/* Value at the bar tip; the longest bar leaves room for its label */}
          <div className="flex items-center gap-2">
            <div
              className="h-2.5 shrink-0 rounded-r-[4px]"
              style={{ width: `calc((100% - 4.5rem) * ${max ? Math.max(it.value / max, 0.01) : 0})`, background: 'var(--chart-series)' }}
            />
            <span className="shrink-0 text-xs font-medium tabular-nums text-fg">{it.display}</span>
          </div>
          {hover === it.key && it.detail && (
            <div className="pointer-events-none absolute right-0 top-0 z-10 -translate-y-full rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs text-fg-2 shadow-pop">
              {it.detail}
            </div>
          )}
        </li>
      ))}
    </ul>
  )
}
