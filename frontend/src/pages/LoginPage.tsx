import { useState, useEffect } from 'react'
import { Navigate, Link, useNavigate } from 'react-router-dom'
import { motion, type Variants } from 'framer-motion'
import { useStore } from '../store/useStore'
import { signInWithGitHub, supabase } from '../lib/supabase'

// ── GitHub icon ───────────────────────────────────────────────────────────────
function GitHubIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="white">
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" />
    </svg>
  )
}

// ── Diamond logo ──────────────────────────────────────────────────────────────
function DiamondLogo({ bg = 'var(--bg-card)' }: { bg?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <svg width="26" height="26" viewBox="0 0 28 28" fill="none">
        <rect x="7" y="7" width="14" height="14" rx="2" transform="rotate(45 14 14)" fill="var(--accent)" opacity="0.9" />
        <rect x="10" y="10" width="8" height="8" rx="1" transform="rotate(45 14 14)" fill={bg} opacity="0.7" />
        <rect x="12" y="12" width="4" height="4" rx="0.5" transform="rotate(45 14 14)" fill="var(--accent)" />
      </svg>
      <span style={{ fontFamily: 'var(--font-display)', fontSize: 19, color: 'var(--text-primary)', letterSpacing: '-0.2px' }}>
        PersonaCR
      </span>
    </div>
  )
}

// ── Sparkle dot (background decoration) ─────────────────────────────────────
function SparkleGroup() {
  const dots = [
    { top: '15%', left: '8%', size: 4, delay: '0s', dur: '6s' },
    { top: '70%', left: '88%', size: 3, delay: '2s', dur: '7s' },
    { top: '40%', left: '92%', size: 4, delay: '3.5s', dur: '5.5s' },
  ]
  return (
    <>
      <style>{`
        @keyframes sparkle-rise {
          0%   { transform: translateY(0);    opacity: 0.3; }
          50%  { opacity: 0.5; }
          100% { transform: translateY(-40px); opacity: 0; }
        }
      `}</style>
      {dots.map((d, i) => (
        <div
          key={i}
          aria-hidden
          style={{
            position: 'fixed',
            top: d.top,
            left: d.left,
            width: d.size,
            height: d.size,
            borderRadius: '50%',
            background: 'white',
            opacity: 0.3,
            animation: `sparkle-rise ${d.dur} ease-in-out ${d.delay} infinite`,
            pointerEvents: 'none',
            zIndex: 0,
          }}
        />
      ))}
    </>
  )
}

// ── Right panel: fingerprint SVG animation ────────────────────────────────────
function FingerprintVisual() {
  const cx = 120
  const cy = 115

  // Concentric arc paths — slightly irregular bezier fingerprint arcs
  const arcs = [
    { r: 90, op: 0.08, dur: 40, dir: 1 },
    { r: 77, op: 0.12, dur: 35, dir: -1 },
    { r: 65, op: 0.18, dur: 30, dir: 1 },
    { r: 53, op: 0.28, dur: 26, dir: -1 },
    { r: 42, op: 0.35, dur: 22, dir: 1 },
    { r: 32, op: 0.28, dur: 20, dir: -1 },
    { r: 22, op: 0.18, dur: 18, dir: 1 },
    { r: 13, op: 0.10, dur: 16, dir: -1 },
  ]

  // Agent dots: angle in degrees, color, orbit radius, speed
  const agents = [
    { angle: 0, color: '#8B7CF6', orbit: 96, dur: 10, label: 'Planner' },
    { angle: 60, color: '#D85A30', orbit: 96, dur: 13, label: 'Style' },
    { angle: 120, color: '#D85A30', orbit: 96, dur: 11, label: 'Defect' },
    { angle: 180, color: '#D4537E', orbit: 96, dur: 14, label: 'QA' },
    { angle: 240, color: '#1D9E75', orbit: 96, dur: 9, label: 'Confidence' },
    { angle: 300, color: '#639922', orbit: 96, dur: 12, label: 'Gate' },
  ]

  // Sparkle particles inside the right panel
  const particles = Array.from({ length: 14 }, (_, i) => ({
    x: 10 + (i * 17) % 220,
    y: 20 + (i * 23) % 200,
    r: i % 2 === 0 ? 2 : 1.5,
    op: 0.2 + (i % 3) * 0.1,
    dur: 4 + (i % 5),
    delay: (i * 0.7) % 6,
  }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <style>{`
        ${arcs.map((a, i) => `
          @keyframes arc-spin-${i} {
            from { transform: rotate(0deg);   }
            to   { transform: rotate(${a.dir * 360}deg); }
          }
        `).join('')}

        ${agents.map((ag, i) => {
        const rad = (ag.angle * Math.PI) / 180
        const sx = Math.cos(rad) * ag.orbit
        const sy = Math.sin(rad) * ag.orbit
        return `
            @keyframes orbit-${i} {
              from { transform: translate(${sx.toFixed(1)}px, ${sy.toFixed(1)}px); }
              to   { transform: translate(${sx.toFixed(1)}px, ${sy.toFixed(1)}px) rotate(360deg)
                                translate(${ag.orbit}px) rotate(-360deg); }
            }
          `
      }).join('')}

        @keyframes particle-float {
          0%   { transform: translateY(0);    opacity: var(--p-op); }
          60%  { opacity: calc(var(--p-op) * 1.4); }
          100% { transform: translateY(-45px); opacity: 0; }
        }
      `}</style>

      <svg
        width="240"
        height="240"
        viewBox="0 0 240 230"
        fill="none"
        style={{ overflow: 'visible' }}
      >
        {/* Ambient glow behind fingerprint center */}
        <defs>
          <radialGradient id="fp-glow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.18" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </radialGradient>
        </defs>
        <ellipse cx={cx} cy={cy} rx="120" ry="120" fill="url(#fp-glow)" />

        {/* Sparkle particles */}
        {particles.map((p, i) => (
          <circle
            key={`particle-${i}`}
            cx={p.x}
            cy={p.y}
            r={p.r}
            fill="white"
            style={{
              // @ts-expect-error CSS custom property
              '--p-op': p.op,
              opacity: p.op,
              animation: `particle-float ${p.dur}s ease-in-out ${p.delay}s infinite`,
            }}
          />
        ))}

        {/* Fingerprint arcs — each rotates around the center independently */}
        {arcs.map((a, i) => (
          <g
            key={`arc-${i}`}
            style={{
              transformOrigin: `${cx}px ${cy}px`,
              animation: `arc-spin-${i} ${a.dur}s linear infinite`,
            }}
          >
            {/* Open arc using path — not a perfect circle, has a gap */}
            <path
              d={describeOpenArc(cx, cy, a.r, 15, 345)}
              stroke="var(--accent)"
              strokeWidth="1.5"
              strokeLinecap="round"
              opacity={a.op}
            />
          </g>
        ))}

        {/* Agent dots orbiting the fingerprint */}
        {agents.map((ag, i) => {
          const rad = (ag.angle * Math.PI) / 180
          const dotX = cx + Math.cos(rad) * ag.orbit
          const dotY = cy + Math.sin(rad) * ag.orbit
          return (
            <g key={`agent-${i}`}>
              {/* Dot glow */}
              <circle cx={dotX} cy={dotY} r="8" fill={ag.color} opacity="0.15" />
              {/* Dot */}
              <circle
                cx={dotX}
                cy={dotY}
                r="4"
                fill={ag.color}
                style={{
                  transformOrigin: `${cx}px ${cy}px`,
                  animation: `arc-spin-${i % 3} ${ag.dur}s linear infinite`,
                }}
              />
            </g>
          )
        })}

        {/* Center dot */}
        <circle cx={cx} cy={cy} r="4" fill="var(--accent)" opacity="0.8" />
        <circle cx={cx} cy={cy} r="2" fill="white" opacity="0.6" />
      </svg>

      <p
        style={{
          fontFamily: 'var(--font-display)',
          fontStyle: 'italic',
          fontSize: 15,
          color: 'var(--accent-text)',
          textAlign: 'center',
          marginTop: 16,
          opacity: 0.75,
          letterSpacing: '0.2px',
        }}
      >
        Your patterns. Your review.
      </p>
    </div>
  )
}

// ── Arc path helper (open arc, like a fingerprint ridge) ─────────────────────
function describeOpenArc(cx: number, cy: number, r: number, startDeg: number, endDeg: number) {
  const toRad = (deg: number) => (deg * Math.PI) / 180
  const x1 = cx + r * Math.cos(toRad(startDeg))
  const y1 = cy + r * Math.sin(toRad(startDeg))
  const x2 = cx + r * Math.cos(toRad(endDeg))
  const y2 = cy + r * Math.sin(toRad(endDeg))
  // Add slight bezier wobble for organic look
  const mx = cx + r * Math.cos(toRad((startDeg + endDeg) / 2))
  const my = cy + r * Math.sin(toRad((startDeg + endDeg) / 2)) - r * 0.04
  return `M ${x1.toFixed(2)} ${y1.toFixed(2)} Q ${mx.toFixed(2)} ${my.toFixed(2)} ${x2.toFixed(2)} ${y2.toFixed(2)}`
}

// ── Stagger variants ──────────────────────────────────────────────────────────
const container: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
}
const item: Variants = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] } },
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function LoginPage() {
  const session = useStore((s) => s.session)
  const setSession = useStore((s) => s.setSession)
  const setUser = useStore((s) => s.setUser)
  const setIsGuest = useStore((s) => s.setIsGuest)
  const navigate = useNavigate()
  const [authError, setAuthError] = useState<string | null>(null)
  const [githubLoading, setGithubLoading] = useState(false)
  // Derive initial completing from hash so we don't sync-setState in the effect.
  const [completing, setCompleting] = useState(() => {
    const params = new URLSearchParams(window.location.hash.slice(1))
    return Boolean(params.get('access_token'))
  })

  // ── OAuth callback handler ────────────────────────────────────────────────
  // The access_token is in the URL hash (#access_token=...) after GitHub auth.
  // We parse it directly and call setSession() — the most reliable approach.
  useEffect(() => {
    const hash = window.location.hash
    const params = new URLSearchParams(hash.slice(1))   // strip leading #
    const accessToken  = params.get('access_token')
    const refreshToken = params.get('refresh_token') ?? ''

    if (!accessToken) return   // not an OAuth callback — normal login page view

    console.log('[PersonaCR] OAuth callback detected, calling setSession...')

    supabase.auth.setSession({ access_token: accessToken, refresh_token: refreshToken })
      .then(({ data, error }) => {
        console.log('[PersonaCR] setSession result:', { data, error })
        if (error || !data.session) {
          setCompleting(false)
          setAuthError(error?.message ?? 'Sign-in failed. Please try again.')
          return
        }
        // Session established — update store then go to chat
        setSession(data.session as unknown as Record<string, unknown>)
        setUser(data.session.user as unknown as Record<string, unknown>)
        setIsGuest(false)
        // Clean hash from URL so it doesn't confuse anything on back-navigation
        window.history.replaceState(null, '', window.location.pathname)
        navigate('/chat', { replace: true })
      })
      .catch((err) => {
        console.error('[PersonaCR] setSession threw:', err)
        setCompleting(false)
        setAuthError(err instanceof Error ? err.message : 'Sign-in failed.')
      })
  }, [navigate, setSession, setUser, setIsGuest])

  if (session) return <Navigate to="/chat" replace />

  // Show "completing sign-in" spinner while PKCE exchange runs
  if (completing) {
    return (
      <div style={{
        minHeight: '100vh', display: 'flex', alignItems: 'center',
        justifyContent: 'center', background: 'var(--bg-primary)',
        flexDirection: 'column', gap: 16,
      }}>
        <svg width="32" height="32" viewBox="0 0 28 28" fill="none">
          <rect x="7" y="7" width="14" height="14" rx="2" transform="rotate(45 14 14)" fill="var(--accent)" opacity="0.9" />
          <rect x="10" y="10" width="8" height="8" rx="1" transform="rotate(45 14 14)" fill="var(--bg-primary)" opacity="0.7" />
          <rect x="12" y="12" width="4" height="4" rx="0.5" transform="rotate(45 14 14)" fill="var(--accent)" />
        </svg>
        <p style={{ fontFamily: 'var(--font-body)', fontSize: 15, color: 'var(--text-secondary)' }}>
          Completing sign-in…
        </p>
      </div>
    )
  }

  const handleGitHub = async () => {
    setAuthError(null)
    setGithubLoading(true)
    // Ensure stale guest mode never masks real OAuth login.
    setIsGuest(false)
    try {
      await signInWithGitHub()
      // signInWithOAuth triggers window.location navigation — browser will leave
      // this page. We intentionally do NOT set an error here; if we reach this
      // line it just means JS ran before the navigation completed (normal).
    } catch (err) {
      // Only land here if Supabase returned an actual error object
      const msg = err instanceof Error ? err.message : String(err)
      setAuthError(msg)
      setGithubLoading(false)
      console.error('GitHub sign-in failed:', err)
    }
    // Note: setGithubLoading(false) is intentionally omitted on success —
    // the button stays in "Redirecting…" state until the browser navigates away.
  }

  const handleGuest = () => {
    setIsGuest(true)
    navigate('/chat', { replace: true })
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: `
          radial-gradient(ellipse 60% 50% at 90% 10%, color-mix(in srgb, var(--accent) 15%, transparent) 0%, transparent 70%),
          radial-gradient(ellipse 50% 40% at 5% 90%,  color-mix(in srgb, var(--accent) 12%, transparent) 0%, transparent 70%),
          var(--bg-primary)
        `,
        padding: 24,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <SparkleGroup />

      {/* Main card */}
      <motion.div
        initial={{ opacity: 0, scale: 0.97 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
        style={{
          display: 'flex',
          flexDirection: 'row',
          width: '100%',
          maxWidth: 720,
          borderRadius: 20,
          overflow: 'hidden',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          background: 'color-mix(in srgb, var(--bg-card) 60%, transparent)',
          border: '0.5px solid var(--border-hover)',
          boxShadow: '0 32px 80px rgba(0,0,0,0.3)',
          position: 'relative',
          zIndex: 1,
        }}
      >
        {/* ── LEFT: login form ──────────────────────────────────────────── */}
        <div
          style={{
            flex: '0 0 55%',
            padding: 40,
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <motion.div variants={container} initial="hidden" animate="show">
            {/* Logo */}
            <motion.div variants={item} style={{ marginBottom: 32 }}>
              <DiamondLogo />
            </motion.div>

            {/* Heading */}
            <motion.h1
              variants={item}
              style={{
                fontFamily: 'var(--font-display)',
                fontSize: 29,
                color: 'var(--text-primary)',
                letterSpacing: '-0.5px',
                lineHeight: 1.15,
              }}
            >
              Welcome back
            </motion.h1>

            {/* Subtitle */}
            <motion.p
              variants={item}
              style={{
                fontFamily: 'var(--font-body)',
                fontSize: 15,
                color: 'var(--text-secondary)',
                marginTop: 8,
                marginBottom: 36,
                lineHeight: 1.5,
              }}
            >
              Sign in to review code against your patterns
            </motion.p>

            {/* Error banner */}
            {authError && (
              <motion.div
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                style={{
                  marginBottom: 16,
                  padding: '10px 14px',
                  background: 'color-mix(in srgb, var(--error, #e55) 12%, transparent)',
                  border: '0.5px solid color-mix(in srgb, var(--error, #e55) 40%, transparent)',
                  borderRadius: 8,
                  fontFamily: 'var(--font-body)',
                  fontSize: 13,
                  color: 'var(--error, #ff6b6b)',
                  lineHeight: 1.5,
                }}
              >
                {authError}
              </motion.div>
            )}

            {/* GitHub OAuth button */}
            <motion.div variants={item}>
              <button
                onClick={handleGitHub}
                disabled={githubLoading}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 10,
                  padding: '14px 20px',
                  background: githubLoading ? 'color-mix(in srgb, var(--accent) 70%, transparent)' : 'var(--accent)',
                  color: 'white',
                  border: 'none',
                  borderRadius: 12,
                  fontFamily: 'var(--font-body)',
                  fontWeight: 500,
                  fontSize: 16,
                  cursor: githubLoading ? 'not-allowed' : 'pointer',
                  boxShadow: '0 4px 16px var(--accent-glow)',
                  transition: 'filter 0.2s ease, transform 0.2s ease',
                }}
                onMouseEnter={(e) => { if (!githubLoading) { e.currentTarget.style.filter = 'brightness(1.1)'; e.currentTarget.style.transform = 'translateY(-1px)' } }}
                onMouseLeave={(e) => { e.currentTarget.style.filter = 'brightness(1)'; e.currentTarget.style.transform = 'translateY(0)' }}
              >
                <GitHubIcon />
                {githubLoading ? 'Redirecting to GitHub…' : 'Continue with GitHub'}
              </button>
            </motion.div>

            {/* Divider */}
            <motion.div
              variants={item}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                margin: '24px 0',
              }}
            >
              <div style={{ flex: 1, borderTop: '0.5px solid var(--border)' }} />
              <span
                style={{
                  fontFamily: 'var(--font-body)',
                  fontSize: 13,
                  color: 'var(--text-tertiary)',
                  whiteSpace: 'nowrap',
                }}
              >
                or
              </span>
              <div style={{ flex: 1, borderTop: '0.5px solid var(--border)' }} />
            </motion.div>

            {/* Guest login button */}
            <motion.div variants={item}>
              <button
                onClick={handleGuest}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 10,
                  padding: '12px 20px',
                  background: 'transparent',
                  color: 'var(--text-secondary)',
                  border: '0.5px solid var(--border)',
                  borderRadius: 12,
                  fontFamily: 'var(--font-body)',
                  fontWeight: 500,
                  fontSize: 15,
                  cursor: 'pointer',
                  transition: 'border-color 0.2s, background 0.2s, color 0.2s',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'var(--border-hover)'
                  e.currentTarget.style.background = 'var(--bg-card)'
                  e.currentTarget.style.color = 'var(--text-primary)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--border)'
                  e.currentTarget.style.background = 'transparent'
                  e.currentTarget.style.color = 'var(--text-secondary)'
                }}
              >
                {/* Person icon */}
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="8" r="4" />
                  <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
                </svg>
                Continue as Guest
              </button>

              <p style={{
                fontFamily: 'var(--font-body)',
                fontSize: 12,
                color: 'var(--text-tertiary)',
                textAlign: 'center',
                marginTop: 10,
                lineHeight: 1.5,
              }}>
                Guest sessions are local only — chats won't be saved
              </p>
            </motion.div>

            {/* Back link */}
            <motion.div variants={item} style={{ marginTop: 'auto', paddingTop: 32 }}>
              <Link
                to="/"
                style={{
                  fontFamily: 'var(--font-body)',
                  fontSize: 14,
                  color: 'var(--text-tertiary)',
                  textDecoration: 'none',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  transition: 'color 0.15s',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--accent-text)')}
                onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-tertiary)')}
              >
                ← Back to home
              </Link>
            </motion.div>
          </motion.div>
        </div>

        {/* ── RIGHT: fingerprint visual ─────────────────────────────────── */}
        <div
          style={{
            flex: '0 0 45%',
            background: '#0A0A0F',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 40,
            position: 'relative',
            overflow: 'hidden',
          }}
        >
          {/* Subtle grid texture */}
          <div
            aria-hidden
            style={{
              position: 'absolute',
              inset: 0,
              backgroundImage: `
                linear-gradient(var(--border) 1px, transparent 1px),
                linear-gradient(90deg, var(--border) 1px, transparent 1px)
              `,
              backgroundSize: '32px 32px',
              opacity: 0.15,
              pointerEvents: 'none',
            }}
          />
          <FingerprintVisual />
        </div>
      </motion.div>
    </div>
  )
}
