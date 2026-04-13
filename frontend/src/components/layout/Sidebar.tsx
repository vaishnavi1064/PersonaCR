import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Plus, Star, MoreVertical, LogOut } from 'lucide-react'
import { useStore } from '../../store/useStore'
import { toggleChatStar } from '../../lib/db'
import { supabase } from '../../lib/supabase'

function DiamondIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 28 28" fill="none">
      <rect x="7" y="7" width="14" height="14" rx="2" transform="rotate(45 14 14)" fill="var(--accent)" opacity="0.9" />
      <rect x="10" y="10" width="8" height="8" rx="1" transform="rotate(45 14 14)" fill="var(--bg-secondary)" opacity="0.7" />
      <rect x="12" y="12" width="4" height="4" rx="0.5" transform="rotate(45 14 14)" fill="var(--accent)" />
    </svg>
  )
}

function SidebarItem({
  id, title, active, starred, onClick,
}: {
  id:      string
  title:   string
  active:  boolean
  starred: boolean
  onClick: () => void
}) {
  const { updateChatStar } = useStore()
  const [hovered, setHovered] = useState(false)

  function handleStar(e: React.MouseEvent) {
    e.stopPropagation()
    const next = !starred
    updateChatStar(id, next)
    toggleChatStar(id, next) // fire-and-forget Supabase update
  }

  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '6px 10px 6px 16px',
        background: active ? 'var(--bg-card)' : hovered ? 'var(--bg-card)' : 'transparent',
        border: 'none',
        borderLeft: active ? '2px solid var(--accent)' : '2px solid transparent',
        cursor: 'pointer',
        textAlign: 'left',
        transition: 'background 0.1s',
      }}
    >
      <span style={{
        fontFamily: 'var(--font-body)',
        fontSize: 12,
        color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        flex: 1,
      }}>
        {title}
      </span>

      {/* Star button — always visible if starred, otherwise only on hover */}
      {(starred || hovered) && (
        <button
          onClick={handleStar}
          title={starred ? 'Unstar' : 'Star'}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: '1px 2px',
            display: 'flex',
            flexShrink: 0,
            color: starred ? '#FBBF24' : 'var(--text-tertiary)',
          }}
        >
          <Star
            size={11}
            style={{ fill: starred ? '#FBBF24' : 'none', transition: 'fill 0.15s' }}
          />
        </button>
      )}
    </button>
  )
}

interface SidebarProps {
  onNewChat?: () => void
}

export default function Sidebar({ onNewChat }: SidebarProps) {
  const { sidebarOpen, activeChatId, setActiveChatId, chats, user, session, isGuest, setIsGuest } = useStore()
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  // Close menu on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    if (menuOpen) document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [menuOpen])

  const guestMode = isGuest && !session

  async function handleLogout() {
    setMenuOpen(false)
    if (guestMode) {
      // Guest: just clear the flag → AuthGuard redirects to /login
      setIsGuest(false)
    } else {
      // Real user: sign out of Supabase → onAuthStateChange clears session → redirect
      await supabase.auth.signOut()
    }
  }

  const starred = chats.filter((c) => c.starred)
  const recent  = chats.filter((c) => !c.starred)

  const displayName = guestMode
    ? 'Guest'
    : (
        (user as { user_metadata?: { full_name?: string; name?: string }; name?: string } | null)
          ?.user_metadata?.full_name
        ?? (user as { user_metadata?: { full_name?: string; name?: string }; name?: string } | null)
          ?.user_metadata?.name
        ?? (user as { name?: string } | null)?.name
        ?? 'Guest'
      )

  const initials = guestMode
    ? 'G'
    : displayName
        .split(' ')
        .map((w: string) => w[0])
        .slice(0, 2)
        .join('')
        .toUpperCase() || 'G'

  const orgLabel = guestMode
    ? 'Guest session'
    : (user as { email?: string } | null)?.email ?? ''

  return (
    <AnimatePresence initial={false}>
      {sidebarOpen && (
        <motion.aside
          key="sidebar"
          initial={{ x: -240, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: -240, opacity: 0 }}
          transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
          style={{
            width: 240,
            flexShrink: 0,
            height: '100%',
            background: 'var(--bg-secondary)',
            borderRight: '0.5px solid var(--border)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
          }}
        >
          {/* ── Logo + new button ───────────────────────────────── */}
          <div style={{ padding: '16px 12px 12px' }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              marginBottom: 14,
              paddingLeft: 4,
            }}>
              <DiamondIcon />
              <span style={{
                fontFamily: 'var(--font-display)',
                fontSize: 14,
                color: 'var(--text-primary)',
                letterSpacing: '-0.1px',
              }}>
                PersonaCR
              </span>
            </div>

            <button
              onClick={onNewChat}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 6,
                padding: '7px 12px',
                background: 'transparent',
                border: '0.5px solid var(--border)',
                borderRadius: 8,
                cursor: 'pointer',
                fontFamily: 'var(--font-body)',
                fontSize: 12,
                color: 'var(--text-secondary)',
                transition: 'background 0.15s, border-color 0.15s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--bg-card)'
                e.currentTarget.style.borderColor = 'var(--border-hover)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent'
                e.currentTarget.style.borderColor = 'var(--border)'
              }}
            >
              <Plus size={13} />
              New review
            </button>
          </div>

          {/* ── Starred (only if any) ───────────────────────────── */}
          {starred.length > 0 && (
            <div style={{ padding: '8px 0 4px' }}>
              <p style={{
                fontFamily: 'var(--font-body)',
                fontSize: 11,
                color: 'var(--text-tertiary)',
                padding: '0 16px',
                marginBottom: 4,
              }}>
                Starred
              </p>
              {starred.map((item) => (
                <SidebarItem
                  key={item.id}
                  id={item.id}
                  title={item.title}
                  active={activeChatId === item.id}
                  starred={true}
                  onClick={() => setActiveChatId(item.id)}
                />
              ))}
            </div>
          )}

          {/* ── Recent (only if any) ────────────────────────────── */}
          {recent.length > 0 && (
            <div style={{ padding: '8px 0 4px', flex: 1, overflowY: 'auto' }}>
              <p style={{
                fontFamily: 'var(--font-body)',
                fontSize: 11,
                color: 'var(--text-tertiary)',
                padding: '0 16px',
                marginBottom: 4,
              }}>
                Recent
              </p>
              {recent.map((item) => (
                <SidebarItem
                  key={item.id}
                  id={item.id}
                  title={item.title}
                  active={activeChatId === item.id}
                  starred={false}
                  onClick={() => setActiveChatId(item.id)}
                />
              ))}
            </div>
          )}

          {/* Spacer when nothing to show */}
          {starred.length === 0 && recent.length === 0 && (
            <div style={{ flex: 1 }} />
          )}

          {/* ── User profile ────────────────────────────────────── */}
          <div
            ref={menuRef}
            style={{
              padding: '10px 12px',
              borderTop: '0.5px solid var(--border)',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              position: 'relative',
            }}
          >
            <div style={{
              width: 28,
              height: 28,
              borderRadius: '50%',
              background: 'var(--accent-surface)',
              color: 'var(--accent)',
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              fontWeight: 500,
            }}>
              {initials}
            </div>

            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{
                fontFamily: 'var(--font-body)',
                fontSize: 12,
                fontWeight: 500,
                color: 'var(--text-primary)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}>
                {displayName}
              </p>
              {orgLabel && (
                <p style={{
                  fontFamily: 'var(--font-body)',
                  fontSize: 11,
                  color: 'var(--text-tertiary)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}>
                  {orgLabel}
                </p>
              )}
            </div>

            <button
              onClick={() => setMenuOpen((v) => !v)}
              style={{
                background: menuOpen ? 'var(--bg-card)' : 'none',
                border: 'none',
                cursor: 'pointer',
                color: 'var(--text-tertiary)',
                padding: 4,
                borderRadius: 4,
                display: 'flex',
                transition: 'background 0.15s',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-card)')}
              onMouseLeave={(e) => { if (!menuOpen) e.currentTarget.style.background = 'none' }}
            >
              <MoreVertical size={14} />
            </button>

            {/* Popup menu */}
            {menuOpen && (
              <div style={{
                position: 'absolute',
                bottom: '110%',
                right: 8,
                background: 'var(--bg-card)',
                border: '0.5px solid var(--border)',
                borderRadius: 8,
                boxShadow: '0 8px 24px rgba(0,0,0,0.25)',
                minWidth: 140,
                overflow: 'hidden',
                zIndex: 100,
              }}>
                <button
                  onClick={handleLogout}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '9px 14px',
                    background: 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                    fontFamily: 'var(--font-body)',
                    fontSize: 13,
                    color: 'var(--text-secondary)',
                    textAlign: 'left',
                    transition: 'background 0.1s, color 0.1s',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'color-mix(in srgb, var(--error) 10%, transparent)'
                    e.currentTarget.style.color = 'var(--error)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'transparent'
                    e.currentTarget.style.color = 'var(--text-secondary)'
                  }}
                >
                  <LogOut size={13} />
                  Sign out
                </button>
              </div>
            )}
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  )
}
