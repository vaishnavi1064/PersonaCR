import { NavLink, useNavigate } from 'react-router-dom'
import { FolderGit2, LayoutDashboard, MessagesSquare, Plus, Settings, X } from 'lucide-react'
import { useStore } from '../../store/useStore'
import { cn } from '../../lib/cn'
import Logo, { LogoMark } from '../ui/Logo'
import Button from '../ui/Button'
import IconButton from '../ui/IconButton'
import ThreadList from '../studio/ThreadList'
import { useCurrentUser } from '../../lib/useCurrentUser'

const NAV = [
  { to: '/repos',     label: 'Repositories', icon: FolderGit2 },
  { to: '/chat',      label: 'Chats',        icon: MessagesSquare },
  { to: '/dashboard', label: 'Dashboard',    icon: LayoutDashboard },
  { to: '/settings',  label: 'Settings',     icon: Settings },
] as const

interface NavSidebarProps {
  /** Icon rail — used on the Chat Studio, which has its own threads pane. */
  compact?: boolean
  /** Called after any navigation — closes the mobile drawer. */
  onNavigate?: () => void
  /** Show a close button (mobile drawer). */
  onClose?: () => void
  className?: string
}

export default function NavSidebar({ compact, onNavigate, onClose, className }: NavSidebarProps) {
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

  if (compact) {
    return (
      <aside className={cn('flex h-full w-16 shrink-0 flex-col items-center gap-2 border-r border-line bg-sidebar py-3', className)}>
        <NavLink to="/repos" aria-label="PersonaCR home" className="mb-1 flex h-9 w-9 items-center justify-center rounded-lg">
          <LogoMark size={24} />
        </NavLink>
        <button
          type="button"
          onClick={newChat}
          aria-label="New chat"
          title="New chat"
          className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-strong text-on-accent cursor-pointer hover:brightness-110"
        >
          <Plus size={17} aria-hidden />
        </button>
        <nav aria-label="Main" className="mt-1">
          <ul className="flex flex-col gap-1">
            {NAV.map(({ to, label, icon: Icon }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  title={label}
                  aria-label={label}
                  className={({ isActive }) => cn(
                    'flex h-9 w-9 items-center justify-center rounded-lg',
                    isActive ? 'bg-surface-hover text-fg shadow-[inset_0_0_0_1px_var(--border)]' : 'text-fg-3 hover:bg-surface hover:text-fg',
                  )}
                >
                  <Icon size={18} aria-hidden />
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </aside>
    )
  }

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

      <div className="min-h-0 flex-1 overflow-y-auto px-1.5 pb-3">
        {chats.length > 0 ? (
          <ThreadList chats={chats} activeChatId={activeChatId} onOpen={openChat} dense />
        ) : !guestMode && (
          <p className="px-4 text-xs text-fg-3">No chats yet.</p>
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
