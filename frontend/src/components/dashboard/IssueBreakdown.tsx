import { motion } from 'framer-motion'

interface BreakdownItem {
  label: string
  pct:   number
  color: string
}

interface Props {
  data: BreakdownItem[]
}

export default function IssueBreakdown({ data }: Props) {
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
        marginBottom: 20,
      }}>
        Issue breakdown
      </p>

      {data.length === 0 ? (
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
            No data yet
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18, flex: 1 }}>
          {data.map((item, i) => (
            <div key={item.label}>
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
                  textTransform: 'capitalize',
                }}>
                  {item.label}
                </span>
                <span style={{
                  fontFamily: 'var(--font-body)',
                  fontSize: 13,
                  fontWeight: 500,
                  color: 'var(--text-primary)',
                }}>
                  {item.pct}%
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
                  animate={{ width: `${item.pct}%` }}
                  transition={{ duration: 0.8, ease: 'easeOut', delay: 0.1 + i * 0.08 }}
                  style={{
                    height: '100%',
                    background: item.color,
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
