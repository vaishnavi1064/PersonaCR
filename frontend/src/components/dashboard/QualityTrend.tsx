import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'

interface TrendPoint {
  date: string
  score: number
}

interface Props {
  data: TrendPoint[]
}

interface TooltipPayload { value: number }

function CustomTooltip({ active, payload, label }: {
  active?: boolean
  payload?: TooltipPayload[]
  label?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '0.5px solid var(--border)',
      borderRadius: 8,
      padding: '8px 12px',
      fontFamily: 'var(--font-body)',
      fontSize: 12,
      color: 'var(--text-primary)',
      boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
    }}>
      <p style={{ color: 'var(--text-tertiary)', marginBottom: 2 }}>{label}</p>
      <p style={{ fontWeight: 500 }}>Score: {payload[0].value}</p>
    </div>
  )
}

function EmptyState() {
  return (
    <div style={{
      height: 220,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
    }}>
      <p style={{
        fontFamily: 'var(--font-body)',
        fontSize: 13,
        color: 'var(--text-tertiary)',
        textAlign: 'center',
        lineHeight: 1.6,
      }}>
        Review code to see your quality trend
      </p>
    </div>
  )
}

export default function QualityTrend({ data }: Props) {
  const accentColor = typeof window !== 'undefined'
    ? getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#8B7CF6'
    : '#8B7CF6'
  const borderColor = typeof window !== 'undefined'
    ? getComputedStyle(document.documentElement).getPropertyValue('--border').trim() || 'rgba(255,255,255,0.08)'
    : 'rgba(255,255,255,0.08)'
  const textTertiary = typeof window !== 'undefined'
    ? getComputedStyle(document.documentElement).getPropertyValue('--text-tertiary').trim() || '#5C5C5B'
    : '#5C5C5B'

  return (
    <div style={{
      border: '0.5px solid var(--border)',
      borderRadius: 12,
      padding: '20px 24px',
      background: 'var(--bg-primary)',
    }}>
      <p style={{
        fontFamily: 'var(--font-body)',
        fontSize: 14,
        fontWeight: 500,
        color: 'var(--text-primary)',
        marginBottom: 20,
      }}>
        Quality trend
      </p>

      {data.length === 0 ? (
        <EmptyState />
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={borderColor} vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: textTertiary, fontFamily: 'var(--font-body)' }}
              axisLine={{ stroke: borderColor }}
              tickLine={false}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fontSize: 11, fill: textTertiary, fontFamily: 'var(--font-body)' }}
              axisLine={{ stroke: borderColor }}
              tickLine={false}
            />
            <ReferenceLine
              y={50}
              stroke={borderColor}
              strokeDasharray="6 4"
              label={{ value: 'threshold', position: 'insideTopRight', fontSize: 9, fill: textTertiary }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Line
              type="monotone"
              dataKey="score"
              stroke={accentColor}
              strokeWidth={2}
              dot={{ r: 4, fill: accentColor, strokeWidth: 0 }}
              activeDot={{ r: 6, fill: accentColor }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
