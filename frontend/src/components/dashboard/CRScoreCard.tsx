import { motion } from 'framer-motion'
import type { CRScoreStats } from '../../lib/db'

interface Props {
  data: CRScoreStats
}

interface BarDef {
  label: string
  value: number | null
  color: string
  tooltip: string
}

export default function CRScoreCard({ data }: Props) {
  const bars: BarDef[] = [
    {
      label: 'Comprehensiveness',
      value: data.comprehensiveness,
      color: 'var(--success)',
      tooltip: 'Comprehensiveness: does the review cover everything important?',
    },
    {
      label: 'Conciseness',
      value: data.conciseness,
      color: 'var(--accent)',
      tooltip: 'Conciseness: is the review free of irrelevant content?',
    },
    {
      label: 'Relevance',
      value: data.relevance,
      color: 'var(--warning)',
      tooltip: 'Relevance: are findings on-topic?',
    },
  ]

  const hasData = bars.some((b) => b.value != null)

  return (
    <div style={{
      border: '0.5px solid var(--border)',
      borderRadius: 12,
      padding: '20px 24px',
      background: 'var(--bg-primary)',
      display: 'flex',
      flexDirection: 'column',
    }}>
      <p style={{
        fontFamily: 'var(--font-body)',
        fontSize: 15,
        fontWeight: 500,
        color: 'var(--text-primary)',
        marginBottom: 4,
      }}>
        Review quality (CRScore)
      </p>
      <p style={{
        fontFamily: 'var(--font-body)',
        fontSize: 11,
        color: 'var(--text-tertiary)',
        marginBottom: 20,
      }}>
        Reference-free code review evaluation, NAACL 2025
      </p>

      {!hasData ? (
        <div style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: 120,
        }}>
          <p style={{
            fontFamily: 'var(--font-body)',
            fontSize: 14,
            color: 'var(--text-tertiary)',
          }}>
            No reviews yet
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18, flex: 1 }}>
          {bars.map((bar, i) => (
            <div key={bar.label} title={bar.tooltip}>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 6,
              }}>
                <span style={{
                  fontFamily: 'var(--font-body)',
                  fontSize: 13,
                  color: 'var(--text-secondary)',
                }}>
                  {bar.label}
                </span>
                <span style={{
                  fontFamily: 'var(--font-body)',
                  fontSize: 13,
                  fontWeight: 500,
                  color: 'var(--text-primary)',
                }}>
                  {bar.value != null ? `${Math.round(bar.value)}%` : '—'}
                </span>
              </div>
              <div style={{
                height: 6,
                background: 'var(--bg-tertiary)',
                borderRadius: 999,
                overflow: 'hidden',
              }}>
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: bar.value != null ? `${Math.min(bar.value, 100)}%` : '0%' }}
                  transition={{ duration: 0.8, ease: 'easeOut', delay: 0.1 + i * 0.08 }}
                  style={{
                    height: '100%',
                    background: bar.color,
                    borderRadius: 999,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
