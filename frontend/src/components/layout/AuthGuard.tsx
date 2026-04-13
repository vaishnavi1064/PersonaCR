import { Navigate } from 'react-router-dom'
import { useStore } from '../../store/useStore'

interface AuthGuardProps {
  children: React.ReactNode
}

function Spinner() {
  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--bg-primary)',
      flexDirection: 'column',
      gap: 16,
    }}>
      <svg width="32" height="32" viewBox="0 0 28 28" fill="none">
        <rect x="7" y="7" width="14" height="14" rx="2" transform="rotate(45 14 14)" fill="var(--accent)" opacity="0.9" />
        <rect x="10" y="10" width="8" height="8" rx="1" transform="rotate(45 14 14)" fill="var(--bg-primary)" opacity="0.7" />
        <rect x="12" y="12" width="4" height="4" rx="0.5" transform="rotate(45 14 14)" fill="var(--accent)" />
      </svg>
      <style>{`
        @keyframes auth-pulse {
          0%, 100% { opacity: 0.4; }
          50%       { opacity: 1; }
        }
      `}</style>
      <div style={{
        width: 6, height: 6, borderRadius: '50%',
        background: 'var(--accent)',
        animation: 'auth-pulse 1.2s ease-in-out infinite',
      }} />
    </div>
  )
}

export default function AuthGuard({ children }: AuthGuardProps) {
  const session     = useStore((s) => s.session)
  const authLoading = useStore((s) => s.authLoading)
  const isGuest     = useStore((s) => s.isGuest)
  const guestMode   = isGuest && !session

  // Real Supabase session always wins over guest mode.
  if (session) return <>{children}</>

  // Guest mode — allow through only when there is no real session.
  if (guestMode) return <>{children}</>

  // Waiting for getSession() to resolve — don't redirect yet
  if (authLoading) return <Spinner />

  // Auth check done — no session and not guest → go to login
  if (!session) return <Navigate to="/login" replace />

  return <>{children}</>
}
