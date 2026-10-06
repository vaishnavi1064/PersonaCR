// Dashboard metrics from saved reviews (domain Reviews, see lib/api/history.ts).
// Scores, trends and quality numbers use scored reviews only — degraded/error
// rows (older ones may exist) are counted separately, never averaged in as 0.
// Nothing here merges fingerprints: style lives per repo, on its own page.
import type { Review } from './api'
import { layoutTimeline } from './timeline'

export interface TrendPoint { id: string | null; createdAt: string; score: number; repoUrl: string }
export interface CategoryCount { category: string; count: number; share: number }
export interface AgentTime { agent: string; avgMs: number; runs: number }
export interface RepoRollup { repoUrl: string; reviews: number; scored: number; avgScore: number | null; lastAt: string | null }

export interface DashboardStats {
  total: number
  scored: number
  /** Reviews with no trustworthy score (degraded/error), excluded from averages. */
  unscored: number
  avgScore: number | null
  trend: TrendPoint[]
  categories: CategoryCount[]
  /** Estimated wall time per review (parallel agents overlap), p50/p95 in ms. */
  reviewTime: { p50: number | null; p95: number | null }
  crScore: { comprehensiveness: number | null; conciseness: number | null; relevance: number | null }
  agentTime: AgentTime[]
  loops: { confidentFirstPass: number | null; qualityGatePassed: number | null; samples: { confidence: number; gate: number } }
  byRepo: RepoRollup[]
}

const isScored = (r: Review) => (r.state === 'ok' || r.state === 'low_confidence') && r.score != null

function mean(xs: number[]): number | null {
  return xs.length ? xs.reduce((s, x) => s + x, 0) / xs.length : null
}

export function percentile(sorted: number[], p: number): number | null {
  if (sorted.length === 0) return null
  const idx = (p / 100) * (sorted.length - 1)
  const lo = Math.floor(idx)
  const hi = Math.ceil(idx)
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo)
}

export function computeDashboard(reviews: Review[]): DashboardStats {
  const scored = reviews.filter(isScored)

  const trend = scored
    .filter((r) => r.createdAt)
    .map((r) => ({ id: r.id, createdAt: r.createdAt!, score: r.score!, repoUrl: r.repoUrl }))
    .sort((a, b) => a.createdAt.localeCompare(b.createdAt))

  const catCount = new Map<string, number>()
  for (const r of scored) for (const f of r.findings) catCount.set(f.category, (catCount.get(f.category) ?? 0) + 1)
  const catTotal = [...catCount.values()].reduce((s, n) => s + n, 0)
  const categories = [...catCount.entries()]
    .map(([category, count]) => ({ category, count, share: catTotal ? count / catTotal : 0 }))
    .sort((a, b) => b.count - a.count)

  const times = scored.map((r) => layoutTimeline(r.trace).total).filter((t) => t > 0).sort((a, b) => a - b)

  const crs = (k: 'comprehensiveness' | 'conciseness' | 'relevance') =>
    mean(scored.map((r) => r.crScore[k]).filter((v): v is number => v != null))

  const agentAcc = new Map<string, { total: number; runs: number }>()
  for (const r of scored) {
    for (const t of r.trace) {
      if (t.durationMs == null) continue
      const a = agentAcc.get(t.agent) ?? { total: 0, runs: 0 }
      a.total += t.durationMs
      a.runs += 1
      agentAcc.set(t.agent, a)
    }
  }
  const agentTime = [...agentAcc.entries()]
    .map(([agent, { total, runs }]) => ({ agent, avgMs: total / runs, runs }))
    .sort((a, b) => b.avgMs - a.avgMs)

  // Loop health, parsed from the agents' own trace summaries
  let confN = 0, confYes = 0, gateN = 0, gateYes = 0
  for (const r of scored) {
    const first = r.trace.find((t) => t.agent === 'confidence_evaluator' && t.iteration === 1)
    const c = first?.outputSummary && /Confident=(True|False)/.exec(first.outputSummary)
    if (c) { confN++; if (c[1] === 'True') confYes++ }
    const gates = r.trace.filter((t) => t.agent === 'quality_gate')
    const g = gates.at(-1)?.outputSummary && /Passed=(True|False)/.exec(gates.at(-1)!.outputSummary!)
    if (g) { gateN++; if (g[1] === 'True') gateYes++ }
  }

  const repos = new Map<string, Review[]>()
  for (const r of reviews) repos.set(r.repoUrl, [...(repos.get(r.repoUrl) ?? []), r])
  const byRepo = [...repos.entries()].map(([repoUrl, rs]) => {
    const s = rs.filter(isScored)
    return {
      repoUrl,
      reviews: rs.length,
      scored: s.length,
      avgScore: mean(s.map((r) => r.score!)),
      lastAt: rs.map((r) => r.createdAt).filter((d): d is string => !!d).sort().at(-1) ?? null,
    }
  }).sort((a, b) => (b.lastAt ?? '').localeCompare(a.lastAt ?? ''))

  return {
    total: reviews.length,
    scored: scored.length,
    unscored: reviews.length - scored.length,
    avgScore: mean(scored.map((r) => r.score!)),
    trend,
    categories,
    reviewTime: { p50: percentile(times, 50), p95: percentile(times, 95) },
    crScore: { comprehensiveness: crs('comprehensiveness'), conciseness: crs('conciseness'), relevance: crs('relevance') },
    agentTime,
    loops: {
      confidentFirstPass: confN ? confYes / confN : null,
      qualityGatePassed: gateN ? gateYes / gateN : null,
      samples: { confidence: confN, gate: gateN },
    },
    byRepo,
  }
}
