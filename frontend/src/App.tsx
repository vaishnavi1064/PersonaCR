import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { useEffect } from 'react'
import { useStore } from './store/useStore'
import { supabase } from './lib/supabase'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import ChatPage from './pages/ChatPage'
import DashboardPage from './pages/DashboardPage'
import AuthGuard from './components/layout/AuthGuard'

// Apply stored theme immediately (before first paint) to prevent flash
try {
  const stored = JSON.parse(localStorage.getItem('personacr-store') ?? '{}')
  document.documentElement.setAttribute('data-theme',  stored?.state?.theme  ?? 'dark')
  document.documentElement.setAttribute('data-accent', stored?.state?.accent ?? 'purple')
} catch {
  document.documentElement.setAttribute('data-theme',  'dark')
  document.documentElement.setAttribute('data-accent', 'purple')
}

export default function App() {
  const {
    theme, accent, authLoading,
    setSession, setUser, setAuthLoading, setIsGuest,
  } = useStore()

  // Keep theme/accent in sync at runtime
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    document.documentElement.setAttribute('data-accent', accent)
  }, [theme, accent])

  // Bootstrap auth state once before rendering routes
  useEffect(() => {
    let bootstrapped = false

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (event, session) => {
        if (session) {
          setSession(session as unknown as Record<string, unknown>)
          setUser(session.user as unknown as Record<string, unknown>)
          setIsGuest(false)   // real auth always overrides guest mode
        } else {
          setSession(null)
          setUser(null)
        }

        // INITIAL_SESSION is emitted on app load; SIGNED_IN covers OAuth callback completion.
        if (event === 'INITIAL_SESSION' || event === 'SIGNED_IN' || event === 'SIGNED_OUT') {
          bootstrapped = true
          setAuthLoading(false)
        }
      }
    )

    // Fallback check: if INITIAL_SESSION event is delayed/missed, resolve explicitly.
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (bootstrapped) return
      if (session) {
        setSession(session as unknown as Record<string, unknown>)
        setUser(session.user as unknown as Record<string, unknown>)
        setIsGuest(false)
      } else {
        setSession(null)
        setUser(null)
      }
      setAuthLoading(false)
    }).catch(err => {
      console.error("Supabase auth error:", err)
      if (!bootstrapped) setAuthLoading(false)
    })

    return () => subscription.unsubscribe()
  }, [setSession, setUser, setAuthLoading, setIsGuest])

  // Do not render router until auth bootstrap is complete.
  if (authLoading) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--bg-primary)',
      }}>
        <svg width="34" height="34" viewBox="0 0 28 28" fill="none">
          <rect x="7" y="7" width="14" height="14" rx="2" transform="rotate(45 14 14)" fill="var(--accent)" opacity="0.9" />
          <rect x="10" y="10" width="8" height="8" rx="1" transform="rotate(45 14 14)" fill="var(--bg-primary)" opacity="0.7" />
          <rect x="12" y="12" width="4" height="4" rx="0.5" transform="rotate(45 14 14)" fill="var(--accent)" />
        </svg>
      </div>
    )
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/chat" element={<AuthGuard><ChatPage /></AuthGuard>} />
        <Route path="/dashboard" element={<AuthGuard><DashboardPage /></AuthGuard>} />
      </Routes>
    </BrowserRouter>
  )
}
