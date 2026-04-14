const findings = [
  { type: 'STYLE',  text: 'Missing docstring — 70% coverage in your fingerprint' },
  { type: 'DEFECT', text: 'No null check on input — TypeError risk' },
  { type: 'STYLE',  text: 'Naming deviates from your snake_case patterns' },
  { type: 'DEFECT', text: 'Mutable default argument — classic Python footgun' },
  { type: 'STYLE',  text: 'Function too long (60 lines, your avg is 15)' },
  { type: 'DEFECT', text: 'Bare except clause — should specify exception type' },
  { type: 'STYLE',  text: 'Missing return type annotation' },
  { type: 'DEFECT', text: 'No error handling found — add try/except' },
]

// Duplicate for seamless loop
const items = [...findings, ...findings, ...findings]

export default function ScrollingTicker() {
  return (
    <div
      style={{
        width: '100%',
        overflow: 'hidden',
        opacity: 0.5,
        position: 'relative',
        zIndex: 10,
        borderBottom: '0.5px solid var(--border)',
        background: 'var(--bg-primary)',
      }}
    >
      <style>{`
        @keyframes ticker-scroll {
          0%   { transform: translateX(0); }
          100% { transform: translateX(-33.333%); }
        }
      `}</style>
      <div
        style={{
          display: 'flex',
          gap: 8,
          padding: '8px 0',
          width: 'max-content',
          animation: 'ticker-scroll 30s linear infinite',
          willChange: 'transform',
        }}
      >
        {items.map((f, i) => (
          <div
            key={i}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '5px 12px',
              borderLeft: `2px solid ${f.type === 'STYLE' ? 'var(--style-accent)' : 'var(--defect-accent)'}`,
              background: 'var(--bg-secondary)',
              borderRadius: '0 6px 6px 0',
              whiteSpace: 'nowrap',
              flexShrink: 0,
            }}
          >
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 10,
                letterSpacing: '1px',
                color: f.type === 'STYLE' ? 'var(--style-accent)' : 'var(--defect-accent)',
                fontWeight: 500,
              }}
            >
              {f.type}
            </span>
            <span
              style={{
                fontFamily: 'var(--font-body)',
                fontSize: 13,
                color: 'var(--text-secondary)',
              }}
            >
              {f.text}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
