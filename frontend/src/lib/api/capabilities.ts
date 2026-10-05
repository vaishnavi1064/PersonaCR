// Which backend features exist. UI for a feature that isn't 'available' must
// render <ComingSoon> (or its partial form) — never mock data.
// Flip a flag in the same commit that ships the backend for it.

export type CapabilityLevel = 'available' | 'partial' | 'unavailable'

export interface Capability {
  level: CapabilityLevel
  label: string
  /** What works today / what's missing. */
  detail: string
}

export type CapabilityKey = 'repoSummary' | 'repoChatMemory' | 'findingLines' | 'styleMetrics' | 'analyzeJobs'

export const capabilities: Record<CapabilityKey, Capability> = {
  repoSummary: {
    level: 'unavailable',
    label: 'Repo summary',
    detail: 'A one-line description generated for each imported repo.',
  },
  repoChatMemory: {
    level: 'unavailable',
    label: 'Repo-scoped chat memory',
    detail: 'Answers that remember your past chats about the same repo. Today each question is answered on its own.',
  },
  findingLines: {
    level: 'partial',
    label: 'Line numbers on findings',
    detail: 'Bug findings from static checks carry a line; style findings and some LLM findings do not yet.',
  },
  styleMetrics: {
    level: 'partial',
    label: '"Your repo vs this code" metrics',
    detail: 'Style findings describe the difference in words; exact percentages are not sent yet.',
  },
  analyzeJobs: {
    level: 'unavailable',
    label: 'Background repo analysis',
    detail: 'Analysis runs while you wait; status is not saved if you leave the page.',
  },
}

export function capabilityLevel(key: CapabilityKey): CapabilityLevel {
  return capabilities[key].level
}

export function isAvailable(key: CapabilityKey): boolean {
  return capabilities[key].level === 'available'
}
