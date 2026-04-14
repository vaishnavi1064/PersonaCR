import { useRef } from 'react'
import { motion, useInView } from 'framer-motion'
import { Link } from 'react-router-dom'

export default function BottomCTA() {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: '-60px' })

  return (
    <section
      style={{
        borderTop: '0.5px solid var(--border)',
        paddingTop: 120,
        paddingBottom: 80,
        paddingLeft: 40,
        paddingRight: 40,
        display: 'flex',
        justifyContent: 'center',
      }}
    >
      <motion.div
        ref={ref}
        initial={{ opacity: 0, y: 12 }}
        animate={inView ? { opacity: 1, y: 0 } : {}}
        transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
        style={{
          maxWidth: 600,
          width: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          textAlign: 'center',
        }}
      >
        <h2
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: 33,
            color: 'var(--text-primary)',
            letterSpacing: '-0.5px',
            lineHeight: 1.1,
          }}
        >
          Start reviewing.
        </h2>

        <p
          style={{
            fontFamily: 'var(--font-body)',
            fontSize: 15,
            color: 'var(--text-secondary)',
            marginTop: 12,
            lineHeight: 1.6,
          }}
        >
          Sign in with GitHub. First review in under a minute.
        </p>

        <Link
          to="/login"
          style={{
            display: 'inline-block',
            marginTop: 32,
            fontFamily: 'var(--font-body)',
            fontWeight: 500,
            fontSize: 15,
            color: '#fff',
            textDecoration: 'none',
            padding: '12px 28px',
            background: 'var(--accent)',
            borderRadius: 8,
            transition: 'filter 0.15s ease, transform 0.15s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.filter = 'brightness(1.12)'
            e.currentTarget.style.transform = 'translateY(-1px)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.filter = 'brightness(1)'
            e.currentTarget.style.transform = 'translateY(0)'
          }}
        >
          Sign in with GitHub
        </Link>
      </motion.div>
    </section>
  )
}
