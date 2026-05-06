import { motion } from 'framer-motion'
import type { LoopHealthStats } from '../../lib/db'

interface Props {
  data: LoopHealthStats
}

export default function LoopHealthCard({ data }: Props) {
  const metrics = [
    {
      value: data.confidencePassRate,
      subtitle: 'passed confidence on first try',
    },
    {
      value: data.qualityGatePassRate,
      subtitle: 'passed quality gate',
    },
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1], delay: 0.15 }}
      style={{
        border: '0.5px solid var(--border)',
        borderRadius: 12,
        padding: '20px 24px',
        background: 'var(--bg-primary)',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <p style={{
        fontFamily: 'var(--font-body)',
        fontSize: 15,
        fontWeight: 500,
        color: 'var(--text-primary)',
        marginBottom: 20,
      }}>
        Self-correction
      </p>

      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 20,
        flex: 1,
      }}>
        {metrics.map((m, i) => (
          <motion.div
            key={m.subtitle}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1], delay: 0.2 + i * 0.08 }}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '16px 12px',
              background: 'var(--bg-secondary)',
              borderRadius: 10,
            }}
          >
            <p style={{
              fontFamily: 'var(--font-body)',
              fontSize: 32,
              fontWeight: 500,
              color: m.value != null ? 'var(--accent)' : 'var(--text-tertiary)',
              lineHeight: 1,
              marginBottom: 8,
            }}>
              {m.value != null ? `${m.value}%` : '—'}
            </p>
            <p style={{
              fontFamily: 'var(--font-body)',
              fontSize: 12,
              color: 'var(--text-tertiary)',
              textAlign: 'center',
              lineHeight: 1.4,
            }}>
              {m.subtitle}
            </p>
          </motion.div>
        ))}
      </div>
    </motion.div>
  )
}
