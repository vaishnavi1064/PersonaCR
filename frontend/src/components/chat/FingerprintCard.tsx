interface FingerprintData {
  functions_analyzed?: number
  files_analyzed?: number
  avg_function_length?: number
  error_handling_rate?: number
  docstring_coverage?: number
  naming_convention?: string
  type_hint_usage?: number
  avg_complexity?: number
  cache_status?: string
  repo_name?: string
}

function pct(v?: number) {
  if (v == null) return '—'
  return `${Math.round(v * 100)}%`
}

function round1(v?: number) {
  if (v == null) return '—'
  return v.toFixed(1)
}

export default function FingerprintCard({ data }: { data: FingerprintData }) {
  const funcs = data.functions_analyzed ?? 0

  const stats = [
    { label: 'Avg length',     value: `${round1(data.avg_function_length)} lines` },
    { label: 'Error handling', value: pct(data.error_handling_rate) },
    { label: 'Docstrings',     value: pct(data.docstring_coverage) },
    { label: 'Naming',         value: data.naming_convention ?? '—' },
    ...(data.type_hint_usage != null
      ? [{ label: 'Type hints', value: pct(data.type_hint_usage) }]
      : []),
    ...(data.avg_complexity != null
      ? [{ label: 'Avg complexity', value: round1(data.avg_complexity) }]
      : []),
  ]

  const cacheLabel = data.cache_status === 'fresh' ? 'Loaded from cache.' : 'Fingerprint cached.'

  return (
    <div style={{ marginTop: 8 }}>
      <p style={{
        fontFamily: 'var(--font-body)',
        fontSize: 15,
        color: 'var(--text-primary)',
        marginBottom: 12,
        lineHeight: 1.5,
      }}>
        Analyzed <strong>{funcs}</strong> functions
        {data.repo_name ? <> from <strong>{data.repo_name}</strong></> : ''}.
        {' '}<span style={{ color: 'var(--success)' }}>{cacheLabel}</span>
      </p>

      <div style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${Math.min(stats.length, 4)}, 1fr)`,
        gap: 6,
      }}>
        {stats.slice(0, 4).map((s) => (
          <div
            key={s.label}
            style={{
              background: 'var(--bg-secondary)',
              borderRadius: 8,
              padding: '10px 12px',
              border: '0.5px solid var(--border)',
            }}
          >
            <p style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              color: 'var(--text-tertiary)',
              marginBottom: 4,
              letterSpacing: '0.3px',
            }}>
              {s.label}
            </p>
            <p style={{
              fontFamily: 'var(--font-body)',
              fontSize: 16,
              fontWeight: 500,
              color: 'var(--text-primary)',
              lineHeight: 1,
            }}>
              {s.value}
            </p>
          </div>
        ))}
      </div>

      {/* Extra stats if available */}
      {stats.length > 4 && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${stats.length - 4}, 1fr)`,
          gap: 6,
          marginTop: 6,
        }}>
          {stats.slice(4).map((s) => (
            <div
              key={s.label}
              style={{
                background: 'var(--bg-secondary)',
                borderRadius: 8,
                padding: '10px 12px',
                border: '0.5px solid var(--border)',
              }}
            >
              <p style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
                color: 'var(--text-tertiary)',
                marginBottom: 4,
                letterSpacing: '0.3px',
              }}>
                {s.label}
              </p>
              <p style={{
                fontFamily: 'var(--font-body)',
                fontSize: 16,
                fontWeight: 500,
                color: 'var(--text-primary)',
                lineHeight: 1,
              }}>
                {s.value}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
