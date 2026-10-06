import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { useEffect } from 'react'
import { useStore } from './store/useStore'
import { supabase } from './lib/supabase'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import ChatPage from './pages/ChatPage'
import DashboardPage from './pages/DashboardPage'
import ReposPage from './pages/ReposPage'
import RepoDetailPage from './pages/RepoDetailPage'
import ReviewPage from './pages/ReviewPage'
import SettingsPage from './pages/SettingsPage'
import NotFoundPage from './pages/NotFoundPage'
import AuthGuard from './components/layout/AuthGuard'
import AppShell from './components/shell/AppShell'
import { LogoMark } from './components/ui/Logo'

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
        <LogoMark size={34} innerFill="var(--bg-primary)" />
      </div>
    )
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route element={<AuthGuard><AppShell /></AuthGuard>}>
          <Route path="/repos" element={<ReposPage />} />
          <Route path="/repos/:owner/:name" element={<RepoDetailPage />} />
          <Route path="/reviews/:id" element={<ReviewPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  )
}
