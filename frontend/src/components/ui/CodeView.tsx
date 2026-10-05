import { useEffect, useRef, useState, type ReactNode } from 'react'
import { cn } from '../../lib/cn'
import { highlightLines, type Token } from '../../lib/highlight'

interface CodeViewProps {
  code: string
  /** Syntax highlighting; unsupported languages render as plain text. */
  language?: string
  /** 1-based line to highlight (e.g. the line of a clicked finding). */
  highlightLine?: number | null
  /** Gutter marker for a line (e.g. a severity dot). */
  marker?: (line: number) => ReactNode
  /** Content rendered under a line (e.g. the findings on it). */
  annotation?: (line: number) => ReactNode
  /** Click on a line's number/marker. */
  onLineClick?: (line: number) => void
  className?: string
}

/** Load highlighted tokens; null (plain text) until ready or when unsupported. */
function useHighlighted(code: string, language: string | undefined): Token[][] | null {
  const key = `${language}\u0000${code}`
  const [state, setState] = useState<{ key: string; lines: Token[][] | null } | null>(null)
  useEffect(() => {
    if (!language) return
    let alive = true
    highlightLines(code, language).then(
      (lines) => { if (alive) setState({ key, lines }) },
      () => { if (alive) setState({ key, lines: null }) },
    )
    return () => { alive = false }
  }, [key, code, language])
  return state?.key === key ? state.lines : null
}

/** Read-only code with a line-number gutter, optional highlight, markers and inline annotations. */
export default function CodeView({ code, language, highlightLine, marker, annotation, onLineClick, className }: CodeViewProps) {
  const lines = code.replace(/\n$/, '').split('\n')
  const tokens = useHighlighted(code.replace(/\n$/, ''), language)
  const lineRefs = useRef<Array<HTMLDivElement | null>>([])

  useEffect(() => {
    if (highlightLine == null) return
    // inline 'start': rows span the full scroll width — never scroll the gutter out of view
    lineRefs.current[highlightLine - 1]?.scrollIntoView({ block: 'center', inline: 'start', behavior: 'smooth' })
  }, [highlightLine])

  const gutter = String(lines.length).length

  return (
    <div className={cn('overflow-auto bg-canvas py-2 font-mono text-[12.5px] leading-6', className)}>
      <div className="min-w-max">
        {lines.map((line, i) => {
          const n = i + 1
          const hit = n === highlightLine
          const mark = marker?.(n)
          const note = annotation?.(n)
          const lineTokens = tokens?.[i]
          return (
            <div key={i}>
              <div
                ref={(el) => { lineRefs.current[i] = el }}
                className={cn('flex border-l-2 pr-4', hit ? 'border-accent bg-accent-soft' : 'border-transparent')}
                aria-current={hit ? 'true' : undefined}
              >
                <button
                  type="button"
                  tabIndex={onLineClick && mark ? 0 : -1}
                  disabled={!onLineClick || !mark}
                  onClick={() => onLineClick?.(n)}
                  aria-label={mark ? `Findings on line ${n}` : undefined}
                  className={cn(
                    'flex shrink-0 select-none items-center justify-end gap-1.5 pl-2 pr-3 text-right tabular-nums',
                    hit ? 'text-accent-fg' : 'text-fg-3',
                    onLineClick && mark ? 'cursor-pointer hover:text-fg' : 'cursor-default',
                  )}
                  style={{ minWidth: `${gutter + 4}ch` }}
                >
                  <span className="flex w-2 justify-center" aria-hidden>{mark}</span>
                  <span aria-hidden>{n}</span>
                </button>
                <span className="whitespace-pre text-fg-2">
                  {lineTokens
                    ? lineTokens.map((t, j) => <span key={j} className={t.cls || undefined}>{t.text}</span>)
                    : line || ' '}
                  {lineTokens && lineTokens.length === 0 && ' '}
                </span>
              </div>
              {note && <div className="border-l-2 border-accent/40 py-1.5 pl-3 pr-3 font-sans" style={{ marginLeft: `${gutter + 4}ch` }}>{note}</div>}
            </div>
          )
        })}
      </div>
    </div>
  )
}
