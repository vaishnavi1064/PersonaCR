import { useRef, useState } from 'react'
import { motion, useInView } from 'framer-motion'

// ── Decorative mini fingerprint lines for Card 1 ──────────────────────────────
function MiniFingerprint() {
  return (
    <svg
      aria-hidden
      width="80"
      height="80"
      viewBox="0 0 80 80"
      style={{
        position: 'absolute',
        bottom: 16,
        right: 16,
        pointerEvents: 'none',
        opacity: 0.07,
      }}
    >
      {[
        'M 10 70 Q 40 -10 70 70',
        'M 16 72 Q 40 0 64 72',
        'M 22 74 Q 40 10 58 74',
        'M 28 75 Q 40 18 52 75',
      ].map((d, i) => (
        <path
          key={i}
          d={d}
          fill="none"
          stroke="var(--accent)"
          strokeWidth="1"
        />
      ))}
    </svg>
  )
}

// ── Agent dots for Card 3 ─────────────────────────────────────────────────────
const agentDots = [
  { color: '#8B7CF6', label: 'Planner' },
  { color: '#D85A30', label: 'Style Analyst' },
  { color: '#D85A30', label: 'Defect Hunter' },
  { color: '#D4537E', label: 'QA Checker' },
  { color: '#1D9E75', label: 'Confidence' },
  { color: '#639922', label: 'Quality Gate' },
]

// ── Venue badges for Card 2 ───────────────────────────────────────────────────
const venues = ['EMNLP', 'NAACL', 'ACL', 'MSR']

// ── BentoCard wrapper ─────────────────────────────────────────────────────────
function BentoCard({
  children,
  style: extraStyle,
}: {
  children: React.ReactNode
  style?: React.CSSProperties
}) {
  const [hovered, setHovered] = useState(false)

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: hovered ? 'var(--bg-card-hover)' : 'var(--bg-card)',
        padding: 32,
        position: 'relative',
        overflow: 'hidden',
        transform: hovered ? 'translateY(-1px)' : 'translateY(0)',
        transition: 'background 0.15s ease, transform 0.15s ease',
        cursor: 'default',
        ...extraStyle,
      }}
    >
      {children}
    </div>
  )
}

function CardHeading({ children }: { children: React.ReactNode }) {
  return (
    <h3
      style={{
        fontFamily: 'var(--font-display)',
        fontSize: 18,
        color: 'var(--text-primary)',
        letterSpacing: '-0.2px',
        lineHeight: 1.2,
        marginBottom: 10,
      }}
    >
      {children}
    </h3>
  )
}

function CardBody({ children }: { children: React.ReactNode }) {
  return (
    <p
      style={{
        fontFamily: 'var(--font-body)',
        fontSize: 13,
        color: 'var(--text-secondary)',
        lineHeight: 1.6,
      }}
    >
      {children}
    </p>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function BentoFeatures() {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: '-60px' })

  return (
    <section
      style={{
        padding: '100px 40px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        borderTop: '0.5px solid var(--border)',
      }}
    >
      {/* Section label */}
      <motion.p
        initial={{ opacity: 0 }}
        animate={inView ? { opacity: 1 } : {}}
        transition={{ duration: 0.5 }}
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 11,
          letterSpacing: '2px',
          textTransform: 'uppercase',
          color: 'var(--text-tertiary)',
          marginBottom: 60,
          textAlign: 'center',
        }}
      >
        What makes this different
      </motion.p>

      {/* Bento grid — outer container bg = --border, gap = 1px creates divider lines */}
      <motion.div
        ref={ref}
        initial={{ opacity: 0, y: 20 }}
        animate={inView ? { opacity: 1, y: 0 } : {}}
        transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1], delay: 0.1 }}
        style={{
          width: '100%',
          maxWidth: 720,
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gridTemplateRows: 'auto auto',
          gap: 1,
          background: 'var(--border)',
          borderRadius: 12,
          overflow: 'hidden',
        }}
      >
        {/* Card 1 — Personal */}
        <BentoCard>
          <CardHeading>Personal, not universal</CardHeading>
          <CardBody>
            Reviews compare against your coding fingerprint. Every developer gets
            feedback shaped by their own history.
          </CardBody>
          <MiniFingerprint />
        </BentoCard>

        {/* Card 2 — Research-grounded */}
        <BentoCard>
          <CardHeading>Research-grounded</CardHeading>
          <CardBody>Built on 9 papers from top venues.</CardBody>
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 6,
              marginTop: 14,
            }}
          >
            {venues.map((v) => (
              <span
                key={v}
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 9,
                  background: 'var(--accent-surface)',
                  color: 'var(--accent-text)',
                  borderRadius: 999,
                  padding: '3px 8px',
                  letterSpacing: '0.5px',
                  display: 'inline-flex',
                  alignItems: 'center',
                }}
              >
                {v}
              </span>
            ))}
          </div>
        </BentoCard>

        {/* Card 3 — Parallel agents */}
        <BentoCard>
          <CardHeading>Parallel agents</CardHeading>
          <CardBody>
            Style Analyst and Defect Hunter run simultaneously. Two agentic loops
            self-correct before results.
          </CardBody>
          <div
            style={{
              display: 'flex',
              gap: 6,
              alignItems: 'center',
              marginTop: 14,
            }}
          >
            {agentDots.map((dot, i) => (
              <div
                key={i}
                title={dot.label}
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: dot.color,
                  flexShrink: 0,
                }}
              />
            ))}
          </div>
        </BentoCard>

        {/* Card 4 — Editor-native */}
        <BentoCard>
          <CardHeading>Editor-native</CardHeading>
          <CardBody>MCP server connects to your coding tools.</CardBody>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              marginTop: 14,
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              color: 'var(--text-tertiary)',
            }}
          >
            <span>Claude Code</span>
            <span style={{ opacity: 0.4 }}>·</span>
            <span>Cursor</span>
            <span style={{ opacity: 0.4 }}>·</span>
            <span>VS Code</span>
          </div>
        </BentoCard>
      </motion.div>
    </section>
  )
}
