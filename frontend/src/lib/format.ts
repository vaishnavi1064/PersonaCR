/** 0.79 → "79%". null → "—". */
export function pct(fraction: number | null | undefined): string {
  return fraction == null || !Number.isFinite(fraction) ? '—' : `${Math.round(fraction * 100)}%`
}

/** 1452 → "1,452". null → "—". */
export function count(n: number | null | undefined): string {
  return n == null || !Number.isFinite(n) ? '—' : n.toLocaleString('en-US')
}

/** Elapsed wall time: "8s", "1m 12s", "1h 3m". */
export function elapsed(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ${s % 60}s`
  return `${Math.floor(m / 60)}h ${m % 60}m`
}

const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })
const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ['year', 31_536_000], ['month', 2_592_000], ['week', 604_800],
  ['day', 86_400], ['hour', 3_600], ['minute', 60],
]

/** ISO timestamp → "3 hours ago" / "yesterday" / "just now". null → null. */
export function relativeTime(iso: string | null | undefined, now = Date.now()): string | null {
  if (!iso) return null
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return null
  const diff = Math.round((t - now) / 1000)
  for (const [unit, secs] of UNITS) {
    if (Math.abs(diff) >= secs) return rtf.format(Math.round(diff / secs), unit)
  }
  return 'just now'
}

/** Absolute timestamp for tooltips. */
export function absoluteTime(iso: string | null | undefined): string | undefined {
  if (!iso) return undefined
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? undefined : d.toLocaleString()
}
