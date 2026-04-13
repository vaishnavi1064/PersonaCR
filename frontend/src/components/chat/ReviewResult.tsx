import IssueCard from './IssueCard'
import AgentTrace from './AgentTrace'

interface Issue {
  type: string       // 'style' | 'defect' (lowercase from real API)
  category?: string
  severity?: string
  description: string
}

interface QualityScores {
  comprehensiveness?: number
  conciseness?: number
  relevance?: number
}

interface ReviewOutput {
  style_score?: number
  defect_score?: number
  quality_scores?: QualityScores
  quality_gate_passed?: boolean
  pseudo_refs_generated?: number
  confidence?: Record<string, unknown>
}

interface AgentTraceEntry {
  agent_name: string
  input_summary?: string
  output_summary?: string
  decision?: string
  execution_time_ms?: number
  iteration?: number
  summary?: string
  elapsed_ms?: number
}

interface ReviewData {
  overall_score: number
  status: string
  iterations?: number
  issues?: Issue[]
  review_output?: ReviewOutput
  agent_trace?: AgentTraceEntry[]
  latency_ms?: number
}

function scoreColor(score: number) {
  if (score >= 70) return 'var(--success)'
  if (score >= 50) return 'var(--warning)'
  return 'var(--error)'
}

function statusStyle(status: string) {
  const s = (status ?? '').toLowerCase()
  if (s === 'passed')
    return { bg: 'rgba(74,222,128,0.1)', color: 'var(--success)', label: 'passed' }
  if (s === 'low_confidence')
    return { bg: 'rgba(251,191,36,0.1)', color: 'var(--warning)', label: 're-reviewed' }
  if (s === 'quality_gate_failed')
    return { bg: 'rgba(248,113,113,0.1)', color: 'var(--error)', label: 'gate failed' }
  return { bg: 'rgba(251,191,36,0.1)', color: 'var(--warning)', label: s }
}

function fmt(v?: number) {
  return v != null ? v.toFixed(2) : null
}

export default function ReviewResult({ data }: { data: ReviewData }) {
  const { bg, color, label } = statusStyle(data.status ?? 'passed')
  const issues = data.issues ?? []
  const qs = data.review_output?.quality_scores

  const pills = [
    fmt(qs?.comprehensiveness) && { label: `Comp ${fmt(qs?.comprehensiveness)}` },
    fmt(qs?.conciseness)       && { label: `Conc ${fmt(qs?.conciseness)}` },
    fmt(qs?.relevance)         && { label: `Rel  ${fmt(qs?.relevance)}` },
    issues.length > 0          && { label: `${issues.length} issues` },
  ].filter(Boolean) as { label: string }[]

  return (
    <div style={{ marginTop: 8 }}>
      {/* Score row */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        marginBottom: 14,
        paddingBottom: 12,
        borderBottom: '0.5px solid var(--border)',
        flexWrap: 'wrap',
      }}>
        <span style={{
          fontFamily: 'var(--font-display)',
          fontSize: 28,
          color: scoreColor(data.overall_score),
          lineHeight: 1,
        }}>
          {Math.round(data.overall_score)}
        </span>
        <span style={{ fontFamily: 'var(--font-body)', fontSize: 13, color: 'var(--text-secondary)' }}>
          /100
        </span>
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          background: bg,
          color,
          padding: '2px 10px',
          borderRadius: 999,
          letterSpacing: '0.3px',
        }}>
          {label}
        </span>
        {data.iterations != null && data.iterations > 1 && (
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            color: 'var(--text-tertiary)',
            background: 'var(--bg-secondary)',
            padding: '2px 8px',
            borderRadius: 999,
          }}>
            {data.iterations} iterations
          </span>
        )}
        {data.latency_ms != null && (
          <span style={{
            marginLeft: 'auto',
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            color: 'var(--text-tertiary)',
          }}>
            {(data.latency_ms / 1000).toFixed(1)}s
          </span>
        )}
      </div>

      {/* Issues */}
      {issues.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 12 }}>
          {issues.map((issue, i) => (
            <IssueCard key={i} issue={issue} />
          ))}
        </div>
      )}

      {issues.length === 0 && (
        <p style={{
          fontFamily: 'var(--font-body)',
          fontSize: 13,
          color: 'var(--success)',
          marginBottom: 12,
        }}>
          No issues found — code matches your patterns well.
        </p>
      )}

      {/* Quality pills */}
      {pills.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
          {pills.map((p) => (
            <span
              key={p.label}
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 10,
                color: 'var(--text-tertiary)',
                background: 'var(--bg-secondary)',
                border: '0.5px solid var(--border)',
                borderRadius: 999,
                padding: '2px 10px',
              }}
            >
              {p.label}
            </span>
          ))}
        </div>
      )}

      {/* Agent trace */}
      {data.agent_trace && data.agent_trace.length > 0 && (
        <AgentTrace traces={data.agent_trace} />
      )}
    </div>
  )
}
