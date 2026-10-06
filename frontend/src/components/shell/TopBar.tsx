import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { ChevronDown, LogOut, Menu, Settings } from 'lucide-react'
import { useStore } from '../../store/useStore'
import { useCurrentUser } from '../../lib/useCurrentUser'
import IconButton from '../ui/IconButton'
import Avatar from '../ui/Avatar'
import { LogoMark } from '../ui/Logo'
import ThemeToggle from '../layout/ThemeToggle'

const SECTION: Record<string, string> = {
  '/repos': 'Repositories',
  '/chat': 'Chats',
  '/dashboard': 'Dashboard',
  '/settings': 'Settings',
}

export default function TopBar({ onOpenMenu }: { onOpenMenu: () => void }) {
  const { pathname } = useLocation()
  const chats = useStore((s) => s.chats)
  const activeChatId = useStore((s) => s.activeChatId)

  // Breadcrumb: section (linked when there's a deeper crumb) → current page
  const parts = pathname.split('/').filter(Boolean)
  const root = '/' + (parts[0] ?? '')
  const crumbs: { label: string; to?: string }[] = []
  if (root === '/chat') {
    crumbs.push({ label: 'Chats' }, { label: chats.find((c) => c.id === activeChatId)?.title ?? 'New chat' })
  } else if (root === '/repos' && parts.length >= 3) {
    crumbs.push({ label: 'Repositories', to: '/repos' }, { label: `${decodeURIComponent(parts[1])}/${decodeURIComponent(parts[2])}` })
  } else if (root === '/reviews') {
    crumbs.push({ label: 'Repositories', to: '/repos' }, { label: 'Review' })
  } else if (SECTION[root]) {
    crumbs.push({ label: SECTION[root] })
  }

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-canvas px-4 sm:px-6">
      <IconButton label="Open menu" icon={<Menu size={18} />} onClick={onOpenMenu} className="lg:hidden" />
      <LogoMark size={22} innerFill="var(--bg-primary)" className="lg:hidden" />

      <nav aria-label="Breadcrumb" className="min-w-0 flex-1">
        <ol className="flex min-w-0 items-center gap-2 text-sm">
          {crumbs.map((c, i) => {
            const last = i === crumbs.length - 1
            return (
              <li key={i} className={last ? 'flex min-w-0 items-center gap-2' : 'hidden shrink-0 items-center gap-2 sm:flex'}>
                {i > 0 && <span className="hidden text-fg-3 sm:inline" aria-hidden>/</span>}
                {last
                  ? <span className="truncate font-medium text-fg" aria-current="page">{c.label}</span>
                  : c.to ? <Link to={c.to} className="text-fg-3 hover:text-fg">{c.label}</Link> : <span className="text-fg-3">{c.label}</span>}
              </li>
            )
          })}
        </ol>
      </nav>

      <div className="flex shrink-0 items-center gap-2">
        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  )
}

function UserMenu() {
  const { displayName, initials, email, avatarUrl, guestMode, signOut } = useCurrentUser()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-2 rounded-lg py-1 pl-1 pr-2 cursor-pointer hover:bg-surface-hover"
      >
        <Avatar src={avatarUrl} initials={initials} size={30} />
        <span className="hidden max-w-[140px] truncate text-sm font-medium text-fg sm:block">{displayName}</span>
        <ChevronDown size={14} className="hidden text-fg-3 sm:block" aria-hidden />
      </button>

      {open && (
        <div role="menu" className="absolute right-0 top-full z-50 mt-1.5 w-60 overflow-hidden rounded-xl border border-line bg-surface shadow-pop">
          <div className="border-b border-line px-3.5 py-3">
            <p className="truncate text-sm font-medium text-fg">{displayName}</p>
            <p className="truncate text-xs text-fg-3">{guestMode ? 'Guest session — nothing is saved' : email}</p>
          </div>
          <div className="p-1">
            <Link
              to="/settings"
              role="menuitem"
              onClick={() => setOpen(false)}
              className="flex h-9 items-center gap-2.5 rounded-md px-2.5 text-sm text-fg-2 hover:bg-surface-hover hover:text-fg"
            >
              <Settings size={15} aria-hidden /> Settings
            </Link>
            <button
              type="button"
              role="menuitem"
              onClick={() => { setOpen(false); signOut() }}
              className="flex h-9 w-full items-center gap-2.5 rounded-md px-2.5 text-left text-sm text-fg-2 cursor-pointer hover:bg-danger/10 hover:text-danger"
            >
              <LogOut size={15} aria-hidden /> {guestMode ? 'Leave guest session' : 'Sign out'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
