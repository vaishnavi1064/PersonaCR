import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Check, ChevronDown, Lock, Plus } from 'lucide-react'
import { fingerprintChips, repoShortName, type Repo } from '../../lib/api'
import { cn } from '../../lib/cn'
import GitHubMark from '../ui/GitHubMark'
import Chip from '../ui/Chip'

interface RepoPickerProps {
  repos: Repo[]
  value: string | null
  onChange: (url: string) => void
  /** Chat has messages — its repo can no longer change. */
  locked: boolean
  loading?: boolean
}

/** One repo per chat. Only analyzed (Ready) repos can be picked. */
export default function RepoPicker({ repos, value, onChange, locked, loading }: RepoPickerProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onDown(e: MouseEvent) { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey) }
  }, [open])

  const label = value ? repoShortName(value) : null

  if (locked && value) {
    return (
      <span
        className="inline-flex h-8 min-w-0 items-center gap-2 rounded-lg border border-line bg-surface px-2.5 text-sm text-fg"
        title="Each chat stays on one repo. Start a new chat to use another."
      >
        <GitHubMark size={13} />
        <span className="truncate font-medium">{label}</span>
        <Lock size={12} className="shrink-0 text-fg-3" aria-label="Locked to this chat" />
      </span>
    )
  }

  return (
    <div ref={ref} className="relative min-w-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className={cn(
          'inline-flex h-8 max-w-full items-center gap-2 rounded-lg border px-2.5 text-sm cursor-pointer',
          value ? 'border-line bg-surface text-fg hover:border-line-strong' : 'border-accent/60 bg-accent-soft text-accent-fg hover:border-accent',
        )}
      >
        <GitHubMark size={13} />
        <span className="truncate font-medium">{label ?? 'Choose a repo'}</span>
        <ChevronDown size={14} className="shrink-0 text-fg-3" aria-hidden />
      </button>

      {open && (
        <div className="absolute left-0 top-full z-40 mt-1.5 w-80 max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl border border-line bg-surface shadow-pop">
          <p className="border-b border-line px-3 py-2 text-xs text-fg-3">Answers and reviews use this repo’s fingerprint.</p>
          <ul role="listbox" aria-label="Repositories" className="max-h-72 overflow-y-auto p-1">
            {loading && repos.length === 0 && <li className="px-3 py-2 text-sm text-fg-3">Loading repos…</li>}
            {!loading && repos.length === 0 && <li className="px-3 py-2 text-sm text-fg-3">No repos imported yet.</li>}
            {repos.map((r) => {
              const ready = r.fingerprint != null && r.status !== 'analyzing'
              const selected = r.url === value
              return (
                <li key={r.url}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={selected}
                    disabled={!ready}
                    onClick={() => { onChange(r.url); setOpen(false) }}
                    className="flex w-full items-start gap-2 rounded-lg px-2.5 py-2 text-left cursor-pointer hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <span className="mt-0.5 w-3.5 shrink-0 text-accent">{selected && <Check size={14} aria-hidden />}</span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium text-fg">{r.fullName}</span>
                      {ready ? (
                        <span className="mt-1 flex flex-wrap gap-1">{fingerprintChips(r.fingerprint, 2).map((c) => <Chip key={c} className="!text-[11px]">{c}</Chip>)}</span>
                      ) : (
                        <span className="text-xs text-fg-3">{r.status === 'analyzing' ? 'Analyzing…' : 'Not analyzed yet'}</span>
                      )}
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
          <Link to="/repos" className="flex items-center gap-2 border-t border-line px-3 py-2.5 text-sm text-fg-2 hover:bg-surface-hover hover:text-fg">
            <Plus size={14} aria-hidden /> Import a repo
          </Link>
        </div>
      )}
    </div>
  )
}
