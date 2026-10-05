import { Plus, Star } from 'lucide-react'
import { groupChatsByRepo, repoShortName } from '../../lib/api'
import type { ChatMeta } from '../../lib/db'
import { toggleChatStar } from '../../lib/db'
import { useStore } from '../../store/useStore'
import { relativeTime } from '../../lib/format'
import { cn } from '../../lib/cn'
import GitHubMark from '../ui/GitHubMark'

interface ThreadListProps {
  chats: ChatMeta[]
  activeChatId: string | null
  onOpen: (id: string) => void
  /** "+" on a repo group: new chat in that repo. */
  onNewInRepo?: (repoUrl: string) => void
  /** Block switching (e.g. while a review is running). */
  disabledReason?: string | null
  /** Denser rows for the app sidebar. */
  dense?: boolean
}

/** Chat threads grouped by repo, most recently active repo first. */
export default function ThreadList({ chats, activeChatId, onOpen, onNewInRepo, disabledReason, dense }: ThreadListProps) {
  const groups = groupChatsByRepo(chats)
  return (
    <div className="flex flex-col gap-4">
      {groups.map((g) => (
        <section key={g.repoUrl ?? 'none'} aria-label={g.repoUrl ? repoShortName(g.repoUrl) : 'No repo'}>
          <div className="group/head flex items-center gap-1.5 px-3 pb-1">
            {g.repoUrl && <span className="text-fg-3"><GitHubMark size={11} /></span>}
            <h3 className="min-w-0 flex-1 truncate text-[11px] font-medium uppercase tracking-wider text-fg-3" title={g.repoUrl ?? undefined}>
              {g.repoUrl ? repoShortName(g.repoUrl).split('/')[1] : 'No repo'}
            </h3>
            <span className="text-[11px] tabular-nums text-fg-3">{g.chats.length}</span>
            {onNewInRepo && g.repoUrl && (
              <button
                type="button"
                onClick={() => onNewInRepo(g.repoUrl!)}
                disabled={!!disabledReason}
                title={disabledReason ?? `New chat in ${repoShortName(g.repoUrl)}`}
                aria-label={`New chat in ${repoShortName(g.repoUrl)}`}
                className="flex h-5 w-5 items-center justify-center rounded text-fg-3 cursor-pointer hover:bg-surface-hover hover:text-fg disabled:cursor-not-allowed disabled:opacity-40"
              >
                <Plus size={12} aria-hidden />
              </button>
            )}
          </div>
          <ul className="flex flex-col gap-px">
            {g.chats.map((c) => (
              <ThreadItem key={c.id} chat={c} active={c.id === activeChatId} onOpen={onOpen} disabledReason={disabledReason} dense={dense} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}

function ThreadItem({ chat, active, onOpen, disabledReason, dense }: {
  chat: ChatMeta; active: boolean; onOpen: (id: string) => void; disabledReason?: string | null; dense?: boolean
}) {
  const updateChatStar = useStore((s) => s.updateChatStar)

  function toggleStar() {
    const next = !chat.starred
    updateChatStar(chat.id, next)
    toggleChatStar(chat.id, next) // fire-and-forget Supabase update
  }

  const blocked = !!disabledReason && !active

  return (
    <li className="group relative">
      <button
        type="button"
        onClick={() => onOpen(chat.id)}
        disabled={blocked}
        title={blocked ? disabledReason! : chat.title}
        aria-current={active ? 'page' : undefined}
        className={cn(
          'flex w-full flex-col rounded-md pl-3 pr-8 text-left cursor-pointer disabled:cursor-not-allowed disabled:opacity-50',
          dense ? 'py-1.5' : 'py-2',
          active ? 'bg-surface-hover text-fg shadow-[inset_0_0_0_1px_var(--border)]' : 'text-fg-2 hover:bg-surface hover:text-fg',
        )}
      >
        <span className="truncate text-[13px]">{chat.title}</span>
        {!dense && <span className="text-[11px] text-fg-3">{relativeTime(chat.updated_at)}</span>}
      </button>
      <button
        type="button"
        onClick={toggleStar}
        aria-label={chat.starred ? `Unstar ${chat.title}` : `Star ${chat.title}`}
        aria-pressed={chat.starred}
        className={cn(
          'absolute right-1.5 flex h-6 w-6 items-center justify-center rounded cursor-pointer',
          dense ? 'top-1/2 -translate-y-1/2' : 'top-2',
          chat.starred ? 'text-warning' : 'text-fg-3 opacity-0 hover:text-fg group-hover:opacity-100 focus-visible:opacity-100',
        )}
      >
        <Star size={12} fill={chat.starred ? 'currentColor' : 'none'} aria-hidden />
      </button>
    </li>
  )
}
