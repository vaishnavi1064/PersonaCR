const AGENT_COLORS: Record<string, string> = {
  planner:               '#8B7CF6',
  style_analyst:         '#D85A30',
  defect_hunter:         '#D85A30',
  qa_checker:            '#D4537E',
  confidence_evaluator:  '#1D9E75',
  pseudo_ref_generator:  '#BA7517',
  sts_scorer:            '#BA7517',
  quality_gate:          '#639922',
  quality_gate_reloop:   '#639922',
}

function agentColor(name: string) {
  const key = name.toLowerCase().replace(/[\s-]+/g, '_')
  return AGENT_COLORS[key] ?? '#888'
}

interface TraceEntry {
  agent_name: string
  // real API fields
  input_summary?: string
  output_summary?: string
  decision?: string
  execution_time_ms?: number
  iteration?: number
  // legacy/sample fields
  summary?: string
  elapsed_ms?: number
}

export default function AgentTrace({ traces }: { traces: TraceEntry[] }) {
  if (!traces || traces.length === 0) return null

  return (
    <details style={{ marginTop: 10 }}>
      <summary style={{
        fontFamily: 'var(--font-body)',
        fontSize: 12,
        color: 'var(--text-tertiary)',
        cursor: 'pointer',
        userSelect: 'none',
        listStyle: 'none',
        display: 'flex',
        alignItems: 'center',
        gap: 4,
      }}>
        <span>▸</span> Agent trace ({traces.length} steps)
      </summary>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 3, marginTop: 8 }}>
        {traces.map((t, i) => {
          // Prefer real API fields, fall back to sample fields
          const summaryText = t.output_summary || t.summary || t.decision || '—'
          const ms = t.execution_time_ms ?? t.elapsed_ms

          return (
            <div
              key={i}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                background: 'var(--bg-secondary)',
                borderRadius: 6,
                padding: '5px 8px',
              }}
            >
              <div style={{
                width: 6, height: 6,
                borderRadius: '50%',
                background: agentColor(t.agent_name),
                flexShrink: 0,
              }} />
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
                color: 'var(--text-primary)',
                width: 160,
                flexShrink: 0,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}>
                {t.agent_name}
              </span>
              <span style={{
                fontFamily: 'var(--font-body)',
                fontSize: 11,
                color: 'var(--text-tertiary)',
                flex: 1,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}>
                {summaryText}
              </span>
              {ms != null && (
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11,
                  color: 'var(--text-tertiary)',
                  flexShrink: 0,
                  marginLeft: 4,
                }}>
                  {ms}ms
                </span>
              )}
              {t.iteration != null && t.iteration > 1 && (
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 10,
                  color: 'var(--warning)',
                  flexShrink: 0,
                  marginLeft: 2,
                }}>
                  iter{t.iteration}
                </span>
              )}
            </div>
          )
        })}
      </div>
    </details>
  )
}
