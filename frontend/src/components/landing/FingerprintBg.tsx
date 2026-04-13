import { useMemo } from 'react'

interface Line {
  x1: number
  y1: number
  length: number
  angle: number
  opacity: number
  duration: number
  delay: number
}

export default function FingerprintBg() {
  const lines = useMemo<Line[]>(() => {
    // Deterministic pseudo-random so SSR/hydration matches
    const rng = (seed: number) => {
      const x = Math.sin(seed + 1) * 10000
      return x - Math.floor(x)
    }
    return Array.from({ length: 65 }, (_, i) => ({
      x1: rng(i * 3.1) * 100,
      y1: rng(i * 3.7) * 100,
      length: 60 + rng(i * 5.3) * 140,
      angle: rng(i * 7.1) * 360,
      opacity: 0.025 + rng(i * 2.9) * 0.04,
      duration: 18 + rng(i * 4.1) * 14,
      delay: rng(i * 6.3) * -20,
    }))
  }, [])

  return (
    <div
      aria-hidden
      style={{
        position: 'absolute',
        inset: 0,
        overflow: 'hidden',
        pointerEvents: 'none',
        zIndex: 0,
      }}
    >
      <style>{`
        @keyframes fp-float {
          0%   { transform: translateY(0px) rotate(var(--fp-angle)); }
          50%  { transform: translateY(-12px) rotate(calc(var(--fp-angle) + 4deg)); }
          100% { transform: translateY(0px) rotate(var(--fp-angle)); }
        }
      `}</style>
      {lines.map((line, i) => {
        const x2 = line.x1 + Math.cos((line.angle * Math.PI) / 180) * line.length * 0.7
        const y2 = line.y1 + Math.sin((line.angle * Math.PI) / 180) * line.length * 0.7
        return (
          <svg
            key={i}
            style={{
              position: 'absolute',
              inset: 0,
              width: '100%',
              height: '100%',
              // @ts-expect-error CSS custom property
              '--fp-angle': `${line.angle}deg`,
              animation: `fp-float ${line.duration}s ease-in-out ${line.delay}s infinite`,
            }}
          >
            <line
              x1={`${line.x1}%`}
              y1={`${line.y1}%`}
              x2={`${x2}%`}
              y2={`${y2}%`}
              stroke="var(--accent)"
              strokeWidth="0.8"
              opacity={line.opacity}
              strokeLinecap="round"
            />
          </svg>
        )
      })}
    </div>
  )
}
