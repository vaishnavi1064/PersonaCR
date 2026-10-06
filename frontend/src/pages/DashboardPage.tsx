import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { BarChart3, TriangleAlert } from 'lucide-react'
import {
  AGENT_LABEL, fetchAllReviews, fingerprintChips, isAccountUserId, parseRepoUrl, repoShortName, reviewFromRow,
  type AgentName, type Review,
} from '../lib/api'
import { computeDashboard } from '../lib/dashboardStats'
import { useCurrentUser } from '../lib/useCurrentUser'
import { useUserRepos } from '../lib/useUserRepos'
import { formatMs } from '../lib/timeline'
import { signInWithGitHub } from '../lib/supabase'
import PageHeader from '../components/ui/PageHeader'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Chip from '../components/ui/Chip'
import EmptyState from '../components/ui/EmptyState'
import FilterSelect from '../components/ui/FilterSelect'
import { buttonClass } from '../components/ui/styles'
import TrendChart from '../components/dashboard/TrendChart'
import BarList from '../components/dashboard/BarList'
import ReviewHistoryTable from '../components/dashboard/ReviewHistoryTable'
import RepoRollupTable from '../components/dashboard/RepoRollupTable'

type Load = { status: 'loading' } | { status: 'ok'; reviews: Review[] } | { status: 'error'; message: string }

const ALL = 'all'
const pct = (v: number | null) => (v == null ? '—' : `${Math.round(v * 100)}%`)
const label = (s: string) => s.replace(/_/g, ' ')

function Section({ title, subtitle, children, className }: { title: string; subtitle?: string; children: React.ReactNode; className?: string }) {
  return (
    <Card className={`flex flex-col p-5 ${className ?? ''}`}>
      <h2 className="text-[15px] font-semibold text-fg">{title}</h2>
      {subtitle && <p className="mt-0.5 text-xs text-fg-3">{subtitle}</p>}
      <div className="mt-4 flex-1">{children}</div>
    </Card>
  )
}

function Tile({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <Card className="p-4">
      <p className="text-xs text-fg-3">{label}</p>
      <p className="mt-1 truncate text-xl font-semibold tabular-nums text-fg">{value}</p>
      {note && <p className="mt-0.5 text-xs text-fg-3">{note}</p>}
    </Card>
  )
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="flex h-full min-h-28 items-center justify-center text-center text-sm text-fg-3">{children}</p>
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const { userId, guestMode } = useCurrentUser()
  const account = isAccountUserId(userId)
  const { repos } = useUserRepos(userId)
  const [params, setParams] = useSearchParams()
  const [load, setLoad] = useState<Load>({ status: 'loading' })
  const [key, setKey] = useState(0)

  useEffect(() => {
    if (!account) return
    let alive = true
    fetchAllReviews(userId).then(
      (rows) => { if (alive) setLoad({ status: 'ok', reviews: rows.map((r) => reviewFromRow(r).review) }) },
      (err) => { if (alive) setLoad({ status: 'error', message: err instanceof Error ? err.message : String(err) }) },
    )
    return () => { alive = false }
  }, [account, userId, key])

  const all = useMemo(() => (load.status === 'ok' ? load.reviews : []), [load])
  const repoOptions = useMemo(() => [...new Set(all.map((r) => r.repoUrl))].sort((a, b) => repoShortName(a).localeCompare(repoShortName(b))), [all])

  // ?repo=owner/name
  const repoParam = params.get('repo')
  const selected = repoOptions.find((u) => repoShortName(u).toLowerCase() === repoParam?.toLowerCase()) ?? null
  const setRepo = (url: string | null) => setParams(url ? { repo: repoShortName(url) } : {}, { replace: true })

  const reviews = useMemo(() => (selected ? all.filter((r) => r.repoUrl === selected) : all), [all, selected])
  const stats = useMemo(() => computeDashboard(reviews), [reviews])
  const selectedRepo = selected ? repos.find((r) => r.url === selected) ?? null : null
  const selectedParsed = selected ? parseRepoUrl(selected) : null

  if (!account) {
    return (
      <div className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:py-10">
        <PageHeader title="Dashboard" description="Scores, trends and agent timing across your saved reviews." />
        <EmptyState
          className="mt-8"
          icon={<BarChart3 size={20} />}
          title={guestMode ? 'Guest reviews aren’t saved' : 'Sign in to see your dashboard'}
          description="The dashboard is built from your saved review history. Sign in with GitHub to keep reviews."
          action={<Button variant="primary" onClick={() => signInWithGitHub()}>Sign in with GitHub</Button>}
        />
      </div>
    )
  }

  const description = load.status === 'loading'
    ? 'Loading your reviews…'
    : selected
      ? `${stats.total} review${stats.total === 1 ? '' : 's'} of ${repoShortName(selected)}`
      : `${stats.total} review${stats.total === 1 ? '' : 's'} across ${repoOptions.length} repo${repoOptions.length === 1 ? '' : 's'}`

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-8 sm:px-6 lg:py-10">
      <PageHeader
        title="Dashboard"
        description={description}
        actions={repoOptions.length > 0 && (
          <FilterSelect
            label="Repository"
            value={selected ?? ALL}
            onChange={(v) => setRepo(v === ALL ? null : v)}
            options={[{ value: ALL, label: 'All repos' }, ...repoOptions.map((u) => ({ value: u, label: repoShortName(u) }))]}
            className="w-full sm:w-72"
          />
        )}
      />

      {load.status === 'error' && (
        <div className="flex flex-col gap-3 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 sm:flex-row sm:items-center sm:justify-between" role="alert">
          <p className="flex items-start gap-2 text-sm text-fg-2">
            <TriangleAlert size={16} className="mt-0.5 shrink-0 text-danger" aria-hidden />
            <span><span className="font-medium text-fg">Couldn’t load your reviews.</span> {load.message}</span>
          </p>
          <Button size="sm" onClick={() => { setLoad({ status: 'loading' }); setKey((k) => k + 1) }}>Retry</Button>
        </div>
      )}

      {load.status === 'loading' && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-busy>
          {[0, 1, 2, 3].map((i) => <div key={i} className="h-24 animate-pulse rounded-xl bg-surface" />)}
        </div>
      )}

      {load.status === 'ok' && all.length === 0 && (
        <EmptyState
          icon={<BarChart3 size={20} />}
          title="No saved reviews yet"
          description="Review code in a chat and it shows up here. Reviews that couldn’t produce a score aren’t saved."
          action={<Link to="/chat" className={buttonClass('primary')}>Go to Chats</Link>}
        />
      )}

      {load.status === 'ok' && all.length > 0 && (
        <>
          {/* Headline: one hero number, then supporting tiles */}
          <div className="grid gap-4 lg:grid-cols-[1.2fr_2fr]">
            <Card className="p-5">
              <p className="text-xs text-fg-3">Average score</p>
              <p className="mt-1 flex items-baseline gap-1.5">
                <span className="text-5xl font-semibold tabular-nums tracking-tight text-fg">{stats.avgScore == null ? '—' : stats.avgScore.toFixed(1)}</span>
                {stats.avgScore != null && <span className="text-sm text-fg-3">/100</span>}
              </p>
              <p className="mt-2 text-xs text-fg-3">
                From {stats.scored} scored review{stats.scored === 1 ? '' : 's'}
                {stats.unscored > 0 && <> · {stats.unscored} without a score (degraded/error) not counted</>}
              </p>
            </Card>
            <div className="grid gap-4 sm:grid-cols-3">
              <Tile label="Reviews" value={String(stats.total)} note={selected ? undefined : `${repoOptions.length} repo${repoOptions.length === 1 ? '' : 's'}`} />
              <Tile
                label="Most common finding"
                value={stats.categories[0] ? label(stats.categories[0].category) : '—'}
                note={stats.categories[0] ? `${stats.categories[0].count} of ${stats.categories.reduce((s, c) => s + c.count, 0)} findings` : undefined}
              />
              <Tile
                label="Review time (est.)"
                value={stats.reviewTime.p50 == null ? '—' : formatMs(stats.reviewTime.p50)}
                note={stats.reviewTime.p95 == null ? undefined : `median · p95 ${formatMs(stats.reviewTime.p95)}`}
              />
            </div>
          </div>

          {selected && selectedParsed && (
            <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="text-sm text-fg">Reviewed against <span className="font-medium">{repoShortName(selected)}</span>’s own fingerprint</p>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {selectedRepo?.fingerprint
                    ? fingerprintChips(selectedRepo.fingerprint).map((c) => <Chip key={c}>{c}</Chip>)
                    : <span className="text-xs text-fg-3">Not in your repositories any more.</span>}
                </div>
              </div>
              <Link to={`/repos/${selectedParsed.owner}/${selectedParsed.name}?tab=atlas`} className={buttonClass('outline', 'sm')}>Convention Atlas</Link>
            </Card>
          )}

          <div className="grid items-stretch gap-4 lg:grid-cols-[2fr_1fr]">
            <Section title="Score per review" subtitle="Each point is a scored review, oldest to newest. Click a point to open it.">
              {stats.trend.length === 0
                ? <Empty>No scored reviews yet.</Empty>
                : <TrendChart points={stats.trend} showRepo={!selected} onSelect={(id) => navigate(`/reviews/${id}`)} />}
            </Section>
            <Section title="Findings by category" subtitle="Across scored reviews">
              {stats.categories.length === 0
                ? <Empty>No findings yet.</Empty>
                : <BarList
                    label="Findings by category"
                    items={stats.categories.slice(0, 6).map((c) => ({
                      key: c.category, label: label(c.category), value: c.count,
                      display: `${Math.round(c.share * 100)}%`, detail: `${c.count} finding${c.count === 1 ? '' : 's'}`,
                    }))}
                  />}
            </Section>
          </div>

          <div className="grid items-stretch gap-4 md:grid-cols-2">
            <Section title="Review quality" subtitle="CRScore-style averages, 0–1: coverage of the code’s issues, focus, and their balance">
              {stats.crScore.relevance == null && stats.crScore.comprehensiveness == null
                ? <Empty>No quality scores yet.</Empty>
                : (
                  <dl className="flex flex-col gap-3.5">
                    {([['Coverage', stats.crScore.comprehensiveness], ['Focus', stats.crScore.conciseness], ['Relevance', stats.crScore.relevance]] as const).map(([name, v]) => (
                      <div key={name}>
                        <div className="mb-1 flex justify-between text-[13px]">
                          <dt className="text-fg-2">{name}</dt>
                          <dd className="font-medium tabular-nums text-fg">{v == null ? '—' : v.toFixed(2)}</dd>
                        </div>
                        <div className="h-2 rounded-full" style={{ background: 'color-mix(in srgb, var(--chart-series) 18%, transparent)' }} aria-hidden>
                          <div className="h-full rounded-full" style={{ width: `${(v ?? 0) * 100}%`, background: 'var(--chart-series)' }} />
                        </div>
                      </div>
                    ))}
                  </dl>
                )}
            </Section>
            <Section title="Feedback loops" subtitle="How often reviews needed a second look">
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg border border-line p-3">
                  <p className="text-2xl font-semibold tabular-nums text-fg">{pct(stats.loops.confidentFirstPass)}</p>
                  <p className="mt-0.5 text-xs text-fg-3">confident on the first pass{stats.loops.samples.confidence ? ` (${stats.loops.samples.confidence} reviews)` : ''}</p>
                </div>
                <div className="rounded-lg border border-line p-3">
                  <p className="text-2xl font-semibold tabular-nums text-fg">{pct(stats.loops.qualityGatePassed)}</p>
                  <p className="mt-0.5 text-xs text-fg-3">passed the quality gate{stats.loops.samples.gate ? ` (${stats.loops.samples.gate} reviews)` : ''}</p>
                </div>
              </div>
              <p className="mt-3 text-xs text-fg-3">A review runs at most two passes: a low-confidence first pass is re-planned, or — if that second pass is still free — a failed quality gate triggers a re-review.</p>
            </Section>
          </div>

          <Section title="Time per agent" subtitle="Average duration per run, across scored reviews">
            {stats.agentTime.length === 0
              ? <Empty>No agent timings recorded.</Empty>
              : <BarList
                  label="Average time per agent"
                  items={stats.agentTime.map((a) => ({
                    key: a.agent, label: AGENT_LABEL[a.agent as AgentName] ?? label(a.agent), value: a.avgMs,
                    display: formatMs(a.avgMs), detail: `${a.runs} run${a.runs === 1 ? '' : 's'}`,
                  }))}
                />}
          </Section>

          {!selected && stats.byRepo.length > 0 && (
            <section>
              <h2 className="mb-1 text-[15px] font-semibold text-fg">By repository</h2>
              <p className="mb-3 text-xs text-fg-3">Each repo is reviewed against its own fingerprint — styles are never averaged across repos.</p>
              <RepoRollupTable rows={stats.byRepo} onFilter={(u) => setRepo(u)} />
            </section>
          )}

          <section>
            <h2 className="mb-3 text-[15px] font-semibold text-fg">Review history</h2>
            {reviews.length === 0 ? <Card className="p-5"><Empty>No reviews for this repo.</Empty></Card> : <ReviewHistoryTable reviews={reviews} showRepo={!selected} />}
          </section>
        </>
      )}
    </div>
  )
}
