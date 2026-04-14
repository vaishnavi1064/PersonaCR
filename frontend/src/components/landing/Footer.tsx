import { Link } from 'react-router-dom'

function DiamondLogo() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <svg width="22" height="22" viewBox="0 0 28 28" fill="none">
        <rect
          x="7" y="7" width="14" height="14" rx="2"
          transform="rotate(45 14 14)"
          fill="var(--accent)" opacity="0.9"
        />
        <rect
          x="10" y="10" width="8" height="8" rx="1"
          transform="rotate(45 14 14)"
          fill="var(--bg-secondary)" opacity="0.7"
        />
        <rect
          x="12" y="12" width="4" height="4" rx="0.5"
          transform="rotate(45 14 14)"
          fill="var(--accent)"
        />
      </svg>
      <span
        style={{
          fontFamily: 'var(--font-display)',
          fontSize: 17,
          color: 'var(--text-primary)',
          letterSpacing: '-0.2px',
        }}
      >
        PersonaCR
      </span>
    </div>
  )
}

function FooterColHeading({ children }: { children: React.ReactNode }) {
  return (
    <p
      style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 12,
        letterSpacing: '1.5px',
        textTransform: 'uppercase',
        color: 'var(--text-tertiary)',
        marginBottom: 12,
      }}
    >
      {children}
    </p>
  )
}

interface FooterLinkProps {
  href: string
  external?: boolean
  children: React.ReactNode
}

function FooterLink({ href, external, children }: FooterLinkProps) {
  const sharedStyle: React.CSSProperties = {
    display: 'block',
    fontFamily: 'var(--font-body)',
    fontSize: 14,
    color: 'var(--text-secondary)',
    textDecoration: 'none',
    marginBottom: 8,
    cursor: 'pointer',
    transition: 'color 0.15s',
  }

  const handleEnter = (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.currentTarget.style.color = 'var(--text-primary)'
  }
  const handleLeave = (e: React.MouseEvent<HTMLAnchorElement>) => {
    e.currentTarget.style.color = 'var(--text-secondary)'
  }

  if (external) {
    return (
      <a
        href={href}
        target="_blank"
        rel="noreferrer"
        style={sharedStyle}
        onMouseEnter={handleEnter}
        onMouseLeave={handleLeave}
      >
        {children}
      </a>
    )
  }

  return (
    <Link
      to={href}
      style={sharedStyle}
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
    >
      {children}
    </Link>
  )
}

export default function Footer() {
  return (
    <footer
      style={{
        background: 'var(--bg-secondary)',
        borderTop: '0.5px solid var(--border)',
        width: '100%',
      }}
    >
      <div
        style={{
          maxWidth: 960,
          margin: '0 auto',
          padding: '48px 40px 32px',
        }}
      >
        {/* Three-column grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1.5fr 1fr 1fr',
            gap: 48,
          }}
        >
          {/* Left — brand */}
          <div>
            <DiamondLogo />
            <p
              style={{
                fontFamily: 'var(--font-body)',
                fontSize: 14,
                color: 'var(--text-secondary)',
                marginTop: 10,
                lineHeight: 1.5,
              }}
            >
              Personalized multi-agent code review
            </p>
            <p
              style={{
                fontFamily: 'var(--font-body)',
                fontSize: 13,
                color: 'var(--text-tertiary)',
                marginTop: 4,
              }}
            >
              Built by Vaishnavi Chaughule
            </p>
          </div>

          {/* Middle — Product */}
          <div>
            <FooterColHeading>Product</FooterColHeading>
            <FooterLink href="/chat">Chat</FooterLink>
            <FooterLink href="/dashboard">Dashboard</FooterLink>
            <FooterLink href="http://localhost:8000/docs" external>API</FooterLink>
            <FooterLink href="http://localhost:8000/mcp" external>MCP</FooterLink>
          </div>

          {/* Right — Connect */}
          <div>
            <FooterColHeading>Connect</FooterColHeading>
            <FooterLink
              href="https://github.com/vaishnavi1064/PersonaCR"
              external
            >
              GitHub
            </FooterLink>
            <FooterLink
              href="https://linkedin.com/in/vaishnavichaughule"
              external
            >
              LinkedIn
            </FooterLink>
            <FooterLink
              href="https://github.com/vaishnavi1064/PersonaCR/blob/main/research/RELATED_WORK.md"
              external
            >
              Research
            </FooterLink>
          </div>
        </div>

        {/* Bottom row */}
        <div
          style={{
            borderTop: '0.5px solid var(--border)',
            paddingTop: 20,
            marginTop: 32,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 8,
          }}
        >
          <span
            style={{
              fontFamily: 'var(--font-display)',
              fontStyle: 'italic',
              fontSize: 14,
              color: 'var(--text-tertiary)',
            }}
          >
            Grounded in 9 papers from EMNLP, NAACL, ACL, and MSR
          </span>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 13,
              color: 'var(--text-tertiary)',
            }}
          >
            2026
          </span>
        </div>
      </div>
    </footer>
  )
}
