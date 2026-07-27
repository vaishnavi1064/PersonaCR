import { useRef, useState, useEffect } from 'react'
import { motion, useInView, animate } from 'framer-motion'

// ── Types ────────────────────────────────────────────────────────────────────
interface IssueCard {
  type: 'STYLE' | 'DEFECT'
  text: string
}

// ── Data ─────────────────────────────────────────────────────────────────────
const issues: IssueCard[] = [
  { type: 'STYLE',  text: 'Missing docstring. Your fingerprint shows 70% coverage.' },
  { type: 'DEFECT', text: 'No null check on input. TypeError risk.' },
  { type: 'STYLE',  text: 'Naming deviates from your snake_case patterns.' },
]

const pills = [
  { label: 'comp', value: '0.80' },
  { label: 'conc', value: '0.67' },
  { label: 'rel',  value: '0.73' },
]

// ── Score counter ─────────────────────────────────────────────────────────────
function ScoreCounter({ inView }: { inView: boolean }) {
  const [display, setDisplay] = useState(0)
  const hasRun = useRef(false)

  useEffect(() => {
    if (!inView || hasRun.current) return
    hasRun.current = true
    const controls = animate(0, 80, {
      duration: 1.5,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (v) => setDisplay(Math.round(v)),
    })
    return () => controls.stop()
  }, [inView])

  return (
    <span
      style={{
        fontFamily: 'var(--font-display)',
        fontSize: 41,
        lineHeight: 1,
        color: 'var(--success)',
      }}
    >
      {display}
    </span>
  )
}

// ── WindowChrome ──────────────────────────────────────────────────────────────
function WindowChrome() {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '12px 16px',
        borderBottom: '1px solid #1E1E20',
      }}
    >
      {['#FF5F57', '#FFBD2E', '#28C840'].map((color, i) => (
        <div
          key={i}
          style={{ width: 8, height: 8, borderRadius: '50%', background: color }}
        />
      ))}
      <span
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 12,
          color: '#555',
          marginLeft: 8,
        }}
      >
        review output
      </span>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function ProductShowcase() {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: '-80px' })

  return (
    <section
      style={{
        padding: '80px 40px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
      }}
    >
      <div ref={ref} style={{ width: '100%', maxWidth: 560 }}>
        {/* ── Terminal card ──────────────────────────────────────────────── */}
        <div
          style={{
            background: '#0D0D0F',
            border: '1px solid #1E1E20',
            borderRadius: 10,
            overflow: 'hidden',
            fontFamily: 'var(--font-mono)',
            boxShadow: '0 24px 64px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.04)',
          }}
        >
          <WindowChrome />

          <div style={{ padding: '20px 20px 16px' }}>
            {/* Score row */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={inView ? { opacity: 1 } : {}}
              transition={{ duration: 0.4 }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                marginBottom: 20,
                paddingBottom: 16,
                borderBottom: '1px solid #1E1E20',
              }}
            >
              <ScoreCounter inView={inView} />
              <span style={{ fontFamily: 'var(--font-body)', fontSize: 15, color: '#555' }}>
                /100
              </span>
              <span
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11,
                  color: 'var(--success)',
                  background: '#162A20',
                  padding: '2px 8px',
                  borderRadius: 4,
                }}
              >
                passed
              </span>
              <span
                style={{
                  marginLeft: 'auto',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 12,
                  color: '#444',
                }}
              >
                8.5s
              </span>
            </motion.div>

            {/* Issue cards */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14 }}>
              {issues.map((issue, i) => {
                const isStyle = issue.type === 'STYLE'
                return (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -20 }}
                    animate={inView ? { opacity: 1, x: 0 } : {}}
                    transition={{
                      duration: 0.4,
                      ease: [0.22, 1, 0.36, 1],
                      delay: 0.3 + i * 0.2,
                    }}
                    style={{
                      borderLeft: `2px solid ${isStyle ? 'var(--style-accent)' : 'var(--defect-accent)'}`,
                      background: isStyle ? '#1A1710' : '#1A1010',
                      borderRadius: '0 6px 6px 0',
                      padding: '9px 12px',
                      display: 'flex',
                      alignItems: 'baseline',
                      gap: 8,
                    }}
                  >
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: 10,
                        letterSpacing: '0.8px',
                        color: isStyle ? 'var(--style-accent)' : 'var(--defect-accent)',
                        flexShrink: 0,
                        fontWeight: 500,
                      }}
                    >
                      {issue.type}
                    </span>
                    <span
                      style={{
                        fontFamily: 'var(--font-body)',
                        fontSize: 13,
                        color: '#A1A1A0',
                        lineHeight: 1.4,
                      }}
                    >
                      {issue.text}
                    </span>
                  </motion.div>
                )
              })}
            </div>

            {/* Quality pills */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={inView ? { opacity: 1 } : {}}
              transition={{ duration: 0.4, delay: 1.0 }}
              style={{ display: 'flex', gap: 6 }}
            >
              {pills.map((p) => (
                <div
                  key={p.label}
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 10,
                    color: '#666',
                    background: '#1a1a1a',
                    border: '1px solid #2a2a2a',
                    borderRadius: 4,
                    padding: '3px 8px',
                    letterSpacing: '0.3px',
                  }}
                >
                  {p.label}{' '}
                  <span style={{ color: '#888' }}>{p.value}</span>
                </div>
              ))}
            </motion.div>
          </div>
        </div>

        {/* ── Stat labels below terminal ─────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={inView ? { opacity: 1 } : {}}
          transition={{ duration: 0.5, delay: 1.3 }}
          style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            gap: 10,
            marginTop: 18,
            fontFamily: 'var(--font-mono)',
            fontSize: 13,
            color: 'var(--text-tertiary)',
          }}
        >
          <span>8.5s total</span>
          <span style={{ opacity: 0.4 }}>·</span>
          <span>6 agents</span>
          <span style={{ opacity: 0.4 }}>·</span>
          <span>9 papers</span>
        </motion.div>
      </div>
    </section>
  )
}
