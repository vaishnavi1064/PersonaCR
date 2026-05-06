import { useEffect, useState, useMemo } from 'react'
import Sidebar from '../components/layout/Sidebar'
import TopBar from '../components/layout/TopBar'
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
    <div style={{
      display: 'flex',
      height: '100vh',
      background: 'var(--bg-primary)',
      color: 'var(--text-primary)',
      overflow: 'hidden',
    }}>
      <Sidebar />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
        <TopBar title="Dashboard" />

        <div style={{ flex: 1, overflowY: 'auto' }}>
          <div style={{
            maxWidth: 960,
            width: '100%',
            margin: '0 auto',
            padding: '28px 24px 48px',
            display: 'flex',
            flexDirection: 'column',
            gap: 24,
          }}>
            {/* Heading */}
            <div>
              <h1 style={{
                fontFamily: 'var(--font-display)',
                fontSize: 25,
                color: 'var(--text-primary)',
                letterSpacing: '-0.3px',
                marginBottom: 4,
              }}>
                Dashboard
              </h1>
              <p style={{
                fontFamily: 'var(--font-body)',
                fontSize: 14,
                color: 'var(--text-tertiary)',
              }}>
                {loading
                  ? 'Loading your data…'
                  : stats.totalReviews === 0
                    ? 'No reviews yet — go to Chat to get started.'
                    : `${stats.totalReviews} review${stats.totalReviews === 1 ? '' : 's'} across your repos.`}
              </p>
            </div>

            {/* Summary cards */}
            <SummaryCards
              avgScore={stats.avgScore}
              totalReviews={stats.totalReviews}
              topIssue={stats.topIssue}
              latencyP50={advanced.latency.p50}
              latencyP95={advanced.latency.p95}
            />

            {/* Charts row */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '2fr 1fr',
              gap: 16,
              alignItems: 'stretch',
            }}>
              <QualityTrend data={stats.trendData} />
              <IssueBreakdown data={stats.breakdown} />
            </div>

            {/* New metrics row: CRScore + Loop Health */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: 16,
              alignItems: 'stretch',
            }}>
              <CRScoreCard data={advanced.crScore} />
              <LoopHealthCard data={advanced.loopHealth} />
            </div>

            {/* Per-agent latency */}
            <AgentLatencyChart data={advanced.agentLatency} />

            {/* Review history */}
            <div>
              <p style={{
                fontFamily: 'var(--font-body)',
                fontSize: 15,
                fontWeight: 500,
                color: 'var(--text-primary)',
                marginBottom: 12,
              }}>
                Review history
              </p>
              <ReviewHistory rows={historyRows} />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
