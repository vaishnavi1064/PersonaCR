import { languageColor, languageLabel } from '../repos/languages'

/** Stacked bar + legend of functions per language. */
export default function LanguageBar({ distribution }: { distribution: Record<string, number> }) {
  const entries = Object.entries(distribution).filter(([, n]) => n > 0).sort((a, b) => b[1] - a[1])
  const total = entries.reduce((s, [, n]) => s + n, 0)
  if (total === 0) return <p className="text-sm text-fg-3">No language breakdown recorded.</p>
  return (
    <div>
      <div className="flex h-2 overflow-hidden rounded-full bg-raised" role="img" aria-label={entries.map(([l, n]) => `${languageLabel(l)} ${Math.round((n / total) * 100)}%`).join(', ')}>
        {entries.map(([l, n]) => (
          <span key={l} style={{ width: `${(n / total) * 100}%`, background: languageColor(l) }} />
        ))}
      </div>
      <ul className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-fg-2">
        {entries.map(([l, n]) => (
          <li key={l} className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ background: languageColor(l) }} aria-hidden />
            {languageLabel(l)}
            <span className="tabular-nums text-fg-3">{((n / total) * 100).toFixed(1)}% · {n.toLocaleString('en-US')} fn</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
