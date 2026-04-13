import { useRef } from 'react'
import { motion, useInView } from 'framer-motion'

const steps = [
  {
    id: '01—FP',
    heading: 'Fingerprint',
    description:
      'Paste a GitHub repo. We extract 30 features and build a quantified profile of how you write code.',
  },
  {
    id: '02—RV',
    heading: 'Review',
    description:
      'Submit new code. Six specialized agents review it against your patterns in parallel — style, defects, quality.',
  },
  {
    id: '03—EV',
    heading: 'Improve',
    description:
      'Track quality over time. See where you deviate most and watch your consistency grow.',
  },
]

export default function HowItWorks() {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: '-80px' })

  return (
    <section
      style={{
        padding: '100px 40px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        borderTop: '0.5px solid var(--border)',
      }}
    >
      {/* Section label */}
      <motion.p
        initial={{ opacity: 0 }}
        animate={inView ? { opacity: 1 } : {}}
        transition={{ duration: 0.5 }}
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 11,
          letterSpacing: '2px',
          textTransform: 'uppercase',
          color: 'var(--text-tertiary)',
          marginBottom: 56,
          textAlign: 'center',
        }}
      >
        How it works
      </motion.p>

      {/* 3-column grid */}
      <div
        ref={ref}
        style={{
          width: '100%',
          maxWidth: 720,
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          position: 'relative',
        }}
      >
        {/* Dashed connecting lines (pseudo-element would work but inline is safer) */}
        <div
          aria-hidden
          style={{
            position: 'absolute',
            top: 14,
            left: '33.333%',
            width: '33.333%',
            height: 1,
            borderTop: '1px dashed var(--border)',
            pointerEvents: 'none',
          }}
        />

        {steps.map((step, i) => (
          <motion.div
            key={step.id}
            initial={{ opacity: 0, y: 16 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            transition={{
              duration: 0.5,
              ease: [0.22, 1, 0.36, 1],
              delay: i * 0.15,
            }}
            style={{
              padding: i === 1 ? '0 40px' : i === 2 ? '0 0 0 40px' : '0 40px 0 0',
            }}
          >
            {/* Step ID */}
            <p
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 12,
                color: 'var(--text-tertiary)',
                marginBottom: 16,
                letterSpacing: '0.5px',
              }}
            >
              {step.id}
            </p>

            {/* Heading */}
            <h3
              style={{
                fontFamily: 'var(--font-display)',
                fontSize: 22,
                color: 'var(--text-primary)',
                letterSpacing: '-0.3px',
                lineHeight: 1.1,
                marginBottom: 12,
              }}
            >
              {step.heading}
            </h3>

            {/* Description */}
            <p
              style={{
                fontFamily: 'var(--font-body)',
                fontSize: 13,
                color: 'var(--text-secondary)',
                lineHeight: 1.6,
              }}
            >
              {step.description}
            </p>
          </motion.div>
        ))}
      </div>
    </section>
  )
}
