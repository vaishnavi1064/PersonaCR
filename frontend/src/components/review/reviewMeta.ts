import type { Review } from '../../lib/api'
import type { PillTone } from '../ui/StatusPill'

export function scoreColor(score: number | null): string {
  if (score == null) return 'var(--text-tertiary)'
  if (score >= 70) return 'var(--success)'
  if (score >= 50) return 'var(--warning)'
  return 'var(--error)'
}

export function statePill(r: Pick<Review, 'state' | 'backendStatus'>): { tone: PillTone; label: string } {
  if (r.state === 'error') return { tone: 'danger', label: 'Error' }
  if (r.state === 'degraded') return { tone: 'warning', label: 'Degraded' }
  if (r.state === 'low_confidence') return { tone: 'warning', label: 'Low confidence' }
  if (r.backendStatus === 'quality_gate_failed') return { tone: 'warning', label: 'Quality gate failed' }
  return { tone: 'success', label: 'Passed' }
}
