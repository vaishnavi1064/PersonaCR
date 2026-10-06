import { MessagesSquare, Plus, Star } from 'lucide-react'
import type { ChatMeta } from '../../lib/db'
import { absoluteTime, relativeTime } from '../../lib/format'
import Button from '../ui/Button'
import Card from '../ui/Card'
import EmptyState from '../ui/EmptyState'
import type { Loadable } from './loadable'

interface RepoChatsTabProps {
  state: Loadable<ChatMeta[]>
  guest: boolean
  ready: boolean
  onOpen: (chatId: string) => void
  onNewChat: () => void
  onRetry: () => void
}

export default function RepoChatsTab({ state, guest, ready, onOpen, onNewChat, onRetry }: RepoChatsTabProps) {
  const newChat = (
    <Button variant="primary" size="sm" icon={<Plus size={14} />} onClick={onNewChat} disabled={!ready} title={ready ? undefined : 'Analyze the repo first'}>
      New chat in this repo
    </Button>
  )

  if (guest) {
    return <EmptyState icon={<MessagesSquare size={20} />} title="Guest chats aren’t saved" description="Sign in with GitHub to keep chats about this repo." action={newChat} />
  }
  if (state.status === 'loading') {
    return <div className="flex flex-col gap-2" aria-busy>{[0, 1, 2].map((i) => <div key={i} className="h-14 animate-pulse rounded-xl bg-surface" />)}</div>
  }
  if (state.status === 'error') {
    return <EmptyState title="Couldn’t load chats" description={state.message} action={<Button onClick={onRetry}>Retry</Button>} />
  }
  if (state.data.length === 0) {
    return <EmptyState icon={<MessagesSquare size={20} />} title="No chats about this repo yet" description="Ask about its code or review new code against its style." action={newChat} />
  }
  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">{newChat}</div>
      <Card className="overflow-hidden p-0">
        <ul className="divide-y divide-line">
          {state.data.map((c) => (
            <li key={c.id}>
              <button type="button" onClick={() => onOpen(c.id)} className="flex w-full items-center gap-3 px-4 py-3 text-left cursor-pointer hover:bg-surface-hover">
                <MessagesSquare size={15} className="shrink-0 text-fg-3" aria-hidden />
                <span className="min-w-0 flex-1 truncate text-sm text-fg">{c.title}</span>
                {c.starred && <Star size={13} className="shrink-0 text-warning" fill="currentColor" aria-label="Starred" />}
                <span className="shrink-0 text-xs text-fg-3" title={absoluteTime(c.updated_at)}>{relativeTime(c.updated_at)}</span>
              </button>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}
