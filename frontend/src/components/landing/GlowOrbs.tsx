export default function GlowOrbs() {
  return (
    <div aria-hidden style={{ position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none', zIndex: 0 }}>
      <style>{`
        @keyframes orb-float-a {
          0%   { transform: translateY(0px); }
          50%  { transform: translateY(-20px); }
          100% { transform: translateY(0px); }
        }
        @keyframes orb-float-b {
          0%   { transform: translateY(0px); }
          50%  { transform: translateY(20px); }
          100% { transform: translateY(0px); }
        }
      `}</style>

      {/* Top-right orb */}
      <div
        style={{
          position: 'absolute',
          top: '-60px',
          right: '-60px',
          width: 360,
          height: 360,
          borderRadius: '50%',
          background: 'var(--accent-glow)',
          filter: 'blur(80px)',
          opacity: 0.25,
          animation: 'orb-float-a 10s ease-in-out infinite',
        }}
      />

      {/* Bottom-left orb */}
      <div
        style={{
          position: 'absolute',
          bottom: '-80px',
          left: '-80px',
          width: 320,
          height: 320,
          borderRadius: '50%',
          background: 'var(--accent-glow)',
          filter: 'blur(90px)',
          opacity: 0.18,
          animation: 'orb-float-b 10s ease-in-out 2s infinite',
        }}
      />
    </div>
  )
}
