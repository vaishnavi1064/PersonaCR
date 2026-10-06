import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { CircleCheck, Loader2, TriangleAlert, X } from 'lucide-react'
import { fingerprintChips, parseRepoUrl, type ParsedRepoUrl, type Repo } from '../../lib/api'
import { useRepoJobs } from '../../store/useRepoJobs'
import { count, elapsed } from '../../lib/format'
import { useNow } from '../../lib/useNow'
import Button from '../ui/Button'
import Chip from '../ui/Chip'
import IconButton from '../ui/IconButton'
import GitHubMark from '../ui/GitHubMark'

interface ImportRepoDialogProps {
  userId: string
  initialValue?: string
  onClose: () => void
  onStartChat: (repo: Repo) => void
}

/**
 * Import a repo by URL. Progress is honest: analysis is one synchronous
 * request, so all we know is that it's running and for how long.
 * Mount it only while open so its state resets each time.
 */
export default function ImportRepoDialog({ userId, initialValue = '', onClose, onStartChat }: ImportRepoDialogProps) {
  const titleId = useId()
  const errorId = useId()
  const dialogRef = useRef<HTMLDivElement>(null)
  const [value, setValue] = useState(initialValue)
  const [invalid, setInvalid] = useState(false)
  const [target, setTarget] = useState<ParsedRepoUrl | null>(null)

  const job = useRepoJobs((s) => (target ? s.jobs[target.url] : undefined))
  const startAnalyze = useRepoJobs((s) => s.startAnalyze)
  const now = useNow(job?.state === 'analyzing')

  // Restore focus to whatever opened the dialog
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null
    return () => opener?.focus?.()
  }, [])

  function submit(e: FormEvent) {
    e.preventDefault()
    const parsed = parseRepoUrl(value)
    if (!parsed) { setInvalid(true); return }
    setTarget(parsed)
    startAnalyze(parsed, userId)
  }

  function retry() {
    if (!target || job?.state !== 'failed') return
    startAnalyze(target, userId, { force: job.force })
  }

  function onKeyDown(e: KeyboardEvent) {
    if (e.key === 'Escape') { e.stopPropagation(); onClose(); return }
    if (e.key !== 'Tab' || !dialogRef.current) return
    // Keep focus inside the dialog
    const focusables = dialogRef.current.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input, a[href], [tabindex]:not([tabindex="-1"])',
    )
    if (focusables.length === 0) return
    const first = focusables[0]
    const last = focusables[focusables.length - 1]
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
  }

  const running = job?.state === 'analyzing'

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 pt-[12vh]" onKeyDown={onKeyDown}>
      <div className="fixed inset-0 bg-black/60" onClick={onClose} aria-hidden />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative w-full max-w-lg rounded-2xl border border-line bg-surface shadow-pop"
      >
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div>
            <h2 id={titleId} className="text-base font-semibold text-fg">Import a repository</h2>
            <p className="mt-0.5 text-[13px] text-fg-3">PersonaCR learns your conventions from a public GitHub repo.</p>
          </div>
          <IconButton label="Close" icon={<X size={16} />} size="sm" onClick={onClose} />
        </div>

        <div className="px-5 py-5">
          {!job && (
            <form onSubmit={submit} noValidate>
              <label htmlFor="repo-url" className="text-sm font-medium text-fg-2">GitHub repo URL</label>
              <div className="relative mt-1.5">
                <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-fg-3"><GitHubMark size={15} /></span>
                <input
                  id="repo-url"
                  autoFocus
                  value={value}
                  onChange={(e) => { setValue(e.target.value); setInvalid(false) }}
                  placeholder="https://github.com/owner/repo"
                  autoComplete="off"
                  spellCheck={false}
                  aria-invalid={invalid || undefined}
                  aria-describedby={invalid ? errorId : undefined}
                  className="h-10 w-full rounded-lg border border-line bg-canvas pl-9 pr-3 text-sm text-fg placeholder:text-fg-3 focus:border-accent focus:outline-none aria-invalid:border-danger"
                />
              </div>
              {invalid ? (
                <p id={errorId} className="mt-1.5 text-[13px] text-danger">Enter a GitHub repo URL like https://github.com/owner/repo, or owner/repo.</p>
              ) : (
                <p className="mt-1.5 text-[13px] text-fg-3">Public repos only. Large repos can take several minutes.</p>
              )}
              <div className="mt-5 flex justify-end gap-2">
                <Button onClick={onClose}>Cancel</Button>
                <Button type="submit" variant="primary" disabled={!value.trim()}>Import</Button>
              </div>
            </form>
          )}

          {job && target && (
            <div className="flex flex-col gap-4">
              <div className="flex items-center gap-2 text-sm">
                <GitHubMark size={15} />
                <span className="truncate font-medium text-fg">{target.fullName}</span>
              </div>

              {running && (
                <div className="rounded-xl border border-line bg-canvas p-4" role="status" aria-live="polite">
                  <p className="flex items-center gap-2 text-sm font-medium text-fg">
                    <Loader2 size={15} className="animate-spin text-accent" aria-hidden />
                    Analyzing… {elapsed(now - job.startedAt)} elapsed
                  </p>
                  <p className="mt-1.5 text-[13px] text-fg-3">
                    Reading the code, measuring conventions (naming, type hints, docstrings, error handling),
                    and indexing functions for reviews. You can close this — the card keeps updating.
                  </p>
                </div>
              )}

              {job.state === 'failed' && (
                <div className="rounded-xl border border-danger/30 bg-danger/10 p-4" role="alert">
                  <p className="flex items-center gap-2 text-sm font-medium text-danger">
                    <TriangleAlert size={15} aria-hidden /> Import failed after {elapsed(job.finishedAt - job.startedAt)}
                  </p>
                  <p className="mt-1.5 break-words text-[13px] text-fg-2">{job.error}</p>
                </div>
              )}

              {job.state === 'done' && (
                <div className="rounded-xl border border-success/30 bg-success/10 p-4" role="status">
                  <p className="flex items-center gap-2 text-sm font-medium text-success">
                    <CircleCheck size={15} aria-hidden />
                    {job.result.cacheStatus === 'fresh'
                      ? 'Already up to date — loaded the saved analysis'
                      : `Analyzed ${count(job.result.repo.functionsCount)} functions in ${elapsed(job.finishedAt - job.startedAt)}`}
                  </p>
                  {fingerprintChips(job.result.repo.fingerprint).length > 0 && (
                    <div className="mt-2.5 flex flex-wrap gap-1.5">
                      {fingerprintChips(job.result.repo.fingerprint).map((c) => <Chip key={c}>{c}</Chip>)}
                    </div>
                  )}
                  {job.result.indexError && (
                    <p className="mt-2.5 text-[13px] text-warning">
                      Code search indexing failed, so reviews won’t include similar examples from this repo. Reanalyze to try again.
                    </p>
                  )}
                </div>
              )}

              <div className="flex flex-wrap justify-end gap-2">
                {running && <Button onClick={onClose}>Run in background</Button>}
                {job.state === 'failed' && (
                  <>
                    <Button onClick={() => { useRepoJobs.getState().dismissJob(target.url); setTarget(null) }}>Edit URL</Button>
                    <Button variant="primary" onClick={retry}>Retry</Button>
                  </>
                )}
                {job.state === 'done' && (
                  <>
                    <Button onClick={onClose}>Done</Button>
                    <Button variant="primary" onClick={() => onStartChat(job.result.repo)}>Start chat</Button>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
