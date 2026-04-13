import { useRef, useState, useEffect } from 'react'
import { motion, useInView, animate } from 'framer-motion'

interface StatConfig {
  target: number
  prefix?: string
  suffix?: string
  label: string
  static?: boolean
}

const stats: StatConfig[] = [
  { target: 48, suffix: '%',  label: 'faster via parallel execution' },
  { target: 69, suffix: 'ms', label: 'quality scoring latency' },
  { target: 9,  suffix: '',   label: 'research papers' },
  { target: 0,  prefix: '$',  suffix: '', label: 'infrastructure cost', static: true },
]

function AnimatedNumber({ config, trigger }: { config: StatConfig; trigger: boolean }) {
  const [display, setDisplay] = useState(config.static ? config.target : 0)
  const hasRun = useRef(false)

  useEffect(() => {
    if (!trigger || hasRun.current || config.static) return
    hasRun.current = true
    const controls = animate(0, config.target, {
      duration: 1.5,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (v) => setDisplay(Math.round(v)),
    })
    return () => controls.stop()
  }, [trigger, config.target, config.static])

  return (
    <span>
      {config.prefix ?? ''}
      {display}
      {config.suffix ?? ''}
    </span>
  )
}

export default function Stats() {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: '-60px' })

  return (
    <section
      style={{
        padding: '80px 40px',
        borderTop: '0.5px solid var(--border)',
        display: 'flex',
        justifyContent: 'center',
      }}
    >
      <div
        ref={ref}
        style={{
          width: '100%',
          maxWidth: 600,
          display: 'flex',
          justifyContent: 'space-between',
          gap: 32,
          flexWrap: 'wrap',
        }}
      >
        {stats.map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 12 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            transition={{
              duration: 0.5,
              ease: [0.22, 1, 0.36, 1],
              delay: i * 0.08,
            }}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 6,
              textAlign: 'center',
              flex: '1 1 100px',
            }}
          >
            <span
              style={{
                fontFamily: 'var(--font-display)',
                fontSize: 40,
                lineHeight: 1,
                color: 'var(--accent)',
                letterSpacing: '-1px',
              }}
            >
              <AnimatedNumber config={stat} trigger={inView} />
            </span>
            <span
              style={{
                fontFamily: 'var(--font-body)',
                fontSize: 12,
                color: 'var(--text-tertiary)',
                lineHeight: 1.4,
                maxWidth: 100,
              }}
            >
              {stat.label}
            </span>
          </motion.div>
        ))}
      </div>
    </section>
  )
}
