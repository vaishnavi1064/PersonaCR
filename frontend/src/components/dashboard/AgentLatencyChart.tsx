import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts'
import type { AgentLatencyEntry } from '../../lib/db'

interface Props {
  data: AgentLatencyEntry[]
}

function toTitleCase(snake: string): string {
  return snake.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

interface TooltipPayloadItem {
  payload: { agent: string; avgMs: number; count: number }
}

function CustomTooltip({ active, payload }: {
  active?: boolean
  payload?: TooltipPayloadItem[]
}) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '0.5px solid var(--border)',
      borderRadius: 8,
      padding: '8px 12px',
      fontFamily: 'var(--font-body)',
      fontSize: 13,
      color: 'var(--text-primary)',
      boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
    }}>
      <p style={{ fontWeight: 500, marginBottom: 2 }}>{toTitleCase(d.agent)}</p>
      <p style={{ color: 'var(--text-secondary)' }}>Avg: {d.avgMs} ms</p>
      <p style={{ color: 'var(--text-tertiary)' }}>Executions: {d.count}</p>
    </div>
  )
}

export default function AgentLatencyChart({ data }: Props) {
  const accentColor = typeof window !== 'undefined'
    ? getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#8B7CF6'
    : '#8B7CF6'
  const borderColor = typeof window !== 'undefined'
    ? getComputedStyle(document.documentElement).getPropertyValue('--border').trim() || 'rgba(255,255,255,0.08)'
    : 'rgba(255,255,255,0.08)'
  const textTertiary = typeof window !== 'undefined'
    ? getComputedStyle(document.documentElement).getPropertyValue('--text-tertiary').trim() || '#5C5C5B'
    : '#5C5C5B'

  const chartData = data.map((d) => ({
    ...d,
    name: toTitleCase(d.agent),
  }))

  return (
    <div style={{
      border: '0.5px solid var(--border)',
      borderRadius: 12,
      padding: '20px 24px',
      background: 'var(--bg-primary)',
    }}>
      <p style={{
        fontFamily: 'var(--font-body)',
        fontSize: 15,
        fontWeight: 500,
        color: 'var(--text-primary)',
        marginBottom: 20,
      }}>
        Per-agent latency
      </p>

      {data.length === 0 ? (
        <div style={{
          height: 220,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          <p style={{
            fontFamily: 'var(--font-body)',
            fontSize: 14,
            color: 'var(--text-tertiary)',
            textAlign: 'center',
            lineHeight: 1.6,
          }}>
            No reviews yet to measure
          </p>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={Math.max(220, chartData.length * 36)}>
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 4, right: 40, left: 0, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke={borderColor} horizontal={false} />
            <XAxis
              type="number"
              tick={{ fontSize: 12, fill: textTertiary, fontFamily: 'var(--font-body)' }}
              axisLine={{ stroke: borderColor }}
              tickLine={false}
              unit=" ms"
            />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fontSize: 12, fill: textTertiary, fontFamily: 'var(--font-body)' }}
              axisLine={{ stroke: borderColor }}
              tickLine={false}
              width={130}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: 'var(--accent-surface)' }} />
            <Bar
              dataKey="avgMs"
              fill={accentColor}
              radius={[0, 4, 4, 0]}
              barSize={18}
            />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
