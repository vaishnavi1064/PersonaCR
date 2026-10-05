import { NavLink, useNavigate } from 'react-router-dom'
import { FolderGit2, LayoutDashboard, MessagesSquare, Plus, Settings, Star, X } from 'lucide-react'
import { useStore } from '../../store/useStore'
import type { ChatMeta } from '../../store/useStore'
import { toggleChatStar } from '../../lib/db'
import { cn } from '../../lib/cn'
import Logo from '../ui/Logo'
import Button from '../ui/Button'
import IconButton from '../ui/IconButton'
import { useCurrentUser } from '../../lib/useCurrentUser'

const NAV = [
  { to: '/repos',     label: 'Repositories', icon: FolderGit2 },
  { to: '/chat',      label: 'Chats',        icon: MessagesSquare },
  { to: '/dashboard', label: 'Dashboard',    icon: LayoutDashboard },
  { to: '/settings',  label: 'Settings',     icon: Settings },
] as const

interface NavSidebarProps {
  /** Called after any navigation — closes the mobile drawer. */
  onNavigate?: () => void
  /** Show a close button (mobile drawer). */
  onClose?: () => void
  className?: string
}

export default function NavSidebar({ onNavigate, onClose, className }: NavSidebarProps) {
  const navigate = useNavigate()
  const chats = useStore((s) => s.chats)
  const activeChatId = useStore((s) => s.activeChatId)
  const setActiveChatId = useStore((s) => s.setActiveChatId)
  const requestNewChat = useStore((s) => s.requestNewChat)
  const { guestMode } = useCurrentUser()

  function newChat() {
    requestNewChat()
    navigate('/chat')
    onNavigate?.()
  }

  function openChat(id: string) {
    setActiveChatId(id)
    navigate('/chat')
    onNavigate?.()
  }

  const starred = chats.filter((c) => c.starred)
  const recent = chats.filter((c) => !c.starred)

  return (
    <aside className={cn('flex h-full w-[232px] shrink-0 flex-col border-r border-line bg-sidebar', className)}>
      <div className="flex h-14 items-center justify-between px-4">
        <NavLink to="/repos" onClick={onNavigate} aria-label="PersonaCR home" className="rounded-md">
          <Logo />
        </NavLink>
        {onClose && <IconButton label="Close menu" icon={<X size={16} />} size="sm" onClick={onClose} />}
      </div>

      <div className="px-3 pb-3">
        <Button variant="primary" className="w-full" icon={<Plus size={15} />} onClick={newChat}>
          New chat
        </Button>
      </div>

      <nav aria-label="Main" className="px-3">
        <ul className="flex flex-col gap-0.5">
          {NAV.map(({ to, label, icon: Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                onClick={onNavigate}
                className={({ isActive }) => cn(
                  'flex h-9 items-center gap-3 rounded-lg px-3 text-sm',
                  isActive
                    ? 'bg-surface-hover font-medium text-fg shadow-[inset_0_0_0_1px_var(--border)]'
                    : 'text-fg-2 hover:bg-surface hover:text-fg',
                )}
              >
                <Icon size={17} aria-hidden />
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <div className="mx-4 my-3 h-px bg-line" role="presentation" />

      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
        {starred.length > 0 && (
          <ChatGroup title="Starred" chats={starred} activeChatId={activeChatId} onOpen={openChat} />
        )}
        {recent.length > 0 && (
          <ChatGroup title="Recent chats" chats={recent} activeChatId={activeChatId} onOpen={openChat} />
        )}
        {chats.length === 0 && !guestMode && (
          <p className="px-3 text-xs text-fg-3">No chats yet.</p>
        )}
      </div>

      {guestMode && (
        <div className="m-3 rounded-lg border border-line bg-surface p-3 text-xs text-fg-3">
          <p className="font-medium text-fg-2">Guest session</p>
          <p className="mt-0.5">Nothing is saved. Sign in with GitHub to keep repos and chats.</p>
        </div>
      )}
    </aside>
  )
}

function ChatGroup({
  title, chats, activeChatId, onOpen,
}: { title: string; chats: ChatMeta[]; activeChatId: string | null; onOpen: (id: string) => void }) {
  return (
    <div className="mb-3">
      <p className="px-3 pb-1 text-[11px] font-medium uppercase tracking-wider text-fg-3">{title}</p>
      <ul className="flex flex-col gap-px">
        {chats.map((c) => <ChatItem key={c.id} chat={c} active={c.id === activeChatId} onOpen={onOpen} />)}
      </ul>
    </div>
  )
}

function ChatItem({ chat, active, onOpen }: { chat: ChatMeta; active: boolean; onOpen: (id: string) => void }) {
  const updateChatStar = useStore((s) => s.updateChatStar)

  function toggleStar() {
    const next = !chat.starred
    updateChatStar(chat.id, next)
    toggleChatStar(chat.id, next) // fire-and-forget Supabase update
  }

  return (
    <li className="group relative">
      <button
        type="button"
        onClick={() => onOpen(chat.id)}
        aria-current={active ? 'page' : undefined}
        className={cn(
          'flex h-8 w-full items-center rounded-md pl-3 pr-8 text-left text-[13px] cursor-pointer',
          active ? 'bg-surface-hover text-fg' : 'text-fg-2 hover:bg-surface hover:text-fg',
        )}
      >
        <span className="truncate">{chat.title}</span>
      </button>
      <button
        type="button"
        onClick={toggleStar}
        aria-label={chat.starred ? `Unstar ${chat.title}` : `Star ${chat.title}`}
        aria-pressed={chat.starred}
        className={cn(
          'absolute right-1.5 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded cursor-pointer',
          chat.starred ? 'text-warning' : 'text-fg-3 opacity-0 hover:text-fg group-hover:opacity-100 focus-visible:opacity-100',
        )}
      >
        <Star size={12} fill={chat.starred ? 'currentColor' : 'none'} aria-hidden />
      </button>
    </li>
  )
}
