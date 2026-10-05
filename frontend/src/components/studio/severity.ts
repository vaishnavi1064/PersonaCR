import type { Severity } from '../../lib/api'
import type { PillTone } from '../ui/StatusPill'

export const SEVERITY_TONE: Record<Severity, PillTone> = {
  critical: 'danger', high: 'danger', medium: 'warning', low: 'neutral',
}

export const SEVERITY_RANK: Record<Severity, number> = { critical: 0, high: 1, medium: 2, low: 3 }

export function severityColor(s: Severity): string {
  return s === 'critical' || s === 'high' ? 'var(--error)' : s === 'medium' ? 'var(--warning)' : 'var(--text-tertiary)'
}
