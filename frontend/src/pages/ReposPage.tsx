import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { FolderGit2, Plus, SearchX, TriangleAlert } from 'lucide-react'
import { ApiError, isActiveAnalysis, listRepos, type Repo, type RepoStatus } from '../lib/api'
import { useRepoJobs, type RepoJob } from '../store/useRepoJobs'
import { useStore } from '../store/useStore'
import { useCurrentUser } from '../lib/useCurrentUser'
import PageHeader from '../components/ui/PageHeader'
import Button from '../components/ui/Button'
import EmptyState from '../components/ui/EmptyState'
import SearchInput from '../components/ui/SearchInput'
import FilterSelect from '../components/ui/FilterSelect'
import RepoCard, { RepoCardSkeleton } from '../components/repos/RepoCard'
import ImportRepoDialog from '../components/repos/ImportRepoDialog'
import { languageLabel } from '../components/repos/languages'

type ListState =
  | { status: 'loading' }
  | { status: 'ok'; repos: Repo[] }
  | { status: 'error'; message: string }

type SortKey = 'recent' | 'name' | 'functions'

const STATUS_OPTIONS = [
  { value: 'all', label: 'Status' },
  { value: 'ready', label: 'Ready' },
  { value: 'analyzing', label: 'Analyzing' },
  { value: 'added', label: 'Added' },
  { value: 'failed', label: 'Failed' },
]

const SORT_OPTIONS = [
  { value: 'recent', label: 'Recent' },
  { value: 'name', label: 'Name A–Z' },
  { value: 'functions', label: 'Most functions' },
]

/** A repo that only exists as an in-flight or failed first import. */
function placeholderRepo(job: RepoJob): Repo {
  const [owner = '', name = job.fullName] = job.fullName.split('/')
  return {
    url: job.url, fullName: job.fullName, owner, name, status: 'added', error: null,
    languages: [], functionsCount: null, analyzedAt: null, lastCommitSha: null, fingerprint: null, summary: null, analysis: null,
  }
}

export default function ReposPage() {
  const navigate = useNavigate()
  const { userId, guestMode } = useCurrentUser()
  const requestNewChat = useStore((s) => s.requestNewChat)
  const jobs = useRepoJobs((s) => s.jobs)
  const sessionRepos = useRepoJobs((s) => s.sessionRepos)
  const completedCount = useRepoJobs((s) => s.completedCount)
  const startAnalyze = useRepoJobs((s) => s.startAnalyze)
  const dismissJob = useRepoJobs((s) => s.dismissJob)

  const [list, setList] = useState<ListState>({ status: 'loading' })
  const [reloadKey, setReloadKey] = useState(0)
  const [params, setParams] = useSearchParams()
  // ?import=owner/repo (from a repo page for an unknown repo) opens the dialog prefilled
  const importParam = params.get('import')
  const [importOpen, setImportOpen] = useState(() => importParam != null)
  const [query, setQuery] = useState('')
  const [language, setLanguage] = useState('all')
  const [status, setStatus] = useState<'all' | RepoStatus>('all')
  const [sort, setSort] = useState<SortKey>('recent')

  // Fetch on mount, on retry, and after any analysis finishes (keeps the old list while refetching)
  useEffect(() => {
    const ctrl = new AbortController()
    listRepos(userId, ctrl.signal).then(
      (repos) => setList({ status: 'ok', repos }),
      (err) => {
        if (ctrl.signal.aborted) return
        const message = err instanceof ApiError && err.kind === 'network'
          ? 'Could not reach the PersonaCR server. Is the backend running?'
          : err instanceof Error ? err.message : String(err)
        setList({ status: 'error', message })
      },
    )
    return () => ctrl.abort()
  }, [userId, reloadKey, completedCount])

  // Background analyses this tab isn't watching (started elsewhere, or before a reload):
  // re-read the list until they finish
  useEffect(() => {
    if (list.status !== 'ok') return
    const pending = list.repos.some((r) => isActiveAnalysis(r.analysis) && jobs[r.url]?.state !== 'analyzing')
    if (!pending) return
    const t = setTimeout(() => setReloadKey((k) => k + 1), 3000)
    return () => clearTimeout(t)
  }, [list, jobs])

  const repos = useMemo(() => {
    const byUrl = new Map<string, Repo>()
    if (list.status === 'ok') for (const r of list.repos) byUrl.set(r.url, r)
    // This session's analyses are fresher than the server row (and are all guests have)
    // The server (fingerprint + background-analysis record) wins; this session's
    // results only fill in what it doesn't have yet (e.g. right after a sync analyze)
    for (const r of Object.values(sessionRepos)) {
      const prev = byUrl.get(r.url)
      if (!prev) byUrl.set(r.url, r)
      else if (!prev.fingerprint && r.fingerprint && !isActiveAnalysis(prev.analysis)) {
        byUrl.set(r.url, { ...prev, ...r, status: 'ready', error: null, analysis: prev.analysis, analyzedAt: r.analyzedAt ?? prev.analyzedAt })
      }
    }
    for (const j of Object.values(jobs)) if (!byUrl.has(j.url)) byUrl.set(j.url, placeholderRepo(j))
    return [...byUrl.values()].map((r) => {
      const j = jobs[r.url]
      if (!j || j.state === 'done') return r
      return j.state === 'analyzing'
        ? { ...r, status: 'analyzing' as const, error: null }
        : { ...r, status: 'failed' as const, error: j.error }
    })
  }, [list, sessionRepos, jobs])
  // Failed first imports that were never saved: offer Dismiss instead of Open
  const placeholders = useMemo(() => {
    const saved = new Set(list.status === 'ok' ? list.repos.map((r) => r.url) : [])
    return new Set(
      Object.values(jobs)
        .filter((j) => j.state === 'failed' && !saved.has(j.url) && !sessionRepos[j.url])
        .map((j) => j.url),
    )
  }, [list, jobs, sessionRepos])

  const languageOptions = useMemo(() => {
    const langs = [...new Set(repos.flatMap((r) => r.languages.map((l) => l.toLowerCase())))].sort()
    return [{ value: 'all', label: 'Language' }, ...langs.map((l) => ({ value: l, label: languageLabel(l) }))]
  }, [repos])

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    const sortTime = (r: Repo) => {
      const j = jobs[r.url]
      if (j && j.state !== 'done') return 1e15 + j.startedAt // in-flight and failed first, newest on top
      return r.analyzedAt ? Date.parse(r.analyzedAt) || 0 : 0
    }
    return repos
      .filter((r) => !q || r.fullName.toLowerCase().includes(q))
      .filter((r) => language === 'all' || r.languages.some((l) => l.toLowerCase() === language))
      .filter((r) => status === 'all' || r.status === status)
      .sort((a, b) => {
        if (sort === 'name') return a.fullName.localeCompare(b.fullName)
        if (sort === 'functions') return (b.functionsCount ?? -1) - (a.functionsCount ?? -1)
        return sortTime(b) - sortTime(a)
      })
  }, [repos, jobs, query, language, status, sort])

  const filtering = query.trim() !== '' || language !== 'all' || status !== 'all'

  function startChat(repo: Repo) {
    requestNewChat(repo.url)
    navigate('/chat')
  }

  function retryList() {
    setList({ status: 'loading' })
    setReloadKey((k) => k + 1)
  }

  function clearFilters() {
    setQuery(''); setLanguage('all'); setStatus('all')
  }

  const importButton = (
    <Button variant="primary" icon={<Plus size={15} />} onClick={() => setImportOpen(true)}>Import repo</Button>
  )

  const total = repos.length
  const description = list.status === 'loading' && total === 0
    ? 'Loading your repos…'
    : `${total} repo${total === 1 ? '' : 's'} — new code is reviewed against the style PersonaCR learned from each.`

  return (
    <div className="mx-auto w-full max-w-[1400px] px-4 py-8 sm:px-6 lg:py-10">
      <PageHeader title="Repositories" description={description} actions={importButton} />

      {total > 0 && (
        <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
          <SearchInput value={query} onChange={setQuery} placeholder="Search repos" className="w-full sm:w-72" />
          <div className="grid grid-cols-3 gap-2 sm:flex">
            <FilterSelect label="Language" value={language} options={languageOptions} onChange={setLanguage} />
            <FilterSelect label="Status" value={status} options={STATUS_OPTIONS} onChange={(v) => setStatus(v as typeof status)} />
            <FilterSelect label="Sort" value={sort} options={SORT_OPTIONS} onChange={(v) => setSort(v as SortKey)} />
          </div>
        </div>
      )}

      {guestMode && (
        <p className="mt-5 rounded-lg border border-line bg-surface px-4 py-2.5 text-[13px] text-fg-3">
          Guest session — repos you import are kept only until you close this tab.
        </p>
      )}

      {list.status === 'error' && (
        <div className="mt-5 flex flex-col gap-3 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 sm:flex-row sm:items-center sm:justify-between" role="alert">
          <p className="flex items-start gap-2 text-sm text-fg-2">
            <TriangleAlert size={16} className="mt-0.5 shrink-0 text-danger" aria-hidden />
            <span><span className="font-medium text-fg">Couldn’t load your saved repos.</span> {list.message}</span>
          </p>
          <Button size="sm" onClick={retryList}>Retry</Button>
        </div>
      )}

      <div className="mt-6">
        {list.status === 'loading' && total === 0 ? (
          <Grid>{Array.from({ length: 6 }, (_, i) => <RepoCardSkeleton key={i} />)}</Grid>
        ) : total === 0 ? (
          list.status === 'ok' && (
            <EmptyState
              icon={<FolderGit2 size={20} />}
              title="Import your first repo"
              description="PersonaCR reads a public GitHub repo, learns its conventions — naming, type hints, docstrings, error handling — and reviews new code against them."
              action={importButton}
            />
          )
        ) : visible.length === 0 ? (
          <EmptyState
            icon={<SearchX size={20} />}
            title="No repos match these filters"
            action={filtering ? <Button onClick={clearFilters}>Clear filters</Button> : undefined}
          />
        ) : (
          <Grid>
            {visible.map((r) => (
              <RepoCard
                key={r.url}
                repo={r}
                job={jobs[r.url]}
                placeholder={placeholders.has(r.url)}
                onAnalyze={(repo, force) => startAnalyze(repo, userId, { force })}
                onStartChat={startChat}
                onDismiss={(repo) => dismissJob(repo.url)}
              />
            ))}
          </Grid>
        )}
      </div>

      {importOpen && (
        <ImportRepoDialog
          userId={userId}
          initialValue={importParam ?? ''}
          onClose={() => { setImportOpen(false); if (importParam != null) setParams({}, { replace: true }) }}
          onStartChat={(repo) => { setImportOpen(false); startChat(repo) }}
        />
      )}
    </div>
  )
}

function Grid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-[repeat(auto-fill,minmax(min(100%,300px),1fr))] gap-4">{children}</div>
}
