import { useEffect, useRef } from 'react'
import { cn } from '../../lib/cn'

interface CodeViewProps {
  code: string
  /** 1-based line to highlight (e.g. the line of a clicked finding). */
  highlightLine?: number | null
  className?: string
}

/** Read-only code block with a line-number gutter and an optional highlighted line. */
export default function CodeView({ code, highlightLine, className }: CodeViewProps) {
  const lines = code.replace(/\n$/, '').split('\n')
  const lineRefs = useRef<Array<HTMLDivElement | null>>([])

  useEffect(() => {
    if (highlightLine == null) return
    lineRefs.current[highlightLine - 1]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [highlightLine])

  const gutter = String(lines.length).length

  return (
    <div className={cn('overflow-auto rounded-lg border border-line bg-canvas py-2 font-mono text-[12.5px] leading-6', className)}>
      <div className="min-w-max">
        {lines.map((line, i) => {
          const n = i + 1
          const hit = n === highlightLine
          return (
            <div
              key={i}
              ref={(el) => { lineRefs.current[i] = el }}
              className={cn('flex border-l-2 pr-4', hit ? 'border-accent bg-accent-soft' : 'border-transparent')}
              aria-current={hit ? 'true' : undefined}
            >
              <span
                className={cn('select-none px-3 text-right tabular-nums', hit ? 'text-accent-fg' : 'text-fg-3')}
                style={{ minWidth: `${gutter + 2}ch` }}
                aria-hidden
              >
                {n}
              </span>
              <span className="whitespace-pre text-fg-2">{line || ' '}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
