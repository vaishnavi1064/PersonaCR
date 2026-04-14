import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

function PersonaCRLogo() {
  return (
    <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 10, textDecoration: 'none' }}>
      {/* Layered diamond SVG icon */}
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
        <rect
          x="7" y="7" width="14" height="14"
          rx="2"
          transform="rotate(45 14 14)"
          fill="var(--accent)"
          opacity="0.9"
        />
        <rect
          x="10" y="10" width="8" height="8"
          rx="1"
          transform="rotate(45 14 14)"
          fill="var(--bg-primary)"
          opacity="0.7"
        />
        <rect
          x="12" y="12" width="4" height="4"
          rx="0.5"
          transform="rotate(45 14 14)"
          fill="var(--accent)"
        />
      </svg>
      <span
        style={{
          fontFamily: 'var(--font-display)',
          fontSize: 19,
          color: 'var(--text-primary)',
          letterSpacing: '-0.3px',
        }}
      >
        PersonaCR
      </span>
    </Link>
  )
}

export default function LandingNav() {
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <nav
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 50,
        width: '100%',
        padding: '16px 40px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: scrolled ? 'var(--bg-secondary)' : 'transparent',
        borderBottom: scrolled ? '1px solid var(--border)' : '1px solid transparent',
        backdropFilter: scrolled ? 'blur(16px)' : 'none',
        WebkitBackdropFilter: scrolled ? 'blur(16px)' : 'none',
        transition: 'background 0.2s ease, border-color 0.2s ease, backdrop-filter 0.2s ease',
      }}
    >
      <PersonaCRLogo />

      <div style={{ display: 'flex', alignItems: 'center', gap: 28 }}>
        {/* Text links */}
        <a
          href="https://github.com/vaishnavi1064/PersonaCR/blob/main/research/RELATED_WORK.md"
          target="_blank"
          rel="noreferrer"
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 14,
            color: 'var(--text-tertiary)',
            textDecoration: 'none',
            transition: 'color 0.15s',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-secondary)')}
          onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-tertiary)')}
        >
          Research
        </a>
        <a
          href="https://github.com/vaishnavi1064/PersonaCR"
          target="_blank"
          rel="noreferrer"
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 14,
            color: 'var(--text-tertiary)',
            textDecoration: 'none',
            transition: 'color 0.15s',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-secondary)')}
          onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-tertiary)')}
        >
          GitHub
        </a>

        {/* Sign in outline */}
        <Link
          to="/login"
          style={{
            fontFamily: 'var(--font-body)',
            fontSize: 14,
            fontWeight: 500,
            color: 'var(--text-primary)',
            textDecoration: 'none',
            padding: '6px 16px',
            border: '1px solid var(--border)',
            borderRadius: 8,
            transition: 'border-color 0.15s, background 0.15s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = 'var(--border-hover)'
            e.currentTarget.style.background = 'var(--bg-tertiary)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = 'var(--border)'
            e.currentTarget.style.background = 'transparent'
          }}
        >
          Sign in
        </Link>

        {/* Get started filled */}
        <Link
          to="/login"
          style={{
            fontFamily: 'var(--font-body)',
            fontSize: 14,
            fontWeight: 500,
            color: '#fff',
            textDecoration: 'none',
            padding: '6px 16px',
            background: 'var(--accent)',
            borderRadius: 8,
            transition: 'background 0.15s',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--accent-dark)')}
          onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--accent)')}
        >
          Get started
        </Link>
      </div>
    </nav>
  )
}
