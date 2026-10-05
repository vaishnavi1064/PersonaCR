import type { RepoStatus } from '../../lib/api'
import StatusPill, { type PillTone } from '../ui/StatusPill'

const META: Record<RepoStatus, { tone: PillTone; label: string }> = {
  ready:     { tone: 'success', label: 'Ready' },
  analyzing: { tone: 'accent',  label: 'Analyzing' },
  added:     { tone: 'neutral', label: 'Added' },
  failed:    { tone: 'danger',  label: 'Failed' },
}

export default function RepoStatusPill({ status }: { status: RepoStatus }) {
  const m = META[status]
  return <StatusPill tone={m.tone} pulse={status === 'analyzing'}>{m.label}</StatusPill>
}
