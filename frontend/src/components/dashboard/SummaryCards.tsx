import { motion } from 'framer-motion'

interface Props {
  avgScore:     number | null
  totalReviews: number
  topIssue:     string | null
  latencyP50?:  number | null  // milliseconds
  latencyP95?:  number | null  // milliseconds
}

function fmt(label: string) {
  return label.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function formatMs(ms: number): string {
  return (ms / 1000).toFixed(1) + 's'
}

export default function SummaryCards({ avgScore, totalReviews, topIssue, latencyP50, latencyP95 }: Props) {
  const hasLatency = latencyP50 != null && latencyP95 != null

  const cards = [
    {
      label: 'Avg score',
      value: avgScore != null ? avgScore.toFixed(1) : '—',
      accent: avgScore != null,
      small: false,
    },
    {
      label: 'Total reviews',
      value: String(totalReviews),
      accent: false,
      small: false,
    },
    {
      label: 'Top issue',
      value: topIssue ? fmt(topIssue) : '—',
      accent: false,
      small: !!topIssue,
    },
    {
      label: 'Pipeline latency',
      value: hasLatency
        ? `p50: ${formatMs(latencyP50)} · p95: ${formatMs(latencyP95)}`
        : '—',
      accent: false,
      small: hasLatency,
    },
  ]

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
      {cards.map((card, i) => (
        <motion.div
          key={card.label}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1], delay: i * 0.06 }}
          style={{
            background: 'var(--bg-secondary)',
            border: '0.5px solid var(--border)',
            borderRadius: 10,
            padding: '16px 20px',
          }}
        >
          <p style={{
            fontFamily: 'var(--font-body)',
            fontSize: 13,
            color: 'var(--text-tertiary)',
            marginBottom: 6,
          }}>
            {card.label}
          </p>
          <p style={{
            fontFamily: 'var(--font-body)',
            fontSize: card.small ? 16 : 24,
            fontWeight: 500,
            color: card.accent ? 'var(--accent)' : 'var(--text-primary)',
            lineHeight: 1.15,
          }}>
            {card.value}
          </p>
        </motion.div>
      ))}
    </div>
  )
}
