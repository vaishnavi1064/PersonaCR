import { Menu } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import { useStore } from '../../store/useStore'
import ThemeToggle from './ThemeToggle'
import AccentPicker from '../ui/AccentPicker'

export default function TopBar({ title = 'New review' }: { title?: string }) {
  const { toggleSidebar } = useStore()
  const { pathname } = useLocation()
  const isChat = pathname === '/chat'

  return (
    <header style={{
      height: 48,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 20px',
      borderBottom: '0.5px solid var(--border)',
      background: 'var(--bg-primary)',
      flexShrink: 0,
      gap: 12,
    }}>
      {/* Left */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
        <button
          onClick={toggleSidebar}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--text-secondary)',
            display: 'flex',
            alignItems: 'center',
            padding: 4,
            borderRadius: 6,
            flexShrink: 0,
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-secondary)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
        >
          <Menu size={16} />
        </button>
        <span style={{
          fontFamily: 'var(--font-body)',
          fontSize: 14,
          color: 'var(--text-secondary)',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          maxWidth: 260,
        }}>
          {title}
        </span>
      </div>

      {/* Right */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
        {/* Chat pill */}
        <NavPill href="/chat" active={isChat} label="Chat" />
        {/* Dashboard pill */}
        <NavPill href="/dashboard" active={!isChat} label="Dashboard" />

        <div style={{ width: 1, height: 16, background: 'var(--border)' }} />
        <ThemeToggle />
        <AccentPicker />
      </div>
    </header>
  )
}

function NavPill({ href, active, label }: { href: string; active: boolean; label: string }) {
  return (
    <Link
      to={href}
      style={{
        fontFamily: 'var(--font-body)',
        fontSize: 13,
        color: active ? 'var(--text-primary)' : 'var(--text-tertiary)',
        textDecoration: 'none',
        padding: '4px 10px',
        borderRadius: 6,
        border: active ? '0.5px solid var(--border)' : '0.5px solid transparent',
        background: active ? 'var(--bg-card)' : 'transparent',
        transition: 'all 0.15s',
      }}
      onMouseEnter={(e) => { if (!active) e.currentTarget.style.color = 'var(--text-secondary)' }}
      onMouseLeave={(e) => { if (!active) e.currentTarget.style.color = 'var(--text-tertiary)' }}
    >
      {label}
    </Link>
  )
}
