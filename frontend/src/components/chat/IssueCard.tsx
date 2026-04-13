interface Issue {
  type: string   // 'style' | 'defect' (real API sends lowercase)
  category?: string
  severity?: string
  description: string
}

export default function IssueCard({ issue }: { issue: Issue }) {
  const isStyle = (issue.type ?? '').toLowerCase() === 'style'

  return (
    <div style={{
      borderLeft: `3px solid ${isStyle ? 'var(--style-accent)' : 'var(--defect-accent)'}`,
      background: 'var(--bg-secondary)',
      borderRadius: '0 8px 8px 0',
      padding: '10px 14px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 5 }}>
        {/* Category badge */}
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 9,
          letterSpacing: '0.5px',
          padding: '1px 6px',
          borderRadius: 999,
          background: isStyle ? 'var(--accent-surface)' : 'rgba(248,113,113,0.1)',
          color: isStyle ? 'var(--style-accent)' : 'var(--defect-accent)',
          fontWeight: 500,
        }}>
          {(issue.category ?? issue.type).toUpperCase()}
        </span>

        {/* Severity */}
        {issue.severity && (
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 9,
            color: 'var(--text-tertiary)',
            letterSpacing: '0.3px',
          }}>
            {issue.severity}
          </span>
        )}
      </div>

      <p style={{
        fontFamily: 'var(--font-body)',
        fontSize: 13,
        color: 'var(--text-secondary)',
        lineHeight: 1.5,
        margin: 0,
      }}>
        {issue.description}
      </p>
    </div>
  )
}
