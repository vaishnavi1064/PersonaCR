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
    level: 'available',
    label: 'Line numbers on findings',
    detail: 'Each finding carries a line checked against the code (exact for static checks, verified by quoting for LLM findings); unverifiable ones say "line n/a".',
  },
  styleMetrics: {
    level: 'available',
    label: '"Your repo vs this code" metrics',
    detail: 'Style findings show the repo’s value next to the same metric measured on the submitted code.',
  },
  analyzeJobs: {
    level: 'available',
    label: 'Background repo analysis',
    detail: 'Analysis runs on the server; its status survives reloads and closed tabs.',
  },
}

export function capabilityLevel(key: CapabilityKey): CapabilityLevel {
  return capabilities[key].level
}

export function isAvailable(key: CapabilityKey): boolean {
  return capabilities[key].level === 'available'
}
