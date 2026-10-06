import { useEffect, useRef, useState, type MouseEvent } from 'react'
import { repoShortName } from '../../lib/api'
import type { TrendPoint } from '../../lib/dashboardStats'

interface TrendChartProps {
  points: TrendPoint[]
  onSelect?: (id: string) => void
  showRepo?: boolean
  height?: number
}

const M = { top: 12, right: 40, bottom: 26, left: 34 }
const TICKS = [0, 25, 50, 75, 100]

function useWidth<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T>(null)
  const [w, setW] = useState(0)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setW(e.contentRect.width))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, w]
}

const fmtDate = (iso: string) => new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })

/**
 * Score per review, in review order (one series: the title names it, no legend).
 * Solid hairline grid, 2px line, surface-ringed dots; hover = crosshair + tooltip.
 */
export default function TrendChart({ points, onSelect, showRepo, height = 220 }: TrendChartProps) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [hover, setHover] = useState<number | null>(null)

  const innerW = Math.max(0, width - M.left - M.right)
  const innerH = height - M.top - M.bottom
  const n = points.length
  const x = (i: number) => M.left + (n <= 1 ? innerW / 2 : (i / (n - 1)) * innerW)
  const y = (v: number) => M.top + innerH - (v / 100) * innerH

  const line = points.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.score).toFixed(1)}`).join('')
  const area = n > 1 ? `${line}L${x(n - 1).toFixed(1)},${y(0)}L${x(0).toFixed(1)},${y(0)}Z` : ''

  // A few x labels: first, last, and evenly spaced in between
  const labelIdx = n <= 1 ? [0] : [...new Set([0, Math.round((n - 1) / 3), Math.round((2 * (n - 1)) / 3), n - 1])]

  function nearest(e: MouseEvent<SVGRectElement>): number {
    const rect = e.currentTarget.getBoundingClientRect()
    const px = e.clientX - rect.left - 8 // overlay starts 8px left of the plot
    const i = n <= 1 ? 0 : Math.round((px / innerW) * (n - 1))
    return Math.max(0, Math.min(n - 1, i))
  }

  function onMove(e: MouseEvent<SVGRectElement>) {
    if (n > 0) setHover(nearest(e))
  }

  // Resolve the point from the click itself — taps and clicks without a prior hover still work
  function onClick(e: MouseEvent<SVGRectElement>) {
    if (n === 0 || !onSelect) return
    const id = points[nearest(e)].id
    if (id) onSelect(id)
  }

  const h = hover != null ? points[hover] : null
  const last = points[n - 1]

  return (
    <div ref={ref} className="relative" style={{ height }}>
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label={`Score per review, ${n} reviews, latest ${last ? Math.round(last.score) : '—'}`}>
          {TICKS.map((t) => (
            <g key={t}>
              <line x1={M.left} x2={width - M.right} y1={y(t)} y2={y(t)} style={{ stroke: 'var(--border)' }} strokeWidth={1} />
              <text x={M.left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="fill-fg-3 text-[11px] tabular-nums">{t}</text>
            </g>
          ))}
          {labelIdx.map((i) => points[i] && (
            <text key={i} x={x(i)} y={height - 6} textAnchor={n > 1 && i === 0 ? 'start' : n > 1 && i === n - 1 ? 'end' : 'middle'} className="fill-fg-3 text-[11px]">
              {fmtDate(points[i].createdAt)}
            </text>
          ))}

          {area && <path d={area} style={{ fill: 'var(--chart-series)', fillOpacity: 0.1 }} />}
          {n > 1 && <path d={line} fill="none" style={{ stroke: 'var(--chart-series)' }} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />}

          {h && hover != null && (
            <line x1={x(hover)} x2={x(hover)} y1={M.top} y2={M.top + innerH} style={{ stroke: 'var(--border-hover)' }} strokeWidth={1} />
          )}
          {points.map((p, i) => (
            <circle
              key={i}
              cx={x(i)}
              cy={y(p.score)}
              r={i === hover ? 6 : 4}
              style={{ fill: 'var(--chart-series)', stroke: 'var(--bg-card)' }}
              strokeWidth={2}
            />
          ))}
          {/* Direct label on the latest point only */}
          {last && (
            <text x={x(n - 1) + 8} y={y(last.score)} dy="0.32em" className="fill-fg-2 text-[11px] font-medium tabular-nums">
              {Math.round(last.score)}
            </text>
          )}

          <rect
            x={M.left - 8}
            y={M.top}
            width={innerW + 16}
            height={innerH}
            fill="transparent"
            onMouseMove={onMove}
            onMouseLeave={() => setHover(null)}
            onClick={onClick}
            style={{ cursor: onSelect ? 'pointer' : 'default' }}
          />
        </svg>
      )}

      {h && hover != null && (
        <div
          className="pointer-events-none absolute z-10 rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-pop"
          style={{
            // Beside the point, never on it: left of it in the right half, right of it otherwise
            left: x(hover) > width / 2 ? Math.max(0, x(hover) - 150 - 14) : Math.min(x(hover) + 14, Math.max(0, width - 150)),
            top: Math.min(Math.max(0, y(h.score) - 40), height - 90),
            width: 150,
          }}
        >
          <p className="text-fg-3">{new Date(h.createdAt).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</p>
          <p className="mt-0.5 font-medium text-fg">Score {Math.round(h.score)}</p>
          {showRepo && <p className="truncate text-fg-3">{repoShortName(h.repoUrl)}</p>}
          {h.id && onSelect && <p className="mt-0.5 text-fg-3">Click to open</p>}
        </div>
      )}
    </div>
  )
}
