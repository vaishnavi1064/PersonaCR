import { useState } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'

export interface HistoryRow {
  date:   string
  repo:   string
  score:  number
  issues: number
  status: string
}

interface Props {
  rows: HistoryRow[]
}

function scoreColor(score: number) {
  if (score >= 70) return 'var(--success)'
  if (score >= 50) return 'var(--warning)'
  return 'var(--error)'
}

function statusBadge(status: string) {
  const s = (status ?? '').toLowerCase()
  if (s === 'passed')
    return { bg: 'color-mix(in srgb, var(--success) 10%, transparent)', color: 'var(--success)', label: 'passed' }
  if (s === 'low_confidence' || s === 're-reviewed')
    return { bg: 'color-mix(in srgb, var(--warning) 10%, transparent)', color: 'var(--warning)', label: 're-reviewed' }
  return { bg: 'color-mix(in srgb, var(--error) 10%, transparent)', color: 'var(--error)', label: s.replace(/_/g, ' ') }
}

const cellStyle: React.CSSProperties = {
  fontFamily: 'var(--font-body)',
  fontSize: 14,
  color: 'var(--text-secondary)',
  padding: '14px 20px',
  borderTop: '0.5px solid var(--border)',
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  maxWidth: 0,
}

function TableRow({ row }: { row: HistoryRow }) {
  const [hovered, setHovered] = useState(false)
  const navigate = useNavigate()
  const badge = statusBadge(row.status)

  return (
    <tr
      onClick={() => navigate('/chat')}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        cursor: 'pointer',
        background: hovered ? 'var(--bg-card-hover)' : 'transparent',
        transition: 'background 0.1s ease',
      }}
    >
      <td style={cellStyle}>{row.date}</td>
      <td style={{ ...cellStyle, color: 'var(--text-primary)' }}>{row.repo}</td>
      <td style={{ ...cellStyle, fontWeight: 500, color: scoreColor(row.score) }}>{Math.round(row.score)}</td>
      <td style={cellStyle}>{row.issues}</td>
      <td style={cellStyle}>
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 12,
          background: badge.bg,
          color: badge.color,
          padding: '3px 10px',
          borderRadius: 999,
          whiteSpace: 'nowrap',
          display: 'inline-block',
        }}>
          {badge.label}
        </span>
      </td>
    </tr>
  )
}

export default function ReviewHistory({ rows }: Props) {
  const navigate = useNavigate()

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1], delay: 0.25 }}
      style={{
        border: '0.5px solid var(--border)',
        borderRadius: 12,
        overflow: 'hidden',
        background: 'var(--bg-primary)',
      }}
    >
      {rows.length === 0 ? (
        <div style={{
          padding: '48px 20px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 16,
        }}>
          <p style={{
            fontFamily: 'var(--font-body)',
            fontSize: 15,
            color: 'var(--text-tertiary)',
          }}>
            No reviews yet.
          </p>
          <button
            onClick={() => navigate('/chat')}
            style={{
              fontFamily: 'var(--font-body)',
              fontSize: 14,
              fontWeight: 500,
              color: 'white',
              background: 'var(--accent)',
              border: 'none',
              borderRadius: 8,
              padding: '8px 20px',
              cursor: 'pointer',
              transition: 'filter 0.15s',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.filter = 'brightness(1.1)')}
            onMouseLeave={(e) => (e.currentTarget.style.filter = 'brightness(1)')}
          >
            Start reviewing
          </button>
        </div>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
          <colgroup>
            <col style={{ width: 90 }} />
            <col style={{ width: 'auto' }} />
            <col style={{ width: 80 }} />
            <col style={{ width: 70 }} />
            <col style={{ width: 130 }} />
          </colgroup>
          <thead>
            <tr style={{ background: 'var(--bg-secondary)' }}>
              {['Date', 'Repository', 'Score', 'Issues', 'Status'].map((h) => (
                <th key={h} style={{
                  fontFamily: 'var(--font-body)',
                  fontSize: 13,
                  fontWeight: 500,
                  color: 'var(--text-secondary)',
                  padding: '12px 20px',
                  textAlign: 'left',
                  borderBottom: '0.5px solid var(--border)',
                }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => <TableRow key={i} row={row} />)}
          </tbody>
        </table>
      )}
    </motion.div>
  )
}
