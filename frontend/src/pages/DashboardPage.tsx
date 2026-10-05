import { useEffect, useState, useMemo } from 'react'
import PageHeader from '../components/ui/PageHeader'
import SummaryCards from '../components/dashboard/SummaryCards'
import QualityTrend from '../components/dashboard/QualityTrend'
import IssueBreakdown from '../components/dashboard/IssueBreakdown'
import ReviewHistory from '../components/dashboard/ReviewHistory'
import CRScoreCard from '../components/dashboard/CRScoreCard'
import AgentLatencyChart from '../components/dashboard/AgentLatencyChart'
import LoopHealthCard from '../components/dashboard/LoopHealthCard'
import type { HistoryRow } from '../components/dashboard/ReviewHistory'
import { fetchReviews, computeDashboardStats, computeAdvancedStats } from '../lib/db'
import type { ReviewRow, AdvancedStats } from '../lib/db'
import { supabase } from '../lib/supabase'

export default function DashboardPage() {
  const [loading, setLoading] = useState(true)
  const [reviews, setReviews] = useState<ReviewRow[]>([])
  const [historyRows, setHistoryRows] = useState<HistoryRow[]>([])

  const stats = useMemo(() => computeDashboardStats(reviews), [reviews])
  const advanced = useMemo<AdvancedStats>(() => computeAdvancedStats(reviews), [reviews])

  useEffect(() => {
    let cancelled = false

    async function load() {
      // Get current user — works with real auth or dev bypass
      const { data: { session } } = await supabase.auth.getSession()
      const userId = session?.user?.id

      // In dev mode with no real session, show empty states
      if (!userId) {
        setLoading(false)
        return
      }

      const fetched = await fetchReviews(userId)
      if (cancelled) return

      setReviews(fetched)

      const rows: HistoryRow[] = fetched.map((r) => ({
        date:   new Date(r.created_at).toLocaleDateString('en-US', {
          month: 'short', day: 'numeric',
        }),
        repo:   r.repo_name ?? r.repo_url ?? '—',
        score:  r.overall_score,
        issues: r.issues_count ?? r.issues?.length ?? 0,
        status: r.status,
      }))

      setHistoryRows(rows)
      setLoading(false)
    }

    load()
    return () => { cancelled = true }
  }, [])

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-8 sm:px-6 lg:py-10">
      <PageHeader
        title="Dashboard"
        description={loading
          ? 'Loading your data…'
          : stats.totalReviews === 0
            ? 'No reviews yet — go to Chats to get started.'
            : `${stats.totalReviews} review${stats.totalReviews === 1 ? '' : 's'} across your repos.`}
      />

      <SummaryCards
        avgScore={stats.avgScore}
        totalReviews={stats.totalReviews}
        topIssue={stats.topIssue}
        latencyP50={advanced.latency.p50}
        latencyP95={advanced.latency.p95}
      />

      <div className="grid items-stretch gap-4 lg:grid-cols-[2fr_1fr]">
        <QualityTrend data={stats.trendData} />
        <IssueBreakdown data={stats.breakdown} />
      </div>

      <div className="grid items-stretch gap-4 md:grid-cols-2">
        <CRScoreCard data={advanced.crScore} />
        <LoopHealthCard data={advanced.loopHealth} />
      </div>

      <AgentLatencyChart data={advanced.agentLatency} />

      <section>
        <h2 className="mb-3 text-[15px] font-semibold text-fg">Review history</h2>
        <ReviewHistory rows={historyRows} />
      </section>
    </div>
  )
}
