import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import FingerprintBg from './FingerprintBg'
import GlowOrbs from './GlowOrbs'

const fadeUp = {
  hidden: { opacity: 0, y: 14 },
  show: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1], delay: i * 0.12 },
  }),
}

export default function Hero() {
  return (
    <section
      style={{
        position: 'relative',
        paddingTop: 120,
        paddingBottom: 80,
        paddingLeft: 40,
        paddingRight: 40,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        textAlign: 'center',
        overflow: 'hidden',
      }}
    >
      {/* Ambient background layers */}
      <FingerprintBg />
      <GlowOrbs />

      {/* Content sits above the bg layers */}
      <div style={{ position: 'relative', zIndex: 1, maxWidth: 640 }}>
        {/* Mono label */}
        <motion.p
          custom={0}
          initial="hidden"
          animate="show"
          variants={fadeUp}
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            letterSpacing: '3px',
            textTransform: 'uppercase',
            color: 'var(--text-tertiary)',
            marginBottom: 24,
          }}
        >
          Personalized Code Review
        </motion.p>

        {/* Main heading */}
        <motion.h1
          custom={1}
          initial="hidden"
          animate="show"
          variants={fadeUp}
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: 'clamp(44px, 6vw, 62px)',
            letterSpacing: '-1.5px',
            lineHeight: 1.05,
            color: 'var(--text-primary)',
            marginBottom: 28,
          }}
        >
          Your code has a<br />
          <em style={{ color: 'var(--accent)', fontStyle: 'italic' }}>fingerprint.</em>
          <br />
          We review against it.
        </motion.h1>

        {/* Subtitle */}
        <motion.p
          custom={2}
          initial="hidden"
          animate="show"
          variants={fadeUp}
          style={{
            fontFamily: 'var(--font-body)',
            fontSize: 17,
            color: 'var(--text-secondary)',
            maxWidth: 460,
            lineHeight: 1.7,
            margin: '0 auto 40px',
          }}
        >
          Every tool reviews against generic rules. PersonaCR learns how you write
          code, then holds new code to your own standard.
        </motion.p>

        {/* CTA buttons */}
        <motion.div
          custom={3}
          initial="hidden"
          animate="show"
          variants={fadeUp}
          style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}
        >
          <Link
            to="/login"
            style={{
              fontFamily: 'var(--font-body)',
              fontWeight: 500,
              fontSize: 14,
              color: '#fff',
              textDecoration: 'none',
              padding: '12px 24px',
              background: 'var(--accent)',
              borderRadius: 8,
              transition: 'background 0.15s, transform 0.15s',
              display: 'inline-block',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--accent-dark)'
              e.currentTarget.style.transform = 'translateY(-1px)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'var(--accent)'
              e.currentTarget.style.transform = 'translateY(0)'
            }}
          >
            Get started
          </Link>
          <a
            href="https://github.com/vaishnavi1064/PersonaCR/blob/main/research/RELATED_WORK.md"
            target="_blank"
            rel="noreferrer"
            style={{
              fontFamily: 'var(--font-body)',
              fontSize: 14,
              color: 'var(--text-primary)',
              textDecoration: 'none',
              padding: '12px 24px',
              border: '1px solid var(--border)',
              background: 'transparent',
              borderRadius: 8,
              transition: 'border-color 0.15s, transform 0.15s',
              display: 'inline-block',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = 'var(--border-hover)'
              e.currentTarget.style.transform = 'translateY(-1px)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = 'var(--border)'
              e.currentTarget.style.transform = 'translateY(0)'
            }}
          >
            Read the research
          </a>
        </motion.div>
      </div>
    </section>
  )
}
