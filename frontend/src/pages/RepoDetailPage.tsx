import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, FolderGit2, Loader2, MessageSquarePlus, RefreshCw } from 'lucide-react'
import { fetchRepoChats, fetchRepoReviews, isAccountUserId, type Repo } from '../lib/api'
import type { ChatMeta, ReviewRow } from '../lib/db'
import { useStore } from '../store/useStore'
import { useRepoJobs } from '../store/useRepoJobs'
import { useCurrentUser } from '../lib/useCurrentUser'
import { useUserRepos } from '../lib/useUserRepos'
import { useNow } from '../lib/useNow'
import { elapsed, relativeTime } from '../lib/format'
import Button from '../components/ui/Button'
import EmptyState from '../components/ui/EmptyState'
import Tabs from '../components/ui/Tabs'
import GitHubMark from '../components/ui/GitHubMark'
import { buttonClass } from '../components/ui/styles'
import RepoStatusPill from '../components/repos/RepoStatusPill'
import { activeAnalysis, stuckHint } from '../components/repos/analysisStatus'
import RepoOverview from '../components/repo/RepoOverview'
import ConventionAtlas from '../components/repo/ConventionAtlas'
import RepoChatsTab from '../components/repo/RepoChatsTab'
import RepoReviewsTab from '../components/repo/RepoReviewsTab'
import type { Loadable } from '../components/repo/loadable'

const TABS = ['overview', 'atlas', 'chats', 'reviews'] as const
type Tab = typeof TABS[number]

function useLoad<T>(enabled: boolean, load: () => Promise<T>, deps: unknown[]): [Loadable<T>, () => void] {
  const [state, setState] = useState<Loadable<T>>({ status: 'loading' })
  const [key, setKey] = useState(0)
  useEffect(() => {
    if (!enabled) return
    let alive = true
    load().then(
      (data) => { if (alive) setState({ status: 'ok', data }) },
      (err) => { if (alive) setState({ status: 'error', message: err instanceof Error ? err.message : String(err) }) },
    )
    return () => { alive = false }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, key, ...deps])
  return [state, () => { setState({ status: 'loading' }); setKey((k) => k + 1) }]
}

export default function RepoDetailPage() {
  const { owner = '', name = '' } = useParams()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const tab: Tab = (TABS as readonly string[]).includes(params.get('tab') ?? '') ? (params.get('tab') as Tab) : 'overview'
  const setTab = (t: Tab) => setParams(t === 'overview' ? {} : { tab: t }, { replace: true })

  const { userId, guestMode } = useCurrentUser()
  const account = isAccountUserId(userId)
  const { repos, loading } = useUserRepos(userId)
  const fullName = `${owner}/${name}`.toLowerCase()
  const repo: Repo | undefined = repos.find((r) => r.fullName.toLowerCase() === fullName)
  const repoUrl = repo?.url ?? `https://github.com/${owner}/${name}`

  const job = useRepoJobs((s) => (repo ? s.jobs[repo.url] : undefined))
  const startAnalyze = useRepoJobs((s) => s.startAnalyze)
  const requestNewChat = useStore((s) => s.requestNewChat)
  const setActiveChatId = useStore((s) => s.setActiveChatId)
  const active = repo ? activeAnalysis(repo, job) : null
  const analyzing = active != null
  const now = useNow(analyzing)

  const [chats, retryChats] = useLoad<ChatMeta[]>(account && !!repo, () => fetchRepoChats(userId, repoUrl), [userId, repoUrl])
  const [reviews, retryReviews] = useLoad<ReviewRow[]>(account && !!repo, () => fetchRepoReviews(userId, repoUrl), [userId, repoUrl])

  const ready = repo?.fingerprint != null && !analyzing

  function startChat() {
    requestNewChat(repoUrl)
    navigate('/chat')
  }

  if (!repo) {
    return (
      <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6 lg:py-10">
        <BackLink />
        {loading ? (
          <div className="flex flex-col gap-4" aria-busy>
            <div className="h-10 w-64 animate-pulse rounded-lg bg-surface" />
            <div className="h-48 animate-pulse rounded-xl bg-surface" />
          </div>
        ) : (
          <EmptyState
            icon={<FolderGit2 size={20} />}
            title={`${owner}/${name} isn’t in your repositories`}
            description="Import it to learn its conventions, chat about it and review code against it."
            action={<Link to={`/repos?import=${encodeURIComponent(`${owner}/${name}`)}`} className={buttonClass('primary')}>Import {owner}/{name}</Link>}
          />
        )}
      </div>
    )
  }

  const counts = {
    chats: chats.status === 'ok' ? chats.data.length : undefined,
    reviews: reviews.status === 'ok' ? reviews.data.length : undefined,
  }

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:py-10">
      <BackLink />

      {/* Header — same anatomy as the repo card */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="truncate text-[28px] font-bold leading-tight tracking-tight text-fg sm:text-[34px]" title={repo.fullName}>{repo.name}</h1>
            <RepoStatusPill status={analyzing ? 'analyzing' : repo.status} />
          </div>
          <p className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-fg-3">
            <a href={repo.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 hover:text-fg hover:underline">
              <GitHubMark size={13} /> {repo.fullName}
            </a>
            {active
              ? (
                <span className="inline-flex items-center gap-1.5 text-fg-2" role="status">
                  <Loader2 size={13} className="animate-spin text-accent" aria-hidden /> {active.message}
                  {active.startedAt > 0 && <span className="tabular-nums text-fg-3">· {elapsed(now - active.startedAt)}</span>}
                </span>
              )
              : repo.analyzedAt && <span>Analyzed {relativeTime(repo.analyzedAt)}</span>}
          </p>
          {active && stuckHint(active, now) && <p className="mt-1.5 text-sm text-warning">{stuckHint(active, now)}</p>}
          {!active && (job?.state === 'failed' ? job.error : repo.status === 'failed' ? repo.error : null) && (
            <p className="mt-1.5 text-sm text-danger">{job?.state === 'failed' ? job.error : repo.error}</p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button icon={<RefreshCw size={15} />} loading={analyzing} onClick={() => startAnalyze(repo, userId, { force: true })}>
            {analyzing ? 'Analyzing' : 'Reanalyze'}
          </Button>
          <Button variant="primary" icon={<MessageSquarePlus size={15} />} onClick={startChat} disabled={!ready} title={ready ? undefined : 'Analyze the repo first'}>
            Start chat
          </Button>
        </div>
      </div>

      <Tabs
        className="mt-6"
        label="Repository sections"
        value={tab}
        onChange={(t) => setTab(t as Tab)}
        items={[
          { id: 'overview', label: 'Overview' },
          { id: 'atlas', label: 'Convention Atlas' },
          { id: 'chats', label: 'Chats', count: counts.chats },
          { id: 'reviews', label: 'Reviews', count: counts.reviews },
        ]}
      />

      <div className="mt-6" role="tabpanel" aria-label={tab}>
        {tab === 'overview' && (
          <RepoOverview repo={repo} chats={account ? counts.chats ?? null : null} reviews={account ? counts.reviews ?? null : null} onTab={setTab} />
        )}
        {tab === 'atlas' && (repo.fingerprint
          ? <ConventionAtlas fingerprint={repo.fingerprint} chunksAnalyzed={repo.functionsCount} />
          : <EmptyState title="No fingerprint yet" description="Analyze this repo to build its Convention Atlas." action={<Button variant="primary" onClick={() => startAnalyze(repo, userId, { force: true })}>Analyze</Button>} />)}
        {tab === 'chats' && (
          <RepoChatsTab
            state={chats}
            guest={guestMode || !account}
            ready={ready}
            onOpen={(id) => { setActiveChatId(id); navigate('/chat') }}
            onNewChat={startChat}
            onRetry={retryChats}
          />
        )}
        {tab === 'reviews' && <RepoReviewsTab state={reviews} guest={guestMode || !account} onRetry={retryReviews} />}
      </div>
    </div>
  )
}

function BackLink() {
  return (
    <Link to="/repos" className="mb-4 inline-flex items-center gap-1.5 text-sm text-fg-3 hover:text-fg">
      <ArrowLeft size={14} aria-hidden /> Repositories
    </Link>
  )
}
