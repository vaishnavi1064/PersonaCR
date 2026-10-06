import type { Fingerprint } from '../../lib/api'
import { languageLabel } from '../repos/languages'
import Card from '../ui/Card'
import LanguageBar from './LanguageBar'
import { ATLAS_GROUPS, ATLAS_SPECIAL_KEYS, PATTERN_LABEL, formatMetric, type MetricDef } from './atlasMetrics'

interface ConventionAtlasProps {
  fingerprint: Fingerprint
  /** Chunks analyzed, including file-level ones (num_functions). */
  chunksAnalyzed: number | null
}

function pythonCounts(fp: Fingerprint): { python: number; total: number; others: string[] } {
  const dist = fp.languageDistribution
  const total = Object.values(dist).reduce((s, n) => s + n, 0)
  return {
    python: dist.python ?? 0,
    total,
    others: Object.keys(dist).filter((l) => l !== 'python' && dist[l] > 0),
  }
}

/** The full fingerprint, grouped by category, with exact values and how each is measured. */
export default function ConventionAtlas({ fingerprint: fp, chunksAnalyzed }: ConventionAtlasProps) {
  const raw = fp.raw
  const py = pythonCounts(fp)
  const measured = fp.totalFunctions ?? chunksAnalyzed
  const known = new Set(ATLAS_GROUPS.flatMap((g) => g.metrics.map((m) => m.key)))
  const otherKeys = Object.keys(raw).filter((k) => !known.has(k) && !ATLAS_SPECIAL_KEYS.has(k)).sort()
  const patterns = Object.entries(fp.patternFrequency).sort((a, b) => b[1] - a[1])

  function note(m: MetricDef): string | null {
    if (m.key === 'type_hint_usage' && fp.typeHintFunctions != null) {
      // Current fingerprints: measured on Python/TypeScript only, null when there are none
      if (fp.typeHintFunctions === 0) return 'Not applicable — this repo has no Python or TypeScript functions.'
      const total = fp.totalFunctions ?? py.total
      return fp.typeHintFunctions < total
        ? `Measured on the ${fp.typeHintFunctions.toLocaleString('en-US')} Python/TypeScript functions (of ${total.toLocaleString('en-US')}).`
        : null
    }
    if (!m.pythonOnly || py.total === 0) return null
    if (m.pythonOnly === 'assumed' && py.others.length > 0) {
      return `Not measured outside Python — this analysis predates the fix and counted the ${py.others.map(languageLabel).join(', ')} functions as typed. Reanalyze to measure it properly.`
    }
    if (m.pythonOnly === 'measured' && py.python < py.total) {
      return py.python === 0 ? 'Python only — this repo has no Python functions.' : `Python functions only (${py.python.toLocaleString('en-US')} of ${py.total.toLocaleString('en-US')}).`
    }
    return null
  }

  return (
    <div className="flex flex-col gap-5">
      <p className="text-sm text-fg-3">
        {measured != null
          ? <>Based on <span className="font-medium text-fg">{measured.toLocaleString('en-US')} functions</span></>
          : 'Function count not recorded'}
        {chunksAnalyzed != null && fp.totalFunctions != null && chunksAnalyzed > fp.totalFunctions && (
          <> (plus {(chunksAnalyzed - fp.totalFunctions).toLocaleString('en-US')} file-level chunks used for imports)</>
        )}
        . Values are exact as stored; percentages are shares of functions unless noted.
      </p>

      <div className="grid gap-4 lg:grid-cols-2">
        {ATLAS_GROUPS.map((g) => (
          <Card key={g.id} className="p-0">
            <h3 className="border-b border-line px-4 py-3 text-sm font-semibold text-fg">{g.title}</h3>
            <dl className="divide-y divide-line">
              {g.metrics.map((m) => {
                const caveat = note(m)
                const unmeasured = (caveat?.startsWith('Not measured') || caveat?.startsWith('Not applicable')) ?? false
                const { value, exact } = formatMetric(m.kind, raw[m.key])
                return (
                  <div key={m.key} className="flex items-start justify-between gap-4 px-4 py-3">
                    <div className="min-w-0">
                      <dt className="text-sm text-fg">{m.label}</dt>
                      <dd className="mt-0.5 text-xs leading-5 text-fg-3">{m.description}</dd>
                      {caveat && <dd className="mt-1 text-xs leading-5 text-warning">{caveat}</dd>}
                    </div>
                    <dd className="shrink-0 text-right">
                      <span className={unmeasured ? 'text-sm text-fg-3 line-through decoration-fg-3/60' : 'text-sm font-semibold tabular-nums text-fg'}>{value}</span>
                      {exact && <span className="block font-mono text-[11px] text-fg-3">{exact}</span>}
                    </dd>
                  </div>
                )
              })}
            </dl>
          </Card>
        ))}

        <Card className="p-0">
          <h3 className="border-b border-line px-4 py-3 text-sm font-semibold text-fg">Languages</h3>
          <div className="px-4 py-4"><LanguageBar distribution={fp.languageDistribution} /></div>
        </Card>

        <Card className="p-0">
          <h3 className="border-b border-line px-4 py-3 text-sm font-semibold text-fg">Recurring patterns</h3>
          {patterns.length === 0 ? (
            <p className="px-4 py-4 text-sm text-fg-3">None of the patterns PersonaCR looks for (early return, builder, singleton, named exceptions, decorators) were detected.</p>
          ) : (
            <dl className="divide-y divide-line">
              {patterns.map(([p, n]) => (
                <div key={p} className="flex items-center justify-between gap-4 px-4 py-2.5">
                  <dt className="text-sm text-fg">{PATTERN_LABEL[p] ?? p.replace(/_/g, ' ')}</dt>
                  <dd className="text-sm tabular-nums text-fg-2">
                    {n.toLocaleString('en-US')} function{n === 1 ? '' : 's'}
                    {measured ? <span className="text-fg-3"> · {((n / measured) * 100).toFixed(1)}%</span> : null}
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </Card>

        {otherKeys.length > 0 && (
          <Card className="p-0 lg:col-span-2">
            <h3 className="border-b border-line px-4 py-3 text-sm font-semibold text-fg">Other measurements</h3>
            <dl className="grid divide-y divide-line sm:grid-cols-2 sm:divide-y-0">
              {otherKeys.map((k) => (
                <div key={k} className="flex items-center justify-between gap-4 px-4 py-2.5">
                  <dt className="font-mono text-xs text-fg-2">{k}</dt>
                  <dd className="font-mono text-xs text-fg">{typeof raw[k] === 'object' ? JSON.stringify(raw[k]) : String(raw[k])}</dd>
                </div>
              ))}
            </dl>
          </Card>
        )}
      </div>
    </div>
  )
}
